"""Centralized Streamlit session-state keys and dynamic key builders."""


class SessionKey:
    APP_STATE_VERSION = "app_state_version"
    LOGGED_IN = "logged_in"
    CURRENT_USER = "current_user"
    USER_ROLE = "user_role"
    PAGE_MODE = "page_mode"
    QUIZ_QUEUE = "quiz_queue"
    CURRENT_QUESTION_INDEX = "current_question_index"
    USER_ANSWERS = "user_answers"
    ASSESSMENT_RESULTS = "assessment_results"
    REVIEW_QUESTION_INDEX = "review_question_index"
    CHAT_HISTORIES = "chat_histories"
    SESSION_COUNT = "session_count"
    STUDY_SESSION_ID = "study_session_id"
    CURRENT_COURSE = "current_course"
    IS_GRADING = "is_grading"
    GRADING_STARTED = "grading_started"
    ROUTE_LOADING_MESSAGE = "route_loading_message"
    ROUTE_LOADING_ACTIVE = "route_loading_active"
    ROUTE_LOADING_PASSES = "route_loading_passes"


def answer_input(index: int) -> str:
    return f"ans_{index}"


def navigation_button(index: int) -> str:
    return f"nav_btn_{index}"


def review_button(index: int) -> str:
    return f"n_{index}"


def hint_strength(question_id: int) -> str:
    return f"hint_strength_{question_id}"


def hint_safety_status(question_id: int) -> str:
    return f"hint_safety_status_{question_id}"


def pending_pedagogical_intent(question_id: int) -> str:
    return f"pending_pedagogical_intent_{question_id}"


def composer_input(question_id: int) -> str:
    return f"composer_input_{question_id}"


def composer_reset(question_id: int) -> str:
    return f"composer_reset_{question_id}"


def math_widget_version(question_id: int) -> str:
    return f"math_widget_version_{question_id}"


def quick_help_button(question_id: int, quick_index: int) -> str:
    return f"quick_help_{question_id}_{quick_index}"


def send_help_button(question_id: int) -> str:
    return f"send_help_{question_id}"


def math_widget(question_id: int, version: int) -> str:
    return f"react_math_{question_id}_{version}"
