import json

import pandas as pd

import controlled_generation_service as controlled_generation
from admin_content_repository import (
    build_course_name_list,
    make_question_delete_label,
    make_question_edit_label,
)
from admin_observability_repository import (
    build_course_accuracy_dataframe,
    build_leakage_score_distribution,
    summarize_hint_leakage_records,
)
from app_constants import (
    InteractionMarker,
    PageMode,
    RouteAction,
    UserRole,
    format_answer_submission,
    format_tutoring_query,
    should_render_sidebar_for_page,
)
from app_errors import friendly_error
from assessment_logic import (
    assess_with_reference_answer,
    build_assessment_prompt,
    normalize_choice_answer,
)
from course_repository import BASE_COURSES, merge_course_catalog
from database_service import iter_leakage_observability_ddl
from experiment_analytics_service import (
    build_experiment_export_dataframe,
    build_experiment_markdown_report,
    build_grouped_experiment_summary,
    ensure_experiment_observability_columns,
    summarize_hint_experiment,
)
from hint_policy import (
    FALLBACK_SAFE_HINT,
    MAX_HINT_REWRITE_ATTEMPTS,
    get_hint_strength_policy,
    is_high_risk_leakage_score,
    normalize_hint_strength,
)
from hint_request_observability import build_hint_request_observability, count_formula_fragments
from hint_text_utils import format_math, parse_json_object
from interaction_dataset_export_service import (
    DatasetExportFilters,
    anonymize_student_id,
    build_csv_bytes,
    build_dataset_export_dataframe,
    build_dataset_markdown,
    build_jsonl_bytes,
    clamp_export_limit,
    clean_tutoring_prompt,
)
from interaction_repository import build_interaction_payload
from leakage_detection_service import heuristic_leakage_check
from llm_gateway import build_llm_call_metadata
from prompt_config_repository import SYSTEM_INSTRUCTION_KEY
from question_repository import public_ids_to_database_ids
from session_keys import SessionKey, composer_empty_feedback, composer_input, hint_safety_status, quick_help_button
from session_state_manager import (
    begin_route_transition,
    clear_active_assessment_state,
    clear_route_transition,
    complete_assessment_session,
    init_session_state,
    repair_session_state,
    reset_login_session,
    set_authenticated_user,
    start_quiz_session,
)
from student_report_service import calculate_learning_summary, extract_wrong_question_ids


def test_format_math_normalizes_latex_delimiters():
    assert format_math(r"\( x^2 \)") == "$x^2$"
    assert format_math(r"\[ x^2 \]") == "$$x^2$$"


def test_choice_answer_normalization_accepts_common_formats():
    assert normalize_choice_answer("A") == "A"
    assert normalize_choice_answer("a.") == "A"
    assert normalize_choice_answer("（B）") == "B"
    assert normalize_choice_answer("答案：C") == "C"
    assert normalize_choice_answer("选择 D") == "D"
    assert normalize_choice_answer("alpha") is None
    assert normalize_choice_answer("x > 0") is None


def test_sidebar_policy_keeps_immersive_pages_clean():
    assert should_render_sidebar_for_page(PageMode.HOME, UserRole.STUDENT) is True
    assert should_render_sidebar_for_page(PageMode.REPORT, UserRole.STUDENT) is True
    assert should_render_sidebar_for_page(PageMode.ADMIN, UserRole.ADMIN) is True
    assert should_render_sidebar_for_page(PageMode.QUIZ, UserRole.STUDENT) is False
    assert should_render_sidebar_for_page(PageMode.GRADING, UserRole.STUDENT) is False
    assert should_render_sidebar_for_page(PageMode.RESULTS, UserRole.STUDENT) is False
    assert should_render_sidebar_for_page(PageMode.TRANSITION, UserRole.STUDENT) is False
    assert should_render_sidebar_for_page(PageMode.ADMIN, UserRole.STUDENT) is False


def test_reference_answer_assessment_short_circuits_choice_questions():
    question = {"content": "选择正确选项", "answer": "B", "solution": "略"}

    assert assess_with_reference_answer(question, "答案是B") is True
    assert assess_with_reference_answer(question, "A") is False
    assert assess_with_reference_answer({"content": "计算题", "answer": r"x^2", "solution": ""}, r"x^2") is None


def test_assessment_prompt_includes_reference_when_available():
    prompt = build_assessment_prompt(
        {"content": "题目内容", "answer": "A", "solution": "解析内容"},
        "B",
    )

    assert "标准答案：A" in prompt
    assert "标准解析：解析内容" in prompt
    assert "学生答案：B" in prompt


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


def test_generate_controlled_hint_keeps_request_plan_and_system_prompt_order(monkeypatch):
    observed = {}

    monkeypatch.setattr(controlled_generation, "get_dynamic_system_prompt", lambda: "system-prompt")
    monkeypatch.setattr(
        controlled_generation,
        "build_hint_plan",
        lambda question_data, student_answer, is_correct, student_request, hint_strength: "private-plan",
    )

    def fake_generate_student_hint(
        question_data,
        student_answer,
        is_correct,
        student_request,
        hint_plan,
        system_prompt,
        hint_strength="中提示",
    ):
        observed.update(
            {
                "student_request": student_request,
                "hint_plan": hint_plan,
                "system_prompt": system_prompt,
                "hint_strength": hint_strength,
            }
        )
        return "先回到定义。"

    monkeypatch.setattr(controlled_generation, "generate_student_hint", fake_generate_student_hint)
    monkeypatch.setattr(
        controlled_generation,
        "evaluate_hint_leakage",
        lambda *args, **kwargs: {"is_leaking": False, "score": 0, "reason": "未发现泄露"},
    )

    result = controlled_generation.generate_controlled_hint(
        {"id": 1, "content": "题目", "answer": "A", "solution": "解析"},
        "B",
        False,
        "请提示下一步",
        hint_strength="中提示",
    )

    assert observed == {
        "student_request": "请提示下一步",
        "hint_plan": "private-plan",
        "system_prompt": "system-prompt",
        "hint_strength": "中提示",
    }
    assert result["generation_status"] == "success"


def test_generate_controlled_hint_returns_safe_fallback_on_generation_error(monkeypatch):
    monkeypatch.setattr(controlled_generation, "get_dynamic_system_prompt", lambda: "system-prompt")
    monkeypatch.setattr(
        controlled_generation,
        "build_hint_plan",
        lambda question_data, student_answer, is_correct, student_request, hint_strength: "private-plan",
    )

    def raise_generation_error(*args, **kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(controlled_generation, "generate_student_hint", raise_generation_error)

    result = controlled_generation.generate_controlled_hint(
        {"id": 1, "content": "题目", "answer": "A", "solution": "解析"},
        "B",
        False,
        "请提示下一步",
    )

    assert result["generation_status"] == "failed"
    assert result["generation_error"] == "RuntimeError"
    assert result["is_leaking"] == 0
    assert "保底启发式提示" in result["leakage_reason"]


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
                "request_char_count": 12,
                "formula_fragment_count": 0,
                "generation_elapsed_ms": 850,
                "rewrite_triggered": 0,
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
                "request_char_count": 18,
                "formula_fragment_count": 2,
                "generation_elapsed_ms": 1250,
                "rewrite_triggered": 1,
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
    assert summary["avg_request_chars"] == 15.0
    assert summary["avg_formula_fragments"] == 1.0
    assert summary["avg_generation_elapsed_ms"] == 1050.0

    export_df = build_experiment_export_dataframe(df)
    assert "提示强度" in export_df.columns
    assert "教学意图" in export_df.columns
    assert "输入长度" in export_df.columns
    assert "公式数量" in export_df.columns
    assert "生成耗时(ms)" in export_df.columns

    report = build_experiment_markdown_report(df)
    assert "受控解题提示生成实验数据报告" in report
    assert "按课程统计" in report
    assert "按提示强度统计" in report
    assert "平均生成耗时" in report


def test_experiment_grouped_summary_supports_course_dimension():
    df = pd.DataFrame(
        [
            {"id": 1, "course_name": "高等数学", "leakage_score": 0, "rewrite_count": 0},
            {"id": 2, "course_name": "高等数学", "leakage_score": 2, "rewrite_count": 1},
            {"id": 3, "course_name": "线性代数", "leakage_score": 1, "rewrite_count": 0},
        ]
    )

    grouped = build_grouped_experiment_summary(df, "course_name")
    course_counts = dict(zip(grouped["course_name"], grouped["提示数量"], strict=False))

    assert course_counts == {"线性代数": 1, "高等数学": 2}


def test_experiment_observability_columns_backfill_legacy_dataframes():
    df = pd.DataFrame([{"id": 1, "leakage_score": 2, "rewrite_count": 1}])

    normalized = ensure_experiment_observability_columns(df)

    assert normalized["request_char_count"].tolist() == [0]
    assert normalized["formula_fragment_count"].tolist() == [0]
    assert normalized["generation_elapsed_ms"].tolist() == [0]
    assert normalized["rewrite_triggered"].tolist() == [0]


def test_hint_request_observability_counts_text_formula_and_latency():
    query = "请提示下一步\n$x^2+1$\n矩阵：\\begin{pmatrix}1&0\\\\0&1\\end{pmatrix}"

    observability = build_hint_request_observability(query, generation_elapsed_ms=1234.6, rewrite_count=1)

    assert count_formula_fragments(query) == 2
    assert observability == {
        "request_char_count": len(query),
        "formula_fragment_count": 2,
        "generation_elapsed_ms": 1235,
        "rewrite_triggered": 1,
    }


def test_hint_policy_defaults_and_risk_threshold_are_stable():
    assert normalize_hint_strength("未知强度") == "中提示"
    assert "完整推导" in get_hint_strength_policy("中提示")
    assert MAX_HINT_REWRITE_ATTEMPTS == 2
    assert FALLBACK_SAFE_HINT.startswith("这道题我们先抓住关键条件")
    assert is_high_risk_leakage_score(2) is True
    assert is_high_risk_leakage_score("bad-score") is False


def test_llm_call_metadata_counts_messages_and_prompt_chars():
    metadata = build_llm_call_metadata(
        [
            {"role": "system", "content": "系统提示"},
            {"role": "user", "content": "用户问题"},
        ],
        temperature=0.3,
        model="deepseek-chat",
    )

    assert metadata == {
        "model": "deepseek-chat",
        "temperature": 0.3,
        "message_count": 2,
        "prompt_chars": 8,
    }


def test_leakage_observability_ddl_is_centralized():
    ddl = iter_leakage_observability_ddl()

    assert len(ddl) == 14
    assert any("leakage_score" in statement for statement in ddl)
    assert any("generation_elapsed_ms" in statement for statement in ddl)
    assert any("generation_status" in statement for statement in ddl)
    assert any("idx_interaction_hint_strength" in statement for statement in ddl)


def test_session_state_manager_initializes_and_resets_state():
    state = {}
    init_session_state(state)

    assert state[SessionKey.LOGGED_IN] is False
    assert state[SessionKey.APP_STATE_VERSION] == 2
    assert state[SessionKey.PAGE_MODE] == PageMode.HOME
    assert state[SessionKey.QUIZ_QUEUE] == []
    assert state[SessionKey.ROUTE_LOADING_ACTION] is None

    set_authenticated_user("student001", UserRole.STUDENT, state)
    assert state[SessionKey.LOGGED_IN] is True
    assert state[SessionKey.CURRENT_USER] == "student001"

    reset_login_session(state)
    assert state[SessionKey.LOGGED_IN] is False
    assert state[SessionKey.CURRENT_USER] is None
    assert state[SessionKey.PAGE_MODE] == PageMode.HOME


def test_session_state_repair_recovers_blank_page_states():
    state = {
        SessionKey.LOGGED_IN: True,
        SessionKey.CURRENT_USER: "student001",
        SessionKey.USER_ROLE: UserRole.STUDENT,
        SessionKey.PAGE_MODE: PageMode.QUIZ,
        SessionKey.QUIZ_QUEUE: [],
        SessionKey.IS_GRADING: True,
        SessionKey.GRADING_STARTED: True,
    }

    assert repair_session_state(state) is True
    assert state[SessionKey.PAGE_MODE] == PageMode.HOME
    assert state[SessionKey.IS_GRADING] is False
    assert state[SessionKey.GRADING_STARTED] is False


def test_route_transition_state_is_explicit_and_clearable():
    state = {}
    init_session_state(state)

    begin_route_transition(
        RouteAction.START_QUIZ,
        "正在加载题目并初始化测验...",
        icon="📚",
        payload={"course_name": "高等数学"},
        target=state,
    )

    assert state[SessionKey.PAGE_MODE] == PageMode.TRANSITION
    assert state[SessionKey.ROUTE_LOADING_ACTION] == RouteAction.START_QUIZ
    assert state[SessionKey.ROUTE_LOADING_ICON] == "📚"
    assert state[SessionKey.ROUTE_LOADING_PAYLOAD] == {"course_name": "高等数学"}

    clear_route_transition(state)

    assert state[SessionKey.ROUTE_LOADING_ACTION] is None
    assert state[SessionKey.ROUTE_LOADING_ACTIVE] is False
    assert state[SessionKey.ROUTE_LOADING_PAYLOAD] == {}


def test_session_state_repair_migrates_legacy_quiz_sessions_to_home():
    state = {
        SessionKey.LOGGED_IN: True,
        SessionKey.CURRENT_USER: "student001",
        SessionKey.USER_ROLE: UserRole.STUDENT,
        SessionKey.PAGE_MODE: PageMode.QUIZ,
        SessionKey.QUIZ_QUEUE: [{"id": 1001}],
        SessionKey.USER_ANSWERS: {0: "A"},
    }

    assert repair_session_state(state) is True
    assert state[SessionKey.APP_STATE_VERSION] == 2
    assert state[SessionKey.PAGE_MODE] == PageMode.HOME
    assert state[SessionKey.QUIZ_QUEUE] == []
    assert state[SessionKey.USER_ANSWERS] == {}


def test_session_state_repair_resets_missing_authenticated_user():
    state = {
        SessionKey.LOGGED_IN: True,
        SessionKey.CURRENT_USER: None,
        SessionKey.USER_ROLE: UserRole.STUDENT,
        SessionKey.PAGE_MODE: "unknown",
    }

    assert repair_session_state(state) is True
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


def test_clear_active_assessment_state_returns_to_clean_lobby_context():
    state = {
        SessionKey.QUIZ_QUEUE: [{"id": 1001}],
        SessionKey.CURRENT_QUESTION_INDEX: 3,
        SessionKey.USER_ANSWERS: {0: "A"},
        SessionKey.ASSESSMENT_RESULTS: [{"is_correct": False}],
        SessionKey.REVIEW_QUESTION_INDEX: 1,
        SessionKey.CHAT_HISTORIES: {1001: [{"role": "user", "content": "提示"}]},
        SessionKey.STUDY_SESSION_ID: 9,
        SessionKey.CURRENT_COURSE: "高等数学",
        SessionKey.IS_GRADING: True,
        SessionKey.GRADING_STARTED: True,
    }

    clear_active_assessment_state(state)

    assert state[SessionKey.QUIZ_QUEUE] == []
    assert state[SessionKey.CURRENT_QUESTION_INDEX] == 0
    assert state[SessionKey.USER_ANSWERS] == {}
    assert state[SessionKey.ASSESSMENT_RESULTS] == []
    assert state[SessionKey.REVIEW_QUESTION_INDEX] is None
    assert state[SessionKey.CHAT_HISTORIES] == {}
    assert state[SessionKey.STUDY_SESSION_ID] is None
    assert state[SessionKey.CURRENT_COURSE] is None
    assert state[SessionKey.IS_GRADING] is False
    assert state[SessionKey.GRADING_STARTED] is False


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
        request_char_count=18,
        formula_fragment_count=2,
        generation_elapsed_ms=1234,
        rewrite_triggered=1,
        generation_status="timeout",
        generation_error="OpenAIError" * 40,
    )

    assert payload["qid"] == 1001
    assert payload["sid"] == "student001"
    assert len(payload["reason"]) == 255
    assert len(payload["strength"]) == 32
    assert len(payload["intent"]) == 64
    assert len(payload["status"]) == 64
    assert payload["request_chars"] == 18
    assert payload["formula_count"] == 2
    assert payload["elapsed_ms"] == 1234
    assert payload["rewrite_flag"] == 1
    assert payload["generation_status"] == "timeout"
    assert len(payload["generation_error"]) == 255


def test_dynamic_session_key_builders_are_stable():
    assert composer_input(1001) == "composer_input_1001"
    assert composer_empty_feedback(1001) == "composer_empty_feedback_1001"
    assert hint_safety_status(1001) == "hint_safety_status_1001"
    assert quick_help_button(1001, 2) == "quick_help_1001_2"


def test_interaction_marker_formatters_are_stable():
    assert format_answer_submission("A") == f"{InteractionMarker.ANSWER_SUBMISSION}A"
    assert format_tutoring_query("中提示", "请提示下一步") == "【辅导】【提示强度：中提示】请提示下一步"


def test_dataset_export_cleans_prompt_and_anonymizes_student_id():
    raw_df = pd.DataFrame(
        [
            {
                "id": 9,
                "student_id": "3021244094",
                "question_id": 1001,
                "course_name": "高等数学",
                "user_query": "【辅导】【提示强度：中提示】请提示下一步",
                "ai_response": "先回到极限定义。",
                "is_leaking_answer": 0,
                "leakage_score": 0,
                "rewrite_count": 0,
                "leakage_reason": "未发现泄露",
                "hint_strength": "",
                "pedagogical_intent": "",
                "hint_safety_status": "",
                "request_char_count": 8,
                "formula_fragment_count": 0,
                "generation_elapsed_ms": 900,
                "rewrite_triggered": 0,
                "generation_status": "",
                "generation_error": "",
                "created_at": pd.Timestamp("2026-05-11 10:30:00"),
            }
        ]
    )

    export_df = build_dataset_export_dataframe(raw_df, include_raw_student_id=False)

    assert clean_tutoring_prompt("【辅导】【提示强度：强提示】检查错误") == "检查错误"
    assert export_df.loc[0, "sample_id"] == "hint-9"
    assert "student_hash" in export_df.columns
    assert "student_id" not in export_df.columns
    assert export_df.loc[0, "student_hash"] == anonymize_student_id("3021244094")
    assert export_df.loc[0, "student_prompt"] == "请提示下一步"
    assert export_df.loc[0, "hint_strength"] == "中提示"
    assert export_df.loc[0, "pedagogical_intent"] == "未记录"
    assert export_df.loc[0, "hint_safety_status"] == "泄露检测通过"
    assert export_df.loc[0, "generation_status"] == "success"


def test_dataset_export_can_include_raw_student_id_when_admin_requests_it():
    raw_df = pd.DataFrame(
        [
            {
                "id": 10,
                "student_id": "s001",
                "question_id": 1002,
                "course_name": "线性代数",
                "user_query": "【辅导】矩阵怎么做",
                "ai_response": "先观察矩阵秩。",
                "rewrite_count": 1,
                "is_leaking_answer": 0,
            }
        ]
    )

    export_df = build_dataset_export_dataframe(raw_df, include_raw_student_id=True)

    assert "student_id" in export_df.columns
    assert "student_hash" not in export_df.columns
    assert export_df.loc[0, "student_id"] == "s001"
    assert export_df.loc[0, "hint_safety_status"] == "已自动重写"


def test_dataset_export_serializers_and_markdown_dictionary_are_stable():
    export_df = pd.DataFrame(
        [
            {
                "sample_id": "hint-1",
                "student_hash": "abc123",
                "student_prompt": "含有 | 和换行\n的提示",
                "model_response": "先拆条件。",
            }
        ]
    )
    filters = DatasetExportFilters(student_id="3021244094", course_name="高等数学")

    csv_bytes = build_csv_bytes(export_df)
    jsonl_bytes = build_jsonl_bytes(export_df)
    markdown = build_dataset_markdown(export_df.columns.tolist(), len(export_df), filters)

    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    assert json.loads(jsonl_bytes.decode("utf-8").strip())["student_prompt"] == "含有 | 和换行\n的提示"
    assert "智能辅导交互数据集说明" in markdown
    assert "`student_hash`" in markdown
    assert "含义" in markdown


def test_dataset_export_limit_is_clamped():
    assert clamp_export_limit(None) == 1000
    assert clamp_export_limit("bad") == 1000
    assert clamp_export_limit(0) == 1000
    assert clamp_export_limit(1) == 1
    assert clamp_export_limit(6000) == 5000


def test_course_catalog_merge_deduplicates_base_courses():
    custom_courses = [
        ("高等数学", "重复课程不应覆盖基础描述"),
        ("离散数学", "集合、图论与逻辑推理。"),
    ]

    merged = merge_course_catalog(BASE_COURSES, custom_courses)

    assert [name for name, _ in merged].count("高等数学") == 1
    assert ("离散数学", "集合、图论与逻辑推理。") in merged


def test_admin_course_name_list_deduplicates_base_names():
    result = build_course_name_list(["高等数学", "线性代数"], ["高等数学", "离散数学"])
    assert result == ["高等数学", "线性代数", "离散数学"]


def test_admin_question_option_labels_are_stable():
    assert make_question_delete_label(7, "高等数学", "极限题") == "[高等数学] 极限题... (内部ID:7)"
    assert (
        make_question_edit_label(8, "线性代数", "矩阵的特征值与特征向量")
        == "[线性代数] (内部ID:8) 矩阵的特征值与特征向量..."
    )


def test_prompt_config_key_is_stable():
    assert SYSTEM_INSTRUCTION_KEY == "system_instruction"


def test_admin_course_accuracy_summary_maps_public_question_ids():
    answer_records = pd.DataFrame(
        [
            {"question_id": 1001, "ai_response": "正确"},
            {"question_id": "1002", "ai_response": "FAIL"},
            {"question_id": "bad-id", "ai_response": "PASS"},
        ]
    )
    question_records = pd.DataFrame(
        [
            {"id": 1, "category": "高等数学"},
            {"id": 2, "category": "线性代数"},
        ]
    )

    result = build_course_accuracy_dataframe(answer_records, question_records)
    accuracy_map = dict(zip(result["course_name"], result["accuracy_percent"], strict=False))

    assert accuracy_map == {"线性代数": 0.0, "高等数学": 100.0}


def test_admin_hint_leakage_summary_and_score_distribution():
    df = pd.DataFrame(
        [
            {"is_leaking_answer": 0, "leakage_score": 0, "rewrite_count": 0},
            {"is_leaking_answer": 1, "leakage_score": 2, "rewrite_count": 1},
            {"is_leaking_answer": 0, "leakage_score": 2, "rewrite_count": 2},
        ]
    )

    summary = summarize_hint_leakage_records(df)
    distribution = build_leakage_score_distribution(df)
    score_counts = dict(zip(distribution["leakage_score"], distribution["count"], strict=False))
    risk_labels = dict(zip(distribution["leakage_score"], distribution["risk_level"], strict=False))

    assert summary == {
        "total_hints": 3,
        "leaked_hints": 1,
        "rewrite_total": 3,
        "leak_rate": 33.3,
    }
    assert score_counts == {0: 1, 1: 0, 2: 2, 3: 0}
    assert risk_labels[0] == "0 安全"
    assert risk_labels[3] == "3 高风险"


def test_student_report_summary_and_wrong_question_extraction():
    logs = [
        (1001, "正确"),
        (1002, "错误"),
        (1003, "PASS"),
        ("bad-id", "FAIL"),
    ]

    summary = calculate_learning_summary(125, logs)
    wrong_qids = extract_wrong_question_ids(logs)

    assert summary["total_minutes"] == 2
    assert summary["total_answered"] == 4
    assert summary["total_correct"] == 2
    assert summary["accuracy"] == 50.0
    assert wrong_qids == {1002}


def test_friendly_error_message_is_stable():
    assert friendly_error("读取学生报告") == "读取学生报告失败，请稍后重试或联系管理员。"
