def load_guidelines():
    try:
        with open("guidelines.txt", "r") as f:
            return f.read()
    except Exception as e:
        print("Error loading guidelines:", e)
        return ""


def get_context(code_chunk):
    guidelines = load_guidelines()

    return f"""
You are given coding guidelines and code.

Follow the guidelines strictly while analyzing.

=====================
GUIDELINES:
{guidelines}
=====================

CODE:
{code_chunk}
"""