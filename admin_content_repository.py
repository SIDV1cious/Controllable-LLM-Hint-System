from __future__ import annotations

from sqlalchemy import text

from course_repository import BASE_COURSES
from database_service import get_database_engine


def base_course_names() -> list[str]:
    return [name for name, _ in BASE_COURSES]


def build_course_name_list(base_names: list[str], custom_names: list[str]) -> list[str]:
    return base_names + [name for name in custom_names if name not in base_names]


def fetch_custom_course_names() -> list[str]:
    engine = get_database_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT course_name FROM custom_courses")).fetchall()
    return [row[0] for row in rows]


def list_all_course_names() -> list[str]:
    return build_course_name_list(base_course_names(), fetch_custom_course_names())


def create_custom_course(course_name: str, description: str) -> None:
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO custom_courses (course_name, description) VALUES (:n, :d)"),
            {"n": course_name, "d": description},
        )
        conn.commit()


def delete_course_and_questions(course_name: str) -> None:
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM custom_courses WHERE course_name = :c"), {"c": course_name})
        conn.execute(text("DELETE FROM custom_questions WHERE category = :c"), {"c": course_name})
        conn.commit()


def fetch_custom_course_records() -> list[tuple[str, str]]:
    engine = get_database_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT course_name, description FROM custom_courses")).fetchall()
    return [(row[0], row[1]) for row in rows]


def update_course_and_question_category(old_name: str, new_name: str, new_description: str) -> None:
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE custom_courses SET course_name = :new_n, description = :new_d WHERE course_name = :old_n"),
            {"new_n": new_name, "new_d": new_description, "old_n": old_name},
        )
        if new_name != old_name:
            conn.execute(
                text("UPDATE custom_questions SET category = :new_n WHERE category = :old_n"),
                {"new_n": new_name, "old_n": old_name},
            )
        conn.commit()


def create_custom_question(category: str, content: str) -> None:
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO custom_questions (category, content) VALUES (:c, :t)"),
            {"c": category, "t": content},
        )
        conn.commit()


def make_question_delete_label(question_id: int, category: str, preview: str) -> str:
    return f"[{category}] {preview}... (内部ID:{question_id})"


def make_question_edit_label(question_id: int, category: str, content: str) -> str:
    return f"[{category}] (内部ID:{question_id}) {content[:20]}..."


def fetch_question_delete_options() -> dict[str, int]:
    engine = get_database_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, category, LEFT(content, 15) FROM custom_questions")).fetchall()
    return {make_question_delete_label(row[0], row[1], row[2]): row[0] for row in rows}


def delete_custom_question(question_id: int) -> None:
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM custom_questions WHERE id = :id"), {"id": question_id})
        conn.commit()


def fetch_question_edit_options() -> dict[str, tuple[int, str, str]]:
    engine = get_database_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, category, content FROM custom_questions")).fetchall()
    return {make_question_edit_label(row[0], row[1], row[2]): (row[0], row[1], row[2]) for row in rows}


def update_custom_question(question_id: int, category: str, content: str) -> None:
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE custom_questions SET category = :c, content = :t WHERE id = :id"),
            {"c": category, "t": content, "id": question_id},
        )
        conn.commit()


def fetch_question_preview_records() -> list[tuple[int, str, str]]:
    engine = get_database_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, category, content FROM custom_questions ORDER BY id DESC")).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]
