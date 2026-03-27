import gradio as gr
from agents import analyze_code
from orchestrator import parse_llm_output, assign_severity
from parser import parse_code_chunks
import os
from dotenv import load_dotenv

load_dotenv()

try:
    with open("guidelines.txt", "r", encoding="utf-8") as f:
        GUIDELINES = f.read()
except:
    GUIDELINES = ""

SEVERITY_EMOJI = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}


def review_code(code, language):
    if not code.strip():
        return "⚠️ Please enter some code to review."

    fake_diff = f"+++ b/test.{language}"
    chunks = parse_code_chunks(code, fake_diff)

    if not chunks:
        return "⚠️ Could not parse the code."

    output_md = "# 🤖 AI Code Review Report\n\n"

    for chunk in chunks:
        chunk_code = "\n".join(chunk["code"])
        block_type = chunk["type"].replace("_", " ").title()
        start = chunk["start_line"]
        end = chunk["end_line"]

        output_md += f"## 📝 {block_type} (Lines {start}–{end})\n\n"

        for agent in ["security", "performance", "style"]:
            result = analyze_code(agent, chunk_code, GUIDELINES)
            problem, fix = parse_llm_output(result)
            severity = assign_severity(result)
            emoji = SEVERITY_EMOJI.get(severity, "⚪")

            output_md += f"### {emoji} {agent.upper()} — Severity: `{severity}`\n"
            output_md += f"**Problem:** {problem or 'No issue found'}\n\n"
            output_md += f"**Fix:** {fix or 'No fix needed'}\n\n"
            output_md += "---\n\n"

    return output_md


with gr.Blocks(title="AI Code Review Agent") as demo:
    gr.Markdown("# 🤖 AI Code Review Agent")
    gr.Markdown("Paste your code and get instant **Security**, **Performance**, and **Style** feedback.")

    with gr.Row():
        with gr.Column(scale=1):
            code_input = gr.Code(
                label="Your Code",
                language="python",
                lines=18
            )
            language_dropdown = gr.Dropdown(
                choices=["py", "js", "java", "c", "cpp", "sql"],
                value="py",
                label="Language"
            )
            submit_btn = gr.Button("🔍 Review Code", variant="primary", size="lg")

        with gr.Column(scale=1):
            output = gr.Markdown(label="Review Results", value="Results will appear here...")

    submit_btn.click(fn=review_code, inputs=[code_input, language_dropdown], outputs=output)

    gr.Examples(
        examples=[
            ['def login(user):\n    query = "SELECT * FROM users WHERE name=\'" + user + "\'"\n    return query', "py"],
            ['function getData(id) {\n    return eval("data[" + id + "]");\n}', "js"],
        ],
        inputs=[code_input, language_dropdown]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft())
