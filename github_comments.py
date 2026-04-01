import requests
import os
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

SEVERITY_EMOJI = {"HIGH": "🚨", "MEDIUM": "⚠️", "LOW": "ℹ️"}


def format_comment(agent: str, severity: str, problem: str, fix: str) -> str:
    emoji = SEVERITY_EMOJI.get(severity, "ℹ️")
    lang = "python"
    return (
        f"### {emoji} {severity} Issue — `{agent.title()} Review`\n\n"
        f"**Problem:**\n{problem}\n\n"
        f"**Suggested Fix:**\n```{lang}\n{fix}\n```"
    )


def parse_diff_line_map(diff_text: str) -> dict:
    """
    Build a map of { file_path: [(diff_position, actual_line_number), ...] }
    diff_position is what GitHub API requires (1-based position in the hunk).
    """
    file_map = {}
    current_file = None
    diff_position = 0
    current_line = 0

    for raw_line in diff_text.split("\n"):
        if raw_line.startswith("+++ b/"):
            current_file = raw_line[6:].strip()
            file_map[current_file] = []
            diff_position = 0
        elif raw_line.startswith("@@"):
            diff_position += 1
            try:
                new_part = raw_line.split("+")[1].split(",")[0].split(" ")[0]
                current_line = int(new_part) - 1
            except (IndexError, ValueError):
                current_line = 0
        elif current_file is not None:
            if raw_line.startswith("-"):
                diff_position += 1
            elif raw_line.startswith("+"):
                current_line += 1
                diff_position += 1
                file_map[current_file].append((diff_position, current_line))
            elif not raw_line.startswith("\\"):
                current_line += 1
                diff_position += 1

    return file_map


def get_diff_position(file_map: dict, file_path: str, target_line: int):
    entries = file_map.get(file_path, [])
    if not entries:
        return None
    for diff_pos, actual_line in entries:
        if actual_line >= target_line:
            return diff_pos
    return entries[-1][0] if entries else None


def post_review_comment(
    repo: str,
    pr_number: int,
    commit_id: str,
    file_path: str,
    line: int,
    message: str,
):
    """Post a single inline review comment on a GitHub PR."""
    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN not set")
        return False

    owner, repo_name = repo.split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{repo_name}/pulls/{pr_number}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "body": message,
        "commit_id": commit_id,
        "path": file_path,
        "position": line,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code == 201:
            print(f"✅ Comment posted on {file_path} (pos {line})")
            return True
        else:
            print(f"❌ Failed to post comment: {resp.status_code} — {resp.text[:300]}")
            return False
    except Exception as e:
        print(f"❌ GitHub API error: {e}")
        return False


def post_pr_review_comments(
    owner: str,
    repo: str,
    pull_number: int,
    commit_id: str,
    file_path: str,
    findings: list,
    diff_text: str,
    chunk_start_line: int,
):
    """Post all findings for a chunk as inline PR comments."""
    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN not set")
        return

    if not findings:
        return

    file_map = parse_diff_line_map(diff_text)
    # chunk_start_line is 0-based, diff map uses 1-based — add 1
    target_line = max(1, chunk_start_line + 1)
    diff_position = get_diff_position(file_map, file_path, target_line)

    if diff_position is None:
        print(f"⚠️ No diff position found for {file_path} line {target_line} — skipping chunk")
        return

    comments_posted = 0
    for finding in findings:
        problem = finding.get("problem", "").strip()
        fix = finding.get("fix", "").strip()

        if not problem or problem.lower() in ("no issue found", "no issue found in the code"):
            continue

        body = format_comment(finding["agent"], finding["severity"], problem, fix)
        success = post_review_comment(
            repo=f"{owner}/{repo}",
            pr_number=pull_number,
            commit_id=commit_id,
            file_path=file_path,
            line=diff_position,
            message=body,
        )
        if success:
            comments_posted += 1

    print(f"✅ Comments posted for chunk at line {target_line}: {comments_posted}")
