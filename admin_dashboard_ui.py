import plotly.express as px
import streamlit as st

from admin_observability_repository import (
    build_leakage_score_distribution,
    fetch_active_user_trend,
    fetch_course_accuracy_summary,
    fetch_course_study_duration_summary,
    fetch_hint_leakage_records,
    summarize_hint_leakage_records,
)
from app_errors import log_exception


def render_learning_overview_dashboard(conn):
    st.markdown("#### 🕒 最近7天系统活跃人数趋势")
    try:
        df_active = fetch_active_user_trend(conn)
        if not df_active.empty:
            st.line_chart(df_active, x="login_date", y="user_count", use_container_width=True)
    except Exception as e:
        log_exception("Dashboard active users", e)

    st.markdown("---")
    st.markdown("#### 📘 各科课程学习时长占比")
    col_chart1, col_data1 = st.columns([2, 1])
    try:
        df_duration = fetch_course_study_duration_summary(conn)
        if not df_duration.empty:
            fig_pie = px.pie(
                df_duration,
                values="total_minutes",
                names="course_name",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            with col_chart1:
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_data1:
                st.markdown("<div style='margin-top: 100px;'></div>", unsafe_allow_html=True)
                st.dataframe(df_duration[["course_name", "total_minutes"]], hide_index=True)
    except Exception as e:
        log_exception("Dashboard duration", e)

    st.markdown("---")
    st.markdown("#### ✅ 全系统题目平均正确率统计")
    try:
        df_accuracy, has_answer_records = fetch_course_accuracy_summary(conn)
        if not has_answer_records:
            st.info("暂无答题提交数据，无法计算正确率。")
        elif df_accuracy.empty:
            st.warning("⚠️ 无法生成图表：题号映射失败！")
        else:
            fig_bar = px.bar(
                df_accuracy,
                x="course_name",
                y="accuracy_percent",
                labels={"course_name": "课程名称", "accuracy_percent": "正确率 (%)"},
                color_discrete_sequence=["#1f77b4"],
            )
            if len(df_accuracy) == 1:
                fig_bar.update_traces(width=0.2)
            st.plotly_chart(fig_bar, use_container_width=True)
    except Exception as e:
        st.error(f"⚠️ 图表加载报错: {e}")

    st.markdown("---")
    st.markdown("#### 🛡️ 智能辅导答案泄露控制统计")
    try:
        df_leak = fetch_hint_leakage_records(conn)
        if not df_leak.empty:
            leakage_summary = summarize_hint_leakage_records(df_leak)
            c_leak1, c_leak2, c_leak3 = st.columns(3)
            c_leak1.metric("辅导提示总数", leakage_summary["total_hints"])
            c_leak2.metric("最终泄露率", f"{leakage_summary['leak_rate']} %")
            c_leak3.metric("自动重写次数", leakage_summary["rewrite_total"])
            score_df = build_leakage_score_distribution(df_leak)
            fig_leak = px.bar(
                score_df,
                x="risk_level",
                y="count",
                text="count",
                labels={"risk_level": "泄露风险等级", "count": "提示数量"},
                color="risk_level",
                color_discrete_map={
                    "0 安全": "#22c55e",
                    "1 轻微风险": "#84cc16",
                    "2 中等风险": "#f59e0b",
                    "3 高风险": "#ef4444",
                },
            )
            fig_leak.update_traces(width=0.45, textposition="outside", cliponaxis=False)
            fig_leak.update_layout(showlegend=False, bargap=0.45, yaxis_title="提示数量", xaxis_title="泄露风险等级")
            st.plotly_chart(fig_leak, use_container_width=True)
        else:
            st.info("暂无智能辅导提示数据，无法计算泄露控制指标。")
    except Exception as e:
        log_exception("Leakage dashboard", e)
        st.info("当前数据库尚未记录泄露控制扩展指标。")
