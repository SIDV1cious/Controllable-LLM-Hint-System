from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

import streamlit as st


SESSION_DEFAULTS: dict[str, Any] = {
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


def _state(target: MutableMapping[str, Any] | None = None) -> MutableMapping[str, Any]:
    return target if target is not None else st.session_state


def init_session_state(target: MutableMapping[str, Any] | None = None) -> None:
    state = _state(target)
    for key, value in SESSION_DEFAULTS.items():
        if key not in state:
            state[key] = value.copy() if isinstance(value, (dict, list)) else value


def set_authenticated_user(
    username: str,
    role: str,
    target: MutableMapping[str, Any] | None = None,
) -> None:
    state = _state(target)
    state["logged_in"] = True
    state["current_user"] = username
    state["user_role"] = role
    state["page_mode"] = "admin" if role == "admin" else "home"


def navigate_to(page_mode: str, target: MutableMapping[str, Any] | None = None) -> None:
    _state(target)["page_mode"] = page_mode


def reset_login_session(target: MutableMapping[str, Any] | None = None) -> None:
    state = _state(target)
    for key in list(state.keys()):
        del state[key]
    init_session_state(state)


def start_quiz_session(
    course_name: str,
    questions: list[dict[str, Any]],
    study_session_id: int | None,
    target: MutableMapping[str, Any] | None = None,
) -> None:
    state = _state(target)
    state["current_course"] = course_name
    state["quiz_queue"] = questions
    state["user_answers"] = {i: "" for i in range(len(questions))}
    state["current_question_index"] = 0
    state["assessment_results"] = []
    state["review_question_index"] = None
    state["chat_histories"] = {}
    state["study_session_id"] = study_session_id
    state["is_grading"] = False
    state["grading_started"] = False
    state["page_mode"] = "quiz"


def restore_quiz_session(
    questions: list[dict[str, Any]],
    target: MutableMapping[str, Any] | None = None,
) -> None:
    state = _state(target)
    state["quiz_queue"] = questions
    if questions:
        state["current_course"] = questions[0].get("category", "继续测验")
    state["page_mode"] = "quiz"


def append_chat_message(
    question_id: int,
    role: str,
    content: str,
    target: MutableMapping[str, Any] | None = None,
) -> None:
    state = _state(target)
    state.setdefault("chat_histories", {}).setdefault(question_id, []).append(
        {"role": role, "content": content}
    )


def set_assessment_results(
    results: list[dict[str, Any]],
    target: MutableMapping[str, Any] | None = None,
) -> None:
    _state(target)["assessment_results"] = results


def complete_assessment_session(target: MutableMapping[str, Any] | None = None) -> None:
    state = _state(target)
    state["session_count"] = int(state.get("session_count", 0)) + 1
    state["is_grading"] = False
    state["grading_started"] = False
    state["page_mode"] = "results"
