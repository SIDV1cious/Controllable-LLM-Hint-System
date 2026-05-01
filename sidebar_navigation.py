import streamlit as st

from learning_session_service import clear_current_quiz_for_user


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
                    st.session_state.page_mode = "home"
                    st.rerun()

            if st.session_state.page_mode != "report":
                if st.button("📊 我的学情报告"):
                    st.session_state.page_mode = "report"
                    st.rerun()

        if st.button("🚪 退出登录"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
