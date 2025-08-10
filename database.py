import sqlite3
from datetime import datetime
from config import DB_PATH

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        description TEXT,
        created_at TEXT
    )""")

    # Pre-populate courses
    default_courses = [
        ("Boshlang‘ich", "Beginner Quran course"),
        ("O‘rta", "Intermediate Quran course"),
        ("Yuqori", "Advanced Quran course")
    ]
    for name, description in default_courses:
        c.execute("INSERT OR IGNORE INTO courses (name, description, created_at) VALUES (?, ?, ?)",
                  (name, description, datetime.utcnow().isoformat()))

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER UNIQUE,
        first_name TEXT,
        last_name TEXT,
        age INTEGER,
        gender TEXT,
        phone TEXT,
        course_id INTEGER,
        registered_at TEXT,
        is_paid INTEGER DEFAULT 0,
        FOREIGN KEY(course_id) REFERENCES courses(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        method TEXT,
        proof_file_id TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        reviewed_by INTEGER,
        reviewed_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    conn.commit()
    conn.close()
# Course helpers
def add_course(name, description=""):
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO courses (name, description, created_at) VALUES (?, ?, ?)",
              (name, description, datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

def list_courses():
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT id, name, description FROM courses")
    rows = c.fetchall(); conn.close()
    return rows

# User helpers
def save_user(data: dict):
    conn = get_conn()
    c = conn.cursor()

    # Kurs nomidan course_id olish
    course_name = data.get("quran_course")  # Changed from 'course_name' to 'quran_course'
    if not course_name:
        raise ValueError("Course name is missing in the data")

    c.execute("SELECT id FROM courses WHERE name = ?", (course_name,))
    course_row = c.fetchone()

    if course_row:
        course_id = course_row[0]
    else:
        # Add the course if it doesn't exist
        add_course(course_name, description=f"Auto-added course: {course_name}")
        c.execute("SELECT id FROM courses WHERE name = ?", (course_name,))
        course_row = c.fetchone()
        if not course_row:
            raise ValueError(f"Failed to create or retrieve course: {course_name}")
        course_id = course_row[0]

    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO users (tg_id, first_name, last_name, age, gender, phone, course_id, registered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("tg_id"),
        data.get("first_name"),
        data.get("last_name"),
        data.get("age"),
        data.get("gender"),
        data.get("phone"),
        course_id,
        now
    ))

    conn.commit()
    conn.close()

def get_user_by_tg(tg_id):
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    row = c.fetchone(); conn.close()
    return row

def update_user_field(user_id, field, value):
    conn = get_conn(); c = conn.cursor()
    c.execute(f"UPDATE users SET {field} = ? WHERE id = ?", (value, user_id))
    conn.commit(); conn.close()

# Payments
def create_payment(user_id, amount, method, proof_file_id):
    conn = get_conn(); c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("INSERT INTO payments (user_id, amount, method, proof_file_id, created_at) VALUES (?, ?, ?, ?, ?)",
              (user_id, amount, method, proof_file_id, now))
    payment_id = c.lastrowid
    conn.commit(); conn.close()
    return payment_id

def list_pending_payments():
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT p.id, p.user_id, u.first_name, u.last_name, p.amount, p.proof_file_id, p.created_at FROM payments p JOIN users u ON p.user_id = u.id WHERE p.status = 'pending'")
    rows = c.fetchall(); conn.close()
    return rows

def set_payment_status(payment_id, status, reviewed_by=None):
    conn = get_conn(); c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("UPDATE payments SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?", (status, reviewed_by, now, payment_id))
    conn.commit(); conn.close()

# Stats
def get_stats():
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_paid = 1"); paid = c.fetchone()[0]
    c.execute("SELECT course_id, COUNT(*) FROM users GROUP BY course_id")
    per_course = c.fetchall()
    conn.close()
    return {"total": total, "paid": paid, "per_course": per_course}
