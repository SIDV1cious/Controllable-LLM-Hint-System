from html import escape

import streamlit as st

from app_constants import PageMode
from controlled_hint_ui import render_controlled_hint_panel
from hint_system_core import build_result_export, format_math, now_shanghai
from learning_platform_ui import render_assessment_integrity_warning
from session_keys import SessionKey, answer_input, hint_safety_status, navigation_button, review_button
from session_state_manager import clear_active_assessment_state, navigate_to


def apply_results_dashboard_style():
    st.markdown(
        """
<style>
    .results-hero {
        border: 1px solid #dbe4f0;
        border-radius: 22px;
        padding: 20px 24px;
        margin-bottom: 1rem;
        background:
            linear-gradient(135deg, #f8fbff 0%, #eef6ff 100%),
            radial-gradient(circle at right top, rgba(255, 75, 75, 0.09), transparent 14rem);
        box-shadow: 0 18px 42px rgba(30, 64, 175, 0.07);
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
        display: inline-flex;
        align-items: center;
        gap: 8px;
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

    .safety-summary {
        border: 1px solid #dbe7f5;
        border-radius: 16px;
        padding: 14px 16px;
        margin: 1rem 0 0.4rem 0;
        background: linear-gradient(135deg, #f8fbff 0%, #ffffff 100%);
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.04);
    }

    .safety-summary-title {
        color: #1f2937;
        font-size: 16px;
        font-weight: 800;
        margin-bottom: 4px;
    }

    .safety-summary-desc {
        color: #64748b;
        font-size: 13px;
        line-height: 1.55;
        margin-bottom: 10px;
    }

    .safety-summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
        gap: 10px;
    }

    .safety-summary-item {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 10px 12px;
        background: linear-gradient(135deg, #ffffff 0%, #f8fbff 100%);
        box-shadow: 0 8px 18px rgba(15, 23, 42, 0.035);
    }

    .safety-summary-head {
        display: inline-flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        width: 100%;
        color: #334155;
        font-size: 13px;
        font-weight: 750;
        margin-bottom: 6px;
    }

    .safety-summary-badge {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 3px 9px;
        font-size: 12px;
        font-weight: 700;
        white-space: nowrap;
    }

    .safety-summary-safe {
        color: #166534;
        background: #dcfce7;
        border: 1px solid #bbf7d0;
    }

    .safety-summary-rewrite {
        color: #9a3412;
        background: #ffedd5;
        border: 1px solid #fed7aa;
    }

    .safety-summary-detail {
        color: #64748b;
        font-size: 12px;
        line-height: 1.55;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def _render_safety_summary(results: list):
    cards = []
    for index, result in enumerate(results, start=1):
        qid = result["question_data"]["id"]
        status = st.session_state.get(hint_safety_status(qid))
        if not status:
            continue

        label = escape(status.get("label", "已检测"))
        detail = escape(status.get("detail", "暂无检测细节"))
        badge_class = "safety-summary-rewrite" if "重写" in label else "safety-summary-safe"
        cards.append(
            f"""
<div class="safety-summary-item">
    <div class="safety-summary-head">
        <span>题 {index}</span>
        <span class="safety-summary-badge {badge_class}">{label}</span>
    </div>
    <div class="safety-summary-detail">{detail}</div>
</div>
            """
        )

    if not cards:
        return

    st.markdown(
        f"""
<div class="safety-summary">
    <div class="safety-summary-title">本轮智能辅导答案泄露检测状态</div>
    <div class="safety-summary-desc">已生成智能辅导的题目会在这里汇总检测结论，便于复盘提示是否经过安全过滤。</div>
    <div class="safety-summary-grid">{''.join(cards)}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_assessment_workspace():
    page = st.empty()

    with page.container():
        render_assessment_integrity_warning()

        idx = st.session_state[SessionKey.CURRENT_QUESTION_INDEX]
        total = len(st.session_state[SessionKey.QUIZ_QUEUE])
        question = st.session_state[SessionKey.QUIZ_QUEUE][idx]

        current_ans_key = answer_input(idx)
        if current_ans_key in st.session_state:
            st.session_state[SessionKey.USER_ANSWERS][idx] = st.session_state[current_ans_key]

        st.markdown("### 🗂️ 题目列表")
        with st.container():
            cols_per_row = 10
            for row_start in range(0, total, cols_per_row):
                cols = st.columns(cols_per_row)
                for col_index in range(cols_per_row):
                    q_idx = row_start + col_index
                    if q_idx < total:
                        with cols[col_index]:
                            is_answered = bool(st.session_state[SessionKey.USER_ANSWERS].get(q_idx, "").strip())
                            btn_type = "primary" if q_idx == idx else "secondary"
                            btn_label = f"{q_idx + 1} ✅" if is_answered else str(q_idx + 1)

                            if st.button(
                                btn_label, key=navigation_button(q_idx), type=btn_type, use_container_width=True
                            ):
                                st.session_state[SessionKey.CURRENT_QUESTION_INDEX] = q_idx
                                st.rerun()

        st.divider()
        st.progress(
            (idx + 1) / total, text=f"【{st.session_state[SessionKey.CURRENT_COURSE]}】 进度：{idx + 1} / {total}"
        )
        st.markdown(f"### 第 {idx + 1} 题")
        st.info(format_math(question["content"]))

        st.markdown("#### ✍️ 你的解答")
        answer = st.text_area(
            "请输入你的答案（选择题请直接输入选项字母）：",
            value=st.session_state[SessionKey.USER_ANSWERS].get(idx, ""),
            height=150,
            key=current_ans_key,
        )
        st.session_state[SessionKey.USER_ANSWERS][idx] = answer

        nav_cols = st.columns(2)
        with nav_cols[0]:
            if idx > 0 and st.button("⬅️ 上一题", use_container_width=True):
                st.session_state[SessionKey.CURRENT_QUESTION_INDEX] -= 1
                st.rerun()

        with nav_cols[1]:
            if idx < total - 1:
                if st.button("下一题 ➡️", use_container_width=True):
                    st.session_state[SessionKey.CURRENT_QUESTION_INDEX] += 1
                    st.rerun()
            else:
                if st.button("✅ 提交试卷", type="primary", use_container_width=True):
                    missing = [
                        str(answer_idx + 1)
                        for answer_idx in range(total)
                        if not st.session_state[SessionKey.USER_ANSWERS].get(answer_idx, "").strip()
                    ]
                    if missing:
                        st.warning(f"⚠️ 第 {'、'.join(missing)} 题尚未作答，请完成后再提交。")
                    else:
                        st.session_state[SessionKey.IS_GRADING] = True
                        st.session_state[SessionKey.GRADING_STARTED] = False
                        navigate_to(PageMode.GRADING)
                        st.rerun()


def render_automated_grading_screen(sidebar_slot, submit_answers_and_run_assessment):
    st.session_state[SessionKey.IS_GRADING] = True
    if sidebar_slot is not None:
        sidebar_slot.empty()

    st.markdown(
        """
<style>
section[data-testid="stSidebar"],
[data-testid="stSidebar"] {
    display: none !important;
    width: 0 !important;
    min-width: 0 !important;
}

[data-testid="stAppViewContainer"] {
    margin-left: 0 !important;
}

.grading-state-shell {
    min-height: 68vh;
    display: flex;
    align-items: center;
    justify-content: center;
}
</style>
<div class="grading-state-shell">
    <h2>🧠 系统正在阅卷中，请勿刷新或退出...</h2>
</div>
""",
        unsafe_allow_html=True,
    )

    if not st.session_state[SessionKey.GRADING_STARTED]:
        st.session_state[SessionKey.GRADING_STARTED] = True
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
        clear_active_assessment_state()
        navigate_to(PageMode.HOME)
        st.rerun()

    results = st.session_state[SessionKey.ASSESSMENT_RESULTS]
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
        _render_safety_summary(results)

    st.divider()
    left_col, right_col = st.columns([0.95, 1.1], gap="large")
    with left_col:
        with st.container(border=True):
            st.markdown("<div class='review-panel-title'>题目复盘</div>", unsafe_allow_html=True)
            for index, result in enumerate(st.session_state[SessionKey.ASSESSMENT_RESULTS]):
                label = "✅ 正确" if result["is_correct"] else "❌ 错误"
                button_type = "primary" if st.session_state[SessionKey.REVIEW_QUESTION_INDEX] == index else "secondary"
                if st.button(
                    f"题 {index + 1} | {label}",
                    key=review_button(index),
                    type=button_type,
                    use_container_width=True,
                ):
                    st.session_state[SessionKey.REVIEW_QUESTION_INDEX] = index
                    st.rerun()

    with right_col:
        if st.session_state[SessionKey.REVIEW_QUESTION_INDEX] is None:
            with st.container(border=True):
                st.info("👈🏻请先在左侧选择一道题，查看题目详情并请求智能辅导。")
            return

        review_index = st.session_state[SessionKey.REVIEW_QUESTION_INDEX]
        data = st.session_state[SessionKey.ASSESSMENT_RESULTS][review_index]
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
