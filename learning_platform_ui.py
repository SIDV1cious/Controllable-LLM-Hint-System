import streamlit as st

from app_constants import APP_TITLE, UserRole
from course_repository import list_course_catalog
from session_state_manager import set_authenticated_user


def render_assessment_integrity_warning():
    st.markdown(
        """
<div style="padding-top: 34px; margin-top: 10px; overflow: visible;">
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

    html,
    body {
        overflow-y: auto !important;
        overflow-x: hidden !important;
        max-height: none !important;
    }

    body {
        height: auto !important;
    }

    .stApp {
        min-height: 100vh !important;
        overflow-x: hidden !important;
        overflow-y: visible !important;
    }

    .main,
    section.main,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {
        overflow: visible !important;
        max-height: none !important;
    }

    .block-container {
        max-width: 1220px;
        min-height: auto !important;
        height: auto !important;
        max-height: none !important;
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

    .section-kicker {
        color: var(--brand-blue);
        font-size: 0.82rem;
        font-weight: 850;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.25rem;
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

    div[data-testid="stForm"] {
        backdrop-filter: blur(12px);
        box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
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


def render_course_assessment_card(course_name: str, course_desc: str, start_course_assessment_session):
    with st.container(border=True):
        st.markdown("<div class='course-card-eyebrow'>COURSE MODULE</div>", unsafe_allow_html=True)
        st.markdown(f"### {course_name}")
        st.markdown(f"<div class='course-card-note'>{course_desc}</div>", unsafe_allow_html=True)
        if st.button(f"进入《{course_name}》测验", key=f"btn_{course_name}", use_container_width=True):
            start_course_assessment_session(course_name)


def render_identity_access_page(
    authenticate_learning_user,
    register_learning_user,
    record_login_event,
    restore_user_learning_state,
):
    apply_identity_page_layout()
    st.markdown(f"<h1 class='auth-page-title'>{APP_TITLE}</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        tab_l, tab_r = st.tabs(["🔑 登录", "📝 注册"])
        with tab_l:
            with st.form("login_form"):
                u_in = st.text_input("账号/学号")
                p_in = st.text_input("密码", type="password")
                submitted = st.form_submit_button("进入系统", type="primary", use_container_width=True)
                if submitted:
                    is_auth, role = authenticate_learning_user(u_in.strip(), p_in.strip())
                    if is_auth:
                        set_authenticated_user(u_in.strip(), role)
                        record_login_event(u_in.strip())
                        if role != UserRole.ADMIN:
                            restore_user_learning_state(u_in.strip())
                        st.rerun()
                    else:
                        st.error("账号或密码错误")
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


def render_course_selection_portal(start_course_assessment_session):
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
            render_course_assessment_card(course_name, course_desc, start_course_assessment_session)
