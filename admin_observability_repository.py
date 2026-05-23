"""Data access and pure aggregation helpers for the admin observability pages."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import text

from app_constants import InteractionMarker
from database_service import ensure_leakage_observability_columns, get_database_engine

ANSWER_SUBMISSION_PATTERN = f"{InteractionMarker.ANSWER_SUBMISSION}%"
TUTORING_PATTERN = f"{InteractionMarker.TUTORING}%"
ADMIN_OBSERVABILITY_CACHE_TTL_SECONDS = 30
LEAKAGE_SCORE_LEVELS = {
    0: "0 安全",
    1: "1 轻微风险",
    2: "2 中等风险",
    3: "3 高风险",
}


def fetch_active_user_trend(conn) -> pd.DataFrame:
    df = pd.read_sql(
        text(
            "SELECT DATE(login_time) as login_date, COUNT(DISTINCT username) as user_count "
            "FROM login_logs WHERE login_time >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) "
            "GROUP BY login_date ORDER BY login_date"
        ),
        conn,
    )
    if not df.empty:
        df["login_date"] = pd.to_datetime(df["login_date"])
    return df


def fetch_course_study_duration_summary(conn) -> pd.DataFrame:
    df = pd.read_sql(
        text(
            "SELECT course_name, SUM(duration_seconds) as total_seconds "
            "FROM study_sessions WHERE duration_seconds IS NOT NULL GROUP BY course_name"
        ),
        conn,
    )
    if not df.empty:
        df["total_minutes"] = (df["total_seconds"] / 60).round(1)
    return df


def fetch_answer_submission_records(conn) -> pd.DataFrame:
    return pd.read_sql(
        text("SELECT question_id, ai_response FROM interaction_logs WHERE user_query LIKE :pattern"),
        conn,
        params={"pattern": ANSWER_SUBMISSION_PATTERN},
    )


def fetch_custom_question_course_records(conn) -> pd.DataFrame:
    return pd.read_sql(text("SELECT id, category FROM custom_questions"), conn)


def build_course_accuracy_dataframe(answer_records: pd.DataFrame, question_records: pd.DataFrame) -> pd.DataFrame:
    columns = ["course_name", "is_correct", "accuracy_percent"]
    if answer_records.empty or question_records.empty:
        return pd.DataFrame(columns=columns)

    question_course_map = {
        str(1000 + int(row["id"])): str(row["category"])
        for _, row in question_records.iterrows()
        if pd.notna(row["id"])
    }
    enriched = answer_records.copy()
    enriched["clean_id"] = pd.to_numeric(enriched["question_id"], errors="coerce").fillna(-1).astype(int).astype(str)
    enriched["course_name"] = enriched["clean_id"].map(question_course_map)
    valid_records = enriched.dropna(subset=["course_name"]).copy()
    if valid_records.empty:
        return pd.DataFrame(columns=columns)

    valid_records["is_correct"] = valid_records["ai_response"].apply(
        lambda value: 1 if ("正确" in str(value) or "PASS" in str(value)) else 0
    )
    accuracy_df = valid_records.groupby("course_name")["is_correct"].mean().reset_index()
    accuracy_df["accuracy_percent"] = (accuracy_df["is_correct"] * 100).round(1)
    return accuracy_df


def fetch_course_accuracy_summary(conn) -> tuple[pd.DataFrame, bool]:
    answer_records = fetch_answer_submission_records(conn)
    if answer_records.empty:
        return pd.DataFrame(columns=["course_name", "is_correct", "accuracy_percent"]), False
    question_records = fetch_custom_question_course_records(conn)
    return build_course_accuracy_dataframe(answer_records, question_records), True


def fetch_hint_leakage_records(conn) -> pd.DataFrame:
    ensure_leakage_observability_columns()
    return pd.read_sql(
        text(
            "SELECT is_leaking_answer, leakage_score, rewrite_count, request_char_count, "
            "formula_fragment_count, generation_elapsed_ms, rewrite_triggered, "
            "COALESCE(NULLIF(generation_status, ''), 'success') AS generation_status, "
            "COALESCE(NULLIF(generation_strategy, ''), 'fast_path') AS generation_strategy, "
            "COALESCE(timeout_stage, '') AS timeout_stage, "
            "private_progress_signal_request, private_grade_signal_request, private_signal_encoding_request, "
            "private_signal_output_detected, private_signal_output_leaked, private_signal_output_category, "
            "private_signal_output_guarded "
            "FROM interaction_logs WHERE user_query LIKE :pattern"
        ),
        conn,
        params={"pattern": TUTORING_PATTERN},
    )


def summarize_hint_leakage_records(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "total_hints": 0,
            "leaked_hints": 0,
            "rewrite_total": 0,
            "leak_rate": 0.0,
            "avg_generation_elapsed_ms": 0.0,
            "p95_generation_elapsed_ms": 0.0,
            "timeout_rate": 0.0,
            "fast_path_rate": 0.0,
            "rewrite_rate": 0.0,
            "private_signal_output_detected_rate": 0.0,
            "private_signal_output_leaked_rate": 0.0,
            "private_signal_output_guarded_rate": 0.0,
        }

    total_hints = len(df)
    leaked_hints = int(df["is_leaking_answer"].fillna(0).astype(int).sum())
    rewrite_count = pd.to_numeric(df.get("rewrite_count", pd.Series([0] * total_hints)), errors="coerce").fillna(0)
    rewrite_triggered = pd.to_numeric(
        df.get("rewrite_triggered", pd.Series([0] * total_hints)), errors="coerce"
    ).fillna(0)
    elapsed_ms = pd.to_numeric(df.get("generation_elapsed_ms", pd.Series([0] * total_hints)), errors="coerce").fillna(0)
    generation_status = df.get("generation_status", pd.Series(["success"] * total_hints)).fillna("success").astype(str)
    generation_strategy = (
        df.get("generation_strategy", pd.Series(["fast_path"] * total_hints)).fillna("fast_path").astype(str)
    )
    timeout_stage = df.get("timeout_stage", pd.Series([""] * total_hints)).fillna("").astype(str)
    private_signal_output_detected = pd.to_numeric(
        df.get("private_signal_output_detected", pd.Series([0] * total_hints)), errors="coerce"
    ).fillna(0)
    private_signal_output_leaked = pd.to_numeric(
        df.get("private_signal_output_leaked", pd.Series([0] * total_hints)), errors="coerce"
    ).fillna(0)
    private_signal_output_guarded = pd.to_numeric(
        df.get("private_signal_output_guarded", pd.Series([0] * total_hints)), errors="coerce"
    ).fillna(0)
    rewrite_total = int(rewrite_count.astype(int).sum())
    rewrite_session_count = int(((rewrite_triggered.astype(int) > 0) | (rewrite_count.astype(int) > 0)).sum())
    timeout_count = int(((generation_status == "timeout") | (timeout_stage.str.strip() != "")).sum())
    fast_path_count = int((generation_strategy == "fast_path").sum())
    return {
        "total_hints": total_hints,
        "leaked_hints": leaked_hints,
        "rewrite_total": rewrite_total,
        "leak_rate": round(leaked_hints / total_hints * 100, 1),
        "avg_generation_elapsed_ms": round(float(elapsed_ms.mean()), 1),
        "p95_generation_elapsed_ms": round(float(elapsed_ms.quantile(0.95)), 1),
        "timeout_rate": round(timeout_count / total_hints * 100, 1),
        "fast_path_rate": round(fast_path_count / total_hints * 100, 1),
        "rewrite_rate": round(rewrite_session_count / total_hints * 100, 1),
        "private_signal_output_detected_rate": round(
            private_signal_output_detected.astype(int).sum() / total_hints * 100, 1
        ),
        "private_signal_output_leaked_rate": round(
            private_signal_output_leaked.astype(int).sum() / total_hints * 100, 1
        ),
        "private_signal_output_guarded_rate": round(
            private_signal_output_guarded.astype(int).sum() / total_hints * 100, 1
        ),
    }


def build_leakage_score_distribution(df: pd.DataFrame) -> pd.DataFrame:
    columns = ["leakage_score", "risk_level", "count"]
    if df.empty:
        return pd.DataFrame(
            [{"leakage_score": score, "risk_level": label, "count": 0} for score, label in LEAKAGE_SCORE_LEVELS.items()]
        )

    normalized = pd.to_numeric(df["leakage_score"], errors="coerce").fillna(0).astype(int).clip(lower=0, upper=3)
    counts = normalized.value_counts().to_dict()
    rows = [
        {
            "leakage_score": score,
            "risk_level": label,
            "count": int(counts.get(score, 0)),
        }
        for score, label in LEAKAGE_SCORE_LEVELS.items()
    ]
    return pd.DataFrame(rows, columns=columns)


def fetch_recent_login_logs(conn, limit: int = 50) -> pd.DataFrame:
    return pd.read_sql(
        text(
            "SELECT username AS '学号', login_time AS '登录时间' "
            "FROM login_logs ORDER BY login_time DESC LIMIT :limit"
        ),
        conn,
        params={"limit": limit},
    )


def fetch_recent_study_duration_logs(conn, limit: int = 50) -> pd.DataFrame:
    return pd.read_sql(
        text(
            "SELECT username AS '学号', course_name AS '课程', start_time AS '开始时间', "
            "end_time AS '结束时间', duration_seconds AS '学习时长(秒)' "
            "FROM study_sessions ORDER BY start_time DESC LIMIT :limit"
        ),
        conn,
        params={"limit": limit},
    )


def fetch_recent_interaction_logs(conn, limit: int = 50) -> pd.DataFrame:
    ensure_leakage_observability_columns()
    try:
        return pd.read_sql(
            text(
                "SELECT student_id AS '学号', question_id AS '题号', hint_strength AS '提示强度', "
                "pedagogical_intent AS '教学意图', hint_safety_status AS '安全状态', "
                "user_query AS '学生提问', ai_response AS '系统反馈', is_leaking_answer AS '是否泄露', "
                "leakage_score AS '泄露评分', rewrite_count AS '重写次数', rewrite_triggered AS '是否触发重写', "
                "request_char_count AS '输入长度', formula_fragment_count AS '公式数量', "
                "generation_elapsed_ms AS '生成耗时(ms)', generation_status AS '生成状态', "
                "generation_strategy AS '生成策略', timeout_stage AS '超时阶段', "
                "private_progress_signal_request AS '私有进度信号请求', "
                "private_grade_signal_request AS '私有评分信号请求', "
                "private_signal_encoding_request AS '私有编码信号请求', "
                "private_signal_output_detected AS '输出信号已识别', "
                "private_signal_output_leaked AS '输出信号仍泄漏', "
                "private_signal_output_category AS '输出信号类别', "
                "private_signal_output_guarded AS '输出保护触发', "
                "generation_error AS '生成异常', leakage_reason AS '检测原因', "
                "created_at AS '交互时间' FROM interaction_logs ORDER BY created_at DESC LIMIT :limit"
            ),
            conn,
            params={"limit": limit},
        )
    except Exception:
        return pd.read_sql(
            text(
                "SELECT student_id AS '学号', question_id AS '题号', user_query AS '学生提问', "
                "ai_response AS '系统反馈', created_at AS '交互时间' "
                "FROM interaction_logs ORDER BY created_at DESC LIMIT :limit"
            ),
            conn,
            params={"limit": limit},
        )


@st.cache_data(ttl=ADMIN_OBSERVABILITY_CACHE_TTL_SECONDS, show_spinner=False)
def fetch_cached_active_user_trend() -> pd.DataFrame:
    with get_database_engine().connect() as conn:
        return fetch_active_user_trend(conn)


@st.cache_data(ttl=ADMIN_OBSERVABILITY_CACHE_TTL_SECONDS, show_spinner=False)
def fetch_cached_course_study_duration_summary() -> pd.DataFrame:
    with get_database_engine().connect() as conn:
        return fetch_course_study_duration_summary(conn)


@st.cache_data(ttl=ADMIN_OBSERVABILITY_CACHE_TTL_SECONDS, show_spinner=False)
def fetch_cached_course_accuracy_summary() -> tuple[pd.DataFrame, bool]:
    with get_database_engine().connect() as conn:
        return fetch_course_accuracy_summary(conn)


@st.cache_data(ttl=ADMIN_OBSERVABILITY_CACHE_TTL_SECONDS, show_spinner=False)
def fetch_cached_hint_leakage_records() -> pd.DataFrame:
    with get_database_engine().connect() as conn:
        return fetch_hint_leakage_records(conn)


@st.cache_data(ttl=ADMIN_OBSERVABILITY_CACHE_TTL_SECONDS, show_spinner=False)
def fetch_cached_recent_login_logs(limit: int = 50) -> pd.DataFrame:
    with get_database_engine().connect() as conn:
        return fetch_recent_login_logs(conn, limit)


@st.cache_data(ttl=ADMIN_OBSERVABILITY_CACHE_TTL_SECONDS, show_spinner=False)
def fetch_cached_recent_study_duration_logs(limit: int = 50) -> pd.DataFrame:
    with get_database_engine().connect() as conn:
        return fetch_recent_study_duration_logs(conn, limit)


@st.cache_data(ttl=ADMIN_OBSERVABILITY_CACHE_TTL_SECONDS, show_spinner=False)
def fetch_cached_recent_interaction_logs(limit: int = 50) -> pd.DataFrame:
    with get_database_engine().connect() as conn:
        return fetch_recent_interaction_logs(conn, limit)


def clear_admin_observability_cache() -> None:
    fetch_cached_active_user_trend.clear()
    fetch_cached_course_study_duration_summary.clear()
    fetch_cached_course_accuracy_summary.clear()
    fetch_cached_hint_leakage_records.clear()
    fetch_cached_recent_login_logs.clear()
    fetch_cached_recent_study_duration_logs.clear()
    fetch_cached_recent_interaction_logs.clear()
