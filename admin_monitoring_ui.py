import pandas as pd
import streamlit as st


def render_login_logs_tab(conn):
    st.subheader("学生活跃度监控")
    df_login = pd.read_sql(
        "SELECT username AS '学号', login_time AS '登录时间' FROM login_logs ORDER BY login_time DESC LIMIT 50",
        conn,
    )
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
    df_study = pd.read_sql(
        "SELECT username AS '学号', course_name AS '课程', start_time AS '开始时间', "
        "end_time AS '结束时间', duration_seconds AS '学习时长(秒)' "
        "FROM study_sessions ORDER BY start_time DESC LIMIT 50",
        conn,
    )
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
    try:
        df_chat = pd.read_sql(
            "SELECT student_id AS '学号', question_id AS '题号', hint_strength AS '提示强度', "
            "pedagogical_intent AS '教学意图', hint_safety_status AS '安全状态', "
            "user_query AS '学生提问', ai_response AS '系统反馈', is_leaking_answer AS '是否泄露', "
            "leakage_score AS '泄露评分', rewrite_count AS '重写次数', leakage_reason AS '检测原因', "
            "created_at AS '交互时间' FROM interaction_logs ORDER BY created_at DESC LIMIT 50",
            conn,
        )
    except Exception:
        df_chat = pd.read_sql(
            "SELECT student_id AS '学号', question_id AS '题号', user_query AS '学生提问', "
            "ai_response AS '系统反馈', created_at AS '交互时间' "
            "FROM interaction_logs ORDER BY created_at DESC LIMIT 50",
            conn,
        )
    st.dataframe(df_chat, use_container_width=True)
    if not df_chat.empty:
        st.download_button(
            "📥 导出AI辅导监控记录 (CSV)",
            df_chat.to_csv(index=False).encode("utf-8-sig"),
            "ai_interaction_logs.csv",
            "text/csv",
            use_container_width=True,
        )
