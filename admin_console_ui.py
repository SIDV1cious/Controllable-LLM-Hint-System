import streamlit as st

from admin_course_management_ui import render_course_and_question_management_tab
from admin_dashboard_ui import render_learning_overview_dashboard
from admin_monitoring_ui import (
    render_interaction_monitoring_tab,
    render_login_logs_tab,
    render_study_duration_tab,
)
from admin_prompt_ui import render_prompt_configuration_tab
from experiment_admin_ui import render_experiment_analytics_dashboard

ADMIN_SECTIONS = [
    {
        "id": "overview",
        "label": "📊 数据概览",
        "renderer": render_learning_overview_dashboard,
    },
    {
        "id": "experiment",
        "label": "🧪 实验分析",
        "renderer": render_experiment_analytics_dashboard,
    },
    {
        "id": "login_logs",
        "label": "🕒 登录日志",
        "renderer": render_login_logs_tab,
    },
    {
        "id": "study_duration",
        "label": "⏱️ 学习时长追踪",
        "renderer": render_study_duration_tab,
    },
    {
        "id": "ai_monitoring",
        "label": "💬 AI辅导监控",
        "renderer": render_interaction_monitoring_tab,
    },
    {
        "id": "content_management",
        "label": "🛠️ 课程与题库管理",
        "renderer": render_course_and_question_management_tab,
    },
    {
        "id": "prompt_config",
        "label": "⚙️ 智能辅导大模型设置",
        "renderer": render_prompt_configuration_tab,
    },
]
ADMIN_SECTION_OPTIONS = [section["label"] for section in ADMIN_SECTIONS]
ADMIN_SECTION_BY_LABEL = {section["label"]: section for section in ADMIN_SECTIONS}


def _get_selected_admin_section() -> str:
    selected_section = st.session_state.get("admin_console_section", ADMIN_SECTION_OPTIONS[0])
    if selected_section not in ADMIN_SECTION_OPTIONS:
        selected_section = ADMIN_SECTION_OPTIONS[0]
        st.session_state["admin_console_section"] = selected_section
    return selected_section


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

    selected_section = _get_selected_admin_section()
    st.markdown(f"## {selected_section}")
    ADMIN_SECTION_BY_LABEL[selected_section]["renderer"]()
