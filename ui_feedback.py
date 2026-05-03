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


def render_route_loading_overlay(slot, message: str) -> None:
    slot.markdown(
        f"""
<div class="route-loading-overlay">
    <div class="route-loading-card">
        <span class="route-loading-dot"></span>{message}
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )
