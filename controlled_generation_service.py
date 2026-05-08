import json
import logging
import time

from domain_models import ControlledHintResult, LeakageEvaluation, QuestionData
from hint_policy import FALLBACK_SAFE_HINT, MAX_HINT_REWRITE_ATTEMPTS, get_hint_strength_policy, normalize_hint_strength
from hint_text_utils import format_math, parse_json_object
from leakage_detection_service import evaluate_hint_leakage
from llm_gateway import chat_completion_text
from prompt_config_repository import get_system_instruction
from prompts import HINT_PLAN_PROMPT_SYSTEM, REWRITE_PROMPT_SYSTEM, SYSTEM_INSTRUCTION
from system_config import AppConfig

HINT_GENERATION_TIMEOUT_REASON = "生成链路超过总时限，系统已返回保底启发式提示。"
HINT_GENERATION_TIMEOUT_HINT = "这次智能辅导生成等待时间较长，系统先给你一个安全提示：请先回到题目条件，找出本题考查的定义、公式或判定方法，再尝试写出下一步。"
HINT_GENERATION_ERROR_REASON = "模型生成链路异常，系统已返回保底启发式提示。"
HINT_GENERATION_ERROR_HINT = (
    "这次智能辅导生成遇到临时异常，系统先给你一个安全提示：先把题目条件拆成已知量、目标量和可用知识点，"
    "再判断下一步应该验证定义、代入公式，还是比较两个表达式之间的关系。"
)
HINT_LLM_STAGE_MAX_RETRIES = 0


class ControlledHintGenerationTimeout(TimeoutError):
    """Raised when the controlled hint generation pipeline exceeds the total budget."""


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _record_stage_timing(stage_timings: dict[str, int], stage: str, started_at: float) -> None:
    elapsed_ms = _elapsed_ms(started_at)
    stage_timings[stage] = elapsed_ms
    logging.info("Controlled hint stage completed: stage=%s elapsed_ms=%s", stage, elapsed_ms)


def _ensure_generation_budget(started_at: float) -> None:
    if time.perf_counter() - started_at > AppConfig.CONTROLLED_HINT_TOTAL_TIMEOUT_SECONDS:
        raise ControlledHintGenerationTimeout(HINT_GENERATION_TIMEOUT_REASON)


def _build_timeout_result(hint_strength: str, started_at: float, stage_timings: dict[str, int]) -> ControlledHintResult:
    return {
        "hint": format_math(HINT_GENERATION_TIMEOUT_HINT),
        "is_leaking": 0,
        "leakage_score": 0,
        "rewrite_count": 0,
        "leakage_reason": HINT_GENERATION_TIMEOUT_REASON,
        "hint_strength": hint_strength,
        "generation_status": "timeout",
        "generation_elapsed_ms": _elapsed_ms(started_at),
        "stage_timings": dict(stage_timings),
    }


def _build_failed_result(
    hint_strength: str,
    started_at: float,
    stage_timings: dict[str, int],
    exc: Exception,
) -> ControlledHintResult:
    return {
        "hint": format_math(HINT_GENERATION_ERROR_HINT),
        "is_leaking": 0,
        "leakage_score": 0,
        "rewrite_count": 0,
        "leakage_reason": HINT_GENERATION_ERROR_REASON,
        "hint_strength": hint_strength,
        "generation_status": "failed",
        "generation_elapsed_ms": _elapsed_ms(started_at),
        "generation_error": type(exc).__name__[:255],
        "stage_timings": dict(stage_timings),
    }


def get_dynamic_system_prompt() -> str:
    try:
        return get_system_instruction(SYSTEM_INSTRUCTION)
    except Exception as e:
        logging.error(f"Fetch prompt error: {e}")
    return SYSTEM_INSTRUCTION


def build_hint_plan(
    question_data: QuestionData,
    student_answer: str,
    is_correct: bool,
    student_request: str,
    hint_strength: str = "中提示",
) -> str:
    hint_strength = normalize_hint_strength(hint_strength)
    std_ans = question_data.get("answer", "")
    std_sol = question_data.get("solution", "")
    strength_policy = get_hint_strength_policy(hint_strength)
    if not (std_ans or std_sol):
        return json.dumps(
            {
                "knowledge_point": "待由题目判断",
                "diagnosis": "根据学生请求进行局部启发",
                "hint_goal": "引导学生检查当前思路中的下一步",
                "allowed_hint_level": hint_strength,
                "strength_policy": strength_policy,
                "forbidden_content": "最终答案、完整步骤、关键数值",
            },
            ensure_ascii=False,
        )

    prompt = f"""题目：
{question_data['content']}

标准答案：
{std_ans}

标准解析：
{std_sol}

学生答案：
{student_answer}

判题结果：
{'正确' if is_correct else '错误'}

学生请求：
{student_request}

提示强度：
{hint_strength}

强度约束：
{strength_policy}

请生成不会展示给学生的安全提示计划。"""
    try:
        plan_text = chat_completion_text(
            [{"role": "system", "content": HINT_PLAN_PROMPT_SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.1,
            timeout_seconds=AppConfig.CONTROLLED_HINT_STAGE_TIMEOUT_SECONDS,
            max_retries=HINT_LLM_STAGE_MAX_RETRIES,
        )
        plan_obj = parse_json_object(plan_text)
        if plan_obj:
            return json.dumps(plan_obj, ensure_ascii=False)
        return plan_text
    except Exception as e:
        logging.error(f"Build hint plan error: {e}")
        return "围绕题目核心概念进行一步启发，避免最终答案、关键数值和完整解法。"


def generate_student_hint(
    question_data: QuestionData,
    student_answer: str,
    is_correct: bool,
    student_request: str,
    hint_plan: str,
    system_prompt: str,
    hint_strength: str = "中提示",
) -> str:
    hint_strength = normalize_hint_strength(hint_strength)
    strength_policy = get_hint_strength_policy(hint_strength)
    ctx = f"""【Problem】
{question_data['content']}

【Student Answer】
{student_answer}

【Assessment Result】
{'Correct' if is_correct else 'Incorrect'}

【Private Safe Hint Plan】
{hint_plan}

【Student Request】
{student_request}

【Hint Strength】
{hint_strength}

【Strength Policy】
{strength_policy}

请根据私有提示计划生成面向学生的一次性辅导提示。"""
    return chat_completion_text(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": ctx}],
        temperature=0.4,
        timeout_seconds=AppConfig.CONTROLLED_HINT_STAGE_TIMEOUT_SECONDS,
        max_retries=HINT_LLM_STAGE_MAX_RETRIES,
    )


def rewrite_unsafe_hint(
    question_data: QuestionData,
    student_request: str,
    hint_plan: str,
    unsafe_hint: str,
    leakage_result: LeakageEvaluation,
    hint_strength: str = "中提示",
) -> str:
    hint_strength = normalize_hint_strength(hint_strength)
    strength_policy = get_hint_strength_policy(hint_strength)
    prompt = f"""题目：
{question_data['content']}

私有安全提示计划：
{hint_plan}

学生请求：
{student_request}

提示强度：
{hint_strength}

强度约束：
{strength_policy}

泄露检测结果：
{json.dumps(leakage_result, ensure_ascii=False)}

不安全提示：
{unsafe_hint}

请重写为安全、启发式、不会泄露答案的学生提示。"""
    return chat_completion_text(
        [{"role": "system", "content": REWRITE_PROMPT_SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.2,
        timeout_seconds=AppConfig.CONTROLLED_HINT_STAGE_TIMEOUT_SECONDS,
        max_retries=HINT_LLM_STAGE_MAX_RETRIES,
    )


def generate_controlled_hint(
    question_data: QuestionData,
    student_answer: str,
    is_correct: bool,
    student_request: str,
    hint_strength: str = "中提示",
) -> ControlledHintResult:
    total_started_at = time.perf_counter()
    stage_timings: dict[str, int] = {}
    hint_strength = normalize_hint_strength(hint_strength)

    try:
        stage_started_at = time.perf_counter()
        dynamic_prompt = get_dynamic_system_prompt()
        _record_stage_timing(stage_timings, "load_system_prompt", stage_started_at)
        _ensure_generation_budget(total_started_at)

        stage_started_at = time.perf_counter()
        hint_plan = build_hint_plan(question_data, student_answer, is_correct, student_request, hint_strength)
        _record_stage_timing(stage_timings, "build_hint_plan", stage_started_at)
        _ensure_generation_budget(total_started_at)

        stage_started_at = time.perf_counter()
        final_hint = generate_student_hint(
            question_data,
            student_answer,
            is_correct,
            student_request,
            hint_plan,
            dynamic_prompt,
            hint_strength,
        )
        _record_stage_timing(stage_timings, "generate_student_hint", stage_started_at)
        _ensure_generation_budget(total_started_at)

        stage_started_at = time.perf_counter()
        leakage_result = evaluate_hint_leakage(
            question_data,
            final_hint,
            timeout_seconds=AppConfig.CONTROLLED_HINT_STAGE_TIMEOUT_SECONDS,
            max_retries=HINT_LLM_STAGE_MAX_RETRIES,
        )
        _record_stage_timing(stage_timings, "evaluate_leakage", stage_started_at)
        _ensure_generation_budget(total_started_at)

        rewrite_count = 0

        while leakage_result.get("is_leaking") and rewrite_count < MAX_HINT_REWRITE_ATTEMPTS:
            rewrite_count += 1
            stage_started_at = time.perf_counter()
            final_hint = rewrite_unsafe_hint(
                question_data,
                student_request,
                hint_plan,
                final_hint,
                leakage_result,
                hint_strength,
            )
            _record_stage_timing(stage_timings, f"rewrite_hint_{rewrite_count}", stage_started_at)
            _ensure_generation_budget(total_started_at)

            stage_started_at = time.perf_counter()
            leakage_result = evaluate_hint_leakage(
                question_data,
                final_hint,
                timeout_seconds=AppConfig.CONTROLLED_HINT_STAGE_TIMEOUT_SECONDS,
                max_retries=HINT_LLM_STAGE_MAX_RETRIES,
            )
            _record_stage_timing(stage_timings, f"evaluate_rewrite_{rewrite_count}", stage_started_at)
            _ensure_generation_budget(total_started_at)

        if leakage_result.get("is_leaking"):
            final_hint = FALLBACK_SAFE_HINT
            leakage_result = {
                "is_leaking": False,
                "score": 0,
                "reason": "重写后仍有风险，已替换为保底启发式提示",
            }

        elapsed_ms = _elapsed_ms(total_started_at)
        logging.info(
            "Controlled hint generation completed: status=success elapsed_ms=%s stage_timings=%s",
            elapsed_ms,
            stage_timings,
        )

        return {
            "hint": format_math(final_hint),
            "is_leaking": int(bool(leakage_result.get("is_leaking", False))),
            "leakage_score": int(leakage_result.get("score", 0)),
            "rewrite_count": rewrite_count,
            "leakage_reason": leakage_result.get("reason", ""),
            "hint_strength": hint_strength,
            "generation_status": "success",
            "generation_elapsed_ms": elapsed_ms,
            "stage_timings": dict(stage_timings),
        }

    except ControlledHintGenerationTimeout:
        elapsed_ms = _elapsed_ms(total_started_at)
        logging.warning(
            "Controlled hint generation timed out: elapsed_ms=%s stage_timings=%s",
            elapsed_ms,
            stage_timings,
        )
        return _build_timeout_result(hint_strength, total_started_at, stage_timings)
    except Exception as exc:
        elapsed_ms = _elapsed_ms(total_started_at)
        logging.exception(
            "Controlled hint generation failed: elapsed_ms=%s stage_timings=%s error=%s",
            elapsed_ms,
            stage_timings,
            type(exc).__name__,
        )
        return _build_failed_result(hint_strength, total_started_at, stage_timings, exc)
