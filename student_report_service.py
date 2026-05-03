from __future__ import annotations

import re
from typing import Any

from app_constants import InteractionMarker

HINT_STRENGTH_MARK_PATTERN = re.compile(
    rf"{re.escape(InteractionMarker.HINT_STRENGTH_PREFIX)}[^{InteractionMarker.HINT_STRENGTH_SUFFIX}]+"
    rf"{re.escape(InteractionMarker.HINT_STRENGTH_SUFFIX)}"
)


def is_correct_answer_response(response: Any) -> bool:
    response_text = str(response or "")
    return "正确" in response_text or "PASS" in response_text


def is_wrong_answer_response(response: Any) -> bool:
    response_text = str(response or "")
    return "错误" in response_text or "FAIL" in response_text


def calculate_learning_summary(total_seconds: int | float | None, answer_logs: list[tuple[Any, Any]]) -> dict:
    total_answered = len(answer_logs)
    total_correct = sum(1 for _, response in answer_logs if is_correct_answer_response(response))
    accuracy = round(total_correct / total_answered * 100, 1) if total_answered else 0.0
    return {
        "total_minutes": round((total_seconds or 0) / 60),
        "total_answered": total_answered,
        "total_correct": total_correct,
        "accuracy": accuracy,
    }


def extract_wrong_question_ids(answer_logs: list[tuple[Any, Any]]) -> set[int]:
    wrong_qids: set[int] = set()
    for question_id, response in answer_logs:
        if not is_wrong_answer_response(response):
            continue
        try:
            wrong_qids.add(int(question_id))
        except (TypeError, ValueError):
            continue
    return wrong_qids


def clean_restored_tutoring_query(query: Any) -> str:
    cleaned = str(query or "").replace(InteractionMarker.TUTORING, "")
    cleaned = HINT_STRENGTH_MARK_PATTERN.sub("", cleaned)
    return cleaned.strip()
