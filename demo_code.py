# Demo file with intentional bugs

def get_user(username):
    query = "SELECT * FROM users WHERE name='" + username + "'"  # SQL Injection
    return query

def connect_db():
    password = "admin123"  # Hardcoded credential
    return f"postgresql://admin:{password}@localhost/mydb"

def get_all_scores(user_ids, db):
    scores = []
    for uid in user_ids:
        result = db.query("SELECT score FROM users WHERE id=" + str(uid))  # Inefficient
        scores.append(result)
    return scores
# trigger change