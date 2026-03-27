import requests
import os
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

SEVERITY_EMOJI = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}


def format_comment(agent: str, severity: str, problem: str, fix: str) -> str:
    emoji = SEVERITY_EMOJI.get(severity, "⚪")
    return (
        f"### {emoji} **{severity} Severity Issue** — `{agent.title()} Review`\n\n"
        f"**Problem:** {problem}\n\n"
        f"**Suggested Fix:**\n```\n{fix}\n```"
    )


def parse_diff_line_map(diff_text: str) -> dict:
    """
    Returns: { file_path: [(diff_line_number, actual_line_number), ...] }
    diff_line_number is the position in the diff hunk (1-based), used by GitHub API.
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
            # e.g. @@ -10,7 +12,8 @@
            diff_position += 1
            try:
                new_part = raw_line.split("+")[1].split(",")[0].split(" ")[0]
                current_line = int(new_part) - 1
            except (IndexError, ValueError):
                current_line = 0
        elif current_file is not None:
            if raw_line.startswith("-"):
                diff_position += 1  # counts toward position but no new line
            elif raw_line.startswith("+"):
                current_line += 1
                diff_position += 1
                file_map[current_file].append((diff_position, current_line))
            elif not raw_line.startswith("\\"):
                current_line += 1
                diff_position += 1

    return file_map


def get_diff_position(file_map: dict, file_path: str, target_line: int) -> int | None:
    """Find the diff position for a given actual line number in a file."""
    entries = file_map.get(file_path, [])
    if not entries:
        return None
    # Find closest added line at or after target_line
    for diff_pos, actual_line in entries:
        if actual_line >= target_line:
            return diff_pos
    # Fallback: last added line in file
    return entries[-1][0] if entries else None


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
    """
    Post inline review comments on a PR for a list of findings.
    findings: list of dicts with keys: agent, severity, problem, fix
    """
    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN not set")
        return

    file_map = parse_diff_line_map(diff_text)
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    for finding in findings:
        problem = finding.get("problem", "").strip()
        fix = finding.get("fix", "").strip()

        if not problem or problem.lower() in ("no issue found", "no issue found in the code"):
            continue

        diff_position = get_diff_position(file_map, file_path, chunk_start_line + 1)
        if diff_position is None:
            print(f"Skipping comment — no diff position found for {file_path}:{chunk_start_line}")
            continue

        body = format_comment(finding["agent"], finding["severity"], problem, fix)

        payload = {
            "body": body,
            "commit_id": commit_id,
            "path": file_path,
            "position": diff_position,  # GitHub uses diff position, not line number
        }

        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code == 201:
            print(f"✅ Comment posted on {file_path} (diff pos {diff_position})")
        else:
            print(f" Failed to post comment: {resp.status_code} — {resp.text[:200]}")
