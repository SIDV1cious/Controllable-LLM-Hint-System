"""Streamlit Cloud entrypoint for the controllable LLM hint system."""

from controlled_hint_system_app import run_controlled_hint_system

STREAMLIT_DEPLOY_MARKER = "2026-05-22-private-answer-boundary-v6"

if __name__ == "__main__":
    run_controlled_hint_system()
