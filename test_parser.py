from parser import extract_functions

code = """
def login(user):
    query = "SELECT * FROM users WHERE name='" + user + "'"
    return query

def add(a, b):
    return a + b
"""

functions = extract_functions(code)

for f in functions:
    print("\n--- FUNCTION ---\n")
    print(f["code"])