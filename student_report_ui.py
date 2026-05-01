import streamlit as st

from app_constants import ChatRole
from hint_text_utils import format_math
from session_keys import SessionKey
from student_report_repository import (
    fetch_answer_logs,
    fetch_question_details_by_public_ids,
    fetch_total_study_seconds,
)
from student_report_service import calculate_learning_summary, extract_wrong_question_ids


def render_student_learning_report():
    st.markdown("<h1 style='text-align: center;'>📊 个人学情中心与错题记录</h1>", unsafe_allow_html=True)
    st.divider()
    username = st.session_state[SessionKey.CURRENT_USER]
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
