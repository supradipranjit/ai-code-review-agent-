import sys
import os
import logging
sys.stdout.reconfigure(line_buffering=True)

from langgraph_flow import build_graph
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import requests
from dotenv import load_dotenv
from parser import parse_code_chunks
from github_comments import post_pr_review_comments
from database import SessionLocal, engine
from models import Base, PullRequest, ReviewResult

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
MAX_CHUNKS = 20  # limit for large PRs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Server is working"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    with open("dashboard.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/stats")
def stats():
    db = SessionLocal()
    try:
        results = db.query(ReviewResult).all()

        total = len(results)
        by_severity = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        by_agent = {"security": 0, "performance": 0, "style": 0}
        by_pr = {}

        for r in results:
            by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
            by_agent[r.agent_type] = by_agent.get(r.agent_type, 0) + 1
            pr_key = f"PR #{r.pr_id}"
            by_pr[pr_key] = by_pr.get(pr_key, 0) + 1

        return {
            "total_issues": total,
            "by_severity": by_severity,
            "by_agent": by_agent,
            "by_pr": by_pr
        }
    finally:
        db.close()


# ✅ FIXED: Properly placed bug route (OUTSIDE webhook)
@app.get("/test-bug")
def test_bug(user_id: str):
    # ❌ Intentional vulnerability for demo
    query = "SELECT * FROM users WHERE id = " + user_id
    return {"query": query}


def extract_code_from_diff(diff_text):
    code_lines = []
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            code_lines.append(line[1:])
    return "\n".join(code_lines)


def extract_pr_metadata(data: dict) -> dict:
    pr = data["pull_request"]
    repo_full = data["repository"]["full_name"]
    owner, repo = repo_full.split("/", 1)
    return {
        "owner": owner,
        "repo": repo,
        "pull_number": pr["number"],
        "commit_id": pr["head"]["sha"],
    }


def get_changed_files(diff_text: str) -> list:
    files = []
    for line in diff_text.split("\n"):
        if line.startswith("+++ b/"):
            files.append(line[6:].strip())
    return files


def save_to_db(repo_name, pull_number, diff_text, final_results, file_path):
    db = SessionLocal()
    try:
        pr_record = PullRequest(repo_name=repo_name, pr_number=pull_number, diff=diff_text[:5000])
        db.add(pr_record)
        db.commit()
        db.refresh(pr_record)

        for finding in final_results:
            result = ReviewResult(
                pr_id=pr_record.id,
                file_name=file_path,
                agent_type=finding["agent"],
                issue=finding["problem"],
                severity=finding["severity"],
                fix=finding["fix"]
            )
            db.add(result)

        db.commit()
        print(f"Saved {len(final_results)} findings to DB")
    except Exception as e:
        print(f"DB save error: {e}")
        db.rollback()
    finally:
        db.close()


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    print("\n==============================")
    print("PAYLOAD RECEIVED")
    print("Keys:", list(data.keys()))
    print("==============================\n")
    sys.stdout.flush()

    if "pull_request" not in data:
        print("No pull_request key — ignoring")
        sys.stdout.flush()
        return {"status": "ignored"}

    pr = data["pull_request"]
    diff_url = pr["diff_url"]
    print("Diff URL:", diff_url)
    sys.stdout.flush()

    try:
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3.diff"
        }
        diff_response = requests.get(diff_url, headers=headers)
        print("Diff fetch status:", diff_response.status_code)
        sys.stdout.flush()
        diff_text = diff_response.text
    except Exception as e:
        print("Error fetching diff:", e)
        sys.stdout.flush()
        return {"status": "error fetching diff"}

    print("\nRAW DIFF (first 300 chars):\n", diff_text[:300])
    sys.stdout.flush()

    code = extract_code_from_diff(diff_text)
    print("\nEXTRACTED CODE:\n", code)
    sys.stdout.flush()

    if not code.strip():
        return {"status": "no code found"}

    chunks = parse_code_chunks(code, diff_text)
    print("\nCHUNKS:\n", chunks)
    sys.stdout.flush()

    if not chunks:
        return {"status": "no chunks"}

    if len(chunks) > MAX_CHUNKS:
        logger.warning(f"Large PR: {len(chunks)} chunks found — limiting to {MAX_CHUNKS}")
        chunks = chunks[:MAX_CHUNKS]

    graph = build_graph()
    final_results = []

    for chunk in chunks:
        chunk_code = "\n".join(chunk["code"])
        state = {
            "chunk": {
                "code": chunk_code,
                "type": chunk["type"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"]
            }
        }

        try:
            result = graph.invoke(state)
            logger.info(f"Chunk {chunk['type']} processed")
        except Exception as e:
            logger.error(f"Graph invoke failed for chunk: {e} — skipping")
            continue

        if result and isinstance(result, dict):
            final_results.extend(result.get("final", []))
        else:
            print("Invalid graph output:", result)

    print("\nLANGGRAPH FINAL OUTPUT:\n", final_results)
    sys.stdout.flush()

    meta = extract_pr_metadata(data)
    changed_files = get_changed_files(diff_text)
    file_path = changed_files[0] if changed_files else "unknown"

    save_to_db(
        repo_name=f"{meta['owner']}/{meta['repo']}",
        pull_number=meta["pull_number"],
        diff_text=diff_text,
        final_results=final_results,
        file_path=file_path
    )

    try:
        findings_by_chunk = []
        idx = 0
        for chunk in chunks:
            chunk_findings = final_results[idx: idx + 3]
            findings_by_chunk.append((chunk, chunk_findings))
            idx += 3

        for chunk, findings in findings_by_chunk:
            post_pr_review_comments(
                owner=meta["owner"],
                repo=meta["repo"],
                pull_number=meta["pull_number"],
                commit_id=meta["commit_id"],
                file_path=file_path,
                findings=findings,
                diff_text=diff_text,
                chunk_start_line=chunk["start_line"],
            )
    except Exception as e:
        print(f"Failed to post GitHub comments: {e}")
        sys.stdout.flush()

    return {"status": "processed", "final_results": final_results}