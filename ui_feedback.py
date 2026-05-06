"""Small Streamlit feedback wrappers for consistent UI messages."""

from __future__ import annotations

from html import escape

import streamlit as st

SUCCESS_ICON = "✅"
ERROR_ICON = "❌"
WARNING_ICON = "⚠️"
ROUTE_TRANSITION_SECONDS = 0.55


def show_success(message: str) -> None:
    st.toast(message, icon=SUCCESS_ICON)


def show_error(message: str) -> None:
    st.toast(message, icon=ERROR_ICON)


def show_warning(message: str) -> None:
    st.toast(message, icon=WARNING_ICON)


def render_empty_state(
    message: str,
    *,
    title: str = "暂无数据",
    icon: str = "ℹ️",
) -> None:
    safe_title = escape(title)
    safe_message = escape(message)
    safe_icon = escape(icon)
    st.markdown(
        f"""
<div class="ui-empty-state">
    <div class="ui-empty-icon">{safe_icon}</div>
    <div>
        <div class="ui-empty-title">{safe_title}</div>
        <div class="ui-empty-message">{safe_message}</div>
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_full_page_transition(
    message: str,
    icon: str = "🔄",
    route_id: str = "route-page-transition",
    spin_icon: bool = True,
) -> None:
    icon_class = "system-transition-icon is-spinning" if spin_icon else "system-transition-icon"
    st.markdown(
        f"""
<style>
.stApp:has(#{route_id}) section[data-testid="stSidebar"],
.stApp:has(#{route_id}) [data-testid="stSidebar"],
.stApp:has(#{route_id}) [data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    min-width: 0 !important;
}}

.stApp:has(#{route_id}) [data-testid="stAppViewContainer"] {{
    margin-left: 0 !important;
}}

.stApp:has(#{route_id}) [data-stale="true"],
.stApp:has(#{route_id}) [data-stale="true"] * {{
    display: none !important;
    opacity: 0 !important;
    pointer-events: none !important;
}}

.stApp:has(#{route_id}) .block-container {{
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}}

.stApp:has(#{route_id}) .system-transition-shell {{
    min-height: 100vh;
    width: 100%;
}}
</style>
<div id="{route_id}"></div>
<div class="system-transition-shell">
    <h2 class="system-transition-message">
        <span class="{icon_class}">{icon}</span>{message}
    </h2>
</div>
        """,
        unsafe_allow_html=True,
    )
