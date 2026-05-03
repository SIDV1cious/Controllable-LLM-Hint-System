from __future__ import annotations

import streamlit as st
from sqlalchemy import text

from database_service import fetch_custom_question_rows, get_database_engine, question_row_to_dict
from domain_models import QuestionData


def public_ids_to_database_ids(public_ids: list[int]) -> list[int]:
    return [question_id - 1000 for question_id in public_ids if question_id >= 1000]


@st.cache_data(ttl=120, show_spinner=False)
def fetch_questions_by_public_ids(public_ids: list[int]) -> list[QuestionData]:
    db_ids = public_ids_to_database_ids(public_ids)
    if not db_ids:
        return []

    engine = get_database_engine()
    with engine.connect() as conn:
        rows = fetch_custom_question_rows(conn, db_ids)
    questions = [question_row_to_dict(row) for row in rows]
    question_map = {question["id"]: question for question in questions}
    return [question_map[question_id] for question_id in public_ids if question_id in question_map]


@st.cache_data(ttl=120, show_spinner=False)
def fetch_questions_by_course(course_name: str) -> list[QuestionData]:
    engine = get_database_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, category, content, answer, solution FROM custom_questions WHERE category = :c"),
            {"c": course_name},
        ).fetchall()
    return [question_row_to_dict(row) for row in rows]
