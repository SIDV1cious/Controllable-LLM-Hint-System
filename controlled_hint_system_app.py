import logging
import time

import streamlit as st

from admin_console_ui import ADMIN_SECTION_OPTIONS, render_admin_console
from app_constants import APP_TITLE, PageMode, RouteAction, UserRole, should_render_sidebar_for_page
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
    clear_current_quiz_for_user,
    prepare_course_assessment_session,
    record_learning_interaction,
    record_login_event,
    register_learning_user,
    submit_answers_and_run_assessment,
)
from session_keys import SessionKey
from session_state_manager import clear_route_transition, init_session_state, navigate_to, repair_session_state
from sidebar_navigation import render_sidebar_navigation
from student_report_ui import render_student_learning_report
from ui_feedback import ROUTE_TRANSITION_SECONDS, render_full_page_transition

logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


def _render_pending_route_transition(prepare_course_assessment_session_fn):
    action = st.session_state.get(SessionKey.ROUTE_LOADING_ACTION)
    message = st.session_state.get(SessionKey.ROUTE_LOADING_MESSAGE) or "正在加载页面..."
    icon = st.session_state.get(SessionKey.ROUTE_LOADING_ICON) or "🔄"
    payload = st.session_state.get(SessionKey.ROUTE_LOADING_PAYLOAD) or {}

    render_full_page_transition(message, icon=icon, route_id="route-page-transition", spin_icon=icon == "🔄")
    time.sleep(ROUTE_TRANSITION_SECONDS)

    clear_route_transition()
    if action == RouteAction.START_QUIZ:
        course_name = payload.get("course_name")
        if not course_name or not prepare_course_assessment_session_fn(course_name):
            navigate_to(PageMode.HOME)
    elif action == RouteAction.OPEN_REPORT:
        navigate_to(PageMode.REPORT)
    elif action == RouteAction.OPEN_ADMIN_DASHBOARD:
        st.session_state["admin_console_section"] = ADMIN_SECTION_OPTIONS[0]
        navigate_to(PageMode.ADMIN)
    elif action == RouteAction.RETURN_HOME:
        navigate_to(PageMode.HOME)
    else:
        navigate_to(PageMode.ADMIN if st.session_state[SessionKey.USER_ROLE] == UserRole.ADMIN else PageMode.HOME)

    st.rerun()


def run_controlled_hint_system():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_session_state()
    repair_session_state()
    apply_platform_visual_theme()

    main_content_slot = st.empty()

    if not st.session_state[SessionKey.LOGGED_IN]:
        with main_content_slot.container():
            render_identity_access_page(
                authenticate_learning_user,
                register_learning_user,
                record_login_event,
                clear_current_quiz_for_user,
            )
        st.stop()

    if st.session_state[SessionKey.PAGE_MODE] == PageMode.TRANSITION:
        with main_content_slot.container():
            _render_pending_route_transition(prepare_course_assessment_session)
        st.stop()

    sidebar_slot = None
    if should_render_sidebar_for_page(
        st.session_state[SessionKey.PAGE_MODE],
        st.session_state[SessionKey.USER_ROLE],
    ):
        sidebar_slot = st.sidebar.empty()
        render_sidebar_navigation(sidebar_slot)

    with main_content_slot.container():
        if (
            st.session_state[SessionKey.PAGE_MODE] == PageMode.ADMIN
            and st.session_state[SessionKey.USER_ROLE] == UserRole.ADMIN
        ):
            render_admin_console()

        elif (
            st.session_state[SessionKey.PAGE_MODE] == PageMode.HOME
            and st.session_state[SessionKey.USER_ROLE] == UserRole.STUDENT
        ):
            render_course_selection_portal()

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

        else:
            st.session_state[SessionKey.PAGE_MODE] = (
                PageMode.ADMIN if st.session_state[SessionKey.USER_ROLE] == UserRole.ADMIN else PageMode.HOME
            )
            st.rerun()


if __name__ == "__main__":
    run_controlled_hint_system()
