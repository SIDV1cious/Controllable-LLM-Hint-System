from __future__ import annotations

import asyncio
import random
import re

import streamlit as st
from werkzeug.security import generate_password_hash

from app_constants import ChatRole, InteractionMarker, format_answer_submission
from app_errors import log_exception
from hint_system_core import AppConfig, batch_assess, now_shanghai, verify_password
from interaction_repository import (
    build_interaction_payload,
    clear_student_interaction_log_cache,
    fetch_student_interaction_logs,
    insert_interaction_log,
)
from question_repository import fetch_questions_by_course
from session_keys import SessionKey
from session_state_manager import (
    append_chat_message,
    complete_assessment_session,
    set_assessment_results,
    start_quiz_session,
)
from student_report_repository import clear_student_report_cache
from study_session_repository import close_study_session, create_study_session
from ui_texts import EMPTY_COURSE_QUESTION_WARNING
from user_repository import (
    clear_user_current_quiz_ids,
    create_student_user,
    fetch_user_auth_record,
    record_login_log,
    save_user_current_quiz_ids,
    user_exists,
)

HINT_STRENGTH_MARK_PATTERN = re.compile(
    rf"{re.escape(InteractionMarker.HINT_STRENGTH_PREFIX)}[^{InteractionMarker.HINT_STRENGTH_SUFFIX}]+"
    rf"{re.escape(InteractionMarker.HINT_STRENGTH_SUFFIX)}"
)


def _clean_restored_tutoring_query(query: str) -> str:
    cleaned = str(query or "").replace(InteractionMarker.TUTORING, "")
    cleaned = HINT_STRENGTH_MARK_PATTERN.sub("", cleaned)
    return cleaned.strip()


def authenticate_learning_user(username: str, password: str):
    record = fetch_user_auth_record(username)
    if record and verify_password(record[0], password):
        return True, record[1]
    return False, None


def register_learning_user(username: str, password: str) -> bool:
    if user_exists(username):
        return False
    create_student_user(username, generate_password_hash(password))
    return True


def record_login_event(username: str) -> None:
    try:
        record_login_log(username)
    except Exception as exc:
        log_exception("record_login_event error", exc)


def clear_current_quiz_for_user(username: str) -> None:
    clear_user_current_quiz_ids(username)


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
) -> None:
    try:
        payload = build_interaction_payload(
            question_id=qid,
            student_id=st.session_state[SessionKey.CURRENT_USER],
            user_query=qry,
            ai_response=rsp,
            is_leaking_answer=leak,
            leakage_score=leakage_score,
            rewrite_count=rewrite_count,
            leakage_reason=leakage_reason,
            hint_strength=hint_strength,
            pedagogical_intent=pedagogical_intent,
            hint_safety_status=hint_safety_status,
        )
        insert_interaction_log(payload)
        clear_student_interaction_log_cache()
        clear_student_report_cache()
    except Exception as exc:
        log_exception("record_learning_interaction error", exc)


def restore_user_learning_state(username: str) -> None:
    try:
        clear_user_current_quiz_ids(username)

        for qid, query, response in fetch_student_interaction_logs(username):
            if InteractionMarker.TUTORING not in str(query or ""):
                continue
            append_chat_message(qid, ChatRole.USER, _clean_restored_tutoring_query(query))
            append_chat_message(qid, ChatRole.ASSISTANT, response)
    except Exception as exc:
        log_exception("restore_user_learning_state error", exc)


def start_course_assessment_session(course_name: str) -> bool:
    all_questions = fetch_questions_by_course(course_name)
    quiz_size = max(1, AppConfig.QUIZ_SIZE)
    course_questions = random.sample(all_questions, min(quiz_size, len(all_questions))) if all_questions else []

    if not course_questions:
        st.toast(EMPTY_COURSE_QUESTION_WARNING, icon="⚠️")
        return False

    save_user_current_quiz_ids(
        st.session_state[SessionKey.CURRENT_USER],
        [question["id"] for question in course_questions],
    )
    study_session_id = create_study_session(
        st.session_state[SessionKey.CURRENT_USER],
        course_name,
        now_shanghai(),
    )
    start_quiz_session(course_name, course_questions, study_session_id)
    st.rerun()
    return True


def submit_answers_and_run_assessment() -> None:
    assessment_items = []
    quiz_queue = st.session_state[SessionKey.QUIZ_QUEUE]
    user_answers = st.session_state[SessionKey.USER_ANSWERS]
    grading_results = asyncio.run(batch_assess(quiz_queue, user_answers))

    for index, (question, is_correct) in enumerate(zip(quiz_queue, grading_results)):
        user_answer = user_answers.get(index, "未作答")
        assessment_items.append(
            {
                "question_data": question,
                "user_answer": user_answer,
                "is_correct": is_correct,
            }
        )
        record_learning_interaction(
            question["id"],
            format_answer_submission(user_answer),
            "正确" if is_correct else "错误",
        )

    set_assessment_results(assessment_items)

    if st.session_state[SessionKey.STUDY_SESSION_ID]:
        close_study_session(st.session_state[SessionKey.STUDY_SESSION_ID], now_shanghai())
        clear_user_current_quiz_ids(st.session_state[SessionKey.CURRENT_USER])

    complete_assessment_session()
    st.rerun()
