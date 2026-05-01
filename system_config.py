import os
from datetime import datetime

import pytz
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

SHANGHAI_TZ = pytz.timezone("Asia/Shanghai")


def get_secret_or_env(name: str, default: str | None = None):
    try:
        secret_value = st.secrets.get(name)
    except Exception:
        secret_value = None
    return secret_value or os.getenv(name, default)


class AppConfig:
    LLM_API_KEY = get_secret_or_env("LLM_API_KEY")
    DB_USER = get_secret_or_env("DB_USER")
    DB_PASSWORD = get_secret_or_env("DB_PASSWORD")
    DB_HOST = get_secret_or_env("DB_HOST")
    DB_NAME = get_secret_or_env("DB_NAME")
    BASE_URL = "https://api.deepseek.com"
    LLM_MODEL = get_secret_or_env("LLM_MODEL", "deepseek-chat")
    LLM_TIMEOUT_SECONDS = float(get_secret_or_env("LLM_TIMEOUT_SECONDS", "45"))
    LLM_MAX_RETRIES = int(get_secret_or_env("LLM_MAX_RETRIES", "2"))
    ASSESS_CONCURRENCY = int(get_secret_or_env("ASSESS_CONCURRENCY", "5"))
    QUIZ_SIZE = int(get_secret_or_env("QUIZ_SIZE", "10"))


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ)
