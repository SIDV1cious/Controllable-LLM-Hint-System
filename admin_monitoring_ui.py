import streamlit as st

from admin_observability_repository import (
    fetch_cached_recent_interaction_logs,
    fetch_cached_recent_login_logs,
    fetch_cached_recent_study_duration_logs,
)
from ui_feedback import render_empty_state


def render_login_logs_tab():
    st.markdown("<div class='app-section-heading'><h3 class='app-section-title'>学生活跃度监控</h3></div>", unsafe_allow_html=True)
    df_login = fetch_cached_recent_login_logs()
    if df_login.empty:
        render_empty_state("暂无学生登录日志。", title="暂无登录日志", icon="🕒")
        return

    st.dataframe(df_login, use_container_width=True, hide_index=True)
    if not df_login.empty:
        st.download_button(
            "📥 导出登录日志 (CSV)",
            df_login.to_csv(index=False).encode("utf-8-sig"),
            "login_logs.csv",
            "text/csv",
            use_container_width=True,
        )


def render_study_duration_tab():
    st.markdown("<div class='app-section-heading'><h3 class='app-section-title'>各科课程学习时长分析</h3></div>", unsafe_allow_html=True)
    df_study = fetch_cached_recent_study_duration_logs()
    if df_study.empty:
        render_empty_state("暂无学习会话记录。", title="暂无学习时长数据", icon="⏱️")
        return

    st.dataframe(df_study, use_container_width=True, hide_index=True)
    if not df_study.empty:
        st.download_button(
            "📥 导出学习时长记录 (CSV)",
            df_study.to_csv(index=False).encode("utf-8-sig"),
            "study_sessions.csv",
            "text/csv",
            use_container_width=True,
        )


def render_interaction_monitoring_tab():
    st.markdown("<div class='app-section-heading'><h3 class='app-section-title'>大模型交互质量抽查</h3></div>", unsafe_allow_html=True)
    df_chat = fetch_cached_recent_interaction_logs()
    if df_chat.empty:
        render_empty_state("暂无智能辅导交互记录。", title="暂无 AI 辅导监控数据", icon="💬")
        return

    st.dataframe(df_chat, use_container_width=True, hide_index=True)
    if not df_chat.empty:
        st.download_button(
            "📥 导出AI辅导监控记录 (CSV)",
            df_chat.to_csv(index=False).encode("utf-8-sig"),
            "ai_interaction_logs.csv",
            "text/csv",
            use_container_width=True,
        )
