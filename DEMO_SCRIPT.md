# 🎤 AI Code Review Agent — Demo Script

## The Problem (30 seconds)

> "Every software team faces the same bottleneck — code reviews.
> Senior developers spend **5 to 10 hours every week** just reviewing pull requests.
> That's time taken away from building features, fixing real bugs, and shipping products.
> And even with all that effort, human reviewers still miss security vulnerabilities,
> performance issues, and style inconsistencies — especially under deadline pressure."

---

## The Solution (30 seconds)

> "We built an **AI-powered code review agent** that automatically reviews every
> pull request the moment it's opened — no waiting, no scheduling, no bottleneck.
> It uses three specialized AI agents running in parallel:
> one for **security**, one for **performance**, and one for **code style**.
> The results are posted directly as **inline comments on the PR** in GitHub —
> exactly where the developer is already working."

---

## Live Demo Steps

1. Open GitHub repo → show the `demo_code.py` file with intentional bugs
2. Open a new Pull Request with that file
3. Show the webhook firing in the uvicorn terminal
4. Show the AI agents running (SECURITY, PERFORMANCE, STYLE analysis logs)
5. Refresh the GitHub PR → show inline comments appearing on the exact lines
6. Open `http://127.0.0.1:8000/dashboard` → show live charts updating
7. (Optional) Push a fixed version of the code → open another PR → show re-evaluation

---

## The Value (20 seconds)

> "This saves senior developers hours every week.
> It catches security bugs like SQL injection before they reach production.
> It enforces code quality standards automatically and consistently.
> And it gives every developer — junior or senior — instant, actionable feedback.
> Faster reviews mean faster releases, and better code means fewer incidents."

---

## Edge Cases Handled

- Large PRs with many functions → chunked and processed individually
- LLM API failures → retried up to 3 times, then skipped gracefully
- Duplicate findings → deduplicated before posting
- Non-Python files → language auto-detected from file extension
- No functions found → falls back to full-code review

---

## Stack

- **FastAPI** — webhook server
- **LangGraph** — multi-agent orchestration
- **Gemini 2.5 Flash** — LLM for code analysis
- **tree-sitter** — AST-based code parsing
- **PostgreSQL** — findings storage
- **GitHub API** — inline PR comments
- **Gradio** — manual code review UI
- **Chart.js** — live dashboard
