from __future__ import annotations

from sqlalchemy import text

from database_service import get_database_engine
from system_config import now_shanghai


def fetch_user_auth_record(username: str):
    engine = get_database_engine()
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT password_hash, role FROM users WHERE username = :u"),
            {"u": username},
        ).fetchone()


def user_exists(username: str) -> bool:
    engine = get_database_engine()
    with engine.connect() as conn:
        return bool(
            conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": username}).fetchone()
        )


def create_student_user(username: str, password_hash: str) -> None:
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO users (username, password_hash, role) VALUES (:u, :p, 'student')"),
            {"u": username, "p": password_hash},
        )
        conn.commit()


def record_login_log(username: str) -> None:
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO login_logs (username, login_time) VALUES (:u, :t)"),
            {"u": username, "t": now_shanghai()},
        )
        conn.commit()


def get_user_current_quiz_ids(username: str) -> list[int]:
    engine = get_database_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT current_quiz_ids FROM users WHERE username = :u"),
            {"u": username},
        ).fetchone()

    if not row or not row[0]:
        return []
    return [int(item) for item in str(row[0]).split(",") if item.strip()]


def save_user_current_quiz_ids(username: str, question_ids: list[int]) -> None:
    serialized_ids = ",".join(str(question_id) for question_id in question_ids)
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE users SET current_quiz_ids = :ids WHERE username = :u"),
            {"ids": serialized_ids, "u": username},
        )
        conn.commit()


def clear_user_current_quiz_ids(username: str) -> None:
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(text("UPDATE users SET current_quiz_ids = NULL WHERE username = :u"), {"u": username})
        conn.commit()
