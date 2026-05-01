import logging
import time

import pandas as pd
import streamlit as st
from sqlalchemy import text

BASE_COURSES = ["高等数学", "线性代数", "概率统计", "C语言"]


def _load_course_names(conn) -> list:
    try:
        custom_names = [r[0] for r in conn.execute(text("SELECT course_name FROM custom_courses")).fetchall()]
    except Exception as e:
        logging.error(f"Load courses error: {e}")
        custom_names = []
    return BASE_COURSES + [name for name in custom_names if name not in BASE_COURSES]


def _render_course_create_tab(conn):
    with st.form("add_course_form"):
        new_c_name = st.text_input("新课程名称")
        new_c_desc = st.text_input("课程简介描述")
        if st.form_submit_button("确认添加", type="primary", use_container_width=True):
            if new_c_name.strip() and new_c_desc.strip():
                try:
                    conn.execute(
                        text("INSERT INTO custom_courses (course_name, description) VALUES (:n, :d)"),
                        {"n": new_c_name.strip(), "d": new_c_desc.strip()},
                    )
                    conn.commit()
                    st.toast(f"课程《{new_c_name}》添加成功！", icon="✅")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.toast(f"添加失败: {e}", icon="❌")
            else:
                st.toast("请填写完整的课程信息！", icon="⚠️")


def _render_course_delete_tab(conn):
    with st.form("delete_course_form"):
        del_c_list = _load_course_names(conn)
        if del_c_list:
            del_c_name = st.selectbox("选择要下架的课程", del_c_list)
            if st.form_submit_button("确认删除 (将同步删除下属题目)", type="primary", use_container_width=True):
                conn.execute(text("DELETE FROM custom_courses WHERE course_name = :c"), {"c": del_c_name})
                conn.execute(text("DELETE FROM custom_questions WHERE category = :c"), {"c": del_c_name})
                conn.commit()
                st.toast(f"已彻底删除课程《{del_c_name}》！", icon="✅")
                time.sleep(0.5)
                st.rerun()
        else:
            st.info("暂无自定义课程可以删除。")
            st.form_submit_button("确认删除", disabled=True, use_container_width=True)


def _render_course_edit_tab(conn):
    try:
        edit_c_options = {r[0]: r for r in conn.execute(text("SELECT course_name, description FROM custom_courses")).fetchall()}
    except Exception as e:
        logging.error(f"Edit course load error: {e}")
        edit_c_options = {}

    if not edit_c_options:
        st.info("暂无自定义课程可以修改。")
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
                    conn.execute(
                        text("UPDATE custom_courses SET course_name = :new_n, description = :new_d WHERE course_name = :old_n"),
                        {"new_n": updated_c_name.strip(), "new_d": updated_c_desc.strip(), "old_n": selected_c_name},
                    )
                    if updated_c_name.strip() != selected_c_name:
                        conn.execute(
                            text("UPDATE custom_questions SET category = :new_n WHERE category = :old_n"),
                            {"new_n": updated_c_name.strip(), "old_n": selected_c_name},
                        )
                    conn.commit()
                    st.toast("课程修改成功！", icon="✅")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.toast(f"修改失败: {e}", icon="❌")
            else:
                st.toast("课程名称和描述不能为空！", icon="⚠️")


def _render_course_preview_tab(conn):
    try:
        df_custom_c = pd.read_sql(
            "SELECT course_name AS '课程名称', description AS '课程简介描述' FROM custom_courses",
            conn,
        )
        if not df_custom_c.empty:
            st.dataframe(df_custom_c, use_container_width=True)
        else:
            st.info("当前云端数据库中暂无任何自定义课程。")
    except Exception as e:
        st.warning(f"读取课程失败: {e}")


def _render_question_create_tab(conn, all_courses: list):
    with st.form("add_question_form"):
        q_category = st.selectbox("选择所属课程", all_courses)
        q_content = st.text_area("输入题目内容 (支持 LaTeX 格式)")
        if st.form_submit_button("确认录入题目", type="primary", use_container_width=True):
            if q_category and q_content.strip():
                try:
                    conn.execute(
                        text("INSERT INTO custom_questions (category, content) VALUES (:c, :t)"),
                        {"c": q_category, "t": q_content.strip()},
                    )
                    conn.commit()
                    st.toast("题目添加成功！", icon="✅")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.toast(f"题目添加失败: {e}", icon="❌")
            else:
                st.toast("请填写完整的题目内容！", icon="⚠️")


def _render_question_delete_tab(conn):
    with st.form("delete_question_form"):
        try:
            del_q_options = {
                f"[{r[1]}] {r[2]}... (内部ID:{r[0]})": r[0]
                for r in conn.execute(text("SELECT id, category, LEFT(content, 15) FROM custom_questions")).fetchall()
            }
        except Exception as e:
            logging.error(f"Load questions for delete error: {e}")
            del_q_options = {}

        if del_q_options:
            del_q_choice = st.selectbox("选择要删除的错误题目", list(del_q_options.keys()))
            if st.form_submit_button("确认删除该题", type="primary", use_container_width=True):
                conn.execute(text("DELETE FROM custom_questions WHERE id = :id"), {"id": del_q_options[del_q_choice]})
                conn.commit()
                st.toast("指定题目已永久删除！", icon="✅")
                time.sleep(0.5)
                st.rerun()
        else:
            st.info("暂无自定义题目可以删除。")
            st.form_submit_button("确认删除", disabled=True, use_container_width=True)


def _render_question_edit_tab(conn, all_courses: list):
    try:
        edit_q_options = {
            f"[{r[1]}] (内部ID:{r[0]}) {r[2][:20]}...": (r[0], r[1], r[2])
            for r in conn.execute(text("SELECT id, category, content FROM custom_questions")).fetchall()
        }
    except Exception as e:
        logging.error(f"Load questions for edit error: {e}")
        edit_q_options = {}

    if not edit_q_options:
        st.info("暂无自定义题目可以修改。")
        return

    edit_q_choice = st.selectbox("👇 第一步：选择需要修改的题目", list(edit_q_options.keys()), key="edit_q_select")
    selected_id, selected_cat, selected_content = edit_q_options[edit_q_choice]
    with st.form("edit_question_form"):
        new_category = st.selectbox("修改所属课程", all_courses, index=all_courses.index(selected_cat) if selected_cat in all_courses else 0)
        new_content = st.text_area("修改题目内容 (支持 LaTeX 格式)", value=selected_content, height=150)
        if st.form_submit_button("💾 保存修改", type="primary", use_container_width=True):
            if new_content.strip():
                try:
                    conn.execute(
                        text("UPDATE custom_questions SET category = :c, content = :t WHERE id = :id"),
                        {"c": new_category, "t": new_content.strip(), "id": selected_id},
                    )
                    conn.commit()
                    st.toast("题目修改成功！", icon="✅")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.toast(f"修改失败: {e}", icon="❌")
            else:
                st.toast("题目内容不能为空！", icon="⚠️")


def _render_question_preview_tab(conn):
    try:
        df_custom_q = pd.read_sql(
            "SELECT id AS '内部ID', category AS '所属课程', content AS '题目完整内容' FROM custom_questions ORDER BY id DESC",
            conn,
        )
        if not df_custom_q.empty:
            st.dataframe(df_custom_q, use_container_width=True)
        else:
            st.info("当前云端数据库中暂无任何自定义题目。")
    except Exception as e:
        st.warning(f"读取题库失败: {e}")


def render_course_and_question_management_tab(conn):
    st.subheader("📚 课程管理")
    t_c_add, t_c_del, t_c_edit, t_c_view = st.tabs(["➕ 录入新课程", "🗑️ 删除自定义课程", "✏️ 修改自定义课程", "👀 预览自定义课程"])
    with t_c_add:
        _render_course_create_tab(conn)
    with t_c_del:
        _render_course_delete_tab(conn)
    with t_c_edit:
        _render_course_edit_tab(conn)
    with t_c_view:
        _render_course_preview_tab(conn)

    st.divider()
    st.subheader("📝 题库管理")
    all_courses = _load_course_names(conn)
    t_add, t_del, t_edit, t_view = st.tabs(["➕ 录入新题目", "🗑️ 删除自定义题目", "✏️ 修改自定义题目", "👀 预览自定义题库"])
    with t_add:
        _render_question_create_tab(conn, all_courses)
    with t_del:
        _render_question_delete_tab(conn)
    with t_edit:
        _render_question_edit_tab(conn, all_courses)
    with t_view:
        _render_question_preview_tab(conn)
