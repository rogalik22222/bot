import sqlite3

def init_db():
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                telegram_id TEXT,
                nickname TEXT,
                role TEXT,
                server INTEGER
            )
            """
        )
        conn.commit()

def add_user(user_id, telegram_id, nickname, role, server):
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (user_id, telegram_id, nickname, role, server) VALUES (?, ?, ?, ?, ?)",
            (user_id, telegram_id, nickname, role, server)
        )
        conn.commit()

def get_user_role(user_id):
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None

def update_user_role(user_id, new_role):
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = ? WHERE user_id = ?", (new_role, user_id))
        conn.commit()

def get_all_users():
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, nickname, role, server FROM users")
        return cursor.fetchall()

def delete_user(user_id):
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
