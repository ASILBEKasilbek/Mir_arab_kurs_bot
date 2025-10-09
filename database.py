# database.py
import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from config import DB_PATH

# -----------------------------
# Ichki util funksiyalar
# -----------------------------

def _dict_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def get_conn() -> sqlite3.Connection:
    """SQLite ulanishi: FK ON, WAL rejimi, Row factory.
    Har bir ulanish ustida PRAGMA lar yoqiladi.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(r[1] == column for r in cur.fetchall())


# -----------------------------
# Dastlabki sxema va migratsiyalar
# -----------------------------

def init_db() -> None:
    """Jadval(lar)ni yaratadi va eng zarur indekslarni qo'yadi.
    Shuningdek mayda migratsiyalarni ham bajaradi (age -> birth_date o'zgarishi).
    """
    conn = get_conn()
    c = conn.cursor()

    # courses
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            gender TEXT CHECK(gender IN ('erkak', 'ayol', 'hammasi')) DEFAULT 'hammasi',
            boshlanish_sanasi TEXT,
            limit_count INTEGER DEFAULT 0,
            joylar_soni INTEGER DEFAULT 0,
            narx REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )

    # users
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            lang TEXT,
            first_name TEXT,
            last_name TEXT,
            birth_date TEXT,             -- YYYY.MM.DD
            gender TEXT,
            phone TEXT,
            address TEXT,                -- manzil
            passport_front TEXT,         -- passport oldi rasmi
            passport_back TEXT,          -- passport orqa rasmi
            course_id INTEGER,
            registered_at TEXT DEFAULT (datetime('now')),
            is_paid INTEGER DEFAULT 0,   -- 0 yoki 1
            paid_at TEXT,
            registration_message_id INTEGER,
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
        """
    )

    # payments
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            method TEXT,
            proof_file_id TEXT,
            status TEXT CHECK(status IN ('pending','approved','rejected')) DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            reviewed_by INTEGER,
            reviewed_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    # Indekslar (agar yo'q bo'lsa yaratiladi)
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_course_id ON users(course_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)")

    # ---- Kichik migratsiyalar ----
    # 1) Eski kodda age bo'lgan: endi birth_date ishlatiladi.
    # Agar mavjud bazada birth_date ustuni bo'lmasa, qo'shib qo'yamiz.
    if not _column_exists(conn, "users", "birth_date"):
        c.execute("ALTER TABLE users ADD COLUMN birth_date TEXT")

    if not _column_exists(conn, "users", "registration_message_id"):
        c.execute("ALTER TABLE users ADD COLUMN registration_message_id INTEGER")
        
    if not _column_exists(conn, "users", "course_start_option"):
        c.execute("ALTER TABLE users ADD COLUMN course_start_option TEXT")  
        # qiymatlar: 'begin', 'middle' va hokazo

    # registered_at, created_at defaultlari yo'q bo'lishi mumkin bo'lgan eski bazalar uchun
    # (SQLite da DEFAULT ni ALTER bilan qo'yib bo'lmaydi, shu bois bu yerda faqat mavjud yozuvlar bo'sh bo'lsa to'ldiriladi)
    c.execute("UPDATE users SET registered_at = COALESCE(registered_at, datetime('now'))")
    c.execute("UPDATE payments SET created_at = COALESCE(created_at, datetime('now'))")
    c.execute("UPDATE courses SET created_at = COALESCE(created_at, datetime('now'))")
    if not _column_exists(conn, "users", "start_type"):
        c.execute("ALTER TABLE users ADD COLUMN start_type TEXT")
    if not _column_exists(conn, "users", "start_month"):
        c.execute("ALTER TABLE users ADD COLUMN start_month TEXT")



    conn.commit()
    conn.close()


# -----------------------------
# Courses CRUD
# -----------------------------



def add_course(
    name: str,
    description: Optional[str] = None,
    gender: str = "hammasi",
    boshlanish_sanasi: Optional[str] = None,  # 'DD.MM.YYYY'
    limit_count: int = 0,
    narx: float = 0.0,
) -> int:
    if boshlanish_sanasi:
        try:
            datetime.strptime(boshlanish_sanasi, "%d.%m.%Y")  # Yangi format
        except ValueError:
            raise ValueError("Sana DD.MM.YYYY formatida bo‘lishi kerak")
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO courses (
            name, description, gender, boshlanish_sanasi, limit_count, joylar_soni, narx
        )
        VALUES (?, ?, ?, ?, ?, 0, ?)
        """,
        (name, description, gender, boshlanish_sanasi, limit_count, narx),
    )
    course_id = c.lastrowid
    conn.commit()
    conn.close()
    return course_id

def list_courses() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, name, description, gender, boshlanish_sanasi, limit_count, joylar_soni, narx, created_at
        FROM courses
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()
    return [_dict_from_row(r) for r in rows]


def delete_course(course_id: int) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    conn.commit()
    conn.close()


def get_course_by_id(course_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    conn.close()
    return _dict_from_row(row) if row else None


# -----------------------------
# Users CRUD
# -----------------------------

def save_user(user_data: dict) -> int:
    try:
        if not isinstance(user_data, dict):
            raise ValueError("user_data must be a dictionary")

        if user_data.get("birth_date"):
            try:
                datetime.strptime(user_data["birth_date"], "%d.%m.%Y")
            except ValueError:
                raise ValueError("birth_date must be in DD.MM.YYYY format")
        
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO users (
                tg_id, lang, first_name, last_name, birth_date, gender, phone, 
                address, passport_front, passport_back, course_id, registered_at, 
                is_paid, paid_at, registration_message_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_data["tg_id"],
                user_data.get("lang"),
                user_data.get("first_name"),
                user_data.get("last_name"),
                user_data.get("birth_date"),
                user_data.get("gender"),
                user_data.get("phone"),
                user_data.get("address"),
                user_data.get("passport_front"),
                user_data.get("passport_back"),
                user_data.get("course_id"),
                user_data.get("registered_at"),
                user_data.get("is_paid", 0),
                user_data.get("paid_at"),
                user_data.get("registration_message_id"),
            ),
        )
        user_id = c.lastrowid
        if isinstance(user_id, tuple):
            user_id = user_id[0]

        conn.commit()
        conn.close()
        return user_id
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        raise e
 
def update_user_field(tg_id: int, field: str, value: str):
    allowed_fields = [
        "lang", "first_name", "last_name", "birth_date", "gender", 
        "phone", "address", "passport_front", "passport_back", 
        "course_id", "is_paid", "paid_at", "registration_message_id",
        "start_type", "start_month"
    ]


    if field not in allowed_fields:
        raise ValueError(f"Invalid field: {field}")
    
    if field == "birth_date":
        try:
            datetime.strptime(value, "%d.%m.%Y")
        except ValueError:
            raise ValueError("birth_date must be in DD.MM.YYYY format")
    
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"UPDATE users SET {field} = ? WHERE tg_id = ?", (value, tg_id))
    conn.commit()
    conn.close()

def get_user_by_tg(identifier: int) -> Optional[Dict[str, Any]]:
    """identifier: id yoki tg_id (ikkalasidan biri ham bo'lishi mumkin)."""
    conn = get_conn()
    row = conn.execute(
        """
        SELECT id, tg_id, lang, first_name, last_name, birth_date, gender, phone,
               address, course_id, registered_at, is_paid, paid_at, passport_front, passport_back, registration_message_id
        FROM users
        WHERE id = ? OR tg_id = ?
        """,
        (identifier, identifier),
    ).fetchone()
    conn.close()
    return _dict_from_row(row) if row else None



# -----------------------------
# Payments
# -----------------------------

def create_payment(user_id: int, amount: float, method: str, proof_file_id: str) -> int:
    conn = get_conn()
    c = conn.cursor()

    # Foydalanuvchi borligini tekshirish
    row = c.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"User {user_id} does not exist")

    c.execute(
        "INSERT INTO payments (user_id, amount, method, proof_file_id) VALUES (?, ?, ?, ?)",
        (user_id, amount, method, proof_file_id),
    )
    payment_id = c.lastrowid
    conn.commit()
    conn.close()
    return payment_id


def list_pending_payments() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT p.id, p.user_id, u.first_name, u.last_name, p.amount, p.proof_file_id, p.created_at
        FROM payments p
        JOIN users u ON p.user_id = u.id
        WHERE p.status = 'pending'
        ORDER BY p.id DESC
        """
    ).fetchall()
    conn.close()
    return [_dict_from_row(r) for r in rows]


def set_payment_status(payment_id: int, status: str, reviewed_by: Optional[int] = None) -> None:
    if status not in {"pending", "approved", "rejected"}:
        raise ValueError("status must be one of: pending | approved | rejected")

    conn = get_conn()
    c = conn.cursor()

    # To'lov mavjudmi
    pay = c.execute("SELECT user_id FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if not pay:
        conn.close()
        raise ValueError(f"Payment {payment_id} not found")

    now = datetime.utcnow().isoformat()
    c.execute(
        "UPDATE payments SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?",
        (status, reviewed_by, now, payment_id),
    )

    # Agar tasdiqlansa, foydalanuvchini ham is_paid=1 qilish (agar kerak bo'lsa)
    user_id = pay["user_id"] if isinstance(pay, sqlite3.Row) else pay[0]
    if status == "approved":
        c.execute(
            "UPDATE users SET is_paid = 1, paid_at = COALESCE(paid_at, ?) WHERE id = ?",
            (now, user_id),
        )
        # Kurs joylar_soni ni oshirish
        c.execute(
            """
            UPDATE courses 
            SET joylar_soni = joylar_soni + 1 
            WHERE id = (SELECT course_id FROM users WHERE id = ?)
            """,
            (user_id,)
        )

    conn.commit()
    conn.close()


# -----------------------------
# Statistika / Query yordamchilari
# -----------------------------

def get_stats() -> Dict[str, Any]:
    conn = get_conn()
    c = conn.cursor()

    total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    paid = c.execute("SELECT COUNT(*) FROM users WHERE is_paid = 1").fetchone()[0]
    per_course = c.execute(
        """
        SELECT c.id AS course_id, c.name AS course_name, COUNT(u.id) AS users_count
        FROM courses c
        LEFT JOIN users u ON u.course_id = c.id
        GROUP BY c.id, c.name
        ORDER BY c.id
        """
    ).fetchall()

    conn.close()
    return {
        "total": total,
        "paid": paid,
        "per_course": [
            {
                "course_id": r[0],
                "course_name": r[1],
                "users_count": r[2],
            }
            for r in per_course
        ],
    }


def get_all_users() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    conn.close()
    return [_dict_from_row(r) for r in rows]


def get_users_by_gender(gender: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, tg_id, lang, first_name, last_name, birth_date, gender, phone, address, course_id
        FROM users
        WHERE gender = ?
        ORDER BY id DESC
        """,
        (gender,),
    ).fetchall()
    conn.close()
    return [_dict_from_row(r) for r in rows]


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute(
        """
        SELECT id, tg_id, lang, first_name, last_name, birth_date, gender, phone, address, course_id
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    conn.close()
    return _dict_from_row(row) if row else None

def update_course(
    course_id: int,
    name: str,
    description: Optional[str] = None,
    gender: str = "hammasi",
    boshlanish_sanasi: Optional[str] = None,
    limit_count: int = 0,
    narx: float = 0.0
) -> None:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        UPDATE courses SET
            name = ?,
            description = ?,
            gender = ?,
            boshlanish_sanasi = ?,
            limit_count = ?,
            narx = ?
        WHERE id = ?
        """,
        (name, description, gender, boshlanish_sanasi, limit_count, narx, course_id)
    )
    if c.rowcount == 0:
        conn.close()
        raise ValueError(f"Course ID {course_id} does not exist")
    conn.commit()
    conn.close()
    
def get_course_by_id(course_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    conn.close()
    return _dict_from_row(row) if row else None