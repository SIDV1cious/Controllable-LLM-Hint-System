import streamlit as st

from app_constants import ChatRole
from hint_text_utils import format_math
from learning_session_service import restore_user_learning_state
from session_keys import SessionKey
from student_report_repository import (
    fetch_answer_logs,
    fetch_question_details_by_public_ids,
    fetch_total_study_seconds,
)
from student_report_service import calculate_learning_summary, extract_wrong_question_ids
from ui_feedback import render_route_loading_overlay

REPORT_HISTORY_LOADED_PREFIX = "report_history_loaded_for_"


def render_student_learning_report():
    st.markdown(
        """
<div class="page-hero">
    <div class="section-kicker">LEARNING PROFILE</div>
    <h1 class="page-hero-title">📊 个人学情中心与错题记录</h1>
    <p class="page-hero-subtitle">汇总个人学习时长、历史正确率与错题复盘，帮助你追踪知识掌握情况。</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    username = st.session_state[SessionKey.CURRENT_USER]
    report_history_key = f"{REPORT_HISTORY_LOADED_PREFIX}{username}"
    route_loading_passes = int(st.session_state.get(SessionKey.ROUTE_LOADING_PASSES, 0) or 0)
    route_loading_active = bool(st.session_state.get(SessionKey.ROUTE_LOADING_ACTIVE)) or route_loading_passes > 0
    route_loading_message = st.session_state.get(SessionKey.ROUTE_LOADING_MESSAGE)
    needs_history_restore = not st.session_state.get(report_history_key)
    should_show_loading_overlay = route_loading_active or needs_history_restore
    loading_overlay_slot = st.empty()
    if should_show_loading_overlay:
        render_route_loading_overlay(loading_overlay_slot, route_loading_message or "正在整理个人学情报告...")

    def finish_loading_transition() -> None:
        if route_loading_active:
            remaining_passes = max(route_loading_passes, 1) - 1
            st.session_state[SessionKey.ROUTE_LOADING_PASSES] = remaining_passes
            st.session_state[SessionKey.ROUTE_LOADING_ACTIVE] = remaining_passes > 0
            if remaining_passes <= 0:
                st.session_state[SessionKey.ROUTE_LOADING_MESSAGE] = None
            st.rerun()
        if needs_history_restore:
            st.session_state[SessionKey.ROUTE_LOADING_PASSES] = 0
            st.session_state[SessionKey.ROUTE_LOADING_ACTIVE] = False
            st.session_state[SessionKey.ROUTE_LOADING_MESSAGE] = None
            st.rerun()

    if needs_history_restore:
        restore_user_learning_state(username)
        st.session_state[report_history_key] = True

    total_seconds = fetch_total_study_seconds(username)
    answer_logs = fetch_answer_logs(username)
    summary = calculate_learning_summary(total_seconds, answer_logs)
    wrong_qids = extract_wrong_question_ids(answer_logs)

    col1, col2, col3 = st.columns(3)
    col1.metric("⏱️ 累计专注学习", f"{summary['total_minutes']} 分钟")
    col2.metric("✅ 累计答提示", f"{summary['total_correct']} 题")
    col3.metric("🎯 历史平均正确率", f"{summary['accuracy']} %")

    st.markdown("---")
    st.subheader("📓 错题记录与智能辅导")
    if not wrong_qids:
        finish_loading_transition()
        st.info("你目前没有任何错题记录")
        return

    q_dict = fetch_question_details_by_public_ids(wrong_qids)

    for qid in wrong_qids:
        if qid not in q_dict:
            continue

        q_data = q_dict[qid]
        with st.expander(f"[{q_data['category']}] 错题回顾 (题号: {qid})"):
            st.info(format_math(q_data["content"]))
            chat_histories = st.session_state[SessionKey.CHAT_HISTORIES]
            if qid in chat_histories and chat_histories[qid]:
                st.markdown("##### 💬 智能辅导记录")
                for message in chat_histories[qid]:
                    if message["role"] == ChatRole.USER:
                        st.markdown(f"**🧑‍🎓 你**: {message['content']}")
                    else:
                        st.markdown(f"**🤖 智能辅导员**: {message['content']}")
            else:
                st.caption("暂无针对此题的对话辅导记录。")

    finish_loading_transition()
