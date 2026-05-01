import pandas as pd

from app_constants import (
    InteractionMarker,
    PageMode,
    UserRole,
    format_answer_submission,
    format_tutoring_query,
)
from course_repository import BASE_COURSES, merge_course_catalog
from experiment_analytics_service import (
    build_experiment_export_dataframe,
    build_experiment_markdown_report,
    summarize_hint_experiment,
)
from hint_text_utils import format_math, parse_json_object
from interaction_repository import build_interaction_payload
from leakage_detection_service import heuristic_leakage_check
from question_repository import public_ids_to_database_ids
from session_keys import SessionKey, composer_input, hint_safety_status, quick_help_button
from session_state_manager import (
    complete_assessment_session,
    init_session_state,
    reset_login_session,
    set_authenticated_user,
    start_quiz_session,
)


def test_format_math_normalizes_latex_delimiters():
    assert format_math(r"\( x^2 \)") == "$x^2$"
    assert format_math(r"\[ x^2 \]") == "$$x^2$$"


def test_parse_json_object_accepts_fenced_json():
    raw = """```json
{"is_leaking": false, "score": 0}
```"""
    assert parse_json_object(raw) == {"is_leaking": False, "score": 0}


def test_heuristic_leakage_check_detects_choice_answer_leakage():
    result = heuristic_leakage_check("A", "这道题的正确选项是 A。")
    assert result["is_leaking"] is True
    assert result["score"] == 3


def test_heuristic_leakage_check_allows_non_answer_hint():
    result = heuristic_leakage_check("A", "先判断函数在分段点两侧的极限。")
    assert result["is_leaking"] is False
    assert result["score"] == 0


def test_experiment_summary_and_export_are_stable():
    df = pd.DataFrame(
        [
            {
                "id": 1,
                "student_id": "s001",
                "question_id": 1001,
                "course_name": "高等数学",
                "hint_strength": "中提示",
                "pedagogical_intent": "错因诊断",
                "hint_safety_status": "泄露检测通过",
                "is_leaking_answer": 0,
                "leakage_score": 0,
                "rewrite_count": 0,
                "leakage_reason": "未发现泄露",
                "student_request": "检查错误",
                "ai_response": "先回到定义。",
                "created_at": pd.Timestamp("2026-05-01 09:00:00"),
            },
            {
                "id": 2,
                "student_id": "s002",
                "question_id": 1002,
                "course_name": "线性代数",
                "hint_strength": "强提示",
                "pedagogical_intent": "下一步引导",
                "hint_safety_status": "已自动重写",
                "is_leaking_answer": 0,
                "leakage_score": 2,
                "rewrite_count": 1,
                "leakage_reason": "候选提示包含关键中间结论",
                "student_request": "提示下一步",
                "ai_response": "先列出矩阵的基本关系。",
                "created_at": pd.Timestamp("2026-05-01 09:05:00"),
            },
        ]
    )

    summary = summarize_hint_experiment(df)
    assert summary["total_hints"] == 2
    assert summary["final_leak_rate"] == 0.0
    assert summary["rewrite_rate"] == 50.0
    assert summary["avg_leakage_score"] == 1.0

    export_df = build_experiment_export_dataframe(df)
    assert "提示强度" in export_df.columns
    assert "教学意图" in export_df.columns

    report = build_experiment_markdown_report(df)
    assert "受控解题提示生成实验数据报告" in report
    assert "按提示强度统计" in report


def test_session_state_manager_initializes_and_resets_state():
    state = {}
    init_session_state(state)

    assert state[SessionKey.LOGGED_IN] is False
    assert state[SessionKey.PAGE_MODE] == PageMode.HOME
    assert state[SessionKey.QUIZ_QUEUE] == []

    set_authenticated_user("student001", UserRole.STUDENT, state)
    assert state[SessionKey.LOGGED_IN] is True
    assert state[SessionKey.CURRENT_USER] == "student001"

    reset_login_session(state)
    assert state[SessionKey.LOGGED_IN] is False
    assert state[SessionKey.CURRENT_USER] is None
    assert state[SessionKey.PAGE_MODE] == PageMode.HOME


def test_start_quiz_session_clears_transient_learning_state():
    state = {
        "chat_histories": {1001: [{"role": "user", "content": "旧问题"}]},
        "assessment_results": [{"old": True}],
        "review_question_index": 2,
        "is_grading": True,
        "grading_started": True,
    }
    questions = [{"id": 1001, "category": "高等数学", "content": "题目"}]

    start_quiz_session("高等数学", questions, 9, state)

    assert state[SessionKey.CURRENT_COURSE] == "高等数学"
    assert state[SessionKey.QUIZ_QUEUE] == questions
    assert state[SessionKey.USER_ANSWERS] == {0: ""}
    assert state[SessionKey.CHAT_HISTORIES] == {}
    assert state[SessionKey.ASSESSMENT_RESULTS] == []
    assert state[SessionKey.PAGE_MODE] == PageMode.QUIZ


def test_complete_assessment_session_moves_to_results():
    state = {"session_count": 3, "is_grading": True, "grading_started": True}

    complete_assessment_session(state)

    assert state[SessionKey.SESSION_COUNT] == 4
    assert state[SessionKey.IS_GRADING] is False
    assert state[SessionKey.GRADING_STARTED] is False
    assert state[SessionKey.PAGE_MODE] == PageMode.RESULTS


def test_public_question_id_mapping_is_stable():
    assert public_ids_to_database_ids([1001, 1005, 999]) == [1, 5]


def test_interaction_payload_truncates_observability_fields():
    payload = build_interaction_payload(
        question_id=1001,
        student_id="student001",
        user_query="【辅导】请提示下一步",
        ai_response="先回到定义。",
        leakage_reason="x" * 300,
        hint_strength="中提示" * 20,
        pedagogical_intent="错因诊断" * 20,
        hint_safety_status="泄露检测通过" * 20,
    )

    assert payload["qid"] == 1001
    assert payload["sid"] == "student001"
    assert len(payload["reason"]) == 255
    assert len(payload["strength"]) == 32
    assert len(payload["intent"]) == 64
    assert len(payload["status"]) == 64


def test_dynamic_session_key_builders_are_stable():
    assert composer_input(1001) == "composer_input_1001"
    assert hint_safety_status(1001) == "hint_safety_status_1001"
    assert quick_help_button(1001, 2) == "quick_help_1001_2"


def test_interaction_marker_formatters_are_stable():
    assert format_answer_submission("A") == f"{InteractionMarker.ANSWER_SUBMISSION}A"
    assert format_tutoring_query("中提示", "请提示下一步") == "【辅导】【提示强度：中提示】请提示下一步"


def test_course_catalog_merge_deduplicates_base_courses():
    custom_courses = [
        ("高等数学", "重复课程不应覆盖基础描述"),
        ("离散数学", "集合、图论与逻辑推理。"),
    ]

    merged = merge_course_catalog(BASE_COURSES, custom_courses)

    assert [name for name, _ in merged].count("高等数学") == 1
    assert ("离散数学", "集合、图论与逻辑推理。") in merged
