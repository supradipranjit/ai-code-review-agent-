from tree_sitter_languages import get_parser

# Map file extensions to tree-sitter language names and their block node types
LANGUAGE_MAP = {
    ".py":   ("python",     ["function_definition", "class_definition"]),
    ".js":   ("javascript", ["function_declaration", "arrow_function", "class_declaration", "method_definition"]),
    ".java": ("java",       ["method_declaration", "class_declaration", "constructor_declaration"]),
    ".cpp":  ("cpp",        ["function_definition", "class_specifier"]),
    ".c":    ("c",          ["function_definition"]),
    ".sql":  ("sql",        ["create_function", "create_procedure", "select_statement", "insert_statement", "update_statement", "delete_statement"]),
}

DEFAULT_LANGUAGE = ("python", ["function_definition", "class_definition"])


def detect_language(diff_text: str):
    for ext, lang_info in LANGUAGE_MAP.items():
        if f"--- a/" in diff_text or f"+++ b/" in diff_text:
            for line in diff_text.split("\n"):
                if line.startswith("+++ b/") and line.endswith(ext):
                    return lang_info
    return DEFAULT_LANGUAGE


def parse_code_chunks(code: str, diff_text: str = ""):
    if not code.strip():
        return []

    language, node_types = detect_language(diff_text)
    print(f"Detected language: {language}")

    try:
        parser = get_parser(language)
        tree = parser.parse(bytes(code, "utf8"))
        root = tree.root_node
    except Exception as e:
        print(f"Tree-sitter parsing error ({language}):", e)
        return []

    lines = code.split("\n")
    chunks = []

    def extract_blocks(node):
        if node.type in node_types:
            start = node.start_point[0]
            end = node.end_point[0]
            chunks.append({
                "type": node.type,
                "start_line": start,
                "end_line": end,
                "code": lines[start:end + 1]
            })
        for child in node.children:
            extract_blocks(child)

    extract_blocks(root)

    if not chunks:
        print("No AST chunks found — using fallback")
        chunks.append({
            "type": "full_code",
            "start_line": 0,
            "end_line": len(lines),
            "code": lines
        })

    return chunks
