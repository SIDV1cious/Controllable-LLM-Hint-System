from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from app_constants import DEFAULT_RESTORED_COURSE_NAME, PageMode, UserRole
from session_keys import SessionKey

CURRENT_APP_STATE_VERSION = 2

SESSION_DEFAULTS: dict[str, Any] = {
    SessionKey.APP_STATE_VERSION: CURRENT_APP_STATE_VERSION,
    SessionKey.LOGGED_IN: False,
    SessionKey.CURRENT_USER: None,
    SessionKey.USER_ROLE: UserRole.STUDENT,
    SessionKey.PAGE_MODE: PageMode.HOME,
    SessionKey.QUIZ_QUEUE: [],
    SessionKey.CURRENT_QUESTION_INDEX: 0,
    SessionKey.USER_ANSWERS: {},
    SessionKey.ASSESSMENT_RESULTS: [],
    SessionKey.REVIEW_QUESTION_INDEX: None,
    SessionKey.CHAT_HISTORIES: {},
    SessionKey.SESSION_COUNT: 0,
    SessionKey.STUDY_SESSION_ID: None,
    SessionKey.CURRENT_COURSE: None,
    SessionKey.IS_GRADING: False,
    SessionKey.GRADING_STARTED: False,
}

VALID_PAGE_MODES = {
    PageMode.ADMIN,
    PageMode.HOME,
    PageMode.QUIZ,
    PageMode.GRADING,
    PageMode.RESULTS,
    PageMode.REPORT,
}
STUDENT_PAGE_MODES = {PageMode.HOME, PageMode.QUIZ, PageMode.GRADING, PageMode.RESULTS, PageMode.REPORT}


def _state(target: MutableMapping[str, Any] | None = None) -> MutableMapping[str, Any]:
    return target if target is not None else st.session_state


def init_session_state(target: MutableMapping[str, Any] | None = None) -> None:
    state = _state(target)
    for key, value in SESSION_DEFAULTS.items():
        if key not in state:
            state[key] = value.copy() if isinstance(value, (dict, list)) else value


def repair_session_state(target: MutableMapping[str, Any] | None = None) -> bool:
    state = _state(target)
    previous_version = state.get(SessionKey.APP_STATE_VERSION)
    init_session_state(state)
    changed = False

    if previous_version != CURRENT_APP_STATE_VERSION:
        state[SessionKey.APP_STATE_VERSION] = CURRENT_APP_STATE_VERSION
        if state.get(SessionKey.LOGGED_IN) and state.get(SessionKey.PAGE_MODE) in {PageMode.QUIZ, PageMode.GRADING}:
            clear_active_assessment_state(state)
            state[SessionKey.PAGE_MODE] = PageMode.HOME
            changed = True

    if not state.get(SessionKey.LOGGED_IN):
        if state.get(SessionKey.CURRENT_USER) is not None:
            state[SessionKey.CURRENT_USER] = None
            changed = True
        if state.get(SessionKey.USER_ROLE) not in {UserRole.ADMIN, UserRole.STUDENT}:
            state[SessionKey.USER_ROLE] = UserRole.STUDENT
            changed = True
        if state.get(SessionKey.PAGE_MODE) != PageMode.HOME:
            state[SessionKey.PAGE_MODE] = PageMode.HOME
            changed = True
        return changed

    if not state.get(SessionKey.CURRENT_USER):
        reset_login_session(state)
        return True

    role = state.get(SessionKey.USER_ROLE)
    if role not in {UserRole.ADMIN, UserRole.STUDENT}:
        role = UserRole.STUDENT
        state[SessionKey.USER_ROLE] = role
        changed = True

    page_mode = state.get(SessionKey.PAGE_MODE)
    if page_mode not in VALID_PAGE_MODES:
        page_mode = PageMode.ADMIN if role == UserRole.ADMIN else PageMode.HOME
        state[SessionKey.PAGE_MODE] = page_mode
        changed = True

    if role == UserRole.ADMIN:
        if page_mode != PageMode.ADMIN:
            state[SessionKey.PAGE_MODE] = PageMode.ADMIN
            changed = True
        return changed

    if page_mode not in STUDENT_PAGE_MODES:
        page_mode = PageMode.HOME
        state[SessionKey.PAGE_MODE] = page_mode
        changed = True

    if page_mode in {PageMode.QUIZ, PageMode.GRADING} and not state.get(SessionKey.QUIZ_QUEUE):
        state[SessionKey.PAGE_MODE] = PageMode.HOME
        state[SessionKey.IS_GRADING] = False
        state[SessionKey.GRADING_STARTED] = False
        changed = True

    if page_mode == PageMode.RESULTS and not state.get(SessionKey.ASSESSMENT_RESULTS):
        state[SessionKey.PAGE_MODE] = PageMode.HOME
        changed = True

    return changed


def set_authenticated_user(
    username: str,
    role: str,
    target: MutableMapping[str, Any] | None = None,
) -> None:
    state = _state(target)
    state[SessionKey.LOGGED_IN] = True
    state[SessionKey.CURRENT_USER] = username
    state[SessionKey.USER_ROLE] = role
    state[SessionKey.PAGE_MODE] = PageMode.ADMIN if role == UserRole.ADMIN else PageMode.HOME


def navigate_to(page_mode: str, target: MutableMapping[str, Any] | None = None) -> None:
    _state(target)[SessionKey.PAGE_MODE] = page_mode


def clear_active_assessment_state(target: MutableMapping[str, Any] | None = None) -> None:
    state = _state(target)
    state[SessionKey.QUIZ_QUEUE] = []
    state[SessionKey.CURRENT_QUESTION_INDEX] = 0
    state[SessionKey.USER_ANSWERS] = {}
    state[SessionKey.ASSESSMENT_RESULTS] = []
    state[SessionKey.REVIEW_QUESTION_INDEX] = None
    state[SessionKey.CHAT_HISTORIES] = {}
    state[SessionKey.STUDY_SESSION_ID] = None
    state[SessionKey.CURRENT_COURSE] = None
    state[SessionKey.IS_GRADING] = False
    state[SessionKey.GRADING_STARTED] = False


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
    state[SessionKey.CURRENT_COURSE] = course_name
    state[SessionKey.QUIZ_QUEUE] = questions
    state[SessionKey.USER_ANSWERS] = {i: "" for i in range(len(questions))}
    state[SessionKey.CURRENT_QUESTION_INDEX] = 0
    state[SessionKey.ASSESSMENT_RESULTS] = []
    state[SessionKey.REVIEW_QUESTION_INDEX] = None
    state[SessionKey.CHAT_HISTORIES] = {}
    state[SessionKey.STUDY_SESSION_ID] = study_session_id
    state[SessionKey.IS_GRADING] = False
    state[SessionKey.GRADING_STARTED] = False
    state[SessionKey.PAGE_MODE] = PageMode.QUIZ


def restore_quiz_session(
    questions: list[dict[str, Any]],
    target: MutableMapping[str, Any] | None = None,
) -> None:
    state = _state(target)
    state[SessionKey.QUIZ_QUEUE] = questions
    if questions:
        state[SessionKey.CURRENT_COURSE] = questions[0].get("category", DEFAULT_RESTORED_COURSE_NAME)
    state[SessionKey.PAGE_MODE] = PageMode.QUIZ


def append_chat_message(
    question_id: int,
    role: str,
    content: str,
    target: MutableMapping[str, Any] | None = None,
) -> None:
    state = _state(target)
    state.setdefault(SessionKey.CHAT_HISTORIES, {}).setdefault(question_id, []).append(
        {"role": role, "content": content}
    )


def set_assessment_results(
    results: list[dict[str, Any]],
    target: MutableMapping[str, Any] | None = None,
) -> None:
    _state(target)[SessionKey.ASSESSMENT_RESULTS] = results


def complete_assessment_session(target: MutableMapping[str, Any] | None = None) -> None:
    state = _state(target)
    state[SessionKey.SESSION_COUNT] = int(state.get(SessionKey.SESSION_COUNT, 0)) + 1
    state[SessionKey.IS_GRADING] = False
    state[SessionKey.GRADING_STARTED] = False
    state[SessionKey.PAGE_MODE] = PageMode.RESULTS
