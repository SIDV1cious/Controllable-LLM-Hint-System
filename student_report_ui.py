import logging

import streamlit as st
from sqlalchemy import bindparam, text

from database_service import get_database_engine
from hint_text_utils import format_math


def render_student_learning_report():
    st.markdown("<h1 style='text-align: center;'>📊 个人学情中心与错题记录</h1>", unsafe_allow_html=True)
    st.divider()
    engine = get_database_engine()
    with engine.connect() as conn:
        study_res = conn.execute(
            text("SELECT SUM(duration_seconds) FROM study_sessions WHERE username = :u"),
            {"u": st.session_state.current_user},
        ).fetchone()
        total_seconds = study_res[0] if study_res and study_res[0] else 0
        total_minutes = round(total_seconds / 60)

        ans_logs = conn.execute(
            text(
                "SELECT question_id, ai_response FROM interaction_logs "
                "WHERE student_id = :u AND user_query LIKE '【答案提交】%%'"
            ),
            {"u": st.session_state.current_user},
        ).fetchall()
        total_answered = len(ans_logs)
        total_correct = sum(1 for log in ans_logs if "正确" in str(log[1]) or "PASS" in str(log[1]))
        accuracy = round((total_correct / total_answered * 100), 1) if total_answered > 0 else 0.0

        wrong_qids = set()
        for log in ans_logs:
            if "错误" in str(log[1]) or "FAIL" in str(log[1]):
                try:
                    wrong_qids.add(int(log[0]))
                except Exception as e:
                    logging.error(f"Parse qid error: {e}")

    col1, col2, col3 = st.columns(3)
    col1.metric("⏱️ 累计专注学习", f"{total_minutes} 分钟")
    col2.metric("✅ 累计答提示", f"{total_correct} 题")
    col3.metric("🎯 历史平均正确率", f"{accuracy} %")

    st.markdown("---")
    st.subheader("📓 错题记录与智能辅导")
    if not wrong_qids:
        st.info("你目前没有任何错题记录")
        return

    db_ids = [int(qid) - 1000 for qid in wrong_qids]
    q_dict = {}
    if db_ids:
        with engine.connect() as conn:
            try:
                stmt = text(
                    "SELECT id, category, content FROM custom_questions WHERE id IN :ids"
                ).bindparams(bindparam("ids", expanding=True))
                res = conn.execute(stmt, {"ids": db_ids}).fetchall()
                q_dict = {1000 + r[0]: {"category": r[1], "content": r[2]} for r in res}
            except Exception as e:
                logging.error(f"Fetch wrong questions error: {e}")

    for qid in wrong_qids:
        if qid not in q_dict:
            continue

        q_data = q_dict[qid]
        with st.expander(f"[{q_data['category']}] 错题回顾 (题号: {qid})"):
            st.info(format_math(q_data["content"]))
            if qid in st.session_state.chat_histories and st.session_state.chat_histories[qid]:
                st.markdown("##### 💬 智能辅导记录")
                for message in st.session_state.chat_histories[qid]:
                    if message["role"] == "user":
                        st.markdown(f"**🧑‍🎓 你**: {message['content']}")
                    else:
                        st.markdown(f"**🤖 智能辅导员**: {message['content']}")
            else:
                st.caption("暂无针对此题的对话辅导记录。")
