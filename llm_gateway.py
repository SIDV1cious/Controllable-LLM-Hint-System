import logging
import time
from typing import TypedDict

from openai import AsyncOpenAI, OpenAI

from system_config import AppConfig


class LLMCallMetadata(TypedDict):
    model: str
    temperature: float
    message_count: int
    prompt_chars: int


def classify_llm_error(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "timeout" in name or "timeout" in message or "timed out" in message:
        return "timeout"
    if "rate" in name or "rate" in message or "429" in message:
        return "rate_limit"
    if "auth" in name or "api key" in message or "401" in message or "403" in message:
        return "auth"
    if "connect" in name or "network" in message or "connection" in message:
        return "network"
    return "llm_error"


client = OpenAI(
    api_key=AppConfig.LLM_API_KEY or "missing-api-key",
    base_url=AppConfig.BASE_URL,
    timeout=AppConfig.LLM_TIMEOUT_SECONDS,
    max_retries=AppConfig.LLM_MAX_RETRIES,
)

aclient = AsyncOpenAI(
    api_key=AppConfig.LLM_API_KEY or "missing-api-key",
    base_url=AppConfig.BASE_URL,
    timeout=AppConfig.LLM_TIMEOUT_SECONDS,
    max_retries=AppConfig.LLM_MAX_RETRIES,
)


def build_llm_call_metadata(messages: list, temperature: float, model: str | None = None) -> LLMCallMetadata:
    prompt_chars = sum(len(str(message.get("content", ""))) for message in messages if isinstance(message, dict))
    return {
        "model": model or AppConfig.LLM_MODEL,
        "temperature": temperature,
        "message_count": len(messages),
        "prompt_chars": prompt_chars,
    }


def chat_completion_text(
    messages: list,
    temperature: float = 0.2,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
    stage_name: str = "llm_call",
) -> str:
    if not AppConfig.LLM_API_KEY:
        raise RuntimeError("未配置 LLM_API_KEY，无法调用大模型。")

    metadata = build_llm_call_metadata(messages, temperature)
    started_at = time.perf_counter()
    try:
        request_options = {}
        if timeout_seconds is not None:
            request_options["timeout"] = timeout_seconds
        if max_retries is not None:
            request_options["max_retries"] = max_retries
        request_client = client.with_options(**request_options) if request_options else client
        resp = request_client.chat.completions.create(
            model=metadata["model"],
            messages=messages,
            temperature=temperature,
        )
        content = (resp.choices[0].message.content or "").strip()
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 1)
        logging.info(
            "LLM call succeeded: stage=%s model=%s temperature=%s messages=%s prompt_chars=%s response_chars=%s elapsed_ms=%s",
            stage_name,
            metadata["model"],
            metadata["temperature"],
            metadata["message_count"],
            metadata["prompt_chars"],
            len(content),
            elapsed_ms,
        )
        return content
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 1)
        error_type = classify_llm_error(exc)
        logging.exception(
            "LLM call failed: stage=%s error_type=%s model=%s temperature=%s messages=%s prompt_chars=%s elapsed_ms=%s",
            stage_name,
            error_type,
            metadata["model"],
            metadata["temperature"],
            metadata["message_count"],
            metadata["prompt_chars"],
            elapsed_ms,
        )
        raise


call_deepseek_chat = chat_completion_text
