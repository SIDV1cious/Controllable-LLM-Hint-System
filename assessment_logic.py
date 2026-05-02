"""Deterministic assessment helpers used before falling back to the LLM judge."""

from __future__ import annotations

import re
from typing import Any

CHOICE_ANSWER_PATTERN = re.compile(
    r"(?:^|答案|选项|选择|应选|我的答案)\s*(?:是|为|:|：)?\s*[\(（]?\s*([A-D])\s*[\)）]?"
    r"\s*(?=$|[.。、,，:：\s]|项|选项)",
    re.IGNORECASE,
)

FULLWIDTH_CHOICE_TRANSLATION = str.maketrans(
    {
        "Ａ": "A",
        "Ｂ": "B",
        "Ｃ": "C",
        "Ｄ": "D",
        "ａ": "a",
        "ｂ": "b",
        "ｃ": "c",
        "ｄ": "d",
    }
)


def normalize_choice_answer(raw_answer: Any) -> str | None:
    """Extract a single-choice label from common student/reference answer formats."""
    value = str(raw_answer or "").strip().translate(FULLWIDTH_CHOICE_TRANSLATION)
    if not value:
        return None

    match = CHOICE_ANSWER_PATTERN.search(value)
    if not match:
        return None

    return match.group(1).upper()


def assess_with_reference_answer(question: dict, student_answer: str) -> bool | None:
    """Return a deterministic grade for single-choice questions, otherwise defer to LLM."""
    reference_choice = normalize_choice_answer(question.get("answer", ""))
    if not reference_choice:
        return None

    student_choice = normalize_choice_answer(student_answer)
    return student_choice == reference_choice


def build_assessment_prompt(question: dict, student_answer: str) -> str:
    std_ans = question.get("answer", "")
    std_sol = question.get("solution", "")
    if std_ans or std_sol:
        return (
            f"题目：{question['content']}\n"
            f"标准答案：{std_ans}\n"
            f"标准解析：{std_sol}\n"
            f"学生答案：{student_answer}\n"
            "任务：请严格对照标准答案判断学生是否正确。正确输出PASS，错误输出FAIL。"
        )

    return f"题目：{question['content']}\n学生答案：{student_answer}\n任务：判断是否正确。正确输出PASS，错误输出FAIL。"
