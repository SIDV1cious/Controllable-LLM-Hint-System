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
    .block-container {
        max-width: 1220px;
        padding-top: 1.25rem;
        padding-bottom: 2rem;
    }

    h1, h2, h3 {
        color: #1f2937;
        letter-spacing: -0.02em;
    }

    div.stButton > button,
    div[data-testid="stDownloadButton"] > button {
        border-radius: 11px;
        font-weight: 650;
        border-color: #d7deea;
    }

    div[data-testid="stForm"],
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 14px;
        border-color: #dce3ee;
        box-shadow: 0 12px 30px rgba(31, 41, 55, 0.04);
    }

    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #f8fbff 0%, #eef5ff 100%);
        border: 1px solid #dbe7f5;
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: 0 10px 28px rgba(37, 99, 235, 0.06);
    }

    section[data-testid="stSidebar"] {
        background: #f8fafc;
        border-right: 1px solid #e5e7eb;
    }

    .course-card-note {
        min-height: 44px;
        color: #536075;
        font-size: 0.92rem;
        line-height: 1.55;
        margin: 0.35rem 0 0.85rem 0;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def apply_identity_page_layout():
    st.markdown(
        """
<style>
    .block-container {
        min-height: 100vh;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }

    .block-container > div:first-child {
        min-height: 100vh;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
    }

    .auth-page-title {
        text-align: center;
        margin: 0 0 1.35rem 0;
        color: #1f2937;
        font-size: clamp(2rem, 3vw, 2.85rem);
        font-weight: 800;
        letter-spacing: -0.04em;
    }

    @media (max-height: 760px) {
        .block-container {
            padding-top: 3rem !important;
            padding-bottom: 2rem !important;
        }

        .block-container > div:first-child {
            min-height: auto;
            justify-content: flex-start !important;
        }
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def render_course_assessment_card(course_name: str, course_desc: str, start_course_assessment_session):
    with st.container(border=True):
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
    st.markdown("<h1 style='text-align: center;'>🏫 课程学习大厅</h1>", unsafe_allow_html=True)
    st.write("请选择你要进行随堂测验的课程模块：")
    st.divider()
    base_courses = list_course_catalog()
    cols = st.columns(4)
    for idx, (course_name, course_desc) in enumerate(base_courses):
        with cols[idx % 4]:
            render_course_assessment_card(course_name, course_desc, start_course_assessment_session)
