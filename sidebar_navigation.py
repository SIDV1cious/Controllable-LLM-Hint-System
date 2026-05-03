import streamlit as st

from app_constants import PageMode, UserRole
from learning_session_service import clear_current_quiz_for_user
from session_keys import SessionKey
from session_state_manager import clear_active_assessment_state, navigate_to, reset_login_session


def render_sidebar_navigation(sidebar_slot):
    if st.session_state[SessionKey.PAGE_MODE] == PageMode.GRADING:
        sidebar_slot.empty()
        return

    with sidebar_slot.container():
        role_label = "管理员" if st.session_state[SessionKey.USER_ROLE] == UserRole.ADMIN else "学生"
        st.write(f"当前账号: `{st.session_state[SessionKey.CURRENT_USER]}` ({role_label})")

        if st.session_state[SessionKey.USER_ROLE] == UserRole.STUDENT:
            if st.session_state[SessionKey.PAGE_MODE] != PageMode.HOME:
                if st.button("🏠 返回大厅"):
                    clear_current_quiz_for_user(st.session_state[SessionKey.CURRENT_USER])
                    clear_active_assessment_state()
                    st.session_state[SessionKey.ROUTE_LOADING_MESSAGE] = "正在返回课程学习大厅..."
                    navigate_to(PageMode.HOME)
                    st.rerun()

            if st.session_state[SessionKey.PAGE_MODE] != PageMode.REPORT:
                if st.button("📊 我的学情报告"):
                    st.session_state[SessionKey.ROUTE_LOADING_MESSAGE] = "正在整理个人学情报告..."
                    navigate_to(PageMode.REPORT)
                    st.rerun()

        if st.button("🚪 退出登录"):
            if st.session_state[SessionKey.USER_ROLE] == UserRole.STUDENT:
                clear_current_quiz_for_user(st.session_state[SessionKey.CURRENT_USER])
            reset_login_session()
            st.rerun()
