import pandas as pd
import streamlit as st

from admin_content_repository import (
    create_custom_course,
    create_custom_question,
    delete_course_and_questions,
    delete_custom_question,
    fetch_custom_course_records,
    fetch_question_delete_options,
    fetch_question_edit_options,
    fetch_question_preview_records,
    list_all_course_names,
    update_course_and_question_category,
    update_custom_question,
)
from ui_feedback import render_empty_state, show_error, show_success, show_warning


def _load_course_names() -> list:
    try:
        return list_all_course_names()
    except Exception:
        return ["高等数学", "线性代数", "概率统计", "C语言"]


def _render_course_create_tab():
    with st.form("add_course_form"):
        new_c_name = st.text_input("新课程名称")
        new_c_desc = st.text_input("课程简介描述")
        if st.form_submit_button("确认添加", type="primary", use_container_width=True):
            if new_c_name.strip() and new_c_desc.strip():
                try:
                    create_custom_course(new_c_name.strip(), new_c_desc.strip())
                    show_success(f"课程《{new_c_name}》添加成功！")
                    st.rerun()
                except Exception as e:
                    show_error(f"添加失败: {e}")
            else:
                show_warning("请填写完整的课程信息！")


def _render_course_delete_tab():
    with st.form("delete_course_form"):
        del_c_list = _load_course_names()
        if del_c_list:
            del_c_name = st.selectbox("选择要下架的课程", del_c_list)
            if st.form_submit_button("确认删除 (将同步删除下属题目)", type="primary", use_container_width=True):
                delete_course_and_questions(del_c_name)
                show_success(f"已彻底删除课程《{del_c_name}》！")
                st.rerun()
        else:
            render_empty_state("暂无自定义课程可以删除。", title="课程列表为空", icon="📚")
            st.form_submit_button("确认删除", disabled=True, use_container_width=True)


def _render_course_edit_tab():
    try:
        edit_c_options = {record[0]: record for record in fetch_custom_course_records()}
    except Exception:
        edit_c_options = {}

    if not edit_c_options:
        render_empty_state("暂无自定义课程可以修改。", title="课程列表为空", icon="📚")
        return

    edit_c_choice = st.selectbox("👇 第一步：选择需要修改的课程", list(edit_c_options.keys()), key="edit_c_select")
    selected_c_name, selected_c_desc = edit_c_options[edit_c_choice]
    with st.form("edit_course_form"):
        st.write("👇 第二步：在下方直接编辑并保存")
        updated_c_name = st.text_input("修改课程名称", value=selected_c_name)
        updated_c_desc = st.text_input("修改课程简介描述", value=selected_c_desc)
        if st.form_submit_button("💾 保存修改", type="primary", use_container_width=True):
            if updated_c_name.strip() and updated_c_desc.strip():
                try:
                    update_course_and_question_category(
                        selected_c_name,
                        updated_c_name.strip(),
                        updated_c_desc.strip(),
                    )
                    show_success("课程修改成功！")
                    st.rerun()
                except Exception as e:
                    show_error(f"修改失败: {e}")
            else:
                show_warning("课程名称和描述不能为空！")


def _render_course_preview_tab():
    try:
        df_custom_c = pd.DataFrame(
            fetch_custom_course_records(),
            columns=["课程名称", "课程简介描述"],
        )
        if not df_custom_c.empty:
            st.dataframe(df_custom_c, use_container_width=True, hide_index=True)
        else:
            render_empty_state("当前云端数据库中暂无任何自定义课程。", title="暂无自定义课程", icon="📚")
    except Exception as e:
        st.warning(f"读取课程失败: {e}")


def _render_question_create_tab(all_courses: list):
    with st.form("add_question_form"):
        q_category = st.selectbox("选择所属课程", all_courses)
        q_content = st.text_area("输入题目内容 (支持 LaTeX 格式)")
        if st.form_submit_button("确认录入题目", type="primary", use_container_width=True):
            if q_category and q_content.strip():
                try:
                    create_custom_question(q_category, q_content.strip())
                    show_success("题目添加成功！")
                    st.rerun()
                except Exception as e:
                    show_error(f"题目添加失败: {e}")
            else:
                show_warning("请填写完整的题目内容！")


def _render_question_delete_tab():
    with st.form("delete_question_form"):
        try:
            del_q_options = fetch_question_delete_options()
        except Exception:
            del_q_options = {}

        if del_q_options:
            del_q_choice = st.selectbox("选择要删除的错误题目", list(del_q_options.keys()))
            if st.form_submit_button("确认删除该题", type="primary", use_container_width=True):
                delete_custom_question(del_q_options[del_q_choice])
                show_success("指定题目已永久删除！")
                st.rerun()
        else:
            render_empty_state("暂无自定义题目可以删除。", title="题库列表为空", icon="📝")
            st.form_submit_button("确认删除", disabled=True, use_container_width=True)


def _render_question_edit_tab(all_courses: list):
    try:
        edit_q_options = fetch_question_edit_options()
    except Exception:
        edit_q_options = {}

    if not edit_q_options:
        render_empty_state("暂无自定义题目可以修改。", title="题库列表为空", icon="📝")
        return

    edit_q_choice = st.selectbox("👇 第一步：选择需要修改的题目", list(edit_q_options.keys()), key="edit_q_select")
    selected_id, selected_cat, selected_content = edit_q_options[edit_q_choice]
    with st.form("edit_question_form"):
        new_category = st.selectbox(
            "修改所属课程", all_courses, index=all_courses.index(selected_cat) if selected_cat in all_courses else 0
        )
        new_content = st.text_area("修改题目内容 (支持 LaTeX 格式)", value=selected_content, height=150)
        if st.form_submit_button("💾 保存修改", type="primary", use_container_width=True):
            if new_content.strip():
                try:
                    update_custom_question(selected_id, new_category, new_content.strip())
                    show_success("题目修改成功！")
                    st.rerun()
                except Exception as e:
                    show_error(f"修改失败: {e}")
            else:
                show_warning("题目内容不能为空！")


def _render_question_preview_tab():
    try:
        df_custom_q = pd.DataFrame(
            fetch_question_preview_records(),
            columns=["内部ID", "所属课程", "题目完整内容"],
        )
        if not df_custom_q.empty:
            st.dataframe(df_custom_q, use_container_width=True, hide_index=True)
        else:
            render_empty_state("当前云端数据库中暂无任何自定义题目。", title="暂无自定义题目", icon="📝")
    except Exception as e:
        st.warning(f"读取题库失败: {e}")


def render_course_and_question_management_tab():
    st.markdown(
        "<div class='app-section-heading'><h3 class='app-section-title'>📚 课程管理</h3></div>", unsafe_allow_html=True
    )
    t_c_add, t_c_del, t_c_edit, t_c_view = st.tabs(
        ["➕ 录入新课程", "🗑️ 删除自定义课程", "✏️ 修改自定义课程", "👀 预览自定义课程"]
    )
    with t_c_add:
        _render_course_create_tab()
    with t_c_del:
        _render_course_delete_tab()
    with t_c_edit:
        _render_course_edit_tab()
    with t_c_view:
        _render_course_preview_tab()

    st.divider()
    st.markdown(
        "<div class='app-section-heading'><h3 class='app-section-title'>📝 题库管理</h3></div>", unsafe_allow_html=True
    )
    all_courses = _load_course_names()
    t_add, t_del, t_edit, t_view = st.tabs(
        ["➕ 录入新题目", "🗑️ 删除自定义题目", "✏️ 修改自定义题目", "👀 预览自定义题库"]
    )
    with t_add:
        _render_question_create_tab(all_courses)
    with t_del:
        _render_question_delete_tab()
    with t_edit:
        _render_question_edit_tab(all_courses)
    with t_view:
        _render_question_preview_tab()
