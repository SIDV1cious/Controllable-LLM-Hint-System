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
