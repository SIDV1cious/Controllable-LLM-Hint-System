import asyncio
import logging

from llm_gateway import aclient
from prompts import JUDGE_PROMPT_SYSTEM
from system_config import AppConfig


async def async_assess_single(q: dict, ans: str, semaphore: asyncio.Semaphore) -> bool:
    if not AppConfig.LLM_API_KEY:
        logging.error("LLM_API_KEY is missing; assessment request skipped.")
        return False

    std_ans = q.get("answer", "")
    std_sol = q.get("solution", "")
    if std_ans or std_sol:
        prompt = f"题目：{q['content']}\n标准答案：{std_ans}\n标准解析：{std_sol}\n学生答案：{ans}\n任务：请严格对照标准答案判断学生是否正确。正确输出PASS，错误输出FAIL。"
    else:
        prompt = f"题目：{q['content']}\n学生答案：{ans}\n任务：判断是否正确。正确输出PASS，错误输出FAIL。"

    try:
        async with semaphore:
            resp = await aclient.chat.completions.create(
                model=AppConfig.LLM_MODEL,
                messages=[{"role": "system", "content": JUDGE_PROMPT_SYSTEM}, {"role": "user", "content": prompt}],
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
