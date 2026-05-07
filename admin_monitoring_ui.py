import streamlit as st

from admin_observability_repository import (
    fetch_cached_recent_interaction_logs,
    fetch_cached_recent_login_logs,
    fetch_cached_recent_study_duration_logs,
)
from ui_feedback import render_admin_panel_title, render_empty_state


def render_login_logs_tab():
    with st.container(border=True):
        render_admin_panel_title("学生活跃度监控", "🕒")
        df_login = fetch_cached_recent_login_logs()
        if df_login.empty:
            render_empty_state("暂无学生登录日志。", title="暂无登录日志", icon="🕒", compact=True)
            return

        st.dataframe(df_login, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 导出登录日志 (CSV)",
            df_login.to_csv(index=False).encode("utf-8-sig"),
            "login_logs.csv",
            "text/csv",
            use_container_width=True,
        )


def render_study_duration_tab():
    with st.container(border=True):
        render_admin_panel_title("各科课程学习时长分析", "⏱️")
        df_study = fetch_cached_recent_study_duration_logs()
        if df_study.empty:
            render_empty_state("暂无学习会话记录。", title="暂无学习时长数据", icon="⏱️", compact=True)
            return

        st.dataframe(df_study, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 导出学习时长记录 (CSV)",
            df_study.to_csv(index=False).encode("utf-8-sig"),
            "study_sessions.csv",
            "text/csv",
            use_container_width=True,
        )


def render_interaction_monitoring_tab():
    with st.container(border=True):
        render_admin_panel_title("大模型交互质量抽查", "💬")
        df_chat = fetch_cached_recent_interaction_logs()
        if df_chat.empty:
            render_empty_state("暂无智能辅导交互记录。", title="暂无 AI 辅导监控数据", icon="💬", compact=True)
            return

        st.dataframe(df_chat, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 导出AI辅导监控记录 (CSV)",
            df_chat.to_csv(index=False).encode("utf-8-sig"),
            "ai_interaction_logs.csv",
            "text/csv",
            use_container_width=True,
        )
