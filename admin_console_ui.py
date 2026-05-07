import streamlit as st

from admin_course_management_ui import render_course_and_question_management_tab
from admin_dashboard_ui import render_learning_overview_dashboard
from admin_monitoring_ui import (
    render_interaction_monitoring_tab,
    render_login_logs_tab,
    render_study_duration_tab,
)
from admin_observability_repository import clear_admin_observability_cache
from admin_prompt_ui import render_prompt_configuration_tab
from experiment_admin_ui import render_experiment_analytics_dashboard
from experiment_analytics_service import clear_experiment_analytics_cache

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
ADMIN_SECTION_DESCRIPTIONS = {
    "📊 数据概览": "查看系统活跃趋势、课程学习时长、正确率和答案泄露控制指标。",
    "🧪 实验分析": "围绕提示强度、教学意图、泄露检测与自动重写汇总实验数据。",
    "🕒 登录日志": "追踪学生账号登录记录，用于观察系统使用活跃度。",
    "⏱️ 学习时长追踪": "按课程汇总学习会话时长，辅助分析学生投入情况。",
    "💬 AI辅导监控": "抽查智能辅导请求、模型回复与安全控制字段。",
    "🛠️ 课程与题库管理": "维护课程模块与自定义题目，支持答辩演示和扩展测试。",
    "⚙️ 智能辅导大模型设置": "配置系统提示词，统一控制受控提示生成策略。",
}


def _get_selected_admin_section() -> str:
    selected_section = st.session_state.get("admin_console_section", ADMIN_SECTION_OPTIONS[0])
    if selected_section not in ADMIN_SECTION_OPTIONS:
        selected_section = ADMIN_SECTION_OPTIONS[0]
        st.session_state["admin_console_section"] = selected_section
    return selected_section


def _render_admin_section_heading(selected_section: str) -> None:
    heading_col, refresh_col = st.columns([0.78, 0.22])
    with heading_col:
        st.markdown(
            f"""
<div class="admin-section-heading">
    <div>
        <div class="app-section-kicker">CURRENT MODULE</div>
        <h2 class="admin-section-title">{selected_section}</h2>
        <div class="admin-section-subtitle">{ADMIN_SECTION_DESCRIPTIONS[selected_section]}</div>
    </div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with refresh_col:
        st.markdown('<div class="admin-refresh-action-spacer"></div>', unsafe_allow_html=True)
        if st.button(
            "🔄 刷新数据",
            help="清空管理端统计缓存，并重新读取最新看板数据。",
            use_container_width=True,
        ):
            clear_admin_observability_cache()
            clear_experiment_analytics_cache()
            st.toast("管理端统计数据已刷新", icon="🔄")
            st.rerun()


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
    _render_admin_section_heading(selected_section)
    ADMIN_SECTION_BY_LABEL[selected_section]["renderer"]()
