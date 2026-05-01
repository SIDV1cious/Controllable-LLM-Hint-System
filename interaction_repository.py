from __future__ import annotations

from sqlalchemy import text

from database_service import ensure_leakage_observability_columns, get_database_engine
from system_config import now_shanghai


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
) -> dict:
    return {
        "qid": question_id,
        "sid": student_id,
        "qry": user_query,
        "rsp": ai_response,
        "leak": is_leaking_answer,
        "score": leakage_score,
        "rewrites": rewrite_count,
        "reason": leakage_reason[:255],
        "strength": hint_strength[:32],
        "intent": pedagogical_intent[:64],
        "status": hint_safety_status[:64],
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
                    "pedagogical_intent, hint_safety_status, created_at) "
                    "VALUES (:qid, :sid, :qry, :rsp, :leak, :score, :rewrites, :reason, "
                    ":strength, :intent, :status, :time)"
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


def fetch_student_interaction_logs(username: str):
    engine = get_database_engine()
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT question_id, user_query, ai_response " "FROM interaction_logs WHERE student_id = :u"),
            {"u": username},
        ).fetchall()
