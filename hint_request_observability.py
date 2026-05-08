from __future__ import annotations

import re

MATH_DELIMITER_PATTERN = re.compile(
    r"\$\$.*?\$\$|\$[^$]+\$|\\\(.*?\\\)|\\\[.*?\\\]",
    re.DOTALL,
)
LATEX_SIGNAL_PATTERN = re.compile(r"\\begin\{[^}]+\}|\\[a-zA-Z]+|\\.|[\^_]")
FORMULA_SPLIT_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff\n]+")


def normalize_observed_query(query: str | None) -> str:
    return str(query or "").replace("\ufeff", "").strip()


def count_formula_fragments(query: str | None) -> int:
    observed_query = normalize_observed_query(query)
    if not observed_query:
        return 0

    delimited_fragments = MATH_DELIMITER_PATTERN.findall(observed_query)
    if delimited_fragments:
        remaining_query = MATH_DELIMITER_PATTERN.sub("\u200b", observed_query)
        remaining_segments = [segment.strip() for segment in FORMULA_SPLIT_PATTERN.split(remaining_query)]
        remaining_formula_count = sum(1 for segment in remaining_segments if LATEX_SIGNAL_PATTERN.search(segment))
        return len(delimited_fragments) + remaining_formula_count

    segments = [segment.strip() for segment in FORMULA_SPLIT_PATTERN.split(observed_query)]
    formula_segments = [segment for segment in segments if LATEX_SIGNAL_PATTERN.search(segment)]
    return len(formula_segments)


def build_hint_request_observability(
    query: str | None,
    generation_elapsed_ms: int | float | None = 0,
    rewrite_count: int | str | None = 0,
) -> dict:
    observed_query = normalize_observed_query(query)
    try:
        elapsed_ms = max(0, int(round(float(generation_elapsed_ms or 0))))
    except (TypeError, ValueError):
        elapsed_ms = 0

    try:
        rewrite_total = max(0, int(rewrite_count or 0))
    except (TypeError, ValueError):
        rewrite_total = 0

    return {
        "request_char_count": len(observed_query),
        "formula_fragment_count": count_formula_fragments(observed_query),
        "generation_elapsed_ms": elapsed_ms,
        "rewrite_triggered": int(rewrite_total > 0),
    }
