import streamlit as st

from admin_console_ui import ADMIN_SECTION_OPTIONS
from app_constants import PageMode, RouteAction, UserRole
from learning_session_service import clear_current_quiz_for_user
from session_keys import SessionKey
from session_state_manager import begin_route_transition, clear_active_assessment_state, reset_login_session
from ui_texts import ADMIN_DASHBOARD_TRANSITION_MESSAGE, HOME_TRANSITION_MESSAGE, REPORT_TRANSITION_MESSAGE


def render_sidebar_navigation(sidebar_slot):
    if st.session_state[SessionKey.PAGE_MODE] == PageMode.GRADING:
        sidebar_slot.empty()
        return

    with sidebar_slot.container():
        role_label = "管理员" if st.session_state[SessionKey.USER_ROLE] == UserRole.ADMIN else "学生"
        st.markdown(
            f"""
<div class="sidebar-user-card">
    <div class="sidebar-user-label">当前账号</div>
    <div class="sidebar-user-name"><code>{st.session_state[SessionKey.CURRENT_USER]}</code>（{role_label}）</div>
</div>
            """,
            unsafe_allow_html=True,
        )

        if st.session_state[SessionKey.USER_ROLE] == UserRole.STUDENT:
            if st.session_state[SessionKey.PAGE_MODE] != PageMode.HOME:
                if st.button("🏠 返回大厅"):
                    clear_current_quiz_for_user(st.session_state[SessionKey.CURRENT_USER])
                    clear_active_assessment_state()
                    begin_route_transition(RouteAction.RETURN_HOME, HOME_TRANSITION_MESSAGE, icon="🏠")
                    st.rerun()

            if st.session_state[SessionKey.PAGE_MODE] != PageMode.REPORT:
                if st.button("📊 我的学情报告"):
                    begin_route_transition(RouteAction.OPEN_REPORT, REPORT_TRANSITION_MESSAGE, icon="📊")
                    st.rerun()

        if st.session_state[SessionKey.USER_ROLE] == UserRole.ADMIN:
            if st.session_state[SessionKey.PAGE_MODE] == PageMode.ADMIN:
                if st.session_state.get("admin_console_section") not in ADMIN_SECTION_OPTIONS:
                    st.session_state["admin_console_section"] = ADMIN_SECTION_OPTIONS[0]
                st.radio(
                    "教务管理导航",
                    ADMIN_SECTION_OPTIONS,
                    key="admin_console_section",
                )
            elif st.button("🎓 管理端控制台"):
                begin_route_transition(
                    RouteAction.OPEN_ADMIN_DASHBOARD,
                    ADMIN_DASHBOARD_TRANSITION_MESSAGE,
                    icon="🎓",
                )
                st.rerun()

        if st.button("🚪 退出登录"):
            if st.session_state[SessionKey.USER_ROLE] == UserRole.STUDENT:
                clear_current_quiz_for_user(st.session_state[SessionKey.CURRENT_USER])
            reset_login_session()
            st.rerun()
