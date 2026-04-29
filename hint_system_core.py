import asyncio
import json
import logging
import os
import re
from datetime import datetime

import pytz
import streamlit as st
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI
from sqlalchemy import Engine, bindparam, create_engine, text
from werkzeug.security import check_password_hash

from prompts import (
    HINT_PLAN_PROMPT_SYSTEM,
    JUDGE_PROMPT_SYSTEM,
    LEAKAGE_CHECK_PROMPT_SYSTEM,
    REWRITE_PROMPT_SYSTEM,
    SYSTEM_INSTRUCTION,
)

load_dotenv()


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


SHANGHAI_TZ = pytz.timezone("Asia/Shanghai")

HINT_STRENGTH_POLICIES = {
    "轻提示": "只给方向性启发、概念提醒或检查角度，避免任何关键中间式、关键数值和最终结论。",
    "中提示": "给出可执行的下一步思考路径，可以提示应使用的定义、公式或判别方法，但不展开完整推导。",
    "强提示": "给出更具体的分步引导和易错点提醒，但仍不得给出最终答案、直接选项或完整标准解法。",
}

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


@st.cache_resource
def get_database_engine() -> Engine:
    connection_url = f"mysql+pymysql://{AppConfig.DB_USER}:{AppConfig.DB_PASSWORD}@{AppConfig.DB_HOST}/{AppConfig.DB_NAME}"
    return create_engine(connection_url, pool_recycle=1800, pool_pre_ping=True)


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def question_row_to_dict(row) -> dict:
    return {
        "id": 1000 + row[0],
        "category": row[1],
        "content": row[2],
        "answer": row[3] or "",
        "solution": row[4] or "",
    }


def fetch_custom_question_rows(conn, db_ids: list):
    if not db_ids:
        return []

    stmt = text(
        "SELECT id, category, content, answer, solution FROM custom_questions WHERE id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    return conn.execute(stmt, {"ids": list(db_ids)}).fetchall()


def build_result_export(assessment_results: list) -> str:
    total = len(assessment_results)
    correct_count = sum(1 for item in assessment_results if item.get("is_correct"))
    accuracy = round(correct_count / total * 100, 1) if total else 0.0
    lines = [
        "# 本次测验结果",
        "",
        f"导出时间：{now_shanghai():%Y-%m-%d %H:%M:%S}",
        f"总题数：{total}",
        f"答对题数：{correct_count}",
        f"正确率：{accuracy}%",
        "",
    ]

    for index, item in enumerate(assessment_results, start=1):
        question = item.get("question_data", {})
        lines.extend([
            f"## 第 {index} 题",
            "",
            f"结果：{'正确' if item.get('is_correct') else '错误'}",
            f"题目：{question.get('content', '')}",
            f"我的作答：{item.get('user_answer', '')}",
            "",
        ])

    return "\n".join(lines)


def verify_password(db_hash: str, pwd: str) -> bool:
    if db_hash.startswith("scrypt:") or db_hash.startswith("pbkdf2:"):
        return check_password_hash(db_hash, pwd)
    import hashlib

    return hashlib.sha256(pwd.encode("utf-8")).hexdigest() == db_hash


def format_math(text_str: str) -> str:
    text_str = re.sub(r"\\\(\s*", "$", text_str)
    text_str = re.sub(r"\s*\\\)", "$", text_str)
    text_str = re.sub(r"\\\[\s*", "$$", text_str)
    text_str = re.sub(r"\s*\\\]", "$$", text_str)
    return text_str


def parse_json_object(raw_text: str) -> dict:
    if not raw_text:
        return {}
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
    return {}


def chat_completion_text(messages: list, temperature: float = 0.2) -> str:
    if not AppConfig.LLM_API_KEY:
        raise RuntimeError("未配置 LLM_API_KEY，无法调用大模型。")

    resp = client.chat.completions.create(
        model=AppConfig.LLM_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


def get_dynamic_system_prompt() -> str:
    try:
        engine_tmp = get_database_engine()
        with engine_tmp.connect() as conn_tmp:
            dyn_prompt_res = conn_tmp.execute(text(
                "SELECT config_value FROM system_configs WHERE config_key = 'system_instruction'"
            )).fetchone()
            if dyn_prompt_res:
                return dyn_prompt_res[0]
    except Exception as e:
        logging.error(f"Fetch prompt error: {e}")
    return SYSTEM_INSTRUCTION


def get_hint_strength_policy(hint_strength: str) -> str:
    return HINT_STRENGTH_POLICIES.get(hint_strength, HINT_STRENGTH_POLICIES["中提示"])


def build_hint_plan(
    question_data: dict,
    student_answer: str,
    is_correct: bool,
    student_request: str,
    hint_strength: str = "中提示",
) -> str:
    std_ans = question_data.get("answer", "")
    std_sol = question_data.get("solution", "")
    strength_policy = get_hint_strength_policy(hint_strength)
    if not (std_ans or std_sol):
        return json.dumps({
            "knowledge_point": "待由题目判断",
            "diagnosis": "根据学生请求进行局部启发",
            "hint_goal": "引导学生检查当前思路中的下一步",
            "allowed_hint_level": hint_strength,
            "strength_policy": strength_policy,
            "forbidden_content": "最终答案、完整步骤、关键数值",
        }, ensure_ascii=False)

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
    question_data: dict,
    student_answer: str,
    is_correct: bool,
    student_request: str,
    hint_plan: str,
    system_prompt: str,
    hint_strength: str = "中提示",
) -> str:
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


def heuristic_leakage_check(reference_answer: str, candidate_hint: str) -> dict:
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


def evaluate_hint_leakage(question_data: dict, candidate_hint: str) -> dict:
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


def rewrite_unsafe_hint(
    question_data: dict,
    student_request: str,
    hint_plan: str,
    unsafe_hint: str,
    leakage_result: dict,
    hint_strength: str = "中提示",
) -> str:
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
    question_data: dict,
    student_answer: str,
    is_correct: bool,
    student_request: str,
    hint_strength: str = "中提示",
) -> dict:
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

    while leakage_result.get("is_leaking") and rewrite_count < 2:
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
        final_hint = "这道题我们先抓住关键条件，不直接推进到答案。你可以先判断题目考查的是哪个定义、公式或判别方法，再检查你的下一步是否满足它的适用条件。"
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


@st.cache_resource
def ensure_leakage_observability_columns():
    column_statements = [
        "ALTER TABLE interaction_logs ADD COLUMN leakage_score INT DEFAULT 0",
        "ALTER TABLE interaction_logs ADD COLUMN rewrite_count INT DEFAULT 0",
        "ALTER TABLE interaction_logs ADD COLUMN leakage_reason VARCHAR(255)",
        "ALTER TABLE interaction_logs ADD COLUMN hint_strength VARCHAR(32)",
        "ALTER TABLE interaction_logs ADD COLUMN pedagogical_intent VARCHAR(64)",
        "ALTER TABLE interaction_logs ADD COLUMN hint_safety_status VARCHAR(64)",
    ]
    index_statements = [
        "ALTER TABLE interaction_logs ADD INDEX idx_interaction_hint_strength (hint_strength)",
        "ALTER TABLE interaction_logs ADD INDEX idx_interaction_pedagogical_intent (pedagogical_intent)",
    ]

    engine = get_database_engine()
    for ddl in column_statements + index_statements:
        try:
            with engine.connect() as conn:
                conn.execute(text(ddl))
                conn.commit()
        except Exception:
            pass

    return True


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
