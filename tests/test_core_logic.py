import pandas as pd

from experiment_analytics_service import (
    build_experiment_export_dataframe,
    build_experiment_markdown_report,
    summarize_hint_experiment,
)
from hint_text_utils import format_math, parse_json_object
from leakage_detection_service import heuristic_leakage_check


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
    df = pd.DataFrame([
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
    ])

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
