from __future__ import annotations

from sqlalchemy import text

from database_service import get_database_engine


def create_study_session(username: str, course_name: str, start_time) -> int | None:
    engine = get_database_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("INSERT INTO study_sessions (username, course_name, start_time) VALUES (:u, :c, :t)"),
            {"u": username, "c": course_name, "t": start_time},
        )
        conn.commit()
        return result.lastrowid


def close_study_session(study_session_id: int, end_time) -> None:
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE study_sessions "
                "SET end_time = :t, duration_seconds = TIMESTAMPDIFF(SECOND, start_time, :t) "
                "WHERE id = :id"
            ),
            {"t": end_time, "id": study_session_id},
        )
        conn.commit()
