from html import escape

import streamlit as st

from app_constants import ChatRole, format_tutoring_query
from app_errors import log_exception
from hint_system_core import format_math, generate_controlled_hint
from math_comp import math_input
from session_keys import (
    SessionKey,
    composer_empty_feedback,
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
        line-height: 1.45;
        color: #1f2937;
        margin: 0 0 0.55rem 0;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        letter-spacing: -0.01em;
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
        border: 1px solid #dbe7f5;
        border-radius: 15px;
        padding: 10px 12px;
        color: #475569;
        font-size: 14px;
        font-weight: 620;
        line-height: 1.6;
        margin: 0 0 0.95rem 0;
        background:
            linear-gradient(135deg, rgba(248, 251, 255, 0.96), rgba(255, 255, 255, 0.92)),
            radial-gradient(circle at right top, rgba(37, 99, 235, 0.08), transparent 9rem);
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.035);
    }

    .quick-request-label {
        font-size: 15px;
        font-weight: 700;
        color: #334155;
        margin: 0.75rem 0 0.45rem 0;
    }

    .strategy-panel-note {
        color: #64748b;
        font-size: 13px;
        line-height: 1.55;
        margin: -0.1rem 0 0.55rem 0;
    }

    .strength-policy-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 9px;
        margin: 0.45rem 0 0.75rem 0;
    }

    .strength-policy-card {
        border: 1px solid #dbe7f5;
        border-radius: 15px;
        padding: 10px 11px;
        background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(248,251,255,0.82));
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.035);
    }

    .strength-policy-card:not(.selected) {
        opacity: 0.72;
        box-shadow: none;
    }

    .strength-policy-card:not(.selected) .strength-policy-desc {
        color: #94a3b8;
    }

    .strength-policy-card.selected {
        border-color: #ff8f8f;
        background:
            linear-gradient(135deg, rgba(255, 245, 245, 0.96), rgba(248, 251, 255, 0.9)),
            radial-gradient(circle at right top, rgba(255, 75, 75, 0.12), transparent 7rem);
        box-shadow: 0 12px 28px rgba(255, 75, 75, 0.08);
    }

    .strength-policy-label {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: #1f2937;
        font-size: 13px;
        font-weight: 780;
        margin-bottom: 3px;
    }

    .strength-policy-badge {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 2px 8px;
        color: #1d4ed8;
        background: #dbeafe;
        border: 1px solid #bfdbfe;
        font-size: 11px;
        font-weight: 720;
    }

    .strength-policy-desc {
        color: #64748b;
        font-size: 12px;
        line-height: 1.55;
    }

    .quick-request-intent {
        text-align: center;
        color: #64748b;
        font-size: 12px;
        line-height: 1.4;
        margin-top: 0.25rem;
    }

    .current-intent-card {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        border: 1px solid #dbe7f5;
        border-radius: 14px;
        padding: 10px 12px;
        margin: 0.7rem 0 0.65rem 0;
        background:
            linear-gradient(135deg, rgba(248, 251, 255, 0.96), rgba(255, 255, 255, 0.94)),
            radial-gradient(circle at left top, rgba(37, 99, 235, 0.08), transparent 7rem);
    }

    .current-intent-title {
        color: #1f2937;
        font-size: 13px;
        font-weight: 760;
    }

    .current-intent-meta {
        color: #64748b;
        font-size: 12px;
        line-height: 1.5;
    }

    .current-intent-badge {
        flex: 0 0 auto;
        border-radius: 999px;
        padding: 4px 10px;
        color: #1d4ed8;
        background: #dbeafe;
        border: 1px solid #bfdbfe;
        font-size: 12px;
        font-weight: 740;
        white-space: nowrap;
    }

    .stApp:has(.tutoring-title) div.stButton > button {
        min-height: 2.55rem;
    }

    .composer-guide {
        font-size: 18px;
        font-weight: 700;
        line-height: 1.6;
        margin: 0.65rem 0 0.65rem 0;
        color: #1f2937;
    }

    .composer-empty-alert {
        border: 1px solid #fecaca;
        background:
            linear-gradient(135deg, #fff7f7 0%, #fff 100%),
            radial-gradient(circle at left center, rgba(255, 75, 75, 0.10), transparent 7rem);
        color: #991b1b;
        border-radius: 14px;
        padding: 10px 12px;
        margin: 0.55rem 0 0.2rem 0;
        font-size: 14px;
        font-weight: 700;
        line-height: 1.55;
        box-shadow: 0 10px 22px rgba(153, 27, 27, 0.06);
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
        border-radius: 16px;
        border: 1px solid #dbe7f5;
        background:
            linear-gradient(135deg, #f8fbff 0%, #ffffff 100%),
            radial-gradient(circle at right top, rgba(255, 75, 75, 0.08), transparent 8rem);
        padding: 13px 15px;
        margin: 0.8rem 0 0.35rem 0;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.045);
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

    .safety-metric-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 8px;
        margin: 0.65rem 0 0.55rem 0;
    }

    .safety-metric-item {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 8px 9px;
        background: rgba(255, 255, 255, 0.78);
    }

    .safety-metric-label {
        color: #64748b;
        font-size: 11px;
        font-weight: 720;
        line-height: 1.35;
        margin-bottom: 3px;
    }

    .safety-metric-value {
        color: #1f2937;
        font-size: 13px;
        font-weight: 780;
        line-height: 1.35;
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
        background:
            linear-gradient(135deg, rgba(255, 255, 255, 0.86), rgba(248, 251, 255, 0.78));
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.035);
        margin-bottom: 0.65rem;
    }

    .tutoring-chat-title {
        font-size: 20px;
        font-weight: 700;
        line-height: 1.55;
        color: #1f2937;
    }

    .tutoring-message-meta {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        margin-bottom: 0.35rem;
        color: #64748b;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.02em;
    }

    .tutoring-message-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #2563eb;
        box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
    }

    .tutoring-message-meta.user .tutoring-message-dot {
        background: #ff4b4b;
        box-shadow: 0 0 0 4px rgba(255, 75, 75, 0.12);
    }

    .generation-status-card,
    .rewrite-notice-card {
        border: 1px solid #dbe7f5;
        border-radius: 14px;
        padding: 10px 12px;
        margin: 0.45rem 0 0.65rem 0;
        background: linear-gradient(135deg, #f8fbff 0%, #ffffff 100%);
        color: #475569;
        font-size: 13px;
        line-height: 1.55;
    }

    .generation-status-card strong,
    .rewrite-notice-card strong {
        color: #1f2937;
        font-weight: 760;
    }

    .rewrite-notice-card {
        border-color: #fed7aa;
        background: linear-gradient(135deg, #fff7ed 0%, #ffffff 100%);
    }

    div[data-testid="stChatMessage"] p {
        line-height: 1.75;
    }

    div[data-testid="stRadio"] label {
        font-weight: 650;
    }

    div[data-testid="stRadio"] {
        padding: 0.15rem 0 0.25rem 0;
    }

    @media (max-width: 720px) {
        .strength-policy-grid {
            grid-template-columns: 1fr;
        }

        .safety-metric-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .tutoring-title {
            font-size: 18px;
        }

        .composer-guide {
            font-size: 16px;
        }
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


def _render_message_header(role: str, title: str, description: str) -> None:
    role_class = "user" if role == ChatRole.USER else "assistant"
    st.markdown(
        f"""
<div class="tutoring-message-meta {role_class}">
    <span class="tutoring-message-dot"></span>
    <span>{escape(title)}</span>
    <span>｜{escape(description)}</span>
</div>
        """,
        unsafe_allow_html=True,
    )


def _render_strength_policy_cards(selected_strength: str) -> None:
    policy_meta = {
        "轻提示": ("方向提醒", "只指出概念入口和思考方向，尽量保留学生自主推理空间。"),
        "中提示": ("下一步引导", "提示下一步关键思路，适合卡在中间步骤时使用。"),
        "强提示": ("分步支架", "给出更具体的分步提示，但仍避免直接暴露最终答案。"),
    }
    cards = []
    for label, description in HINT_STRENGTH_OPTIONS.items():
        badge, teaching_goal = policy_meta.get(label, ("策略控制", description))
        selected_class = " selected" if label == selected_strength else ""
        cards.append(
            f"""
<div class="strength-policy-card{selected_class}">
    <div class="strength-policy-label">
        {escape(label)}
        <span class="strength-policy-badge">{escape(badge)}</span>
    </div>
    <div class="strength-policy-desc">{escape(teaching_goal)}</div>
</div>
            """
        )

    st.markdown(f"<div class='strength-policy-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def _render_current_intent(pedagogical_intent: str, selected_strength: str) -> None:
    st.markdown(
        f"""
<div class="current-intent-card">
    <div>
        <div class="current-intent-title">当前教学意图</div>
        <div class="current-intent-meta">本轮请求将按“{escape(selected_strength)}”控制提示粒度，并记录用于后续学习行为分析。</div>
    </div>
    <div class="current-intent-badge">{escape(pedagogical_intent)}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _render_generation_status() -> None:
    st.markdown(
        """
<div class="generation-status-card">
    <strong>生成链路：</strong>正在生成启发式提示，并同步进行答案泄露检测与必要重写。
</div>
        """,
        unsafe_allow_html=True,
    )


def _render_rewrite_notice(rewrite_count: int) -> None:
    st.markdown(
        f"""
<div class="rewrite-notice-card">
    <strong>自动重写：</strong>已重写 {rewrite_count} 次，以降低答案信息泄露风险。
</div>
        """,
        unsafe_allow_html=True,
    )


def _render_hint_dialogue_history(history: list):
    for message in history:
        with st.chat_message(message["role"]):
            role = message.get("role")
            if role == ChatRole.USER:
                _render_message_header(ChatRole.USER, "学生提问", "作为本轮受控提示的输入意图")
                st.markdown(format_math(message["content"]))
            elif role == ChatRole.ASSISTANT and message.get("content") == TUTORING_TITLE:
                _render_message_header(ChatRole.ASSISTANT, "辅导入口", "可选择提示强度与教学意图")
                st.markdown(
                    f"<div class='tutoring-chat-title'>{TUTORING_TITLE}</div>",
                    unsafe_allow_html=True,
                )
            else:
                _render_message_header(ChatRole.ASSISTANT, "受控智能辅导", "启发式提示 · 泄露检测 · 安全输出")
                st.markdown(format_math(message["content"]))


def _build_safety_status(controlled: dict, pedagogical_intent: str) -> dict:
    rewrite_count = int(controlled.get("rewrite_count", 0))
    leakage_score = int(controlled.get("leakage_score", 0))
    reason = controlled.get("leakage_reason", "未返回检测原因")
    hint_strength = controlled.get("hint_strength", "中提示")

    if rewrite_count > 0:
        return {
            "label": "已自动重写",
            "badge_class": "safety-badge-rewrite",
            "hint_strength": hint_strength,
            "pedagogical_intent": pedagogical_intent,
            "leakage_score": leakage_score,
            "rewrite_count": rewrite_count,
            "reason": reason,
            "detail": f"提示强度：{hint_strength}；泄露评分：{leakage_score}；重写次数：{rewrite_count}；原因：{reason}",
        }

    return {
        "label": "泄露检测通过",
        "badge_class": "safety-badge-safe",
        "hint_strength": hint_strength,
        "pedagogical_intent": pedagogical_intent,
        "leakage_score": leakage_score,
        "rewrite_count": rewrite_count,
        "reason": reason,
        "detail": f"提示强度：{hint_strength}；泄露评分：{leakage_score}；原因：{reason}",
    }


def _render_safety_status(status: dict):
    label = escape(status["label"])
    badge_class = escape(status["badge_class"])
    hint_strength_value = escape(str(status.get("hint_strength", "未记录")))
    pedagogical_intent_value = escape(str(status.get("pedagogical_intent", "未记录")))
    leakage_score_value = escape(str(status.get("leakage_score", "未记录")))
    rewrite_count = status.get("rewrite_count")
    rewrite_value = "未重写" if rewrite_count in (None, 0, "0") else f"{escape(str(rewrite_count))} 次"
    reason = status.get("reason") or status.get("detail", "")
    reason_detail = escape(str(reason))
    st.markdown(
        f"""
<div class="safety-status-card">
    <div class="safety-status-title">
        答案泄露检测状态
        <span class="safety-badge {badge_class}">{label}</span>
    </div>
    <div class="safety-metric-grid">
        <div class="safety-metric-item">
            <div class="safety-metric-label">提示强度</div>
            <div class="safety-metric-value">{hint_strength_value}</div>
        </div>
        <div class="safety-metric-item">
            <div class="safety-metric-label">教学意图</div>
            <div class="safety-metric-value">{pedagogical_intent_value}</div>
        </div>
        <div class="safety-metric-item">
            <div class="safety-metric-label">泄露评分</div>
            <div class="safety-metric-value">{leakage_score_value}</div>
        </div>
        <div class="safety-metric-item">
            <div class="safety-metric-label">自动重写</div>
            <div class="safety-metric-value">{rewrite_value}</div>
        </div>
    </div>
    <div class="safety-status-meta">检测说明：{reason_detail}</div>
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
    composer_empty_feedback_key = composer_empty_feedback(qid)
    math_widget_version_key = math_widget_version(qid)

    if composer_input_key not in st.session_state:
        st.session_state[composer_input_key] = ""

    if composer_reset_key not in st.session_state:
        st.session_state[composer_reset_key] = False

    if composer_empty_feedback_key not in st.session_state:
        st.session_state[composer_empty_feedback_key] = False

    if math_widget_version_key not in st.session_state:
        st.session_state[math_widget_version_key] = 0

    if pending_intent_key not in st.session_state:
        st.session_state[pending_intent_key] = DEFAULT_PEDAGOGICAL_INTENT

    if st.session_state[composer_reset_key]:
        st.session_state[composer_input_key] = ""
        st.session_state[composer_empty_feedback_key] = False
        st.session_state[math_widget_version_key] += 1
        st.session_state[composer_reset_key] = False

    generation_pending = bool(history and history[-1]["role"] == ChatRole.USER)

    st.markdown("<div class='tutoring-divider'></div>", unsafe_allow_html=True)
    st.markdown("<div class='hint-control-label'>提示强度控制</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='strategy-panel-note'>选择本轮提示的介入程度，系统会据此约束提示粒度与答案暴露风险。</div>",
        unsafe_allow_html=True,
    )
    selected_strength = st.radio(
        "提示强度控制",
        list(HINT_STRENGTH_OPTIONS.keys()),
        index=1,
        key=hint_strength_key,
        horizontal=True,
        label_visibility="collapsed",
        format_func=lambda label: f"{label}｜{HINT_STRENGTH_OPTIONS[label]}",
    )
    _render_strength_policy_cards(selected_strength)

    st.markdown("<div class='quick-request-label'>快捷请求</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='strategy-panel-note'>快捷请求会记录教学意图，便于后续分析学生更需要哪类辅导。</div>",
        unsafe_allow_html=True,
    )
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
                f"<div class='quick-request-intent'>{escape(request_config['intent'])}</div>",
                unsafe_allow_html=True,
            )

    _render_current_intent(
        st.session_state.get(pending_intent_key, DEFAULT_PEDAGOGICAL_INTENT),
        selected_strength,
    )

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
            if composer_value.strip():
                st.session_state[composer_empty_feedback_key] = False

    if st.session_state.get(composer_empty_feedback_key):
        st.markdown(
            f"<div class='composer-empty-alert'>{escape(TUTORING_EMPTY_WARNING)}</div>",
            unsafe_allow_html=True,
        )

    send_col1, send_col2 = st.columns([5, 1])
    with send_col2:
        send_label = "生成中..." if generation_pending else "发送"
        if st.button(
            send_label,
            key=send_help_button(qid),
            type="primary",
            use_container_width=True,
            disabled=generation_pending,
        ):
            query = st.session_state.get(composer_input_key, "").strip()
            if query:
                history.append({"role": ChatRole.USER, "content": query})
                st.session_state[pending_intent_key] = DEFAULT_PEDAGOGICAL_INTENT
                st.session_state[composer_empty_feedback_key] = False
                st.session_state[composer_reset_key] = True
                st.rerun()
            else:
                st.session_state[composer_empty_feedback_key] = True
                st.toast(TUTORING_EMPTY_WARNING, icon="⚠️")
                st.rerun()

    if history and history[-1]["role"] == ChatRole.USER:
        with st.chat_message("assistant"):
            last_query = history[-1]["content"]
            pedagogical_intent = st.session_state.get(pending_intent_key, DEFAULT_PEDAGOGICAL_INTENT)
            try:
                _render_message_header(ChatRole.ASSISTANT, "生成中", "提示生成 · 泄露检测 · 自动重写")
                _render_generation_status()
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
                status = _build_safety_status(controlled, pedagogical_intent)
                st.session_state[safety_status_key] = status
                _render_safety_status(status)
                if controlled["rewrite_count"] > 0:
                    _render_rewrite_notice(controlled["rewrite_count"])
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
                    "hint_strength": selected_strength,
                    "pedagogical_intent": pedagogical_intent,
                    "leakage_score": "未生成",
                    "rewrite_count": 0,
                    "reason": "模型生成异常，已返回保底启发式提示。",
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
