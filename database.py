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
            gender TEXT CHECK(gender IN ('erkak', 'ayol', 'hammasi')) DEFAULT 'hammasi',
            boshlanish_sanasi TEXT DEFAULT '2025-08-01',
            limit_count INTEGER DEFAULT 0,
            joylar_soni INTEGER DEFAULT 0,
            narx REAL DEFAULT 0.0,
            created_at TEXT
        )
    """)

    # Pre-populate courses (modify as needed)
    default_courses = [
        ("Quran for Beginners", "Learn basic Quran reading", "hammasi", "2025-08-01", 30, 25, 100000.0),
        ("Advanced Tajweed", "Master Tajweed rules", "erkak", "2025-09-01", 20, 15, 150000.0),
        ("Quran Memorization", "Memorize key surahs", "ayol", "2025-08-15", 25, 20, 120000.0)
    ]
    for name, description, gender, boshlanish_sanasi, limit_count, joylar_soni, narx in default_courses:
        c.execute("INSERT OR IGNORE INTO courses (name, description, gender, boshlanish_sanasi, limit_count, joylar_soni, narx, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (name, description, gender, boshlanish_sanasi, limit_count, joylar_soni, narx, datetime.utcnow().isoformat()))

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER UNIQUE,
        lang TEXT,
        first_name TEXT,
        last_name TEXT,
        age INTEGER,
        gender TEXT,
        phone TEXT,
        course_id INTEGER,
        registered_at TEXT,
        is_paid INTEGER DEFAULT 0,
        paid_at TEXT,
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
    )
    """)

    conn.commit()
    conn.close()

def add_course(name, description, gender, boshlanish_sanasi, limit_count, narx):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO courses (
            name, description, gender, boshlanish_sanasi, limit_count, joylar_soni, narx, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (name, description, gender, boshlanish_sanasi, limit_count, 0, narx))
    conn.commit()
    conn.close()

def list_courses():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, name, description, gender, boshlanish_sanasi, limit_count, joylar_soni, narx FROM courses
    """)
    rows = c.fetchall()
    conn.close()
    return rows

def delete_course(course_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    conn.commit()
    conn.close()

def get_course_by_id(course_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
    row = c.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "gender": row[3],
            "boshlanish_sanasi": row[4],
            "limit_count": row[5],
            "joylar_soni": row[6],
            "narx": row[7],
            "created_at": row[8],
        }
    return None

def save_user(data: dict):
    conn = get_conn()
    c = conn.cursor()
    course_id = data.get("course_id")
    if course_id:
        c.execute("SELECT id FROM courses WHERE id = ?", (course_id,))
        if not c.fetchone():
            conn.close()
            raise ValueError(f"Course ID {course_id} does not exist")

    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO users (tg_id, lang, first_name, last_name, age, gender, phone, course_id, registered_at, is_paid, paid_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("tg_id"),
        data.get("lang"),
        data.get("first_name"),
        data.get("last_name"),
        data.get("age"),
        data.get("gender"),
        data.get("phone"),
        course_id,
        now,
        data.get("is_paid", 0),
        data.get("paid_at")
    ))
    conn.commit()
    conn.close()

def get_user_by_tg(identifier):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, tg_id, lang, first_name, last_name, age, gender, phone, course_id, registered_at, is_paid, paid_at 
        FROM users
        WHERE id = ? OR tg_id = ?
    """, (identifier, identifier))
    
    row = c.fetchone()
    conn.close()
    return row


def update_user_field(user_identifier, field, value):
    """
    user_identifier: tg_id yoki id bo'lishi mumkin (int)
    field: yangilanadigan ustun nomi
    value: yangi qiymat
    """
    allowed_fields = [
        "lang", "first_name", "last_name", "age", "gender",
        "phone", "course_id", "registered_at", "is_paid", "paid_at"
    ]
    if field not in allowed_fields:
        raise ValueError("Invalid field")
    
    conn = get_conn()
    c = conn.cursor()
    
    # course_id uchun tekshiruv
    if field == "course_id" and value is not None:
        c.execute("SELECT id FROM courses WHERE id = ?", (value,))
        if not c.fetchone():
            conn.close()
            raise ValueError(f"Course ID {value} does not exist")
    
    # user_identifier qaysi ustun ekanini aniqlash
    if isinstance(user_identifier, int):
        # avval tg_id bo‘lib ko‘riladi
        c.execute("SELECT id FROM users WHERE tg_id = ? OR id = ?", (user_identifier, user_identifier))
        user = c.fetchone()
        if not user:
            conn.close()
            raise ValueError(f"User with identifier {user_identifier} not found")
        
        # yangilash
        c.execute(f"UPDATE users SET {field} = ? WHERE tg_id = ? OR id = ?", (value, user_identifier, user_identifier))
    
    conn.commit()
    conn.close()


def create_payment(user_id, amount, method, proof_file_id):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("INSERT INTO payments (user_id, amount, method, proof_file_id, created_at) VALUES (?, ?, ?, ?, ?)",
              (user_id, amount, method, proof_file_id, now))
    payment_id = c.lastrowid
    conn.commit()
    conn.close()
    return payment_id

def list_pending_payments():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT p.id, p.user_id, u.first_name, u.last_name, p.amount, p.proof_file_id, p.created_at 
        FROM payments p 
        JOIN users u ON p.user_id = u.id 
        WHERE p.status = 'pending'
    """)
    rows = c.fetchall()
    conn.close()
    return rows

def set_payment_status(payment_id, status, reviewed_by=None):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("UPDATE payments SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?", 
              (status, reviewed_by, now, payment_id))
    conn.commit()
    conn.close()

def get_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_paid = 1")
    paid = c.fetchone()[0]
    c.execute("SELECT course_id, COUNT(*) FROM users GROUP BY course_id")
    per_course = c.fetchall()
    conn.close()
    return {"total": total, "paid": paid, "per_course": per_course}

def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, tg_id, lang, first_name, last_name, age, gender, phone, course_id FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def get_users_by_gender(gender):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, tg_id, lang, first_name, last_name, age, gender, phone, course_id FROM users WHERE gender = ?", (gender,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_user_by_id(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, tg_id, lang, first_name, last_name, age, gender, phone, course_id FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row