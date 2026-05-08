from __future__ import annotations

import streamlit as st
from sqlalchemy import text

from database_service import ensure_leakage_observability_columns, get_database_engine
from system_config import now_shanghai


def _safe_non_negative_int(value: int | float | str | None) -> int:
    try:
        return max(0, int(round(float(value or 0))))
    except (TypeError, ValueError):
        return 0


def build_interaction_payload(
    question_id: int,
    student_id: str,
    user_query: str,
    ai_response: str,
    is_leaking_answer: int = 0,
    leakage_score: int = 0,
    rewrite_count: int = 0,
    leakage_reason: str = "",
    hint_strength: str = "",
    pedagogical_intent: str = "",
    hint_safety_status: str = "",
    request_char_count: int = 0,
    formula_fragment_count: int = 0,
    generation_elapsed_ms: int = 0,
    rewrite_triggered: int = 0,
) -> dict:
    rewrite_total = _safe_non_negative_int(rewrite_count)
    return {
        "qid": question_id,
        "sid": student_id,
        "qry": user_query,
        "rsp": ai_response,
        "leak": is_leaking_answer,
        "score": leakage_score,
        "rewrites": rewrite_total,
        "reason": leakage_reason[:255],
        "strength": hint_strength[:32],
        "intent": pedagogical_intent[:64],
        "status": hint_safety_status[:64],
        "request_chars": _safe_non_negative_int(request_char_count),
        "formula_count": _safe_non_negative_int(formula_fragment_count),
        "elapsed_ms": _safe_non_negative_int(generation_elapsed_ms),
        "rewrite_flag": int(bool(_safe_non_negative_int(rewrite_triggered) or rewrite_total)),
        "time": now_shanghai(),
    }


def insert_interaction_log(payload: dict) -> None:
    engine = get_database_engine()
    with engine.connect() as conn:
        ensure_leakage_observability_columns()
        try:
            conn.execute(
                text(
                    "INSERT INTO interaction_logs "
                    "(question_id, student_id, user_query, ai_response, is_leaking_answer, "
                    "leakage_score, rewrite_count, leakage_reason, hint_strength, "
                    "pedagogical_intent, hint_safety_status, request_char_count, "
                    "formula_fragment_count, generation_elapsed_ms, rewrite_triggered, created_at) "
                    "VALUES (:qid, :sid, :qry, :rsp, :leak, :score, :rewrites, :reason, "
                    ":strength, :intent, :status, :request_chars, :formula_count, :elapsed_ms, :rewrite_flag, :time)"
                ),
                payload,
            )
        except Exception:
            conn.execute(
                text(
                    "INSERT INTO interaction_logs "
                    "(question_id, student_id, user_query, ai_response, is_leaking_answer, created_at) "
                    "VALUES (:qid, :sid, :qry, :rsp, :leak, :time)"
                ),
                payload,
            )
        conn.commit()


@st.cache_data(ttl=30, show_spinner=False)
def fetch_student_interaction_logs(username: str):
    engine = get_database_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT question_id, user_query, ai_response " "FROM interaction_logs WHERE student_id = :u"),
            {"u": username},
        ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def clear_student_interaction_log_cache() -> None:
    fetch_student_interaction_logs.clear()
