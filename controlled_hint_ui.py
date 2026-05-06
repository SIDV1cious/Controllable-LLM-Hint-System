from html import escape

import streamlit as st

from app_constants import ChatRole, format_tutoring_query
from app_errors import log_exception
from hint_system_core import format_math, generate_controlled_hint
from math_comp import math_input
from session_keys import (
    SessionKey,
    composer_input,
    composer_reset,
    hint_safety_status,
    hint_strength,
    math_widget,
    math_widget_version,
    pending_pedagogical_intent,
    quick_help_button,
    send_help_button,
)
from ui_texts import (
    DEFAULT_PEDAGOGICAL_INTENT,
    HINT_STRENGTH_OPTIONS,
    LEGACY_TUTORING_TITLE,
    PEDAGOGICAL_QUICK_REQUESTS,
    TUTORING_COMPOSER_GUIDE,
    TUTORING_EMPTY_WARNING,
    TUTORING_FALLBACK_HINT,
    TUTORING_SPINNER,
    TUTORING_SUBTITLE,
    TUTORING_TITLE,
)


def apply_controlled_hint_panel_style():
    st.markdown(
        """
<style>
    .tutoring-title {
        font-size: 20px;
        font-weight: 700;
        line-height: 1.55;
        color: #1f2937;
        margin: 0 0 0.35rem 0;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }

    .tutoring-title::before {
        content: "";
        display: inline-block;
        width: 7px;
        height: 22px;
        border-radius: 999px;
        background: linear-gradient(180deg, #ff4b4b, #2563eb);
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
        margin: 0.75rem 0 0.45rem 0;
    }

    .stApp:has(.tutoring-title) div.stButton > button {
        min-height: 2.55rem;
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

    .hint-control-label {
        font-size: 15px;
        font-weight: 700;
        color: #334155;
        margin: 0.65rem 0 0.25rem 0;
    }

    .safety-status-card {
        border-radius: 12px;
        border: 1px solid #dbe7f5;
        background: linear-gradient(135deg, #f8fbff 0%, #ffffff 100%);
        padding: 12px 14px;
        margin: 0.7rem 0 0.25rem 0;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
    }

    .safety-status-title {
        font-size: 15px;
        font-weight: 750;
        color: #1f2937;
        margin-bottom: 4px;
    }

    .safety-status-meta {
        font-size: 13px;
        color: #64748b;
        line-height: 1.55;
    }

    .safety-badge {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 2px 9px;
        margin-left: 6px;
        font-size: 12px;
        font-weight: 700;
    }

    .safety-badge-safe {
        color: #166534;
        background: #dcfce7;
        border: 1px solid #bbf7d0;
    }

    .safety-badge-rewrite {
        color: #9a3412;
        background: #ffedd5;
        border: 1px solid #fed7aa;
    }

    div[data-testid="stChatMessage"] {
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        background: rgba(255, 255, 255, 0.78);
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.035);
        margin-bottom: 0.65rem;
    }

    div[data-testid="stRadio"] label {
        font-weight: 650;
    }

    div[data-testid="stRadio"] {
        padding: 0.15rem 0 0.25rem 0;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def _normalize_hint_dialogue_history(history: list):
    if not history:
        history.append({"role": ChatRole.ASSISTANT, "content": TUTORING_TITLE})
        return

    for message in history:
        if message.get("role") == ChatRole.ASSISTANT and message.get("content") == LEGACY_TUTORING_TITLE:
            message["content"] = TUTORING_TITLE


def _render_hint_dialogue_history(history: list):
    for message in history:
        with st.chat_message(message["role"]):
            if message.get("role") == ChatRole.ASSISTANT and message.get("content") == TUTORING_TITLE:
                st.markdown(
                    f"<div style='font-size: 20px; font-weight: 700; line-height: 1.55;'>{TUTORING_TITLE}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(format_math(message["content"]))


def _build_safety_status(controlled: dict) -> dict:
    rewrite_count = int(controlled.get("rewrite_count", 0))
    leakage_score = int(controlled.get("leakage_score", 0))
    reason = controlled.get("leakage_reason", "未返回检测原因")
    hint_strength = controlled.get("hint_strength", "中提示")

    if rewrite_count > 0:
        return {
            "label": "已自动重写",
            "badge_class": "safety-badge-rewrite",
            "detail": f"提示强度：{hint_strength}；泄露评分：{leakage_score}；重写次数：{rewrite_count}；原因：{reason}",
        }

    return {
        "label": "泄露检测通过",
        "badge_class": "safety-badge-safe",
        "detail": f"提示强度：{hint_strength}；泄露评分：{leakage_score}；原因：{reason}",
    }


def _render_safety_status(status: dict):
    label = escape(status["label"])
    badge_class = escape(status["badge_class"])
    detail = escape(status["detail"])
    st.markdown(
        f"""
<div class="safety-status-card">
    <div class="safety-status-title">
        答案泄露检测状态
        <span class="safety-badge {badge_class}">{label}</span>
    </div>
    <div class="safety-status-meta">{detail}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_controlled_hint_panel(data: dict, record_learning_interaction):
    apply_controlled_hint_panel_style()

    qid = data["question_data"]["id"]
    history = st.session_state[SessionKey.CHAT_HISTORIES].setdefault(qid, [])
    _normalize_hint_dialogue_history(history)
    hint_strength_key = hint_strength(qid)
    safety_status_key = hint_safety_status(qid)
    pending_intent_key = pending_pedagogical_intent(qid)

    st.markdown(f"<div class='tutoring-title'>{TUTORING_TITLE}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='tutoring-subtitle'>{TUTORING_SUBTITLE}</div>",
        unsafe_allow_html=True,
    )
    _render_hint_dialogue_history(history)

    if safety_status_key in st.session_state:
        _render_safety_status(st.session_state[safety_status_key])

    composer_input_key = composer_input(qid)
    composer_reset_key = composer_reset(qid)
    math_widget_version_key = math_widget_version(qid)

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
    st.markdown("<div class='hint-control-label'>提示强度控制</div>", unsafe_allow_html=True)
    selected_strength = st.radio(
        "提示强度控制",
        list(HINT_STRENGTH_OPTIONS.keys()),
        index=1,
        key=hint_strength_key,
        horizontal=True,
        label_visibility="collapsed",
        format_func=lambda label: f"{label}｜{HINT_STRENGTH_OPTIONS[label]}",
    )

    st.markdown("<div class='quick-request-label'>快捷请求</div>", unsafe_allow_html=True)
    quick_cols = st.columns(len(PEDAGOGICAL_QUICK_REQUESTS))
    for quick_index, request_config in enumerate(PEDAGOGICAL_QUICK_REQUESTS):
        with quick_cols[quick_index]:
            if st.button(request_config["label"], key=quick_help_button(qid, quick_index), use_container_width=True):
                history.append({"role": ChatRole.USER, "content": request_config["prompt"]})
                st.session_state[pending_intent_key] = request_config["intent"]
                st.session_state[composer_input_key] = ""
                st.session_state[composer_reset_key] = True
                st.rerun()

    st.markdown(
        f"<div class='composer-guide'>{TUTORING_COMPOSER_GUIDE}</div>",
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        composer_value = math_input(
            default_value=st.session_state.get(composer_input_key, ""),
            key=math_widget(qid, st.session_state[math_widget_version_key]),
        )

        if composer_value is not None:
            st.session_state[composer_input_key] = composer_value

    send_col1, send_col2 = st.columns([5, 1])
    with send_col2:
        if st.button("发送", key=send_help_button(qid), type="primary", use_container_width=True):
            query = st.session_state.get(composer_input_key, "").strip()
            if query:
                history.append({"role": ChatRole.USER, "content": query})
                st.session_state[pending_intent_key] = DEFAULT_PEDAGOGICAL_INTENT
                st.session_state[composer_reset_key] = True
                st.rerun()
            else:
                st.warning(TUTORING_EMPTY_WARNING)

    if history and history[-1]["role"] == ChatRole.USER:
        with st.chat_message("assistant"):
            last_query = history[-1]["content"]
            pedagogical_intent = st.session_state.get(pending_intent_key, DEFAULT_PEDAGOGICAL_INTENT)
            try:
                with st.spinner(TUTORING_SPINNER):
                    controlled = generate_controlled_hint(
                        data["question_data"],
                        data["user_answer"],
                        data["is_correct"],
                        last_query,
                        hint_strength=selected_strength,
                    )
                final = controlled["hint"]
                st.markdown(format_math(final))
                status = _build_safety_status(controlled)
                st.session_state[safety_status_key] = status
                _render_safety_status(status)
                if controlled["rewrite_count"] > 0:
                    st.caption(f"已自动重写 {controlled['rewrite_count']} 次，以降低答案泄露风险。")
                history.append({"role": ChatRole.ASSISTANT, "content": final})
                record_learning_interaction(
                    qid,
                    format_tutoring_query(selected_strength, last_query),
                    final,
                    leak=controlled["is_leaking"],
                    leakage_score=controlled["leakage_score"],
                    rewrite_count=controlled["rewrite_count"],
                    leakage_reason=controlled["leakage_reason"],
                    hint_strength=selected_strength,
                    pedagogical_intent=pedagogical_intent,
                    hint_safety_status=status["label"],
                )
            except Exception as exc:
                log_exception("Controlled hint generation error", exc)
                fallback = TUTORING_FALLBACK_HINT
                st.markdown(fallback)
                history.append({"role": ChatRole.ASSISTANT, "content": fallback})
                fallback_status = {
                    "label": "保底安全提示",
                    "badge_class": "safety-badge-safe",
                    "detail": f"提示强度：{selected_strength}；模型生成异常，已返回保底启发式提示。",
                }
                st.session_state[safety_status_key] = fallback_status
                _render_safety_status(fallback_status)
                record_learning_interaction(
                    qid,
                    format_tutoring_query(selected_strength, last_query),
                    fallback,
                    leak=0,
                    hint_strength=selected_strength,
                    pedagogical_intent=pedagogical_intent,
                    hint_safety_status=fallback_status["label"],
                )
