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


def render_admin_console():
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
    tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "📊 可视化数据大屏",
            "🧪 实验分析",
            "🕒 登录日志",
            "⏱️ 学习时长追踪",
            "💬 AI辅导监控",
            "🛠️ 课程与题库管理",
            "⚙️ 智能辅导大模型设置",
        ]
    )

    engine = get_database_engine()
    with engine.connect() as conn:
        with tab0:
            render_learning_overview_dashboard(conn)
        with tab1:
            render_experiment_analytics_dashboard(conn)
        with tab2:
            render_login_logs_tab(conn)
        with tab3:
            render_study_duration_tab(conn)
        with tab4:
            render_interaction_monitoring_tab(conn)
        with tab5:
            render_course_and_question_management_tab()
        with tab6:
            render_prompt_configuration_tab()
