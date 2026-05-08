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
            "LLM call succeeded: model=%s temperature=%s messages=%s prompt_chars=%s response_chars=%s elapsed_ms=%s",
            metadata["model"],
            metadata["temperature"],
            metadata["message_count"],
            metadata["prompt_chars"],
            len(content),
            elapsed_ms,
        )
        return content
    except Exception:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 1)
        logging.exception(
            "LLM call failed: model=%s temperature=%s messages=%s prompt_chars=%s elapsed_ms=%s",
            metadata["model"],
            metadata["temperature"],
            metadata["message_count"],
            metadata["prompt_chars"],
            elapsed_ms,
        )
        raise
