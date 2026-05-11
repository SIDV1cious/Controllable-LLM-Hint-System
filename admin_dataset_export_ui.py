"""Admin UI for exporting controllable tutoring interaction datasets."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from database_service import get_database_engine
from interaction_dataset_export_service import (
    ALL_FILTER_VALUE,
    DATASET_FIELD_DESCRIPTIONS,
    DEFAULT_EXPORT_LIMIT,
    MAX_EXPORT_LIMIT,
    DatasetExportFilters,
    build_csv_bytes,
    build_dataset_filename,
    build_dataset_markdown,
    build_jsonl_bytes,
    fetch_dataset_filter_options,
    fetch_interaction_dataset,
)
from ui_feedback import render_admin_panel_title, render_empty_state

LEAKAGE_OPTIONS = [ALL_FILTER_VALUE, "是", "否"]
REWRITE_OPTIONS = [ALL_FILTER_VALUE, "是", "否"]
PREVIEW_ROW_LIMIT = 50


def _get_filter_options() -> dict[str, list[str]]:
    with get_database_engine().connect() as conn:
        return fetch_dataset_filter_options(conn)


def _fetch_dataset(filters: DatasetExportFilters) -> pd.DataFrame:
    with get_database_engine().connect() as conn:
        return fetch_interaction_dataset(conn, filters)


def _render_filter_panel(options: dict[str, list[str]]) -> DatasetExportFilters:
    with st.container(border=True):
        render_admin_panel_title("数据集筛选条件", "🔎")
        student_col, course_col, range_col = st.columns([0.28, 0.32, 0.4])
        with student_col:
            student_id = st.text_input("学生账号", placeholder="留空表示全部学生")
        with course_col:
            course_name = st.selectbox("课程模块", options["course_names"])
        with range_col:
            use_date_range = st.checkbox("启用时间范围筛选", value=False)

        start_date: date | None = None
        end_date: date | None = None
        if use_date_range:
            today = date.today()
            start_col, end_col = st.columns(2)
            with start_col:
                start_date = st.date_input("开始日期", value=today - timedelta(days=30))
            with end_col:
                end_date = st.date_input("结束日期", value=today)
            if start_date and end_date and start_date > end_date:
                st.warning("开始日期晚于结束日期，系统将自动按结束日期作为开始边界。")
                start_date = end_date

        strength_col, intent_col, safety_col = st.columns(3)
        with strength_col:
            hint_strength = st.selectbox("提示强度", options["hint_strengths"])
        with intent_col:
            pedagogical_intent = st.selectbox("教学意图", options["pedagogical_intents"])
        with safety_col:
            hint_safety_status = st.selectbox("安全状态", options["safety_statuses"])

        leakage_col, rewrite_col, limit_col, identity_col = st.columns([0.22, 0.22, 0.24, 0.32])
        with leakage_col:
            leakage_filter = st.selectbox("是否泄露", LEAKAGE_OPTIONS)
        with rewrite_col:
            rewrite_filter = st.selectbox("是否触发重写", REWRITE_OPTIONS)
        with limit_col:
            limit = st.number_input(
                "最大导出条数",
                min_value=1,
                max_value=MAX_EXPORT_LIMIT,
                value=DEFAULT_EXPORT_LIMIT,
                step=100,
            )
        with identity_col:
            include_raw_student_id = st.checkbox("包含原始学号", value=False)
            if include_raw_student_id:
                st.caption("仅限管理端研究导出，请勿公开传播原始学号。")
            else:
                st.caption("默认导出脱敏 student_hash。")

    return DatasetExportFilters(
        student_id=student_id,
        course_name=course_name,
        start_date=start_date,
        end_date=end_date,
        hint_strength=hint_strength,
        pedagogical_intent=pedagogical_intent,
        hint_safety_status=hint_safety_status,
        leakage_filter=leakage_filter,
        rewrite_filter=rewrite_filter,
        limit=int(limit),
        include_raw_student_id=include_raw_student_id,
    )


def _render_dataset_summary(df: pd.DataFrame, filters: DatasetExportFilters) -> None:
    metric_cols = st.columns(4)
    metric_cols[0].metric("导出样本数", len(df))
    metric_cols[1].metric("涉及课程数", df["course_name"].nunique() if not df.empty else 0)
    metric_cols[2].metric("泄露风险样本", int(df["is_leaking_answer"].sum()) if not df.empty else 0)
    metric_cols[3].metric("学号导出方式", "原始学号" if filters.include_raw_student_id else "脱敏哈希")


def _render_preview_table(df: pd.DataFrame) -> None:
    with st.container(border=True):
        render_admin_panel_title("数据集预览", "👀")
        if df.empty:
            render_empty_state(
                "当前筛选条件下没有可导出的智能辅导交互记录。",
                title="暂无匹配数据",
                icon="📦",
                compact=True,
            )
            return
        st.caption(f"下方仅预览前 {min(PREVIEW_ROW_LIMIT, len(df))} 条记录，下载文件会包含当前筛选结果。")
        st.dataframe(df.head(PREVIEW_ROW_LIMIT), use_container_width=True, hide_index=True, height=360)


def _render_download_area(df: pd.DataFrame, filters: DatasetExportFilters) -> None:
    with st.container(border=True):
        render_admin_panel_title("导出文件", "📥")
        markdown_doc = build_dataset_markdown(df.columns.tolist(), len(df), filters)
        csv_col, jsonl_col, md_col = st.columns(3)
        with csv_col:
            st.download_button(
                "📥 下载 CSV",
                build_csv_bytes(df),
                file_name=build_dataset_filename("csv"),
                mime="text/csv",
                use_container_width=True,
                disabled=df.empty,
            )
        with jsonl_col:
            st.download_button(
                "📦 下载 JSONL",
                build_jsonl_bytes(df),
                file_name=build_dataset_filename("jsonl"),
                mime="application/x-ndjson",
                use_container_width=True,
                disabled=df.empty,
            )
        with md_col:
            st.download_button(
                "📘 下载字段说明",
                markdown_doc.encode("utf-8"),
                file_name=build_dataset_filename("md"),
                mime="text/markdown",
                use_container_width=True,
            )


def _render_field_dictionary(columns: list[str]) -> None:
    with st.expander("查看数据集字段说明", expanded=False):
        field_rows = [
            {"字段": column, "含义": DATASET_FIELD_DESCRIPTIONS.get(column, "数据集扩展字段。")} for column in columns
        ]
        st.dataframe(pd.DataFrame(field_rows), use_container_width=True, hide_index=True)


def render_interaction_dataset_export_tab() -> None:
    st.markdown(
        """
<div class="admin-dataset-export-intro">
    <p>该模块用于提取智能辅导交互数据集，支持按学生、课程、时间、提示强度、教学意图和泄露状态筛选。</p>
    <p>默认导出脱敏学号，不包含标准答案与解析，避免导出数据自身造成答案泄露。</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    options = _get_filter_options()
    filters = _render_filter_panel(options)
    df = _fetch_dataset(filters)

    _render_dataset_summary(df, filters)
    _render_preview_table(df)
    _render_download_area(df, filters)
    _render_field_dictionary(df.columns.tolist())
