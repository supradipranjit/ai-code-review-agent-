# Demo file with intentional bugs for AI Code Review Agent demo


# SECURITY BUG: SQL Injection
def get_user(username):
    query = "SELECT * FROM users WHERE name='" + username + "'"
    return query


# SECURITY BUG: Hardcoded credentials
def connect_db():
    password = "admin123"
    return f"postgresql://admin:{password}@localhost/mydb"


# PERFORMANCE ISSUE: DB query inside loop
def get_all_scores(user_ids, db):
    scores = []
    for uid in user_ids:
        result = db.query("SELECT score FROM users WHERE id=" + str(uid))
        scores.append(result)
    return scores


# PERFORMANCE ISSUE: Unnecessary list copy
def process_items(items):
    all_items = list(items)
    total = 0
    for item in all_items:
        total = total + item
    return total


# STYLE VIOLATION: No type hints, no docstring, bad naming
def calc(x,y,op):
    if op=="add":
        return x+y
    elif op=="sub":
        return x-y
    elif op=="mul":
        return x*y
    else:
        return x/y


# STYLE VIOLATION: Magic numbers
def check_age(a):
    if a>17 and a<65:
        return True
    return False