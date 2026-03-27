def assign_severity(text):
    text = text.lower()
    if "sql injection" in text or "security" in text:
        return "HIGH"
    elif "performance" in text:
        return "MEDIUM"
    else:
        return "LOW"


def parse_llm_output(output):
    try:
        problem_lines = []
        fix_lines = []
        current = None

        for line in output.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.lower().startswith("problem"):
                current = "problem"
                rest = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
                if rest:
                    problem_lines.append(rest)
            elif stripped.lower().startswith("fix"):
                current = "fix"
                rest = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
                if rest:
                    fix_lines.append(rest)
            elif current == "problem":
                problem_lines.append(stripped)
            elif current == "fix":
                fix_lines.append(stripped)

        return " ".join(problem_lines).strip(), " ".join(fix_lines).strip()
    except:
        return output, "No fix found"


def deduplicate(findings: list) -> list:
    seen = set()
    unique = []
    for f in findings:
        key = (f["agent"], f["problem"].lower().strip()[:80])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def orchestrate_results(results):
    final = []

    print("\n" + "=" * 50)
    print("         AI CODE REVIEW REPORT")
    print("=" * 50)

    for item in results:
        chunk = item["chunk"]
        analyses = item["analysis"]

        print(f"\nFunction/Block  : {chunk.get('type', 'unknown').replace('_', ' ').title()}")
        print(f"Lines           : {chunk.get('start_line', '?')} - {chunk.get('end_line', '?')}")
        print("-" * 50)

        for agent, output in analyses.items():
            if not output:
                continue

            problem, fix = parse_llm_output(output)
            severity = assign_severity(output)

            if not problem or problem.lower() in ("no issue found", "no issue found in the code"):
                continue

            print(f"\n[{agent.upper()}]  Severity: {severity}")
            print(f"  Problem : {problem}")
            print(f"  Fix     : {fix or 'No fix needed'}")

            final.append({
                "agent": agent,
                "severity": severity,
                "problem": problem,
                "fix": fix,
                "start_line": chunk.get("start_line", 0),
                "end_line": chunk.get("end_line", 0),
            })

    final = deduplicate(final)
    print("\n" + "=" * 50 + "\n")
    return final
