import pandas as pd
import plotly.express as px
import streamlit as st

from experiment_analytics_service import (
    build_experiment_export_dataframe,
    build_experiment_markdown_report,
    fetch_cached_hint_experiment_logs,
    summarize_hint_experiment,
)
from ui_feedback import render_admin_panel_title, render_empty_state

PLOTLY_CHART_CONFIG = {"displayModeBar": False}


def _apply_experiment_chart_theme(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,251,255,0.68)",
        font={"family": "Arial, sans-serif", "color": "#334155"},
        margin={"l": 20, "r": 20, "t": 18, "b": 20},
        hoverlabel={"bgcolor": "white", "bordercolor": "#dbe4f0", "font_size": 13},
        height=360,
    )
    fig.update_xaxes(showgrid=False, linecolor="#dbe4f0", tickfont={"color": "#64748b"})
    fig.update_yaxes(gridcolor="#e8eef7", zerolinecolor="#dbe4f0", tickfont={"color": "#64748b"})
    return fig


def _filter_experiment_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    filter_cols = st.columns(3)
    with filter_cols[0]:
        courses = sorted(df["course_name"].dropna().astype(str).unique())
        selected_courses = st.multiselect("课程范围", courses, default=courses, key="experiment_course_filter")
    with filter_cols[1]:
        strengths = sorted(df["hint_strength"].dropna().astype(str).unique())
        selected_strengths = st.multiselect("提示强度", strengths, default=strengths, key="experiment_strength_filter")
    with filter_cols[2]:
        intents = sorted(df["pedagogical_intent"].dropna().astype(str).unique())
        selected_intents = st.multiselect("教学意图", intents, default=intents, key="experiment_intent_filter")

    filtered = df.copy()
    if selected_courses:
        filtered = filtered[filtered["course_name"].isin(selected_courses)]
    if selected_strengths:
        filtered = filtered[filtered["hint_strength"].isin(selected_strengths)]
    if selected_intents:
        filtered = filtered[filtered["pedagogical_intent"].isin(selected_intents)]
    return filtered


def _render_summary_metrics(df: pd.DataFrame):
    with st.container(border=True):
        render_admin_panel_title("实验关键指标", "📌")
        summary = summarize_hint_experiment(df)
        metric_cols = st.columns(5)
        metric_cols[0].metric("辅导提示总数", summary["total_hints"])
        metric_cols[1].metric("最终泄露率", f"{summary['final_leak_rate']}%")
        metric_cols[2].metric("自动重写触发率", f"{summary['rewrite_rate']}%")
        metric_cols[3].metric("平均泄露评分", summary["avg_leakage_score"])
        metric_cols[4].metric("高风险候选数", summary["high_risk_count"])


def _render_distribution_charts(df: pd.DataFrame):
    render_admin_panel_title("实验变量分布", "📊")
    chart_cols = st.columns(2)

    strength_df = df.groupby("hint_strength").size().reset_index(name="count")
    intent_df = df.groupby("pedagogical_intent").size().reset_index(name="count")
    score_df = df.groupby("leakage_score").size().reset_index(name="count")
    status_df = df.groupby("hint_safety_status").size().reset_index(name="count")

    with chart_cols[0]:
        with st.container(border=True):
            render_admin_panel_title("提示强度分布", "🎚️")
            fig_strength = px.bar(
                strength_df,
                x="hint_strength",
                y="count",
                labels={"hint_strength": "提示强度", "count": "提示数量"},
                color="hint_strength",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            st.plotly_chart(
                _apply_experiment_chart_theme(fig_strength),
                use_container_width=True,
                config=PLOTLY_CHART_CONFIG,
            )

    with chart_cols[1]:
        with st.container(border=True):
            render_admin_panel_title("教学意图分布", "🧭")
            fig_intent = px.bar(
                intent_df,
                x="pedagogical_intent",
                y="count",
                labels={"pedagogical_intent": "教学意图", "count": "提示数量"},
                color="pedagogical_intent",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            st.plotly_chart(
                _apply_experiment_chart_theme(fig_intent),
                use_container_width=True,
                config=PLOTLY_CHART_CONFIG,
            )

    chart_cols2 = st.columns(2)
    with chart_cols2[0]:
        with st.container(border=True):
            render_admin_panel_title("泄露评分分布", "🛡️")
            fig_score = px.bar(
                score_df,
                x="leakage_score",
                y="count",
                labels={"leakage_score": "泄露评分", "count": "提示数量"},
                color_discrete_sequence=["#2563eb"],
            )
            st.plotly_chart(
                _apply_experiment_chart_theme(fig_score),
                use_container_width=True,
                config=PLOTLY_CHART_CONFIG,
            )

    with chart_cols2[1]:
        with st.container(border=True):
            render_admin_panel_title("安全状态占比", "✅")
            fig_status = px.pie(
                status_df,
                names="hint_safety_status",
                values="count",
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Safe,
            )
            fig_status.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(
                _apply_experiment_chart_theme(fig_status),
                use_container_width=True,
                config=PLOTLY_CHART_CONFIG,
            )


def _render_trend_chart(df: pd.DataFrame):
    with st.container(border=True):
        render_admin_panel_title("生成与安全控制趋势", "📈")
        trend_df = (
            df.groupby("experiment_date")
            .agg(
                提示数量=("id", "count"),
                平均泄露评分=("leakage_score", "mean"),
                自动重写次数=("rewrite_count", "sum"),
            )
            .reset_index()
        )
        fig_trend = px.line(
            trend_df,
            x="experiment_date",
            y=["提示数量", "平均泄露评分", "自动重写次数"],
            markers=True,
            labels={"experiment_date": "日期", "value": "指标值", "variable": "指标"},
        )
        st.plotly_chart(_apply_experiment_chart_theme(fig_trend), use_container_width=True, config=PLOTLY_CHART_CONFIG)


def _render_export_area(df: pd.DataFrame):
    export_df = build_experiment_export_dataframe(df)
    export_cols = st.columns(2)
    with export_cols[0]:
        st.download_button(
            "📥 导出实验明细数据 CSV",
            export_df.to_csv(index=False).encode("utf-8-sig"),
            "controlled_hint_experiment_data.csv",
            "text/csv",
            use_container_width=True,
        )
    with export_cols[1]:
        st.download_button(
            "📄 导出实验统计报告 Markdown",
            build_experiment_markdown_report(df).encode("utf-8-sig"),
            "controlled_hint_experiment_report.md",
            "text/markdown",
            use_container_width=True,
        )


def render_experiment_analytics_dashboard():
    try:
        df = fetch_cached_hint_experiment_logs()
    except Exception as exc:
        st.warning(f"实验数据读取失败：{exc}")
        return

    if df.empty:
        render_empty_state(
            "学生生成过辅导提示后，这里会自动出现统计结果。",
            title="暂无智能辅导实验数据",
            icon="🧪",
            compact=True,
        )
        return

    filtered_df = _filter_experiment_dataframe(df)
    if filtered_df.empty:
        render_empty_state(
            "请调整课程、提示强度或教学意图筛选条件。", title="当前筛选条件下暂无数据", icon="🔎", compact=True
        )
        return

    _render_summary_metrics(filtered_df)
    _render_distribution_charts(filtered_df)
    _render_trend_chart(filtered_df)

    with st.container(border=True):
        render_admin_panel_title("实验明细与导出", "📥")
        _render_export_area(filtered_df)
        st.dataframe(build_experiment_export_dataframe(filtered_df), use_container_width=True, hide_index=True)
