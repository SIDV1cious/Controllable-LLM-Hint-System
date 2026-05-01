import streamlit as st

from learning_session_service import clear_current_quiz_for_user
from session_state_manager import navigate_to, reset_login_session


def render_sidebar_navigation(sidebar_slot):
    if st.session_state.page_mode == "grading":
        sidebar_slot.empty()
        return

    with sidebar_slot.container():
        role_label = "管理员" if st.session_state.user_role == "admin" else "学生"
        st.write(f"当前账号: `{st.session_state.current_user}` ({role_label})")

        if st.session_state.user_role == "student":
            if st.session_state.page_mode != "home":
                if st.button("🏠 返回大厅"):
                    clear_current_quiz_for_user(st.session_state.current_user)
                    navigate_to("home")
                    st.rerun()

            if st.session_state.page_mode != "report":
                if st.button("📊 我的学情报告"):
                    navigate_to("report")
                    st.rerun()

        if st.button("🚪 退出登录"):
            reset_login_session()
            st.rerun()
