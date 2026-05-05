"""Small Streamlit feedback wrappers for consistent UI messages."""

from __future__ import annotations

import streamlit as st

SUCCESS_ICON = "✅"
ERROR_ICON = "❌"
WARNING_ICON = "⚠️"


def show_success(message: str) -> None:
    st.toast(message, icon=SUCCESS_ICON)


def show_error(message: str) -> None:
    st.toast(message, icon=ERROR_ICON)


def show_warning(message: str) -> None:
    st.toast(message, icon=WARNING_ICON)


def render_full_page_transition(
    message: str,
    icon: str = "🔄",
    route_id: str = "route-page-transition",
    spin_icon: bool = True,
) -> None:
    icon_class = "system-transition-icon is-spinning" if spin_icon else "system-transition-icon"
    st.markdown(f'<div id="{route_id}"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="system-transition-shell">
    <h2 class="system-transition-message">
        <span class="{icon_class}">{icon}</span>{message}
    </h2>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_route_loading_overlay(slot, message: str) -> None:
    slot.markdown(
        f"""
<div class="route-loading-overlay">
    <div class="system-transition-shell">
        <h2 class="system-transition-message">
            <span class="system-transition-icon is-spinning">🔄</span>{message}
        </h2>
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )
