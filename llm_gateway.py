from openai import AsyncOpenAI, OpenAI

from system_config import AppConfig

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


def chat_completion_text(messages: list, temperature: float = 0.2) -> str:
    if not AppConfig.LLM_API_KEY:
        raise RuntimeError("未配置 LLM_API_KEY，无法调用大模型。")

    resp = client.chat.completions.create(
        model=AppConfig.LLM_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()
