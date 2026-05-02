"""Centralized policy configuration for controllable hint generation."""

from __future__ import annotations

DEFAULT_HINT_STRENGTH = "中提示"
MAX_HINT_REWRITE_ATTEMPTS = 2
HIGH_RISK_LEAKAGE_SCORE = 2

FALLBACK_SAFE_HINT = (
    "这道题我们先抓住关键条件，不直接推进到答案。你可以先判断题目考查的是哪个定义、公式或判别方法，"
    "再检查你的下一步是否满足它的适用条件。"
)

HINT_STRENGTH_POLICIES = {
    "轻提示": "只给方向性启发、概念提醒或检查角度，避免任何关键中间式、关键数值和最终结论。",
    DEFAULT_HINT_STRENGTH: "给出可执行的下一步思考路径，可以提示应使用的定义、公式或判别方法，但不展开完整推导。",
    "强提示": "给出更具体的分步引导和易错点提醒，但仍不得给出最终答案、直接选项或完整标准解法。",
}


def normalize_hint_strength(hint_strength: str | None) -> str:
    strength = str(hint_strength or "").strip()
    return strength if strength in HINT_STRENGTH_POLICIES else DEFAULT_HINT_STRENGTH


def get_hint_strength_policy(hint_strength: str | None) -> str:
    return HINT_STRENGTH_POLICIES[normalize_hint_strength(hint_strength)]


def is_high_risk_leakage_score(score: int | float | str | None) -> bool:
    try:
        return int(score or 0) >= HIGH_RISK_LEAKAGE_SCORE
    except (TypeError, ValueError):
        return False
