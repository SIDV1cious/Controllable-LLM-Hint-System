import asyncio
import logging

from assessment_logic import assess_with_reference_answer, build_assessment_prompt
from llm_gateway import aclient
from prompts import JUDGE_PROMPT_SYSTEM
from system_config import AppConfig


async def async_assess_single(q: dict, ans: str, semaphore: asyncio.Semaphore) -> bool:
    local_result = assess_with_reference_answer(q, ans)
    if local_result is not None:
        return local_result

    if not AppConfig.LLM_API_KEY:
        logging.error("LLM_API_KEY is missing; assessment request skipped.")
        return False

    try:
        async with semaphore:
            resp = await aclient.chat.completions.create(
                model=AppConfig.LLM_MODEL,
                messages=[
                    {"role": "system", "content": JUDGE_PROMPT_SYSTEM},
                    {"role": "user", "content": build_assessment_prompt(q, ans)},
                ],
            )
        res_text = resp.choices[0].message.content.strip()
        return "PASS" in res_text and "FAIL" not in res_text
    except Exception as e:
        logging.error(f"Async assess error: {e}")
        return False


async def batch_assess(queue: list, answers: dict) -> list:
    semaphore = asyncio.Semaphore(max(1, AppConfig.ASSESS_CONCURRENCY))
    tasks = [async_assess_single(q, answers.get(i, "未作答"), semaphore) for i, q in enumerate(queue)]
    return await asyncio.gather(*tasks)
