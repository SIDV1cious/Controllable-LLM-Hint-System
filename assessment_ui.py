import streamlit as st

from hint_system_core import build_result_export, format_math, now_shanghai
from learning_platform_ui import render_assessment_integrity_warning
from controlled_hint_ui import render_controlled_hint_panel


def apply_results_dashboard_style():
    st.markdown(
        """
<style>
    .results-hero {
        border: 1px solid #dbe4f0;
        border-radius: 18px;
        padding: 18px 20px;
        margin-bottom: 1rem;
        background: linear-gradient(135deg, #f8fbff 0%, #eef6ff 100%);
        box-shadow: 0 18px 38px rgba(30, 64, 175, 0.06);
    }

    .results-title {
        font-size: 28px;
        font-weight: 800;
        color: #1f2937;
        line-height: 1.35;
        margin: 0 0 0.25rem 0;
    }

    .results-desc {
        color: #64748b;
        font-size: 14px;
        line-height: 1.6;
        margin: 0;
    }

    .review-panel-title {
        font-size: 18px;
        font-weight: 750;
        color: #1f2937;
        margin: 0 0 0.8rem 0;
    }

    .question-review-title {
        font-size: 17px;
        font-weight: 750;
        color: #1f2937;
        margin-bottom: 0.45rem;
    }

    .answer-line {
        color: #334155;
        font-size: 15px;
        line-height: 1.7;
        margin: 0.55rem 0 0.85rem 0;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def render_assessment_workspace():
    page = st.empty()

    with page.container():
        render_assessment_integrity_warning()

        idx = st.session_state.current_question_index
        total = len(st.session_state.quiz_queue)
        question = st.session_state.quiz_queue[idx]

        current_ans_key = f"ans_{idx}"
        if current_ans_key in st.session_state:
            st.session_state.user_answers[idx] = st.session_state[current_ans_key]

        st.markdown("### 🗂️ 题目列表")
        with st.container():
            cols_per_row = 10
            for row_start in range(0, total, cols_per_row):
                cols = st.columns(cols_per_row)
                for col_index in range(cols_per_row):
                    q_idx = row_start + col_index
                    if q_idx < total:
                        with cols[col_index]:
                            is_answered = bool(st.session_state.user_answers.get(q_idx, "").strip())
                            btn_type = "primary" if q_idx == idx else "secondary"
                            btn_label = f"{q_idx + 1} ✅" if is_answered else str(q_idx + 1)

                            if st.button(btn_label, key=f"nav_btn_{q_idx}", type=btn_type, use_container_width=True):
                                st.session_state.current_question_index = q_idx
                                st.rerun()

        st.divider()
        st.progress((idx + 1) / total, text=f"【{st.session_state.current_course}】 进度：{idx + 1} / {total}")
        st.markdown(f"### 第 {idx + 1} 题")
        st.info(format_math(question["content"]))

        st.markdown("#### ✍️ 你的解答")
        answer = st.text_area(
            "请输入你的答案（选择题请直接输入选项字母）：",
            value=st.session_state.user_answers.get(idx, ""),
            height=150,
            key=f"ans_{idx}",
        )
        st.session_state.user_answers[idx] = answer

        nav_cols = st.columns(2)
        with nav_cols[0]:
            if idx > 0 and st.button("⬅️ 上一题", use_container_width=True):
                st.session_state.current_question_index -= 1
                st.rerun()

        with nav_cols[1]:
            if idx < total - 1:
                if st.button("下一题 ➡️", use_container_width=True):
                    st.session_state.current_question_index += 1
                    st.rerun()
            else:
                if st.button("✅ 提交试卷", type="primary", use_container_width=True):
                    missing = [
                        str(answer_idx + 1)
                        for answer_idx in range(total)
                        if not st.session_state.user_answers.get(answer_idx, "").strip()
                    ]
                    if missing:
                        st.warning(f"⚠️ 第 {'、'.join(missing)} 题尚未作答，请完成后再提交。")
                    else:
                        st.session_state.is_grading = True
                        st.session_state.grading_started = False
                        st.session_state.page_mode = "grading"
                        st.rerun()


def render_automated_grading_screen(sidebar_slot, submit_answers_and_run_assessment):
    st.session_state.is_grading = True
    sidebar_slot.empty()

    st.markdown(
        """
<style>
section[data-testid="stSidebar"],
[data-testid="stSidebar"],
div[data-testid="stSidebarUserContent"] {
    display: none !important;
    width: 0 !important;
    min-width: 0 !important;
}

header[data-testid="stHeader"],
[data-testid="stHeader"] {
    display: none !important;
}

div[data-testid="stToolbar"],
[data-testid="stToolbar"] {
    display: none !important;
}

.block-container {
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
}

[data-testid="stAppViewContainer"] {
    margin-left: 0 !important;
}

.main, .main .block-container, section.main {
    padding: 0 !important;
    margin: 0 !important;
}

body {
    overflow: hidden !important;
}
</style>
<div style="height: 100vh; display: flex; align-items: center; justify-content: center;">
    <h2>🧠 系统正在阅卷中，请勿刷新或退出...</h2>
</div>
""",
        unsafe_allow_html=True,
    )

    if not st.session_state.grading_started:
        st.session_state.grading_started = True
        submit_answers_and_run_assessment()


def render_assessment_results_dashboard(record_learning_interaction):
    apply_results_dashboard_style()
    st.markdown(
        """
<div class="results-hero">
    <div class="results-title">📊 作答结果与智能辅导</div>
    <p class="results-desc">左侧复盘每一道题的判定结果，右侧查看题目详情并请求受控智能辅导。</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🔄 返回大厅开启新课程"):
        st.session_state.page_mode = "home"
        st.rerun()

    results = st.session_state.assessment_results
    if results:
        total_count = len(results)
        correct_count = sum(1 for item in results if item.get("is_correct"))
        wrong_count = total_count - correct_count
        accuracy = round(correct_count / total_count * 100, 1) if total_count else 0.0

        metric_cols = st.columns(4)
        metric_cols[0].metric("本次题数", total_count)
        metric_cols[1].metric("答对题数", correct_count)
        metric_cols[2].metric("待复盘错题", wrong_count)
        metric_cols[3].metric("正确率", f"{accuracy}%")

        st.download_button(
            "📥 导出本次测验结果",
            build_result_export(results).encode("utf-8-sig"),
            file_name=f"quiz_result_{now_shanghai():%Y%m%d_%H%M%S}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.divider()
    left_col, right_col = st.columns([0.95, 1.1], gap="large")
    with left_col:
        with st.container(border=True):
            st.markdown("<div class='review-panel-title'>题目复盘</div>", unsafe_allow_html=True)
            for index, result in enumerate(st.session_state.assessment_results):
                label = "✅ 正确" if result["is_correct"] else "❌ 错误"
                button_type = "primary" if st.session_state.review_question_index == index else "secondary"
                if st.button(
                    f"题 {index + 1} | {label}",
                    key=f"n_{index}",
                    type=button_type,
                    use_container_width=True,
                ):
                    st.session_state.review_question_index = index
                    st.rerun()

    with right_col:
        if st.session_state.review_question_index is None:
            with st.container(border=True):
                st.info("请先在左侧选择一道题，查看题目详情并请求智能辅导。")
            return

        review_index = st.session_state.review_question_index
        data = st.session_state.assessment_results[review_index]
        with st.container(border=True):
            st.markdown(
                f"<div class='question-review-title'>第 {review_index + 1} 题 · {'正确' if data['is_correct'] else '错误'}</div>",
                unsafe_allow_html=True,
            )
            st.info(format_math(data["question_data"]["content"]))
            st.markdown(
                f"<div class='answer-line'><strong>您的作答：</strong>{data['user_answer']}</div>",
                unsafe_allow_html=True,
            )
            st.divider()
            render_controlled_hint_panel(data, record_learning_interaction)
