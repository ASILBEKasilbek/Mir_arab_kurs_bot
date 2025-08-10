import sqlite3
from config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            age INTEGER,
            gender TEXT,
            phone TEXT,
            quran_course TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_user(data: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (first_name, last_name, age, gender, phone, quran_course)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (data['first_name'], data['last_name'], data['age'], data['gender'], data['phone'], data['quran_course']))
    conn.commit()
    conn.close()
