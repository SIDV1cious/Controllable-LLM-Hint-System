import logging

import streamlit as st

from admin_console_ui import render_admin_console
from app_constants import APP_TITLE, PageMode, UserRole
from assessment_ui import (
    render_assessment_results_dashboard,
    render_assessment_workspace,
    render_automated_grading_screen,
)
from learning_platform_ui import (
    apply_platform_visual_theme,
    render_course_selection_portal,
    render_identity_access_page,
)
from learning_session_service import (
    authenticate_learning_user,
    record_learning_interaction,
    record_login_event,
    register_learning_user,
    restore_user_learning_state,
    start_course_assessment_session,
    submit_answers_and_run_assessment,
)
from session_keys import SessionKey
from session_state_manager import init_session_state
from sidebar_navigation import render_sidebar_navigation
from student_report_ui import render_student_learning_report

logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


def run_controlled_hint_system():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_session_state()
    apply_platform_visual_theme()

    if not st.session_state[SessionKey.LOGGED_IN]:
        render_identity_access_page(
            authenticate_learning_user,
            register_learning_user,
            record_login_event,
            restore_user_learning_state,
        )
        st.stop()

    sidebar_slot = st.sidebar.empty()
    render_sidebar_navigation(sidebar_slot)

    if (
        st.session_state[SessionKey.PAGE_MODE] == PageMode.ADMIN
        and st.session_state[SessionKey.USER_ROLE] == UserRole.ADMIN
    ):
        render_admin_console()

    elif (
        st.session_state[SessionKey.PAGE_MODE] == PageMode.HOME
        and st.session_state[SessionKey.USER_ROLE] == UserRole.STUDENT
    ):
        render_course_selection_portal(start_course_assessment_session)

    elif st.session_state[SessionKey.PAGE_MODE] == PageMode.QUIZ:
        render_assessment_workspace()

    elif st.session_state[SessionKey.PAGE_MODE] == PageMode.GRADING:
        render_automated_grading_screen(sidebar_slot, submit_answers_and_run_assessment)

    elif st.session_state[SessionKey.PAGE_MODE] == PageMode.RESULTS:
        render_assessment_results_dashboard(record_learning_interaction)

    elif (
        st.session_state[SessionKey.PAGE_MODE] == PageMode.REPORT
        and st.session_state[SessionKey.USER_ROLE] == UserRole.STUDENT
    ):
        render_student_learning_report()
