from __future__ import annotations

import streamlit as st
from sqlalchemy import bindparam, text

from app_constants import InteractionMarker
from database_service import get_database_engine


@st.cache_data(ttl=30, show_spinner=False)
def fetch_total_study_seconds(username: str) -> int:
    engine = get_database_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT SUM(duration_seconds) FROM study_sessions WHERE username = :u"),
            {"u": username},
        ).fetchone()
    return int(row[0]) if row and row[0] else 0


@st.cache_data(ttl=30, show_spinner=False)
def fetch_answer_logs(username: str) -> list[tuple[int, str]]:
    engine = get_database_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT question_id, ai_response FROM interaction_logs "
                "WHERE student_id = :u AND user_query LIKE :answer_marker"
            ),
            {"u": username, "answer_marker": f"{InteractionMarker.ANSWER_SUBMISSION}%"},
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


@st.cache_data(ttl=120, show_spinner=False)
def fetch_question_details_by_public_ids(public_question_ids: tuple[int, ...]) -> dict[int, dict[str, str]]:
    db_ids = [int(question_id) - 1000 for question_id in public_question_ids if int(question_id) >= 1000]
    if not db_ids:
        return {}

    stmt = text("SELECT id, category, content FROM custom_questions WHERE id IN :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    engine = get_database_engine()
    with engine.connect() as conn:
        rows = conn.execute(stmt, {"ids": db_ids}).fetchall()
    return {1000 + row[0]: {"category": row[1], "content": row[2]} for row in rows}


def clear_student_report_cache() -> None:
    fetch_total_study_seconds.clear()
    fetch_answer_logs.clear()
    fetch_question_details_by_public_ids.clear()
