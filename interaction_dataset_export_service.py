"""Dataset export helpers for controllable tutoring interactions."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import text

from app_constants import InteractionMarker
from hint_system_core import ensure_leakage_observability_columns, now_shanghai

ALL_FILTER_VALUE = "全部"
DEFAULT_EXPORT_LIMIT = 1000
MAX_EXPORT_LIMIT = 5000
DATASET_EXPORT_HASH_SALT = os.getenv("EXPORT_HASH_SALT", "controllable_hint_dataset_export_v1")
TUTORING_PATTERN = f"{InteractionMarker.TUTORING}%"
HINT_STRENGTH_PATTERN = re.compile(r"【提示强度：([^】]+)】")

DATASET_FIELD_DESCRIPTIONS = {
    "sample_id": "数据样本编号，由交互日志主键生成。",
    "student_id": "学生账号；仅在管理员主动选择包含原始学号时导出。",
    "student_hash": "脱敏后的学生标识，便于追踪同一学生但不暴露账号。",
    "question_id": "题目编号。",
    "course_name": "题目所属课程模块。",
    "student_prompt": "学生输入的智能辅导提示词，已去除系统内部标记。",
    "model_response": "系统最终展示给学生的智能辅导回复。",
    "hint_strength": "提示强度控制变量，如轻提示、中提示、强提示。",
    "pedagogical_intent": "快捷请求或系统识别出的教学意图。",
    "hint_safety_status": "提示安全状态，如泄露检测通过、已自动重写等。",
    "is_leaking_answer": "最终提示是否仍被判定为答案泄露。",
    "leakage_score": "答案泄露风险评分，数值越高风险越大。",
    "rewrite_count": "自动重写次数。",
    "rewrite_triggered": "是否触发过自动重写。",
    "leakage_reason": "泄露检测或重写判断原因。",
    "request_char_count": "学生提示词字符数。",
    "formula_fragment_count": "提示词中的公式片段数量。",
    "generation_elapsed_ms": "智能辅导生成耗时，单位毫秒。",
    "generation_status": "生成链路状态。",
    "generation_strategy": "生成策略，如 fast_path、llm_checked、rewritten、fallback。",
    "private_progress_signal_request": "是否识别到学生索要私有进度/正确性信号。",
    "private_grade_signal_request": "是否识别到学生索要评分、扣分、通过等私有评分信号。",
    "private_signal_encoding_request": "是否识别到学生索要编码、位置、语气等侧信道答案信号。",
    "private_signal_output_detected": "是否识别到输出里出现私有确认、评分、进度、位置或数值信号。",
    "private_signal_output_leaked": "最终输出里是否仍然保留私有信号。",
    "private_signal_output_category": "检测到的私有输出信号类别，如 soft_approval、grade_signal、progress_signal、position_value、zero_semantic。",
    "private_signal_output_guarded": "是否由输出级保护拦截并改写了私有信号回复。",
    "timeout_stage": "发生阶段级超时时的阶段名称。",
    "stage_timings": "各生成阶段耗时 JSON。",
    "generation_error": "生成异常类型或简要原因。",
    "created_at": "交互记录创建时间。",
}


@dataclass(frozen=True)
class DatasetExportFilters:
    student_id: str = ""
    course_name: str = ALL_FILTER_VALUE
    start_date: date | None = None
    end_date: date | None = None
    hint_strength: str = ALL_FILTER_VALUE
    pedagogical_intent: str = ALL_FILTER_VALUE
    hint_safety_status: str = ALL_FILTER_VALUE
    leakage_filter: str = ALL_FILTER_VALUE
    rewrite_filter: str = ALL_FILTER_VALUE
    limit: int = DEFAULT_EXPORT_LIMIT
    include_raw_student_id: bool = False


def clamp_export_limit(limit: int | float | str | None) -> int:
    try:
        normalized = int(limit or DEFAULT_EXPORT_LIMIT)
    except (TypeError, ValueError):
        normalized = DEFAULT_EXPORT_LIMIT
    return max(1, min(normalized, MAX_EXPORT_LIMIT))


def clean_tutoring_prompt(user_query: str) -> str:
    prompt = str(user_query or "")
    if prompt.startswith(InteractionMarker.TUTORING):
        prompt = prompt.removeprefix(InteractionMarker.TUTORING)
    prompt = HINT_STRENGTH_PATTERN.sub("", prompt)
    return prompt.strip()


def anonymize_student_id(student_id: str, salt: str = DATASET_EXPORT_HASH_SALT) -> str:
    normalized = str(student_id or "").strip()
    if not normalized:
        return ""
    return hashlib.sha256(f"{salt}:{normalized}".encode()).hexdigest()[:12]


def derive_hint_strength(row: pd.Series) -> str:
    current = str(row.get("hint_strength") or "").strip()
    if current:
        return current
    match = HINT_STRENGTH_PATTERN.search(str(row.get("user_query") or ""))
    return match.group(1) if match else "未记录"


def derive_safety_status(row: pd.Series) -> str:
    current = str(row.get("hint_safety_status") or "").strip()
    if current:
        return current
    if int(row.get("rewrite_count") or 0) > 0:
        return "已自动重写"
    if int(row.get("is_leaking_answer") or 0) > 0:
        return "仍有泄露风险"
    return "泄露检测通过"


def normalize_filter_options(values: list[Any]) -> list[str]:
    normalized = sorted({str(value).strip() for value in values if str(value or "").strip()})
    return [ALL_FILTER_VALUE, *normalized]


def fetch_dataset_filter_options(conn) -> dict[str, list[str]]:
    ensure_leakage_observability_columns()
    query = text("""
        SELECT DISTINCT
            COALESCE(cq.category, '未知课程') AS course_name,
            il.hint_strength,
            il.pedagogical_intent,
            il.hint_safety_status
        FROM interaction_logs il
        LEFT JOIN custom_questions cq ON il.question_id = cq.id + 1000
        WHERE il.user_query LIKE :tutoring_pattern
        """)
    df = pd.read_sql(query, conn, params={"tutoring_pattern": TUTORING_PATTERN})
    if df.empty:
        return {
            "course_names": [ALL_FILTER_VALUE],
            "hint_strengths": [ALL_FILTER_VALUE],
            "pedagogical_intents": [ALL_FILTER_VALUE],
            "safety_statuses": [ALL_FILTER_VALUE],
        }
    return {
        "course_names": normalize_filter_options(df["course_name"].tolist()),
        "hint_strengths": normalize_filter_options(df["hint_strength"].tolist()),
        "pedagogical_intents": normalize_filter_options(df["pedagogical_intent"].tolist()),
        "safety_statuses": normalize_filter_options(df["hint_safety_status"].tolist()),
    }


def fetch_interaction_dataset(conn, filters: DatasetExportFilters) -> pd.DataFrame:
    ensure_leakage_observability_columns()
    where_clauses = ["il.user_query LIKE :tutoring_pattern"]
    params: dict[str, Any] = {
        "tutoring_pattern": TUTORING_PATTERN,
        "limit": clamp_export_limit(filters.limit),
    }

    student_id = filters.student_id.strip()
    if student_id:
        where_clauses.append("il.student_id = :student_id")
        params["student_id"] = student_id

    if filters.course_name != ALL_FILTER_VALUE:
        where_clauses.append("COALESCE(cq.category, '未知课程') = :course_name")
        params["course_name"] = filters.course_name

    if filters.start_date:
        where_clauses.append("il.created_at >= :start_datetime")
        params["start_datetime"] = datetime.combine(filters.start_date, time.min)

    if filters.end_date:
        where_clauses.append("il.created_at < :end_datetime")
        params["end_datetime"] = datetime.combine(filters.end_date + timedelta(days=1), time.min)

    if filters.hint_strength != ALL_FILTER_VALUE:
        where_clauses.append("il.hint_strength = :hint_strength")
        params["hint_strength"] = filters.hint_strength

    if filters.pedagogical_intent != ALL_FILTER_VALUE:
        where_clauses.append("il.pedagogical_intent = :pedagogical_intent")
        params["pedagogical_intent"] = filters.pedagogical_intent

    if filters.hint_safety_status != ALL_FILTER_VALUE:
        where_clauses.append("il.hint_safety_status = :hint_safety_status")
        params["hint_safety_status"] = filters.hint_safety_status

    if filters.leakage_filter != ALL_FILTER_VALUE:
        where_clauses.append("COALESCE(il.is_leaking_answer, 0) = :is_leaking_answer")
        params["is_leaking_answer"] = 1 if filters.leakage_filter == "是" else 0

    if filters.rewrite_filter != ALL_FILTER_VALUE:
        where_clauses.append("COALESCE(il.rewrite_triggered, 0) = :rewrite_triggered")
        params["rewrite_triggered"] = 1 if filters.rewrite_filter == "是" else 0

    query = text(f"""
        SELECT
            il.id,
            il.student_id,
            il.question_id,
            COALESCE(cq.category, '未知课程') AS course_name,
            il.user_query,
            il.ai_response,
            il.is_leaking_answer,
            il.leakage_score,
            il.rewrite_count,
            il.leakage_reason,
            il.hint_strength,
            il.pedagogical_intent,
            il.hint_safety_status,
            il.request_char_count,
            il.formula_fragment_count,
            il.generation_elapsed_ms,
            il.rewrite_triggered,
            il.generation_status,
            il.generation_strategy,
            il.private_progress_signal_request,
            il.private_grade_signal_request,
            il.private_signal_encoding_request,
            il.private_signal_output_detected,
            il.private_signal_output_leaked,
            il.private_signal_output_category,
            il.private_signal_output_guarded,
            il.timeout_stage,
            il.stage_timings,
            il.generation_error,
            il.created_at
        FROM interaction_logs il
        LEFT JOIN custom_questions cq ON il.question_id = cq.id + 1000
        WHERE {" AND ".join(where_clauses)}
        ORDER BY il.created_at DESC
        LIMIT :limit
        """)
    raw_df = pd.read_sql(query, conn, params=params)
    return build_dataset_export_dataframe(raw_df, include_raw_student_id=filters.include_raw_student_id)


def _normalize_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    for column in [
        "is_leaking_answer",
        "leakage_score",
        "rewrite_count",
        "request_char_count",
        "formula_fragment_count",
        "generation_elapsed_ms",
        "rewrite_triggered",
        "private_progress_signal_request",
        "private_grade_signal_request",
        "private_signal_encoding_request",
        "private_signal_output_detected",
        "private_signal_output_leaked",
        "private_signal_output_guarded",
    ]:
        if column not in normalized.columns:
            normalized[column] = 0
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(0).astype(int)
    if "private_signal_output_category" not in normalized.columns:
        normalized["private_signal_output_category"] = ""
    normalized["private_signal_output_category"] = normalized["private_signal_output_category"].fillna("").astype(str)
    return normalized


def build_dataset_export_dataframe(raw_df: pd.DataFrame, *, include_raw_student_id: bool = False) -> pd.DataFrame:
    identity_column = "student_id" if include_raw_student_id else "student_hash"
    ordered_columns = [
        "sample_id",
        identity_column,
        "question_id",
        "course_name",
        "student_prompt",
        "model_response",
        "hint_strength",
        "pedagogical_intent",
        "hint_safety_status",
        "is_leaking_answer",
        "leakage_score",
        "rewrite_count",
        "rewrite_triggered",
        "leakage_reason",
        "request_char_count",
        "formula_fragment_count",
        "generation_elapsed_ms",
        "generation_status",
        "generation_strategy",
        "private_progress_signal_request",
        "private_grade_signal_request",
        "private_signal_encoding_request",
        "private_signal_output_detected",
        "private_signal_output_leaked",
        "private_signal_output_category",
        "private_signal_output_guarded",
        "timeout_stage",
        "stage_timings",
        "generation_error",
        "created_at",
    ]
    if raw_df.empty:
        return pd.DataFrame(columns=ordered_columns)

    df = _normalize_numeric_columns(raw_df)
    for column in [
        "id",
        "student_id",
        "question_id",
        "course_name",
        "user_query",
        "ai_response",
        "leakage_reason",
        "hint_strength",
        "pedagogical_intent",
        "hint_safety_status",
        "generation_status",
        "generation_strategy",
        "timeout_stage",
        "stage_timings",
        "generation_error",
        "created_at",
    ]:
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].fillna("").astype(str)

    export_df = pd.DataFrame()
    export_df["sample_id"] = "hint-" + df["id"].astype(str)
    if include_raw_student_id:
        export_df["student_id"] = df["student_id"].str.strip()
    else:
        export_df["student_hash"] = df["student_id"].apply(anonymize_student_id)
    export_df["question_id"] = df["question_id"]
    export_df["course_name"] = df["course_name"].replace("", "未知课程")
    export_df["student_prompt"] = df["user_query"].apply(clean_tutoring_prompt)
    export_df["model_response"] = df["ai_response"].str.strip()
    export_df["hint_strength"] = df.apply(derive_hint_strength, axis=1)
    export_df["pedagogical_intent"] = df["pedagogical_intent"].str.strip().replace("", "未记录")
    export_df["hint_safety_status"] = df.apply(derive_safety_status, axis=1)
    export_df["is_leaking_answer"] = df["is_leaking_answer"]
    export_df["leakage_score"] = df["leakage_score"]
    export_df["rewrite_count"] = df["rewrite_count"]
    export_df["rewrite_triggered"] = df["rewrite_triggered"]
    export_df["leakage_reason"] = df["leakage_reason"].str.strip()
    export_df["request_char_count"] = df["request_char_count"]
    export_df["formula_fragment_count"] = df["formula_fragment_count"]
    export_df["generation_elapsed_ms"] = df["generation_elapsed_ms"]
    export_df["generation_status"] = df["generation_status"].str.strip().replace("", "success")
    export_df["generation_strategy"] = df["generation_strategy"].str.strip().replace("", "fast_path")
    export_df["private_progress_signal_request"] = df["private_progress_signal_request"]
    export_df["private_grade_signal_request"] = df["private_grade_signal_request"]
    export_df["private_signal_encoding_request"] = df["private_signal_encoding_request"]
    export_df["private_signal_output_detected"] = df["private_signal_output_detected"]
    export_df["private_signal_output_leaked"] = df["private_signal_output_leaked"]
    export_df["private_signal_output_category"] = df["private_signal_output_category"].str.strip()
    export_df["private_signal_output_guarded"] = df["private_signal_output_guarded"]
    export_df["timeout_stage"] = df["timeout_stage"].str.strip()
    export_df["stage_timings"] = df["stage_timings"].str.strip()
    export_df["generation_error"] = df["generation_error"].str.strip()
    export_df["created_at"] = pd.to_datetime(df.get("created_at"), errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    export_df["created_at"] = export_df["created_at"].fillna("")
    return export_df[ordered_columns]


def build_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def build_jsonl_bytes(df: pd.DataFrame) -> bytes:
    records = df.fillna("").to_dict(orient="records")
    lines = [json.dumps(record, ensure_ascii=False, default=str) for record in records]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def _escape_markdown_cell(value: str) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", "<br>")


def build_dataset_markdown(columns: list[str], total_rows: int, filters: DatasetExportFilters) -> str:
    lines = [
        "# 智能辅导交互数据集说明",
        "",
        f"导出时间：{now_shanghai():%Y-%m-%d %H:%M:%S}",
        f"样本数量：{total_rows}",
        "",
        "## 筛选条件",
        "",
        f"- 学生账号：{filters.student_id.strip() or '全部'}",
        f"- 课程模块：{filters.course_name}",
        f"- 时间范围：{filters.start_date or '不限'} 至 {filters.end_date or '不限'}",
        f"- 提示强度：{filters.hint_strength}",
        f"- 教学意图：{filters.pedagogical_intent}",
        f"- 安全状态：{filters.hint_safety_status}",
        f"- 是否泄露：{filters.leakage_filter}",
        f"- 是否触发重写：{filters.rewrite_filter}",
        f"- 学号导出方式：{'原始学号' if filters.include_raw_student_id else '脱敏哈希'}",
        "",
        "## 字段说明",
        "",
        "| 字段 | 含义 |",
        "| --- | --- |",
    ]
    for column in columns:
        description = DATASET_FIELD_DESCRIPTIONS.get(column, "数据集扩展字段。")
        lines.append(f"| `{_escape_markdown_cell(column)}` | {_escape_markdown_cell(description)} |")
    lines.extend(
        [
            "",
            "## 使用说明",
            "",
            "- CSV 适合人工查看与表格分析。",
            "- JSONL 适合构建后续 LLM 训练、评测或检索增强数据集。",
            "- 默认不包含标准答案和解析，避免导出数据自身造成答案泄露。",
        ]
    )
    return "\n".join(lines)


def build_dataset_filename(extension: str) -> str:
    safe_extension = extension.lstrip(".").lower()
    return f"controlled_hint_interaction_dataset_{now_shanghai():%Y%m%d_%H%M%S}.{safe_extension}"
