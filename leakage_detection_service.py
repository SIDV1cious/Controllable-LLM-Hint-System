import logging
import re

from domain_models import LeakageEvaluation, QuestionData
from hint_text_utils import parse_json_object
from llm_gateway import chat_completion_text
from prompts import LEAKAGE_CHECK_PROMPT_SYSTEM


def heuristic_leakage_check(reference_answer: str, candidate_hint: str) -> LeakageEvaluation:
    hint = candidate_hint or ""
    answer = (reference_answer or "").strip()
    if not answer:
        return {"is_leaking": False, "score": 0, "reason": "无标准答案，启用低风险默认判定"}

    if len(answer) == 1 and answer.upper() in "ABCD":
        direct_patterns = [
            rf"(答案|选项|选择|应选|正确选项)\s*(是|为|:|：)?\s*{answer}",
            rf"{answer}\s*(项|选项)\s*(正确|是对的)?",
            rf"\({answer}\)",
        ]
        if any(re.search(p, hint, flags=re.I) for p in direct_patterns):
            return {"is_leaking": True, "score": 3, "reason": "提示中直接暴露选择题选项"}
        return {"is_leaking": False, "score": 0, "reason": "未发现直接选项泄露"}

    if len(answer) >= 2 and answer in hint:
        return {"is_leaking": True, "score": 3, "reason": "提示中直接包含标准答案文本"}

    return {"is_leaking": False, "score": 0, "reason": "未命中本地泄露规则"}


def evaluate_hint_leakage(
    question_data: QuestionData,
    candidate_hint: str,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
) -> LeakageEvaluation:
    std_ans = question_data.get("answer", "")
    std_sol = question_data.get("solution", "")
    if not (std_ans or std_sol):
        return heuristic_leakage_check(std_ans, candidate_hint)

    prompt = f"""题目：
{question_data['content']}

标准答案：
{std_ans}

标准解析：
{std_sol}

待检测提示：
{candidate_hint}

请判断待检测提示是否泄露答案信息。"""
    try:
        raw = chat_completion_text(
            [{"role": "system", "content": LEAKAGE_CHECK_PROMPT_SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        parsed = parse_json_object(raw)
        if parsed:
            return {
                "is_leaking": bool(parsed.get("is_leaking", False)),
                "score": int(parsed.get("score", 0)),
                "reason": str(parsed.get("reason", ""))[:255],
            }
    except Exception as e:
        logging.error(f"Leakage evaluation error: {e}")

    return heuristic_leakage_check(std_ans, candidate_hint)
