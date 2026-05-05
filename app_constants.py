"""Project-wide constants for the controllable hint generation system."""

APP_TITLE = "基于LLM的可控解题提示生成系统"
DEFAULT_RESTORED_COURSE_NAME = "继续测验"


class UserRole:
    ADMIN = "admin"
    STUDENT = "student"


class PageMode:
    ADMIN = "admin"
    HOME = "home"
    QUIZ = "quiz"
    GRADING = "grading"
    RESULTS = "results"
    REPORT = "report"
    TRANSITION = "transition"


class RouteAction:
    START_QUIZ = "start_quiz"
    OPEN_REPORT = "open_report"
    OPEN_ADMIN_DASHBOARD = "open_admin_dashboard"
    RETURN_HOME = "return_home"


class ChatRole:
    USER = "user"
    ASSISTANT = "assistant"


class InteractionMarker:
    TUTORING = "【辅导】"
    ANSWER_SUBMISSION = "【答案提交】"
    HINT_STRENGTH_PREFIX = "【提示强度："
    HINT_STRENGTH_SUFFIX = "】"


def should_render_sidebar_for_page(page_mode: str, user_role: str) -> bool:
    if page_mode == PageMode.ADMIN and user_role == UserRole.ADMIN:
        return True
    return user_role == UserRole.STUDENT and page_mode in {PageMode.HOME, PageMode.REPORT}


def format_tutoring_query(hint_strength: str, query: str) -> str:
    return (
        f"{InteractionMarker.TUTORING}"
        f"{InteractionMarker.HINT_STRENGTH_PREFIX}{hint_strength}{InteractionMarker.HINT_STRENGTH_SUFFIX}"
        f"{query}"
    )


def format_answer_submission(answer: str) -> str:
    return f"{InteractionMarker.ANSWER_SUBMISSION}{answer}"
