import time

import streamlit as st

from app_constants import APP_TITLE, RouteAction, UserRole
from course_repository import list_course_catalog
from session_state_manager import begin_route_transition, set_authenticated_user
from ui_feedback import ROUTE_TRANSITION_SECONDS, render_full_page_transition
from ui_texts import (
    ADMIN_LOGIN_TRANSITION_MESSAGE,
    COURSE_TRANSITION_MESSAGE,
    STUDENT_LOGIN_TRANSITION_MESSAGE,
)

LOGIN_ERROR_KEY = "identity_login_error"
LOGIN_PENDING_KEY = "identity_login_pending"
LOGIN_PASSWORD_KEY = "identity_login_password"
LOGIN_USERNAME_KEY = "identity_login_username"


def render_assessment_integrity_warning():
    st.markdown(
        """
<div style="padding-top: 10px; margin-top: 0; overflow: visible;">
<div role="alert" style="
    display: flex;
    align-items: center;
    gap: 14px;
    box-sizing: border-box;
    margin: 0.25rem 0 1.4rem 0;
    padding: 18px 22px 18px 22px;
    border-radius: 10px;
    background: #fff8db;
    color: #6b4e00;
    font-size: 16px;
    line-height: 1.75;
    overflow: visible;
">
    <span style="display: inline-flex; align-items: center; justify-content: center; flex: 0 0 24px; width: 24px; height: 24px; margin-top: 0; font-size: 21px; line-height: 1; transform: translateY(-2px); font-family: 'Segoe UI Emoji', 'Segoe UI Symbol', sans-serif;">⚠️</span>
    <span style="display: flex; align-items: center; min-height: 24px; padding-top: 0; font-size: 16px; line-height: 1.45; font-weight: 600;">考试进行中，请勿刷新网页或退出登录，否则未提交的作答记录将会丢失！</span>
</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def apply_platform_visual_theme():
    st.markdown(
        """
<style>
    :root {
        --app-bg: #f6f8fc;
        --card-bg: rgba(255, 255, 255, 0.92);
        --card-border: #dbe4f0;
        --text-main: #1f2937;
        --text-muted: #64748b;
        --brand-red: #ff4b4b;
        --brand-blue: #2563eb;
        --soft-blue: #eef6ff;
        --surface-subtle: rgba(248, 251, 255, 0.86);
        --panel-min-height: 360px;
        --shadow-soft: 0 18px 42px rgba(15, 23, 42, 0.07);
        --shadow-card: 0 12px 30px rgba(30, 64, 175, 0.06);
    }

    .stApp {
        background:
            radial-gradient(circle at 12% 8%, rgba(37, 99, 235, 0.08), transparent 28rem),
            radial-gradient(circle at 88% 18%, rgba(255, 75, 75, 0.07), transparent 24rem),
            linear-gradient(180deg, #fbfdff 0%, var(--app-bg) 100%);
    }

    [data-testid="stHeader"] {
        background: transparent !important;
        box-shadow: none !important;
    }

    [data-testid="stToolbarActions"],
    [data-testid="stHeaderActionElements"],
    [data-testid="stMainMenu"],
    [data-testid="stAppDeployButton"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    #MainMenu,
    footer {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        min-height: 0 !important;
        max-height: 0 !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    .block-container {
        max-width: 1220px;
        padding-top: 1.55rem !important;
        padding-bottom: 2rem !important;
    }

    h1, h2, h3 {
        color: var(--text-main);
        letter-spacing: -0.02em;
    }

    h1 {
        font-weight: 850;
    }

    p, label, span {
        text-rendering: geometricPrecision;
    }

    div.stButton > button,
    div[data-testid="stDownloadButton"] > button {
        border-radius: 11px;
        font-weight: 650;
        border-color: #d7deea;
        transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
    }

    div.stButton > button:hover,
    div[data-testid="stDownloadButton"] > button:hover {
        border-color: #bfd0e8;
        box-shadow: 0 10px 22px rgba(15, 23, 42, 0.08);
        transform: translateY(-1px);
    }

    div.stButton > button[kind="primary"],
    div[data-testid="stFormSubmitButton"] button[kind="primary"] {
        box-shadow: 0 12px 24px rgba(255, 75, 75, 0.18);
    }

    div[data-testid="stForm"],
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 18px;
        border-color: var(--card-border);
        background: var(--card-bg);
        box-shadow: var(--shadow-card);
    }

    div[data-testid="stAlert"] {
        border-radius: 14px;
        border: 1px solid #dbe7f5;
        box-shadow: 0 8px 18px rgba(15, 23, 42, 0.035);
    }

    div[data-testid="stDataFrame"] {
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.035);
    }

    div[data-testid="stPlotlyChart"] {
        min-height: var(--panel-min-height);
        border-radius: 16px;
        padding: 0.15rem 0.25rem;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.58), rgba(248, 251, 255, 0.72));
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-baseweb="select"] {
        border-radius: 12px !important;
    }

    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stTextArea"] textarea:focus {
        border-color: rgba(37, 99, 235, 0.55) !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.10) !important;
    }

    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #ffffff 0%, #eef5ff 100%);
        border: 1px solid #dbe7f5;
        border-radius: 18px;
        padding: 14px 16px;
        box-shadow: var(--shadow-card);
    }

    [data-testid="stMetric"] label {
        color: var(--text-muted);
        font-weight: 700;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        border-right: 1px solid #e5e7eb;
    }

    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.65rem;
    }

    section[data-testid="stSidebar"] label {
        color: #334155;
        font-weight: 700;
    }

    section[data-testid="stSidebar"] div.stButton > button {
        min-height: 2.6rem;
        justify-content: flex-start;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.76);
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] {
        display: grid;
        gap: 0.15rem;
    }

    .sidebar-user-card {
        padding: 12px 12px;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        background: linear-gradient(135deg, #ffffff, #f8fbff);
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.035);
        margin: 0.35rem 0 0.55rem 0;
    }

    .sidebar-user-label {
        color: var(--text-muted);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }

    .sidebar-user-name {
        color: var(--text-main);
        font-size: 14px;
        font-weight: 700;
        line-height: 1.45;
    }

    .page-hero {
        border: 1px solid var(--card-border);
        border-radius: 22px;
        padding: 20px 24px;
        margin: 0 0 1.1rem 0;
        background:
            linear-gradient(135deg, rgba(255, 255, 255, 0.94), rgba(238, 246, 255, 0.92)),
            radial-gradient(circle at right top, rgba(255, 75, 75, 0.10), transparent 14rem);
        box-shadow: var(--shadow-soft);
    }

    .course-lobby-hero {
        margin-top: clamp(0.45rem, 1.6vh, 1.15rem);
    }

    .page-hero-title {
        margin: 0;
        color: var(--text-main);
        font-size: clamp(1.9rem, 3vw, 2.8rem);
        font-weight: 850;
        line-height: 1.2;
        letter-spacing: -0.045em;
    }

    .page-hero-subtitle {
        margin: 0.55rem 0 0 0;
        color: var(--text-muted);
        font-size: 0.98rem;
        line-height: 1.65;
    }

    .course-card-note {
        min-height: 44px;
        color: #536075;
        font-size: 0.92rem;
        line-height: 1.55;
        margin: 0.35rem 0 0.85rem 0;
    }

    .course-selection-guide {
        font-size: 18px;
        font-weight: 700;
        line-height: 1.6;
        margin: 0.75rem 0 0.9rem 0;
        color: var(--text-main);
    }

    .course-card-eyebrow {
        color: var(--brand-blue);
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        margin-bottom: 0.15rem;
    }

    .app-section-heading {
        margin: 1rem 0 0.75rem 0;
    }

    .app-section-kicker {
        color: var(--brand-blue);
        font-size: 0.76rem;
        font-weight: 850;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.18rem;
    }

    .app-section-title {
        color: var(--text-main);
        font-size: clamp(1.35rem, 2.1vw, 1.85rem);
        font-weight: 820;
        line-height: 1.3;
        letter-spacing: -0.035em;
        margin: 0;
    }

    .ui-empty-state {
        display: flex;
        align-items: center;
        gap: 14px;
        min-height: 92px;
        padding: 18px 20px;
        border: 1px solid #dbe7f5;
        border-radius: 18px;
        background:
            linear-gradient(135deg, rgba(255,255,255,0.92), rgba(238,246,255,0.88)),
            radial-gradient(circle at right top, rgba(37,99,235,0.08), transparent 14rem);
        box-shadow: var(--shadow-card);
    }

    .ui-empty-state.compact {
        min-height: 132px;
        justify-content: flex-start;
        margin: 0.2rem 0 0.1rem 0;
        background:
            linear-gradient(135deg, rgba(255,255,255,0.94), rgba(241,247,255,0.9)),
            radial-gradient(circle at left top, rgba(37,99,235,0.08), transparent 12rem);
        box-shadow: none;
    }

    .ui-empty-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 42px;
        height: 42px;
        border-radius: 14px;
        background: #eef6ff;
        font-size: 22px;
    }

    .ui-empty-title {
        color: var(--text-main);
        font-size: 16px;
        font-weight: 800;
        line-height: 1.35;
        margin-bottom: 3px;
    }

    .ui-empty-message {
        color: var(--text-muted);
        font-size: 13px;
        line-height: 1.6;
    }

    .admin-section-heading {
        display: flex;
        align-items: center;
        gap: 14px;
        margin: 0;
        padding: 0;
        border: 0;
        background: transparent;
        box-shadow: none;
    }

    .admin-section-title {
        color: var(--text-main);
        font-size: clamp(1.35rem, 2vw, 1.75rem);
        font-weight: 820;
        letter-spacing: -0.035em;
        line-height: 1.25;
        margin: 0;
    }

    .admin-section-subtitle {
        color: var(--text-muted);
        font-size: 13px;
        line-height: 1.55;
        margin-top: 2px;
    }

    .admin-panel-title {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        color: var(--text-main);
        font-size: clamp(1.05rem, 1.55vw, 1.38rem);
        font-weight: 820;
        line-height: 1.35;
        letter-spacing: -0.03em;
        margin: 0.08rem 0 0.75rem 0;
    }

    .admin-panel-title-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2em;
    }

    .admin-chart-panel {
        min-height: 380px;
    }

    .admin-table-panel {
        min-height: 300px;
    }

    .admin-section-action-button {
        display: flex;
        justify-content: flex-end;
        align-items: center;
    }

    .stApp:has(#route-page-admin) [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #d7e3f3;
        border-radius: 18px;
        background:
            linear-gradient(135deg, rgba(255,255,255,0.88), rgba(248,251,255,0.72)),
            radial-gradient(circle at right top, rgba(37,99,235,0.045), transparent 14rem);
        box-shadow: 0 14px 34px rgba(15, 23, 42, 0.035);
    }

    .stApp:has(#route-page-admin) .js-plotly-plot .modebar {
        display: none !important;
    }

    .stApp:has(#route-page-auth):not(:has(#route-page-home)):not(:has(#route-page-report))
    [data-stale="true"],
    .stApp:has(#route-page-auth):not(:has(#route-page-home)):not(:has(#route-page-report))
    [data-stale="true"] * {
        opacity: 1 !important;
        filter: none !important;
    }

    .stApp:has(#route-page-auth):not(:has(#route-page-home)):not(:has(#route-page-report))
    div[data-testid="stFormSubmitButton"] button:disabled {
        opacity: 1 !important;
        filter: none !important;
    }

    .section-kicker {
        color: var(--brand-blue);
        font-size: 0.82rem;
        font-weight: 850;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.25rem;
    }

    .system-transition-shell {
        min-height: 68vh;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .system-transition-message {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: auto;
        margin: 0 auto;
        text-align: center;
        color: var(--text-main);
        font-size: clamp(1.75rem, 3vw, 2.25rem);
        font-weight: 700;
        line-height: 1.3;
        letter-spacing: -0.03em;
    }

    .system-transition-icon {
        display: inline-block;
        margin-right: 10px;
        transform-origin: center;
    }

    .system-transition-icon.is-spinning {
        animation: identity-spin 1.05s linear infinite;
    }

</style>
        """,
        unsafe_allow_html=True,
    )


def apply_identity_page_layout():
    st.markdown(
        """
<style>
    .auth-page-title {
        text-align: center;
        margin: clamp(4rem, 18vh, 9rem) 0 1.35rem 0;
        color: #1f2937;
        font-size: clamp(2rem, 3vw, 2.85rem);
        font-weight: 850;
        letter-spacing: -0.04em;
    }

    div[data-testid="stTabs"] {
        margin-bottom: 0.7rem;
    }

    .stApp:has(#route-page-auth) div[data-testid="stTabs"],
    .stApp:has(#route-page-auth) div[data-testid="stTabs"] *,
    .stApp:has(#route-page-auth) button[data-testid="stTab"],
    .stApp:has(#route-page-auth) button[data-testid="stTab"] *,
    .stApp:has(#route-page-auth) button[role="tab"],
    .stApp:has(#route-page-auth) button[role="tab"] *,
    .stApp:has(#route-page-auth) button[role="tab"]:disabled,
    .stApp:has(#route-page-auth) button[role="tab"]:disabled * {
        opacity: 1 !important;
        filter: none !important;
    }

    .stApp:has(#route-page-auth) button[role="tab"][aria-selected="true"],
    .stApp:has(#route-page-auth) button[role="tab"][aria-selected="true"] * {
        color: var(--brand-red) !important;
        -webkit-text-fill-color: var(--brand-red) !important;
        font-weight: 750 !important;
    }

    .stApp:has(#route-page-auth) button[role="tab"]:not([aria-selected="true"]),
    .stApp:has(#route-page-auth) button[role="tab"]:not([aria-selected="true"]) * {
        color: #475569 !important;
        -webkit-text-fill-color: #475569 !important;
        font-weight: 650 !important;
    }

    div[data-testid="stForm"] {
        backdrop-filter: blur(12px);
        box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
    }

    .identity-loading-icon {
        display: inline-block;
        margin-right: 10px;
        animation: identity-spin 1.05s linear infinite;
        transform-origin: center;
    }

    .identity-loading-shell {
        min-height: 68vh;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .identity-loading-message {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: auto;
        margin: 0 auto;
        text-align: center;
    }

    @keyframes identity-spin {
        to {
            transform: rotate(360deg);
        }
    }

    @media (max-height: 760px) {
        .auth-page-title {
            margin-top: 3rem;
        }
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def render_course_assessment_card(course_name: str, course_desc: str):
    with st.container(border=True):
        st.markdown("<div class='course-card-eyebrow'>COURSE MODULE</div>", unsafe_allow_html=True)
        st.markdown(f"### {course_name}")
        st.markdown(f"<div class='course-card-note'>{course_desc}</div>", unsafe_allow_html=True)
        if st.button(f"进入《{course_name}》测验", key=f"btn_{course_name}", use_container_width=True):
            begin_route_transition(
                RouteAction.START_QUIZ,
                COURSE_TRANSITION_MESSAGE,
                icon="📚",
                payload={"course_name": course_name},
            )
            st.rerun()


def _login_transition_message_for(username: str) -> str:
    if username.strip().lower() == UserRole.ADMIN:
        return ADMIN_LOGIN_TRANSITION_MESSAGE
    return STUDENT_LOGIN_TRANSITION_MESSAGE


def render_identity_loading_page(message: str = STUDENT_LOGIN_TRANSITION_MESSAGE) -> None:
    render_full_page_transition(message, icon="🔄", route_id="route-page-auth-loading", spin_icon=True)


def render_identity_access_page(
    authenticate_learning_user,
    register_learning_user,
    record_login_event,
    prepare_student_login_state,
):
    def process_pending_login() -> None:
        username = st.session_state.get(LOGIN_USERNAME_KEY, "").strip()
        password = st.session_state.get(LOGIN_PASSWORD_KEY, "").strip()

        if not username or not password:
            st.session_state[LOGIN_ERROR_KEY] = "请输入账号和密码"
            st.session_state.pop(LOGIN_PENDING_KEY, None)
            st.rerun()

        is_auth, role = authenticate_learning_user(username, password)
        if not is_auth:
            st.session_state[LOGIN_ERROR_KEY] = "账号或密码错误"
            st.session_state[LOGIN_PASSWORD_KEY] = ""
            st.session_state.pop(LOGIN_PENDING_KEY, None)
            st.rerun()

        st.session_state.pop(LOGIN_ERROR_KEY, None)
        st.session_state.pop(LOGIN_PENDING_KEY, None)
        st.session_state.pop(LOGIN_PASSWORD_KEY, None)
        set_authenticated_user(username, role)
        record_login_event(username)
        if role != UserRole.ADMIN:
            prepare_student_login_state(username)
        st.rerun()

    apply_identity_page_layout()

    if st.session_state.get(LOGIN_PENDING_KEY):
        pending_username = st.session_state.get(LOGIN_USERNAME_KEY, "")
        render_identity_loading_page(_login_transition_message_for(pending_username))
        time.sleep(ROUTE_TRANSITION_SECONDS)
        process_pending_login()
        st.stop()

    st.markdown('<div id="route-page-auth"></div>', unsafe_allow_html=True)
    st.markdown(f"<h1 class='auth-page-title'>{APP_TITLE}</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        tab_l, tab_r = st.tabs(["🔑 登录", "📝 注册"])
        with tab_l:
            with st.form("login_form"):
                st.text_input("账号/学号", key=LOGIN_USERNAME_KEY)
                st.text_input("密码", type="password", key=LOGIN_PASSWORD_KEY)
                login_submitted = st.form_submit_button(
                    "进入系统",
                    type="primary",
                    use_container_width=True,
                )
                if login_submitted:
                    username = st.session_state.get(LOGIN_USERNAME_KEY, "").strip()
                    password = st.session_state.get(LOGIN_PASSWORD_KEY, "").strip()
                    if not username or not password:
                        st.session_state[LOGIN_ERROR_KEY] = "请输入账号和密码"
                    else:
                        st.session_state.pop(LOGIN_ERROR_KEY, None)
                        st.session_state[LOGIN_PENDING_KEY] = True
                    st.rerun()
                if st.session_state.get(LOGIN_ERROR_KEY):
                    st.error(st.session_state[LOGIN_ERROR_KEY])
        with tab_r:
            with st.form("register_form"):
                ru = st.text_input("新学号")
                rp = st.text_input("新密码", type="password")
                rp2 = st.text_input("确认密码", type="password")
                reg_submitted = st.form_submit_button("立即注册", type="primary", use_container_width=True)
                if reg_submitted:
                    if ru.strip() and rp.strip() == rp2.strip() and register_learning_user(ru.strip(), rp.strip()):
                        st.toast("注册成功！请切换到登录页面。", icon="✅")
                    else:
                        st.error("注册失败（学号已被占用或密码不一致）。")


def render_course_selection_portal():
    st.markdown('<div id="route-page-home"></div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="page-hero course-lobby-hero">
    <div class="section-kicker">LEARNING PORTAL</div>
    <h1 class="page-hero-title">🏫 课程学习大厅</h1>
    <p class="page-hero-subtitle">选择课程模块后进入随堂测验，系统会记录作答情况并提供受控智能辅导。</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='course-selection-guide'>👇🏻请选择你要进行随堂测验的课程模块</div>",
        unsafe_allow_html=True,
    )
    base_courses = list_course_catalog()
    cols = st.columns(4)
    for idx, (course_name, course_desc) in enumerate(base_courses):
        with cols[idx % 4]:
            render_course_assessment_card(course_name, course_desc)
