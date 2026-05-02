import json
import logging

from domain_models import ControlledHintResult, LeakageEvaluation, QuestionData
from hint_policy import FALLBACK_SAFE_HINT, MAX_HINT_REWRITE_ATTEMPTS, get_hint_strength_policy, normalize_hint_strength
from hint_text_utils import format_math, parse_json_object
from leakage_detection_service import evaluate_hint_leakage
from llm_gateway import chat_completion_text
from prompt_config_repository import get_system_instruction
from prompts import HINT_PLAN_PROMPT_SYSTEM, REWRITE_PROMPT_SYSTEM, SYSTEM_INSTRUCTION


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
    )


def generate_controlled_hint(
    question_data: QuestionData,
    student_answer: str,
    is_correct: bool,
    student_request: str,
    hint_strength: str = "中提示",
) -> ControlledHintResult:
    hint_strength = normalize_hint_strength(hint_strength)
    dynamic_prompt = get_dynamic_system_prompt()
    hint_plan = build_hint_plan(question_data, student_answer, is_correct, student_request, hint_strength)
    final_hint = generate_student_hint(
        question_data,
        student_answer,
        is_correct,
        student_request,
        hint_plan,
        dynamic_prompt,
        hint_strength,
    )
    leakage_result = evaluate_hint_leakage(question_data, final_hint)
    rewrite_count = 0

    while leakage_result.get("is_leaking") and rewrite_count < MAX_HINT_REWRITE_ATTEMPTS:
        rewrite_count += 1
        final_hint = rewrite_unsafe_hint(
            question_data,
            student_request,
            hint_plan,
            final_hint,
            leakage_result,
            hint_strength,
        )
        leakage_result = evaluate_hint_leakage(question_data, final_hint)

    if leakage_result.get("is_leaking"):
        final_hint = FALLBACK_SAFE_HINT
        leakage_result = {
            "is_leaking": False,
            "score": 0,
            "reason": "重写后仍有风险，已替换为保底启发式提示",
        }

    return {
        "hint": format_math(final_hint),
        "is_leaking": int(bool(leakage_result.get("is_leaking", False))),
        "leakage_score": int(leakage_result.get("score", 0)),
        "rewrite_count": rewrite_count,
        "leakage_reason": leakage_result.get("reason", ""),
        "hint_strength": hint_strength,
    }
