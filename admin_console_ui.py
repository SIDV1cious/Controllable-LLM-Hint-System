import streamlit as st

from admin_course_management_ui import render_course_and_question_management_tab
from admin_dashboard_ui import render_learning_overview_dashboard
from admin_monitoring_ui import (
    render_interaction_monitoring_tab,
    render_login_logs_tab,
    render_study_duration_tab,
)
from admin_prompt_ui import render_prompt_configuration_tab
from database_service import get_database_engine
from experiment_admin_ui import render_experiment_analytics_dashboard

ADMIN_SECTION_OPTIONS = [
    "📊 可视化数据大屏",
    "🧪 实验分析",
    "🕒 登录日志",
    "⏱️ 学习时长追踪",
    "💬 AI辅导监控",
    "🛠️ 课程与题库管理",
    "⚙️ 智能辅导大模型设置",
]


def render_admin_console():
    st.markdown('<div id="route-page-admin"></div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="page-hero">
    <div class="section-kicker">ADMIN OBSERVABILITY</div>
    <h1 class="page-hero-title">👨‍💻 教务管理看板与控制台</h1>
    <p class="page-hero-subtitle">集中查看学习行为、实验指标、智能辅导安全状态与题库配置，支撑毕业设计系统展示与实验分析。</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    selected_section = st.radio(
        "管理模块",
        ADMIN_SECTION_OPTIONS,
        horizontal=True,
        label_visibility="collapsed",
        key="admin_console_section",
    )

    if selected_section == "🛠️ 课程与题库管理":
        render_course_and_question_management_tab()
        return

    if selected_section == "⚙️ 智能辅导大模型设置":
        render_prompt_configuration_tab()
        return

    with get_database_engine().connect() as conn:
        if selected_section == "📊 可视化数据大屏":
            render_learning_overview_dashboard(conn)
        elif selected_section == "🧪 实验分析":
            render_experiment_analytics_dashboard(conn)
        elif selected_section == "🕒 登录日志":
            render_login_logs_tab(conn)
        elif selected_section == "⏱️ 学习时长追踪":
            render_study_duration_tab(conn)
        elif selected_section == "💬 AI辅导监控":
            render_interaction_monitoring_tab(conn)
