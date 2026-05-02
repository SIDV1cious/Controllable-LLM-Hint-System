import streamlit as st

from admin_observability_repository import (
    fetch_recent_interaction_logs,
    fetch_recent_login_logs,
    fetch_recent_study_duration_logs,
)


def render_login_logs_tab(conn):
    st.subheader("学生活跃度监控")
    df_login = fetch_recent_login_logs(conn)
    st.dataframe(df_login, use_container_width=True)
    if not df_login.empty:
        st.download_button(
            "📥 导出登录日志 (CSV)",
            df_login.to_csv(index=False).encode("utf-8-sig"),
            "login_logs.csv",
            "text/csv",
            use_container_width=True,
        )


def render_study_duration_tab(conn):
    st.subheader("各科课程学习时长分析")
    df_study = fetch_recent_study_duration_logs(conn)
    st.dataframe(df_study, use_container_width=True)
    if not df_study.empty:
        st.download_button(
            "📥 导出学习时长记录 (CSV)",
            df_study.to_csv(index=False).encode("utf-8-sig"),
            "study_sessions.csv",
            "text/csv",
            use_container_width=True,
        )


def render_interaction_monitoring_tab(conn):
    st.subheader("大模型交互质量抽查")
    df_chat = fetch_recent_interaction_logs(conn)
    st.dataframe(df_chat, use_container_width=True)
    if not df_chat.empty:
        st.download_button(
            "📥 导出AI辅导监控记录 (CSV)",
            df_chat.to_csv(index=False).encode("utf-8-sig"),
            "ai_interaction_logs.csv",
            "text/csv",
            use_container_width=True,
        )
