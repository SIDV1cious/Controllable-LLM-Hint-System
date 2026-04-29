import logging

import streamlit as st

from app_core import format_math, generate_controlled_hint
from math_comp import math_input


QUICK_HELP_REQUESTS = [
    ("提示下一步", "请只提示我下一步应该怎么思考，不要给出答案。"),
    ("检查错误", "请帮我指出当前作答最可能错在哪里，但不要直接给最终答案。"),
    ("只给思路", "请只给解题思路和关键概念提醒，避免泄露答案。"),
    ("复习知识点", "请总结这道题涉及的知识点，并给我一个复习方向。"),
]


def apply_tutoring_style():
    st.markdown(
        """
<style>
    .tutoring-title {
        font-size: 20px;
        font-weight: 700;
        line-height: 1.55;
        color: #1f2937;
        margin: 0 0 0.35rem 0;
    }

    .tutoring-subtitle {
        color: #64748b;
        font-size: 14px;
        line-height: 1.55;
        margin-bottom: 0.85rem;
    }

    .quick-request-label {
        font-size: 15px;
        font-weight: 700;
        color: #334155;
        margin: 0.55rem 0 0.45rem 0;
    }

    .composer-guide {
        font-size: 18px;
        font-weight: 700;
        line-height: 1.6;
        margin: 0.55rem 0 0.65rem 0;
        color: #1f2937;
    }

    .tutoring-divider {
        height: 1px;
        background: linear-gradient(90deg, #e5e7eb, rgba(229, 231, 235, 0));
        margin: 0.85rem 0;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def _normalize_history(history: list):
    if not history:
        history.append({"role": "assistant", "content": "请求智能辅导"})
        return

    for message in history:
        if message.get("role") == "assistant" and message.get("content") == "智能辅导":
            message["content"] = "请求智能辅导"


def _render_chat_history(history: list):
    for message in history:
        with st.chat_message(message["role"]):
            if message.get("role") == "assistant" and message.get("content") == "请求智能辅导":
                st.markdown(
                    "<div style='font-size: 20px; font-weight: 700; line-height: 1.55;'>请求智能辅导</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(format_math(message["content"]))


def render_tutoring_panel(data: dict, log_interaction):
    apply_tutoring_style()

    qid = data["question_data"]["id"]
    history = st.session_state.chat_histories.setdefault(qid, [])
    _normalize_history(history)

    st.markdown("<div class='tutoring-title'>请求智能辅导</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='tutoring-subtitle'>系统会先生成启发式提示，再进行答案泄露检测与必要重写。</div>",
        unsafe_allow_html=True,
    )
    _render_chat_history(history)

    composer_input_key = f"composer_input_{qid}"
    composer_reset_key = f"composer_reset_{qid}"
    math_widget_version_key = f"math_widget_version_{qid}"

    if composer_input_key not in st.session_state:
        st.session_state[composer_input_key] = ""

    if composer_reset_key not in st.session_state:
        st.session_state[composer_reset_key] = False

    if math_widget_version_key not in st.session_state:
        st.session_state[math_widget_version_key] = 0

    if st.session_state[composer_reset_key]:
        st.session_state[composer_input_key] = ""
        st.session_state[math_widget_version_key] += 1
        st.session_state[composer_reset_key] = False

    st.markdown("<div class='tutoring-divider'></div>", unsafe_allow_html=True)
    st.markdown("<div class='quick-request-label'>快捷请求</div>", unsafe_allow_html=True)
    quick_cols = st.columns(len(QUICK_HELP_REQUESTS))
    for quick_index, (quick_label, quick_prompt) in enumerate(QUICK_HELP_REQUESTS):
        with quick_cols[quick_index]:
            if st.button(quick_label, key=f"quick_help_{qid}_{quick_index}", use_container_width=True):
                history.append({"role": "user", "content": quick_prompt})
                st.session_state[composer_input_key] = ""
                st.session_state[composer_reset_key] = True
                st.rerun()

    st.markdown(
        "<div class='composer-guide'>👇🏻请在下方输入智能辅导提示词</div>",
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        composer_value = math_input(
            default_value=st.session_state.get(composer_input_key, ""),
            key=f"react_math_{qid}_{st.session_state[math_widget_version_key]}",
        )

        if composer_value is not None:
            st.session_state[composer_input_key] = composer_value

    send_col1, send_col2 = st.columns([5, 1])
    with send_col2:
        if st.button("发送", key=f"send_help_{qid}", type="primary", use_container_width=True):
            query = st.session_state.get(composer_input_key, "").strip()
            if query:
                history.append({"role": "user", "content": query})
                st.session_state[composer_reset_key] = True
                st.rerun()
            else:
                st.warning("请输入辅导问题后再发送。")

    if history and history[-1]["role"] == "user":
        with st.chat_message("assistant"):
            last_query = history[-1]["content"]
            try:
                with st.spinner("正在生成智能辅导并进行答案泄露检测....."):
                    controlled = generate_controlled_hint(
                        data["question_data"],
                        data["user_answer"],
                        data["is_correct"],
                        last_query,
                    )
                final = controlled["hint"]
                st.markdown(format_math(final))
                if controlled["rewrite_count"] > 0:
                    st.caption(f"已自动重写 {controlled['rewrite_count']} 次，以降低答案泄露风险。")
                history.append({"role": "assistant", "content": final})
                log_interaction(
                    qid,
                    f"【辅导】{last_query}",
                    final,
                    leak=controlled["is_leaking"],
                    leakage_score=controlled["leakage_score"],
                    rewrite_count=controlled["rewrite_count"],
                    leakage_reason=controlled["leakage_reason"],
                )
            except Exception as exc:
                logging.error(f"Controlled hint generation error: {exc}")
                fallback = "这道题我们先不急着看答案。你可以先指出题目中最关键的条件是什么，再想一想它对应哪个定义或公式？"
                st.markdown(fallback)
                history.append({"role": "assistant", "content": fallback})
                log_interaction(qid, f"【辅导】{last_query}", fallback, leak=0)
