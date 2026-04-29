import asyncio
import logging
import random
import re

import streamlit as st
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from hint_system_core import (
    AppConfig,
    batch_assess,
    ensure_leakage_observability_columns,
    fetch_custom_question_rows,
    get_database_engine,
    now_shanghai,
    question_row_to_dict,
    verify_password,
)


HINT_STRENGTH_MARK_PATTERN = re.compile(r"【提示强度：[^】]+】")


def _clean_restored_tutoring_query(query: str) -> str:
    cleaned = str(query or "").replace("【辅导】", "")
    cleaned = HINT_STRENGTH_MARK_PATTERN.sub("", cleaned)
    return cleaned.strip()


def authenticate_learning_user(u: str, p: str):
    engine = get_database_engine()
    with engine.connect() as conn:
        res = conn.execute(text("SELECT password_hash, role FROM users WHERE username = :u"), {"u": u}).fetchone()
        if res and verify_password(res[0], p):
            return True, res[1]
        return False, None


def register_learning_user(u: str, p: str) -> bool:
    engine = get_database_engine()
    with engine.connect() as conn:
        if conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": u}).fetchone():
            return False
        conn.execute(
            text("INSERT INTO users (username, password_hash, role) VALUES (:u, :p, 'student')"),
            {"u": u, "p": generate_password_hash(p)},
        )
        conn.commit()
        return True


def record_login_event(username: str):
    try:
        engine = get_database_engine()
        with engine.connect() as conn:
            ts = now_shanghai()
            conn.execute(
                text("INSERT INTO login_logs (username, login_time) VALUES (:u, :t)"),
                {"u": username, "t": ts},
            )
            conn.commit()
    except Exception as e:
        logging.error(f"record_login_event error: {e}")


def record_learning_interaction(
    qid: int,
    qry: str,
    rsp: str,
    leak: int = 0,
    leakage_score: int = 0,
    rewrite_count: int = 0,
    leakage_reason: str = "",
    hint_strength: str = "",
    pedagogical_intent: str = "",
    hint_safety_status: str = "",
):
    try:
        engine = get_database_engine()
        with engine.connect() as conn:
            ts = now_shanghai()
            ensure_leakage_observability_columns()
            try:
                conn.execute(
                    text(
                        "INSERT INTO interaction_logs (question_id, student_id, user_query, ai_response, is_leaking_answer, leakage_score, rewrite_count, leakage_reason, hint_strength, pedagogical_intent, hint_safety_status, created_at) VALUES (:qid, :sid, :qry, :rsp, :leak, :score, :rewrites, :reason, :strength, :intent, :status, :time)"
                    ),
                    {
                        "qid": qid,
                        "sid": st.session_state.current_user,
                        "qry": qry,
                        "rsp": rsp,
                        "leak": leak,
                        "score": leakage_score,
                        "rewrites": rewrite_count,
                        "reason": leakage_reason[:255],
                        "strength": hint_strength[:32],
                        "intent": pedagogical_intent[:64],
                        "status": hint_safety_status[:64],
                        "time": ts,
                    },
                )
            except Exception:
                conn.execute(
                    text(
                        "INSERT INTO interaction_logs (question_id, student_id, user_query, ai_response, is_leaking_answer, created_at) VALUES (:qid, :sid, :qry, :rsp, :leak, :time)"
                    ),
                    {
                        "qid": qid,
                        "sid": st.session_state.current_user,
                        "qry": qry,
                        "rsp": rsp,
                        "leak": leak,
                        "time": ts,
                    },
                )
            conn.commit()
    except Exception as e:
        logging.error(f"record_learning_interaction error: {e}")


def init_session_state():
    defaults = {
        "logged_in": False,
        "current_user": None,
        "user_role": "student",
        "page_mode": "home",
        "quiz_queue": [],
        "current_question_index": 0,
        "user_answers": {},
        "assessment_results": [],
        "review_question_index": None,
        "chat_histories": {},
        "session_count": 0,
        "study_session_id": None,
        "current_course": None,
        "is_grading": False,
        "grading_started": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def restore_user_learning_state(username: str):
    engine = get_database_engine()
    with engine.connect() as conn:
        u_res = conn.execute(text("SELECT current_quiz_ids FROM users WHERE username = :u"), {"u": username}).fetchone()
        if u_res and u_res[0]:
            q_ids = [int(i) for i in u_res[0].split(",") if i.strip()]
            if q_ids:
                db_ids = [i - 1000 for i in q_ids]
                res = fetch_custom_question_rows(conn, db_ids)
                fetched_qs = [question_row_to_dict(r) for r in res]
                q_map = {q["id"]: q for q in fetched_qs}
                st.session_state.quiz_queue = [q_map[qid] for qid in q_ids if qid in q_map]
                if st.session_state.quiz_queue:
                    st.session_state.current_course = st.session_state.quiz_queue[0].get("category", "继续测验")
                st.session_state.page_mode = "quiz"

        logs = conn.execute(
            text("SELECT question_id, user_query, ai_response FROM interaction_logs WHERE student_id = :u"),
            {"u": username},
        ).fetchall()
        for row in logs:
            qid, qry, rsp = row
            if qid not in st.session_state.chat_histories:
                st.session_state.chat_histories[qid] = []
            if "【辅导】" in qry:
                st.session_state.chat_histories[qid].append({"role": "user", "content": _clean_restored_tutoring_query(qry)})
                st.session_state.chat_histories[qid].append({"role": "assistant", "content": rsp})


def start_course_assessment_session(course_name: str):
    engine = get_database_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, category, content, answer, solution FROM custom_questions WHERE category = :c"),
            {"c": course_name},
        ).fetchall()
        quiz_size = max(1, AppConfig.QUIZ_SIZE)
        selected_rows = random.sample(rows, min(quiz_size, len(rows))) if rows else []
        course_questions = [question_row_to_dict(r) for r in selected_rows]

    if not course_questions:
        st.toast("题库内目前无该课程对应题目", icon="⚠️")
        return

    q_ids = ",".join([str(q["id"]) for q in course_questions])
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE users SET current_quiz_ids = :ids WHERE username = :u"),
            {"ids": q_ids, "u": st.session_state.current_user},
        )
        ts = now_shanghai()
        res_insert = conn.execute(
            text("INSERT INTO study_sessions (username, course_name, start_time) VALUES (:u, :c, :t)"),
            {"u": st.session_state.current_user, "c": course_name, "t": ts},
        )
        st.session_state.study_session_id = res_insert.lastrowid
        conn.commit()

    st.session_state.current_course = course_name
    st.session_state.quiz_queue = course_questions
    st.session_state.user_answers = {i: "" for i in range(len(course_questions))}
    st.session_state.current_question_index = 0
    st.session_state.assessment_results = []
    st.session_state.review_question_index = None
    st.session_state.chat_histories = {}
    st.session_state.is_grading = False
    st.session_state.grading_started = False
    st.session_state.page_mode = "quiz"
    st.rerun()


def submit_answers_and_run_assessment():
    st.session_state.assessment_results = []
    results = asyncio.run(batch_assess(st.session_state.quiz_queue, st.session_state.user_answers))

    for i, (q, is_ok) in enumerate(zip(st.session_state.quiz_queue, results)):
        ans = st.session_state.user_answers.get(i, "未作答")
        st.session_state.assessment_results.append({"question_data": q, "user_answer": ans, "is_correct": is_ok})
        record_learning_interaction(q["id"], f"【答案提交】{ans}", "正确" if is_ok else "错误")

    if st.session_state.study_session_id:
        engine = get_database_engine()
        with engine.connect() as conn:
            ts = now_shanghai()
            conn.execute(
                text(
                    "UPDATE study_sessions SET end_time = :t, duration_seconds = TIMESTAMPDIFF(SECOND, start_time, :t) WHERE id = :id"
                ),
                {"t": ts, "id": st.session_state.study_session_id},
            )
            conn.execute(
                text("UPDATE users SET current_quiz_ids = NULL WHERE username = :u"),
                {"u": st.session_state.current_user},
            )
            conn.commit()

    st.session_state.session_count += 1
    st.session_state.is_grading = False
    st.session_state.grading_started = False
    st.session_state.page_mode = "results"
    st.rerun()
