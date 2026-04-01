import sys
import os
import logging
sys.stdout.reconfigure(line_buffering=True)

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import requests
from dotenv import load_dotenv
from langgraph_flow import build_graph
from parser import parse_code_chunks
from github_comments import post_pr_review_comments
from database import SessionLocal, engine
from models import Base, PullRequest, ReviewResult

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
MAX_CHUNKS = 20

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# In-memory fallback stats (used if DB is unavailable)
in_memory_stats = {
    "total_issues": 0,
    "by_severity": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
    "by_agent": {"security": 0, "performance": 0, "style": 0},
    "by_pr": {}
}

try:
    Base.metadata.create_all(bind=engine)
    DB_AVAILABLE = True
    logger.info("✅ Database connected")
except Exception as e:
    DB_AVAILABLE = False
    logger.warning(f"⚠️ DB unavailable — using in-memory stats: {e}")

app = FastAPI()


@app.get("/")
def home():
    return {"message": "AI Code Review Agent is running"}

@app.get("/test-bug")
def test_bug(user_id: str):
    # ❌ Intentional vulnerability for demo
    query = "SELECT * FROM users WHERE id = " + user_id
        # trigger webhook again
    return {"query": query}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    with open("dashboard.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/stats")
def stats():
    if DB_AVAILABLE:
        try:
            db = SessionLocal()
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
            db.close()
            return {"total_issues": total, "by_severity": by_severity, "by_agent": by_agent, "by_pr": by_pr}
        except Exception as e:
            logger.error(f"DB stats error: {e}")

    # Fallback to in-memory
    return in_memory_stats


def update_in_memory_stats(findings: list, pr_key: str):
    in_memory_stats["total_issues"] += len(findings)
    for f in findings:
        sev = f.get("severity", "LOW")
        agent = f.get("agent", "unknown")
        in_memory_stats["by_severity"][sev] = in_memory_stats["by_severity"].get(sev, 0) + 1
        in_memory_stats["by_agent"][agent] = in_memory_stats["by_agent"].get(agent, 0) + 1
        in_memory_stats["by_pr"][pr_key] = in_memory_stats["by_pr"].get(pr_key, 0) + 1


def extract_code_from_diff(diff_text: str) -> str:
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
        "repo_full": repo_full,
        "pull_number": pr["number"],
        "commit_id": pr["head"]["sha"],
    }


def get_changed_files(diff_text: str) -> list:
    return [
        line[6:].strip()
        for line in diff_text.split("\n")
        if line.startswith("+++ b/")
    ]


def save_to_db(repo_name, pull_number, diff_text, final_results, file_path):
    if not DB_AVAILABLE:
        return
    db = SessionLocal()
    try:
        pr_record = PullRequest(repo_name=repo_name, pr_number=pull_number, diff=diff_text[:5000])
        db.add(pr_record)
        db.commit()
        db.refresh(pr_record)
        for finding in final_results:
            db.add(ReviewResult(
                pr_id=pr_record.id,
                file_name=file_path,
                agent_type=finding["agent"],
                issue=finding["problem"],
                severity=finding["severity"],
                fix=finding["fix"]
            ))
        db.commit()
        logger.info(f"✅ Saved {len(final_results)} findings to DB")
    except Exception as e:
        logger.error(f"DB save error: {e}")
        db.rollback()
    finally:
        db.close()


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    logger.info("[1/6] Webhook received")
    logger.info(f"Keys: {list(data.keys())}")
    sys.stdout.flush()

    # Only process pull_request events with action opened/synchronize
    if "pull_request" not in data:
        logger.info("Not a pull_request event — ignoring")
        return {"status": "ignored"}

    action = data.get("action", "")
    if action not in ("opened", "synchronize"):
        logger.info(f"PR action '{action}' — ignoring")
        return {"status": "ignored", "action": action}

    meta = extract_pr_metadata(data)
    pr = data["pull_request"]
    diff_url = pr["diff_url"]
    logger.info(f"PR #{meta['pull_number']} ({action}) | Repo: {meta['repo_full']}")
    sys.stdout.flush()

    # [2/6] Fetch diff
    logger.info("[2/6] Fetching PR diff")
    try:
        diff_response = requests.get(diff_url, headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3.diff"
        })
        logger.info(f"Diff fetch status: {diff_response.status_code}")
        sys.stdout.flush()
        if diff_response.status_code != 200:
            logger.error(f"Failed to fetch diff: {diff_response.status_code}")
            return {"status": "error fetching diff"}
        diff_text = diff_response.text
    except Exception as e:
        logger.error(f"Error fetching diff: {e}")
        return {"status": "error fetching diff"}

    code = extract_code_from_diff(diff_text)
    if not code.strip():
        logger.warning("No code found in diff")
        return {"status": "no code found"}

    chunks = parse_code_chunks(code, diff_text)
    logger.info(f"Chunks found: {len(chunks)}")

    if not chunks:
        return {"status": "no chunks"}

    if len(chunks) > MAX_CHUNKS:
        logger.warning(f"Large PR: {len(chunks)} chunks — limiting to {MAX_CHUNKS}")
        chunks = chunks[:MAX_CHUNKS]

    # [3/6] Run AI agents
    logger.info("[3/6] Running AI agents")
    graph = build_graph()
    final_results = []
    chunks_with_findings = []  # track findings per chunk for correct comment mapping

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
            chunk_findings = result.get("final", []) if result and isinstance(result, dict) else []
            logger.info(f"  Chunk '{chunk['type']}' lines {chunk['start_line']}-{chunk['end_line']}: {len(chunk_findings)} findings")
            final_results.extend(chunk_findings)
            chunks_with_findings.append((chunk, chunk_findings))
        except Exception as e:
            logger.error(f"  Graph invoke failed: {e} — skipping chunk")
            chunks_with_findings.append((chunk, []))

    logger.info(f"Total findings: {len(final_results)}")
    sys.stdout.flush()

    changed_files = get_changed_files(diff_text)
    file_path = changed_files[0] if changed_files else "unknown"
    pr_key = f"PR #{meta['pull_number']}"

    # [4/6] Save findings
    logger.info("[4/6] Saving findings")
    save_to_db(
        repo_name=meta["repo_full"],
        pull_number=meta["pull_number"],
        diff_text=diff_text,
        final_results=final_results,
        file_path=file_path
    )
    update_in_memory_stats(final_results, pr_key)
    logger.info("[5/6] Updating dashboard stats")

    # [6/6] Post inline GitHub PR comments
    logger.info("[6/6] Posting GitHub comments")
    comments_posted = 0
    try:
        for chunk, findings in chunks_with_findings:
            if not findings:
                continue
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
            comments_posted += len([f for f in findings if f.get("problem")])
    except Exception as e:
        logger.error(f"Failed to post GitHub comments: {e}")

    logger.info(f"Done — {comments_posted} comments posted to PR #{meta['pull_number']}")

    return {
        "status": "processed",
        "pr": pr_key,
        "total_findings": len(final_results),
        "comments_posted": comments_posted,
        "final_results": final_results
    }
# webhook test change
