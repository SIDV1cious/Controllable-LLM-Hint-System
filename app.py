import streamlit as st
import os
import random
import time
import hashlib
import re
import json
import pandas as pd
import plotly.express as px
import logging
import asyncio
from typing import Any
from sqlalchemy import bindparam, create_engine, text, Engine
from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv
from datetime import datetime
import pytz
from werkzeug.security import generate_password_hash, check_password_hash
from prompts import (
    SYSTEM_INSTRUCTION,
    JUDGE_PROMPT_SYSTEM,
    HINT_PLAN_PROMPT_SYSTEM,
    LEAKAGE_CHECK_PROMPT_SYSTEM,
    REWRITE_PROMPT_SYSTEM,
)
from math_comp import math_input

load_dotenv()
logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


class AppConfig:
    LLM_API_KEY = st.secrets.get("LLM_API_KEY") or os.getenv("LLM_API_KEY")
    DB_USER = st.secrets.get("DB_USER") or os.getenv("DB_USER")
    DB_PASSWORD = st.secrets.get("DB_PASSWORD") or os.getenv("DB_PASSWORD")
    DB_HOST = st.secrets.get("DB_HOST") or os.getenv("DB_HOST")
    DB_NAME = st.secrets.get("DB_NAME") or os.getenv("DB_NAME")
    BASE_URL = "https://api.deepseek.com"
    LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
    LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
    LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
    ASSESS_CONCURRENCY = int(os.getenv("ASSESS_CONCURRENCY", "5"))
    QUIZ_SIZE = int(os.getenv("QUIZ_SIZE", "10"))
    MAX_REWRITE_ATTEMPTS = int(os.getenv("MAX_REWRITE_ATTEMPTS", "2"))


SHANGHAI_TZ = pytz.timezone('Asia/Shanghai')

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


def clamp_int(value: Any, default: int = 0, low: int = 0, high: int = 3) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def fetch_custom_question_rows(conn, db_ids: list):
    if not db_ids:
        return []

    stmt = text(
        "SELECT id, category, content, answer, solution FROM custom_questions WHERE id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    return conn.execute(stmt, {"ids": db_ids}).fetchall()


def rows_to_question_map(rows) -> dict:
    return {
        1000 + r[0]: {
            "id": 1000 + r[0],
            "category": r[1],
            "content": r[2],
            "answer": r[3] or "",
            "solution": r[4] or "",
        }
        for r in rows
    }


def build_result_export(assessment_results: list) -> str:
    lines = ["# 本次测验结果", "", f"导出时间：{now_shanghai():%Y-%m-%d %H:%M:%S}", ""]
    correct_count = sum(1 for item in assessment_results if item.get("is_correct"))
    total = len(assessment_results)
    accuracy = round(correct_count / total * 100, 1) if total else 0.0
    lines.extend([f"- 总题数：{total}", f"- 答对题数：{correct_count}", f"- 正确率：{accuracy}%", ""])

    for index, item in enumerate(assessment_results, start=1):
        question = item.get("question_data", {})
        lines.extend([
            f"## 第 {index} 题",
            "",
            f"结果：{'正确' if item.get('is_correct') else '错误'}",
            "",
            "题目：",
            str(question.get("content", "")),
            "",
            f"我的作答：{item.get('user_answer', '')}",
            "",
        ])

    return "\n".join(lines)


def apply_global_style():
    st.markdown(
        """
<style>
    .block-container {
        max-width: 1180px;
        padding-top: 1.25rem;
        padding-bottom: 2rem;
    }

    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #f8fbff 0%, #eef5ff 100%);
        border: 1px solid #d9e5f5;
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: 0 10px 30px rgba(30, 64, 175, 0.06);
    }

    div.stButton > button,
    div[data-testid="stDownloadButton"] > button {
        border-radius: 10px;
        font-weight: 650;
    }

    div[data-testid="stForm"] {
        border-radius: 14px;
        border-color: #d9e5f5;
    }

    section[data-testid="stSidebar"] {
        background: #f8fafc;
        border-right: 1px solid #e5e7eb;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def verify_password(db_hash: str, pwd: str) -> bool:
    if db_hash.startswith("scrypt:") or db_hash.startswith("pbkdf2:"):
        return check_password_hash(db_hash, pwd)
    return hashlib.sha256(pwd.encode('utf-8')).hexdigest() == db_hash


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
        temperature=temperature
    )
    return (resp.choices[0].message.content or "").strip()


def get_dynamic_system_prompt() -> str:
    try:
        engine_tmp = get_database_engine()
        with engine_tmp.connect() as conn_tmp:
            dyn_prompt_res = conn_tmp.execute(text(
                "SELECT config_value FROM system_configs WHERE config_key = 'system_instruction'")).fetchone()
            if dyn_prompt_res:
                return dyn_prompt_res[0]
    except Exception as e:
        logging.error(f"Fetch prompt error: {e}")
    return SYSTEM_INSTRUCTION


def build_hint_plan(question_data: dict, student_answer: str, is_correct: bool, student_request: str) -> str:
    std_ans = question_data.get("answer", "")
    std_sol = question_data.get("solution", "")
    if not (std_ans or std_sol):
        return json.dumps({
            "knowledge_point": "待由题目判断",
            "diagnosis": "根据学生请求进行局部启发",
            "hint_goal": "引导学生检查当前思路中的下一步",
            "allowed_hint_level": "direction",
            "forbidden_content": "最终答案、完整步骤、关键数值"
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

请生成不会展示给学生的安全提示计划。"""
    try:
        plan_text = chat_completion_text(
            [{"role": "system", "content": HINT_PLAN_PROMPT_SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.1
        )
        plan_obj = parse_json_object(plan_text)
        if plan_obj:
            return json.dumps(plan_obj, ensure_ascii=False)
        return plan_text
    except Exception as e:
        logging.error(f"Build hint plan error: {e}")
        return "围绕题目核心概念进行一步启发，避免最终答案、关键数值和完整解法。"


def generate_student_hint(question_data: dict, student_answer: str, is_correct: bool,
                          student_request: str, hint_plan: str, system_prompt: str) -> str:
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

请根据私有提示计划生成面向学生的一次性辅导提示。"""
    return chat_completion_text(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": ctx}],
        temperature=0.4
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
            rf"\({answer}\)"
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
            temperature=0
        )
        parsed = parse_json_object(raw)
        if parsed:
            return {
                "is_leaking": bool(parsed.get("is_leaking", False)),
                "score": clamp_int(parsed.get("score", 0)),
                "reason": str(parsed.get("reason", ""))[:255]
            }
    except Exception as e:
        logging.error(f"Leakage evaluation error: {e}")

    return heuristic_leakage_check(std_ans, candidate_hint)


def rewrite_unsafe_hint(question_data: dict, student_request: str, hint_plan: str,
                        unsafe_hint: str, leakage_result: dict) -> str:
    prompt = f"""题目：
{question_data['content']}

私有安全提示计划：
{hint_plan}

学生请求：
{student_request}

泄露检测结果：
{json.dumps(leakage_result, ensure_ascii=False)}

不安全提示：
{unsafe_hint}

请重写为安全、启发式、不会泄露答案的学生提示。"""
    return chat_completion_text(
        [{"role": "system", "content": REWRITE_PROMPT_SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.2
    )


def generate_controlled_hint(question_data: dict, student_answer: str, is_correct: bool, student_request: str) -> dict:
    dynamic_prompt = get_dynamic_system_prompt()
    hint_plan = build_hint_plan(question_data, student_answer, is_correct, student_request)
    final_hint = generate_student_hint(question_data, student_answer, is_correct, student_request, hint_plan,
                                      dynamic_prompt)
    leakage_result = evaluate_hint_leakage(question_data, final_hint)
    rewrite_count = 0

    while leakage_result.get("is_leaking") and rewrite_count < AppConfig.MAX_REWRITE_ATTEMPTS:
        rewrite_count += 1
        final_hint = rewrite_unsafe_hint(question_data, student_request, hint_plan, final_hint, leakage_result)
        leakage_result = evaluate_hint_leakage(question_data, final_hint)

    if leakage_result.get("is_leaking"):
        final_hint = "这道题我们先抓住关键条件，不直接推进到答案。你可以先判断题目考查的是哪个定义、公式或判别方法，再检查你的下一步是否满足它的适用条件。"
        leakage_result = {
            "is_leaking": False,
            "score": 0,
            "reason": "重写后仍有风险，已替换为保底启发式提示"
        }

    return {
        "hint": format_math(final_hint),
        "is_leaking": int(bool(leakage_result.get("is_leaking", False))),
        "leakage_score": int(leakage_result.get("score", 0)),
        "rewrite_count": rewrite_count,
        "leakage_reason": leakage_result.get("reason", "")
    }


def authenticate_user(u: str, p: str):
    engine = get_database_engine()
    with engine.connect() as conn:
        res = conn.execute(text("SELECT password_hash, role FROM users WHERE username = :u"), {"u": u}).fetchone()
        if res and verify_password(res[0], p):
            return True, res[1]
        return False, None


def register_user(u: str, p: str) -> bool:
    engine = get_database_engine()
    with engine.connect() as conn:
        if conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": u}).fetchone():
            return False
        conn.execute(text("INSERT INTO users (username, password_hash, role) VALUES (:u, :p, 'student')"),
                     {"u": u, "p": generate_password_hash(p)})
        conn.commit()
        return True


def log_login(username: str):
    try:
        engine = get_database_engine()
        with engine.connect() as conn:
            ts = now_shanghai()
            conn.execute(text("INSERT INTO login_logs (username, login_time) VALUES (:u, :t)"),
                         {"u": username, "t": ts})
            conn.commit()
    except Exception as e:
        logging.error(f"log_login error: {e}")


@st.cache_resource(show_spinner=False)
def ensure_leakage_observability_columns() -> bool:
    engine = get_database_engine()
    ddl_statements = [
        "ALTER TABLE interaction_logs ADD COLUMN leakage_score INT DEFAULT 0",
        "ALTER TABLE interaction_logs ADD COLUMN rewrite_count INT DEFAULT 0",
        "ALTER TABLE interaction_logs ADD COLUMN leakage_reason VARCHAR(255)",
    ]

    for ddl in ddl_statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(ddl))
        except Exception as e:
            logging.debug(f"Skip leakage schema migration: {e}")
    return True


def log_interaction(
        qid: int,
        qry: str,
        rsp: str,
        leak: int = 0,
        leakage_score: int = 0,
        rewrite_count: int = 0,
        leakage_reason: str = ""
):
    try:
        ensure_leakage_observability_columns()
        engine = get_database_engine()
        with engine.connect() as conn:
            ts = now_shanghai()
            try:
                conn.execute(text(
                    "INSERT INTO interaction_logs (question_id, student_id, user_query, ai_response, is_leaking_answer, leakage_score, rewrite_count, leakage_reason, created_at) VALUES (:qid, :sid, :qry, :rsp, :leak, :score, :rewrites, :reason, :time)"),
                    {"qid": qid, "sid": st.session_state.current_user, "qry": qry, "rsp": rsp, "leak": leak,
                     "score": leakage_score, "rewrites": rewrite_count, "reason": leakage_reason[:255],
                     "time": ts})
            except Exception:
                conn.execute(text(
                    "INSERT INTO interaction_logs (question_id, student_id, user_query, ai_response, is_leaking_answer, created_at) VALUES (:qid, :sid, :qry, :rsp, :leak, :time)"),
                    {"qid": qid, "sid": st.session_state.current_user, "qry": qry, "rsp": rsp, "leak": leak,
                     "time": ts})
            conn.commit()
    except Exception as e:
        logging.error(f"log_interaction error: {e}")


def init_session_state():
    defaults = {
        "logged_in": False, "current_user": None, "user_role": "student", "page_mode": "home",
        "quiz_queue": [], "current_question_index": 0, "user_answers": {},
        "assessment_results": [], "review_question_index": None,
        "chat_histories": {}, "session_count": 0, "study_session_id": None, "current_course": None,
        "is_grading": False, "grading_started": False
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v


init_session_state()


def sync_user_data(username: str):
    engine = get_database_engine()
    with engine.connect() as conn:
        u_res = conn.execute(text("SELECT current_quiz_ids FROM users WHERE username = :u"), {"u": username}).fetchone()
        if u_res and u_res[0]:
            q_ids = [int(i) for i in u_res[0].split(",") if i.strip()]
            if q_ids:
                db_ids = [i - 1000 for i in q_ids]
                if db_ids:
                    q_map = rows_to_question_map(fetch_custom_question_rows(conn, db_ids))
                    st.session_state.quiz_queue = [q_map[qid] for qid in q_ids if qid in q_map]
                    if st.session_state.quiz_queue:
                        st.session_state.current_course = st.session_state.quiz_queue[0].get('category', '继续测验')
                    st.session_state.page_mode = "quiz"

        logs = conn.execute(
            text("SELECT question_id, user_query, ai_response FROM interaction_logs WHERE student_id = :u ORDER BY created_at DESC LIMIT 200"),
            {"u": username}).fetchall()
        for row in reversed(logs):
            qid, qry, rsp = row
            if qid not in st.session_state.chat_histories:
                st.session_state.chat_histories[qid] = []
            if "【辅导】" in qry:
                st.session_state.chat_histories[qid].append({"role": "user", "content": qry.replace("【辅导】", "")})
                st.session_state.chat_histories[qid].append({"role": "assistant", "content": rsp})


def start_experiment_session(course_name: str):
    engine = get_database_engine()
    with engine.connect() as conn:
        id_rows = conn.execute(
            text("SELECT id FROM custom_questions WHERE category = :c"),
            {"c": course_name}
        ).fetchall()
        candidate_ids = [r[0] for r in id_rows]
        selected_ids = random.sample(candidate_ids, k=min(AppConfig.QUIZ_SIZE, len(candidate_ids)))
        q_map = rows_to_question_map(fetch_custom_question_rows(conn, selected_ids))
        course_questions = [q_map[1000 + db_id] for db_id in selected_ids if 1000 + db_id in q_map]

    if not course_questions:
        st.toast("题库内目前无该课程对应题目", icon="⚠️")
        return

    q_ids = ",".join([str(q['id']) for q in course_questions])
    with engine.connect() as conn:
        conn.execute(text("UPDATE users SET current_quiz_ids = :ids WHERE username = :u"),
                     {"ids": q_ids, "u": st.session_state.current_user})
        ts = now_shanghai()
        res_insert = conn.execute(
            text("INSERT INTO study_sessions (username, course_name, start_time) VALUES (:u, :c, :t)"),
            {"u": st.session_state.current_user, "c": course_name, "t": ts})
        st.session_state.study_session_id = res_insert.lastrowid
        conn.commit()

    st.session_state.current_course = course_name
    st.session_state.quiz_queue = course_questions
    st.session_state.user_answers = {i: "" for i in range(len(course_questions))}
    st.session_state.current_question_index = 0
    st.session_state.assessment_results = []
    st.session_state.review_question_index = None
    st.session_state.chat_histories = {}
    st.session_state.is_grading = False
    st.session_state.grading_started = False
    st.session_state.page_mode = "quiz"
    st.rerun()


async def async_assess_single(q: dict, ans: str) -> bool:
    std_ans = q.get("answer", "")
    std_sol = q.get("solution", "")
    if std_ans or std_sol:
        prompt = f"题目：{q['content']}\n标准答案：{std_ans}\n标准解析：{std_sol}\n学生答案：{ans}\n任务：请严格对照标准答案判断学生是否正确。正确输出PASS，错误输出FAIL。"
    else:
        prompt = f"题目：{q['content']}\n学生答案：{ans}\n任务：判断是否正确。正确输出PASS，错误输出FAIL。"
    try:
        resp = await aclient.chat.completions.create(
            model=AppConfig.LLM_MODEL,
            messages=[{"role": "system", "content": JUDGE_PROMPT_SYSTEM}, {"role": "user", "content": prompt}]
        )
        res_text = resp.choices[0].message.content.strip()
        return "PASS" in res_text and "FAIL" not in res_text
    except Exception as e:
        logging.error(f"Async assess error: {e}")
        return False


async def batch_assess(queue: list, answers: dict) -> list:
    semaphore = asyncio.Semaphore(max(1, AppConfig.ASSESS_CONCURRENCY))

    async def guarded_assess(index: int, question: dict) -> bool:
        async with semaphore:
            return await async_assess_single(question, answers.get(index, "未作答"))

    tasks = [guarded_assess(i, q) for i, q in enumerate(queue)]
    return await asyncio.gather(*tasks)


def submit_and_assess():
    st.session_state.assessment_results = []
    results = asyncio.run(batch_assess(st.session_state.quiz_queue, st.session_state.user_answers))

    for i, (q, is_ok) in enumerate(zip(st.session_state.quiz_queue, results)):
        ans = st.session_state.user_answers.get(i, "未作答")
        st.session_state.assessment_results.append({"question_data": q, "user_answer": ans, "is_correct": is_ok})
        log_interaction(q["id"], f"【答案提交】{ans}", "正确" if is_ok else "错误")

    st.session_state.review_question_index = next(
        (i for i, item in enumerate(st.session_state.assessment_results) if not item["is_correct"]),
        0 if st.session_state.assessment_results else None,
    )

    if st.session_state.study_session_id:
        engine = get_database_engine()
        with engine.connect() as conn:
            ts = now_shanghai()
            conn.execute(text(
                "UPDATE study_sessions SET end_time = :t, duration_seconds = TIMESTAMPDIFF(SECOND, start_time, :t) WHERE id = :id"),
                {"t": ts, "id": st.session_state.study_session_id})
            conn.execute(text("UPDATE users SET current_quiz_ids = NULL WHERE username = :u"),
                         {"u": st.session_state.current_user})
            conn.commit()

    st.session_state.session_count += 1
    st.session_state.is_grading = False
    st.session_state.grading_started = False
    st.session_state.page_mode = "results"
    st.rerun()


st.set_page_config(page_title="基于LLM的可控解题提示生成系统", layout="wide")
apply_global_style()

if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>基于LLM的可控解题提示生成系统</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        tab_l, tab_r = st.tabs(["🔑 登录", "📝 注册"])
        with tab_l:
            with st.form("login_form"):
                u_in = st.text_input("账号/学号")
                p_in = st.text_input("密码", type="password")
                submitted = st.form_submit_button("进入系统", type="primary", use_container_width=True)
                if submitted:
                    is_auth, role = authenticate_user(u_in.strip(), p_in.strip())
                    if is_auth:
                        st.session_state.logged_in = True
                        st.session_state.current_user = u_in.strip()
                        st.session_state.user_role = role
                        log_login(u_in.strip())
                        if role == 'admin':
                            st.session_state.page_mode = "admin"
                        else:
                            sync_user_data(u_in.strip())
                        st.rerun()
                    else:
                        st.error("账号或密码错误")
        with tab_r:
            with st.form("register_form"):
                ru = st.text_input("新学号")
                rp = st.text_input("新密码", type="password")
                rp2 = st.text_input("确认密码", type="password")
                reg_submitted = st.form_submit_button("立即注册", type="primary", use_container_width=True)
                if reg_submitted:
                    if ru.strip() and rp.strip() == rp2.strip() and register_user(ru.strip(), rp.strip()):
                        st.toast("注册成功！请切换到登录页面。", icon="✅")
                    else:
                        st.error("注册失败（学号已被占用或密码不一致）。")
    st.stop()

sidebar_slot = st.sidebar.empty()

if st.session_state.page_mode != "grading":
    with sidebar_slot.container():
        st.write(
            f"当前账号: `{st.session_state.current_user}` ({'管理员' if st.session_state.user_role == 'admin' else '学生'})")
        if st.session_state.user_role == 'student':
            if st.session_state.page_mode != "home":
                if st.button("🏠 返回大厅"):
                    engine = get_database_engine()
                    with engine.connect() as conn:
                        conn.execute(text("UPDATE users SET current_quiz_ids = NULL WHERE username = :u"),
                                     {"u": st.session_state.current_user})
                        conn.commit()
                    st.session_state.page_mode = "home"
                    st.rerun()
            if st.session_state.page_mode != "report":
                if st.button("📊 我的学情报告"):
                    st.session_state.page_mode = "report"
                    st.rerun()
        if st.button("🚪 退出登录"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
else:
    sidebar_slot.empty()

if st.session_state.page_mode == "admin" and st.session_state.user_role == "admin":
    st.markdown("<h1>👨‍💻 教务管理看板与控制台</h1>", unsafe_allow_html=True)
    tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📊 可视化数据大屏", "🕒 登录日志", "⏱️ 学习时长追踪", "💬 AI辅导监控", "🛠️ 课程与题库管理",
         "⚙️ 智能辅导大模型设置"])
    engine = get_database_engine()
    with engine.connect() as conn:
        with tab0:
            st.subheader("🎓 全系统学情实时监控看板")
            st.markdown("---")
            st.markdown("#### 🕒 最近7天系统活跃人数趋势")
            try:
                sql_active = text(
                    "SELECT DATE(login_time) as login_date, COUNT(DISTINCT username) as user_count FROM login_logs WHERE login_time >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) GROUP BY login_date ORDER BY login_date;")
                df_active = pd.read_sql(sql_active, conn)
                if not df_active.empty:
                    df_active['login_date'] = pd.to_datetime(df_active['login_date'])
                    st.line_chart(df_active, x='login_date', y='user_count', use_container_width=True)
            except Exception as e:
                logging.error(f"Dashboard Active Users Error: {e}")

            st.markdown("---")
            st.markdown("#### 📘 各科课程学习时长占比")
            col_chart1, col_data1 = st.columns([2, 1])
            try:
                sql_duration = text(
                    "SELECT course_name, SUM(duration_seconds) as total_seconds FROM study_sessions WHERE duration_seconds IS NOT NULL GROUP BY course_name;")
                df_duration = pd.read_sql(sql_duration, conn)
                if not df_duration.empty:
                    df_duration['total_minutes'] = (df_duration['total_seconds'] / 60).round(1)
                    fig_pie = px.pie(df_duration, values='total_minutes', names='course_name', hole=0.4,
                                     color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    with col_chart1:
                        st.plotly_chart(fig_pie, use_container_width=True)
                    with col_data1:
                        st.markdown("<div style='margin-top: 100px;'></div>", unsafe_allow_html=True)
                        st.dataframe(df_duration[['course_name', 'total_minutes']], hide_index=True)
            except Exception as e:
                logging.error(f"Dashboard Duration Error: {e}")

            st.markdown("---")
            st.markdown("#### ✅ 全系统题目平均正确率统计")
            try:
                df_interact_raw = pd.read_sql(
                    "SELECT question_id, ai_response FROM interaction_logs WHERE user_query LIKE '【答案提交】%%'", conn)
                if not df_interact_raw.empty:
                    q_df = pd.read_sql("SELECT id, category FROM custom_questions", conn)
                    q_id_map = {str(1000 + int(row['id'])): str(row['category']) for _, row in q_df.iterrows()}
                    df_interact_raw['clean_id'] = pd.to_numeric(df_interact_raw['question_id'], errors='coerce').fillna(
                        -1).astype(int).astype(str)
                    df_interact_raw['course_name'] = df_interact_raw['clean_id'].map(q_id_map)
                    df_valid = df_interact_raw.dropna(subset=['course_name']).copy()
                    if not df_valid.empty:
                        df_valid['is_correct'] = df_valid['ai_response'].apply(
                            lambda x: 1 if ('正确' in str(x) or 'PASS' in str(x)) else 0)
                        df_accuracy = df_valid.groupby('course_name')['is_correct'].mean().reset_index()
                        df_accuracy['accuracy_percent'] = (df_accuracy['is_correct'] * 100).round(1)
                        fig_bar = px.bar(df_accuracy, x='course_name', y='accuracy_percent',
                                         labels={'course_name': '课程名称', 'accuracy_percent': '正确率 (%)'},
                                         color_discrete_sequence=['#1f77b4'])
                        if len(df_accuracy) == 1:
                            fig_bar.update_traces(width=0.2)
                        st.plotly_chart(fig_bar, use_container_width=True)
                    else:
                        st.warning("⚠️ 无法生成图表：题号映射失败！")
                else:
                    st.info("暂无答题提交数据，无法计算正确率。")
            except Exception as e:
                st.error(f"⚠️ 图表加载报错: {e}")

            st.markdown("---")
            st.markdown("#### 🛡️ 智能辅导答案泄露控制统计")
            try:
                df_leak = pd.read_sql(
                    "SELECT is_leaking_answer, leakage_score, rewrite_count FROM interaction_logs WHERE user_query LIKE '【辅导】%%'",
                    conn)
                if not df_leak.empty:
                    total_hints = len(df_leak)
                    leaked_hints = int(df_leak['is_leaking_answer'].fillna(0).astype(int).sum())
                    rewrite_total = int(df_leak.get('rewrite_count', pd.Series([0] * total_hints)).fillna(0).astype(int).sum())
                    leak_rate = round(leaked_hints / total_hints * 100, 1)
                    c_leak1, c_leak2, c_leak3 = st.columns(3)
                    c_leak1.metric("辅导提示总数", total_hints)
                    c_leak2.metric("最终泄露率", f"{leak_rate} %")
                    c_leak3.metric("自动重写次数", rewrite_total)
                    score_df = df_leak.groupby('leakage_score').size().reset_index(name='count')
                    fig_leak = px.bar(score_df, x='leakage_score', y='count',
                                      labels={'leakage_score': '泄露评分', 'count': '提示数量'},
                                      color_discrete_sequence=['#2ca02c'])
                    st.plotly_chart(fig_leak, use_container_width=True)
                else:
                    st.info("暂无智能辅导提示数据，无法计算泄露控制指标。")
            except Exception as e:
                logging.error(f"Leakage dashboard error: {e}")
                st.info("当前数据库尚未记录泄露控制扩展指标。")

        with tab1:
            st.subheader("学生活跃度监控")
            df_login = pd.read_sql(
                "SELECT username AS '学号', login_time AS '登录时间' FROM login_logs ORDER BY login_time DESC LIMIT 50",
                conn)
            st.dataframe(df_login, use_container_width=True)
            if not df_login.empty:
                st.download_button("📥 导出登录日志 (CSV)", df_login.to_csv(index=False).encode('utf-8-sig'),
                                   "login_logs.csv", "text/csv", use_container_width=True)

        with tab2:
            st.subheader("各科课程学习时长分析")
            df_study = pd.read_sql(
                "SELECT username AS '学号', course_name AS '课程', start_time AS '开始时间', end_time AS '结束时间', duration_seconds AS '学习时长(秒)' FROM study_sessions ORDER BY start_time DESC LIMIT 50",
                conn)
            st.dataframe(df_study, use_container_width=True)
            if not df_study.empty:
                st.download_button("📥 导出学习时长记录 (CSV)", df_study.to_csv(index=False).encode('utf-8-sig'),
                                   "study_sessions.csv", "text/csv", use_container_width=True)

        with tab3:
            st.subheader("大模型交互质量抽查")
            try:
                df_chat = pd.read_sql(
                    "SELECT student_id AS '学号', question_id AS '题号', user_query AS '学生提问', ai_response AS '系统反馈', is_leaking_answer AS '是否泄露', leakage_score AS '泄露评分', rewrite_count AS '重写次数', leakage_reason AS '检测原因', created_at AS '交互时间' FROM interaction_logs ORDER BY created_at DESC LIMIT 50",
                    conn)
            except Exception:
                df_chat = pd.read_sql(
                    "SELECT student_id AS '学号', question_id AS '题号', user_query AS '学生提问', ai_response AS '系统反馈', created_at AS '交互时间' FROM interaction_logs ORDER BY created_at DESC LIMIT 50",
                    conn)
            st.dataframe(df_chat, use_container_width=True)
            if not df_chat.empty:
                st.download_button("📥 导出AI辅导监控记录 (CSV)", df_chat.to_csv(index=False).encode('utf-8-sig'),
                                   "ai_interaction_logs.csv", "text/csv", use_container_width=True)

        with tab4:
            st.subheader("📚 课程管理")
            t_c_add, t_c_del, t_c_edit, t_c_view = st.tabs(
                ["➕ 录入新课程", "🗑️ 删除自定义课程", "✏️ 修改自定义课程", "👀 预览自定义课程"])
            with t_c_add:
                with st.form("add_course_form"):
                    new_c_name = st.text_input("新课程名称")
                    new_c_desc = st.text_input("课程简介描述")
                    if st.form_submit_button("确认添加", type="primary", use_container_width=True):
                        if new_c_name and new_c_desc:
                            try:
                                conn.execute(
                                    text("INSERT INTO custom_courses (course_name, description) VALUES (:n, :d)"),
                                    {"n": new_c_name, "d": new_c_desc})
                                conn.commit()
                                st.toast(f"课程《{new_c_name}》添加成功！", icon="✅")
                                time.sleep(0.5)
                                st.rerun()
                            except Exception as e:
                                st.toast(f"添加失败: {e}", icon="❌")
                        else:
                            st.toast("请填写完整的课程信息！", icon="⚠️")

            with t_c_del:
                with st.form("delete_course_form"):
                    try:
                        del_c_list = [r[0] for r in
                                      conn.execute(text("SELECT course_name FROM custom_courses")).fetchall()]
                    except Exception as e:
                        logging.error(f"Delete course load error: {e}")
                        del_c_list = []
                    if del_c_list:
                        del_c_name = st.selectbox("选择要下架的课程", del_c_list)
                        if st.form_submit_button("确认删除 (将同步删除下属题目)", type="primary",
                                                 use_container_width=True):
                            conn.execute(text("DELETE FROM custom_courses WHERE course_name = :c"), {"c": del_c_name})
                            conn.execute(text("DELETE FROM custom_questions WHERE category = :c"), {"c": del_c_name})
                            conn.commit()
                            st.toast(f"已彻底删除课程《{del_c_name}》！", icon="✅")
                            time.sleep(0.5)
                            st.rerun()
                    else:
                        st.info("暂无自定义课程可以删除。")
                        st.form_submit_button("确认删除", disabled=True, use_container_width=True)

            with t_c_edit:
                try:
                    edit_c_options = {r[0]: r for r in conn.execute(
                        text("SELECT course_name, description FROM custom_courses")).fetchall()}
                except Exception as e:
                    logging.error(f"Edit course load error: {e}")
                    edit_c_options = {}

                if edit_c_options:
                    edit_c_choice = st.selectbox("👇 第一步：选择需要修改的课程", list(edit_c_options.keys()),
                                                 key="edit_c_select")
                    selected_c_name, selected_c_desc = edit_c_options[edit_c_choice]
                    with st.form("edit_course_form"):
                        st.write("👇 第二步：在下方直接编辑并保存")
                        updated_c_name = st.text_input("修改课程名称", value=selected_c_name)
                        updated_c_desc = st.text_input("修改课程简介描述", value=selected_c_desc)
                        if st.form_submit_button("💾 保存修改", type="primary", use_container_width=True):
                            if updated_c_name.strip() and updated_c_desc.strip():
                                try:
                                    conn.execute(text(
                                        "UPDATE custom_courses SET course_name = :new_n, description = :new_d WHERE course_name = :old_n"),
                                        {"new_n": updated_c_name.strip(), "new_d": updated_c_desc.strip(),
                                         "old_n": selected_c_name})
                                    if updated_c_name.strip() != selected_c_name:
                                        conn.execute(text(
                                            "UPDATE custom_questions SET category = :new_n WHERE category = :old_n"),
                                            {"new_n": updated_c_name.strip(), "old_n": selected_c_name})
                                    conn.commit()
                                    st.toast("课程修改成功！", icon="✅")
                                    time.sleep(0.5)
                                    st.rerun()
                                except Exception as e:
                                    st.toast(f"修改失败: {e}", icon="❌")
                            else:
                                st.toast("课程名称和描述不能为空！", icon="⚠️")
                else:
                    st.info("暂无自定义课程可以修改。")

            with t_view:
                try:
                    df_custom_c = pd.read_sql(
                        "SELECT course_name AS '课程名称', description AS '课程简介描述' FROM custom_courses", conn)
                    if not df_custom_c.empty:
                        st.dataframe(df_custom_c, use_container_width=True)
                    else:
                        st.info("当前云端数据库中暂无任何自定义课程。")
                except Exception as e:
                    st.warning(f"读取课程失败: {e}")

            st.divider()
            st.subheader("📝 题库管理")
            hardcoded_c = ["高等数学", "线性代数", "概率统计", "C语言"]
            try:
                custom_course_names = [
                    r[0] for r in conn.execute(text("SELECT course_name FROM custom_courses")).fetchall()
                ]
                all_c = list(dict.fromkeys(hardcoded_c + custom_course_names))
            except Exception as e:
                logging.error(f"Load courses for questions error: {e}")
                all_c = hardcoded_c

            t_add, t_del, t_edit, t_view = st.tabs(
                ["➕ 录入新题目", "🗑️ 删除自定义题目", "✏️ 修改自定义题目", "👀 预览自定义题库"])

            with t_add:
                with st.form("add_question_form"):
                    q_category = st.selectbox("选择所属课程", all_c)
                    q_content = st.text_area("输入题目内容 (支持 LaTeX 格式)")
                    q_answer = st.text_input("标准答案（可选，但建议填写；选择题可填 A/B/C/D）")
                    q_solution = st.text_area("标准解析（可选，用于判题和受控提示生成）", height=120)
                    if st.form_submit_button("确认录入题目", type="primary", use_container_width=True):
                        if q_category and q_content:
                            try:
                                conn.execute(
                                    text("INSERT INTO custom_questions (category, content, answer, solution) VALUES (:c, :t, :a, :s)"),
                                    {
                                        "c": q_category,
                                        "t": q_content,
                                        "a": q_answer.strip(),
                                        "s": q_solution.strip(),
                                    }
                                )
                                conn.commit()
                                st.toast("题目添加成功！", icon="✅")
                                time.sleep(0.5)
                                st.rerun()
                            except Exception as e:
                                st.toast(f"题目添加失败: {e}", icon="❌")
                        else:
                            st.toast("请填写完整的题目内容！", icon="⚠️")

            with t_del:
                with st.form("delete_question_form"):
                    try:
                        del_q_options = {f"[{r[1]}] {r[2]}... (内部ID:{r[0]})": r[0] for r in conn.execute(
                            text("SELECT id, category, LEFT(content, 15) FROM custom_questions")).fetchall()}
                    except Exception as e:
                        logging.error(f"Load questions for delete error: {e}")
                        del_q_options = {}

                    if del_q_options:
                        del_q_choice = st.selectbox("选择要删除的错误题目", list(del_q_options.keys()))
                        if st.form_submit_button("确认删除该题", type="primary", use_container_width=True):
                            conn.execute(text("DELETE FROM custom_questions WHERE id = :id"),
                                         {"id": del_q_options[del_q_choice]})
                            conn.commit()
                            st.toast("指定题目已永久删除！", icon="✅")
                            time.sleep(0.5)
                            st.rerun()
                    else:
                        st.info("暂无自定义题目可以删除。")
                        st.form_submit_button("确认删除", disabled=True, use_container_width=True)

            with t_edit:
                try:
                    edit_q_options = {f"[{r[1]}] (内部ID:{r[0]}) {r[2][:20]}...": (r[0], r[1], r[2], r[3] or "", r[4] or "") for r in
                                      conn.execute(
                                          text("SELECT id, category, content, answer, solution FROM custom_questions")).fetchall()}
                except Exception as e:
                    logging.error(f"Load questions for edit error: {e}")
                    edit_q_options = {}

                if edit_q_options:
                    edit_q_choice = st.selectbox("👇 第一步：选择需要修改的题目", list(edit_q_options.keys()),
                                                 key="edit_q_select")
                    selected_id, selected_cat, selected_content, selected_answer, selected_solution = edit_q_options[edit_q_choice]
                    with st.form("edit_question_form"):
                        new_category = st.selectbox("修改所属课程", all_c,
                                                    index=all_c.index(selected_cat) if selected_cat in all_c else 0)
                        new_content = st.text_area("修改题目内容 (支持 LaTeX 格式)", value=selected_content, height=150)
                        new_answer = st.text_input("修改标准答案", value=selected_answer)
                        new_solution = st.text_area("修改标准解析", value=selected_solution, height=120)
                        if st.form_submit_button("💾 保存修改", type="primary", use_container_width=True):
                            if new_content.strip():
                                try:
                                    conn.execute(
                                        text("UPDATE custom_questions SET category = :c, content = :t, answer = :a, solution = :s WHERE id = :id"),
                                        {
                                            "c": new_category,
                                            "t": new_content,
                                            "a": new_answer.strip(),
                                            "s": new_solution.strip(),
                                            "id": selected_id,
                                        })
                                    conn.commit()
                                    st.toast("题目修改成功！", icon="✅")
                                    time.sleep(0.5)
                                    st.rerun()
                                except Exception as e:
                                    st.toast(f"修改失败: {e}", icon="❌")
                            else:
                                st.toast("题目内容不能为空！", icon="⚠️")
                else:
                    st.info("暂无自定义题目可以修改。")

            with t_view:
                try:
                    df_custom_q = pd.read_sql(
                        "SELECT id AS '内部ID', category AS '所属课程', content AS '题目完整内容', answer AS '标准答案', solution AS '标准解析' FROM custom_questions ORDER BY id DESC",
                        conn)
                    if not df_custom_q.empty:
                        st.dataframe(df_custom_q, use_container_width=True)
                    else:
                        st.info("当前云端数据库中暂无任何自定义题目。")
                except Exception as e:
                    st.warning(f"读取题库失败: {e}")

        with tab5:
            st.subheader("🧠 大模型 Prompt 注入控制台")
            st.info("💡 在这里热更新大模型的底层性格与辅导策略！修改保存后，所有学生的 AI 辅导体验将瞬间改变。")
            try:
                curr_prompt_res = conn.execute(
                    text("SELECT config_value FROM system_configs WHERE config_key = 'system_instruction'")).fetchone()
                current_prompt = curr_prompt_res[0] if curr_prompt_res else SYSTEM_INSTRUCTION
            except Exception as e:
                logging.error(f"Load prompt config error: {e}")
                current_prompt = SYSTEM_INSTRUCTION

            with st.form("prompt_update_form"):
                new_prompt = st.text_area("🔧 当前系统底层提示词 (System Prompt)", value=current_prompt, height=250)
                if st.form_submit_button("💾 保存并全局应用新指令", type="primary", use_container_width=True):
                    if new_prompt.strip():
                        try:
                            conn.execute(text(
                                "INSERT INTO system_configs (config_key, config_value) VALUES ('system_instruction', :val) ON DUPLICATE KEY UPDATE config_value = :val"),
                                {"val": new_prompt.strip()})
                            conn.commit()
                            st.toast("大模型底层指令已热更新！全系统生效！", icon="✅")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.toast(f"更新失败: {e}", icon="❌")
                    else:
                        st.toast("提示词不能为空！", icon="⚠️")

elif st.session_state.page_mode == "home" and st.session_state.user_role == "student":
    st.markdown("<h1 style='text-align: center;'>🏫 课程学习大厅</h1>", unsafe_allow_html=True)
    st.write("请选择你要进行随堂测验的课程模块：")
    st.divider()
    base_courses = [
        ("高等数学", "包含极限、导数、微积分等核心考点，重点测试逻辑推导能力。"),
        ("线性代数", "包含矩阵运算、特征值、二次型等，培养空间与代数转换思维。"),
        ("概率统计", "包含随机变量、分布规律、信息熵等，结合实际应用场景。"),
        ("C语言", "包含指针、数组、结构体等核心语法，锻炼底层逻辑与编程思维。")
    ]
    existing_course_names = {name for name, _ in base_courses}
    engine = get_database_engine()
    with engine.connect() as conn:
        try:
            for r in conn.execute(text("SELECT course_name, description FROM custom_courses")).fetchall():
                if r[0] not in existing_course_names:
                    base_courses.append((r[0], r[1]))
                    existing_course_names.add(r[0])
        except Exception as e:
            logging.error(f"Load courses error: {e}")

    cols = st.columns(4)
    for idx, (c_name, c_desc) in enumerate(base_courses):
        with cols[idx % 4]:
            st.markdown(f"### 📘 {c_name}")
            st.caption(c_desc)
            if st.button(f"进入《{c_name}》测验", key=f"btn_{c_name}", use_container_width=True):
                start_experiment_session(c_name)

elif st.session_state.page_mode == "quiz":
    page = st.empty()

    with page.container():
        st.warning("⚠️ 考试进行中，请勿刷新网页或退出登录，否则未提交的作答记录将会丢失！")

        idx = st.session_state.current_question_index
        total = len(st.session_state.quiz_queue)
        q = st.session_state.quiz_queue[idx]

        current_ans_key = f"ans_{idx}"
        if current_ans_key in st.session_state:
            st.session_state.user_answers[idx] = st.session_state[current_ans_key]

        st.markdown("### 🗂️ 题目列表")
        with st.container():
            cols_per_row = 10
            for i in range(0, total, cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    q_idx = i + j
                    if q_idx < total:
                        with cols[j]:
                            is_answered = bool(st.session_state.user_answers.get(q_idx, "").strip())
                            btn_type = "primary" if q_idx == idx else "secondary"
                            btn_label = f"{q_idx + 1} ✅" if is_answered else str(q_idx + 1)

                            if st.button(btn_label, key=f"nav_btn_{q_idx}", type=btn_type, use_container_width=True):
                                st.session_state.current_question_index = q_idx
                                st.rerun()

        st.divider()

        st.progress((idx + 1) / total, text=f"【{st.session_state.current_course}】 进度：{idx + 1} / {total}")
        st.markdown(f"### 第 {idx + 1} 题")
        st.info(format_math(q['content']))

        st.markdown("#### ✍️ 你的解答")
        ans = st.text_area("请输入你的答案（选择题请直接输入选项字母）：",
                           value=st.session_state.user_answers.get(idx, ""), height=150, key=f"ans_{idx}")
        st.session_state.user_answers[idx] = ans

        cols = st.columns(2)
        with cols[0]:
            if idx > 0 and st.button("⬅️ 上一题", use_container_width=True):
                st.session_state.current_question_index -= 1
                st.rerun()

        with cols[1]:
            if idx < total - 1:
                if st.button("下一题 ➡️", use_container_width=True):
                    st.session_state.current_question_index += 1
                    st.rerun()
            else:
                if st.button("✅ 提交试卷", type="primary", use_container_width=True):
                    missing = [str(i + 1) for i in range(total) if not st.session_state.user_answers.get(i, "").strip()]
                    if missing:
                        st.warning(f"⚠️ 第 {'、'.join(missing)} 题尚未作答，请完成后再提交。")
                    else:
                        st.session_state.is_grading = True
                        st.session_state.grading_started = False
                        st.session_state.page_mode = "grading"
                        st.rerun()

elif st.session_state.page_mode == "grading":
    st.session_state.is_grading = True
    sidebar_slot.empty()

    st.markdown("""
<style>
section[data-testid="stSidebar"],
[data-testid="stSidebar"],
div[data-testid="stSidebarUserContent"] {
    display: none !important;
    width: 0 !important;
    min-width: 0 !important;
}

header[data-testid="stHeader"],
[data-testid="stHeader"] {
    display: none !important;
}

div[data-testid="stToolbar"],
[data-testid="stToolbar"] {
    display: none !important;
}

div[data-testid="collapsedControl"],
[data-testid="collapsedControl"] {
    display: none !important;
}

div[data-testid="stStatusWidget"],
[data-testid="stStatusWidget"] {
    display: none !important;
}

div[data-testid="stDecoration"] {
    display: none !important;
}

#MainMenu,
footer {
    display: none !important;
}

.block-container {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    max-width: 100% !important;
}

html, body, [data-testid="stAppViewContainer"] {
    overflow: hidden !important;
}
</style>
<div style="height: 100vh; display: flex; align-items: center; justify-content: center;">
    <h2>🧠 系统正在阅卷中，请勿刷新或退出...</h2>
</div>
""", unsafe_allow_html=True)

    if not st.session_state.grading_started:
        st.session_state.grading_started = True
        submit_and_assess()

elif st.session_state.page_mode == "results":
    st.title("📊 作答结果与辅导")
    if st.button("🔄 返回大厅开启新课程"):
        st.session_state.page_mode = "home"
        st.rerun()
    st.divider()

    total_count = len(st.session_state.assessment_results)
    correct_count = sum(1 for item in st.session_state.assessment_results if item["is_correct"])
    wrong_count = total_count - correct_count
    accuracy = round(correct_count / total_count * 100, 1) if total_count else 0.0
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("本次题数", total_count)
    metric_col2.metric("答对题数", correct_count)
    metric_col3.metric("待复盘错题", wrong_count)
    metric_col4.metric("正确率", f"{accuracy} %")
    st.download_button(
        "📥 导出本次测验结果",
        build_result_export(st.session_state.assessment_results).encode("utf-8-sig"),
        file_name=f"quiz_result_{now_shanghai():%Y%m%d_%H%M%S}.md",
        mime="text/markdown",
        use_container_width=True,
    )

    l_col, r_col = st.columns([1, 1])
    with l_col:
        st.subheader("题目导航")
        for i, res in enumerate(st.session_state.assessment_results):
            label = "✅ 正确" if res['is_correct'] else "❌ 错误"
            if st.button(f"题 {i + 1} | {label}", key=f"n_{i}", use_container_width=True):
                st.session_state.review_question_index = i
                st.rerun()
    with r_col:
        st.subheader("智能辅导区")
        if st.session_state.review_question_index is not None:
            ridx = st.session_state.review_question_index
            data = st.session_state.assessment_results[ridx]
            qid = data['question_data']['id']
            st.info(format_math(data['question_data']['content']))
            st.write(f"您的作答: {data['user_answer']}")
            st.divider()
            if qid not in st.session_state.chat_histories:
                st.session_state.chat_histories[qid] = []
                if not data['is_correct']:
                    st.session_state.chat_histories[qid].append({"role": "assistant", "content": "智能辅导"})
            for m in st.session_state.chat_histories[qid]:
                with st.chat_message(m["role"]):
                    st.markdown(format_math(m["content"]))

            composer_input_key = f"composer_input_{qid}"
            composer_reset_key = f"composer_reset_{qid}"
            math_widget_version_key = f"math_widget_version_{qid}"

            if composer_input_key not in st.session_state:
                st.session_state[composer_input_key] = ""

            if composer_reset_key not in st.session_state:
                st.session_state[composer_reset_key] = False

            if math_widget_version_key not in st.session_state:
                st.session_state[math_widget_version_key] = 0

            if st.session_state[composer_reset_key]:
                st.session_state[composer_input_key] = ""
                st.session_state[math_widget_version_key] += 1
                st.session_state[composer_reset_key] = False

            with st.container(border=True):
                composer_value = math_input(
                    default_value=st.session_state.get(composer_input_key, ""),
                    key=f"react_math_{qid}_{st.session_state[math_widget_version_key]}"
                )

                if composer_value is not None:
                    st.session_state[composer_input_key] = composer_value

            send_col1, send_col2 = st.columns([5, 1])

            with send_col2:
                if st.button("发送", key=f"send_help_{qid}", type="primary", use_container_width=True):
                    query = st.session_state.get(composer_input_key, "").strip()
                    if query:
                        st.session_state.chat_histories[qid].append({"role": "user", "content": query})
                        st.session_state[composer_reset_key] = True
                        st.rerun()
                    else:
                        st.warning("请输入辅导问题后再发送。")

            if st.session_state.chat_histories[qid] and st.session_state.chat_histories[qid][-1]["role"] == "user":
                with st.chat_message("assistant"):
                    last_query = st.session_state.chat_histories[qid][-1]["content"]
                    try:
                        with st.spinner("正在生成并进行答案泄露检测..."):
                            controlled = generate_controlled_hint(
                                data['question_data'],
                                data['user_answer'],
                                data['is_correct'],
                                last_query
                            )
                        final = controlled["hint"]
                        st.markdown(final)
                        if controlled["rewrite_count"] > 0:
                            st.caption(f"已自动重写 {controlled['rewrite_count']} 次，以降低答案泄露风险。")
                        st.session_state.chat_histories[qid].append({"role": "assistant", "content": final})
                        log_interaction(
                            qid,
                            f"【辅导】{last_query}",
                            final,
                            leak=controlled["is_leaking"],
                            leakage_score=controlled["leakage_score"],
                            rewrite_count=controlled["rewrite_count"],
                            leakage_reason=controlled["leakage_reason"]
                        )
                    except Exception as e:
                        logging.error(f"Controlled hint generation error: {e}")
                        fallback = "这道题我们先不急着看答案。你可以先指出题目中最关键的条件是什么，再想一想它对应哪个定义或公式？"
                        st.markdown(fallback)
                        st.session_state.chat_histories[qid].append({"role": "assistant", "content": fallback})
                        log_interaction(qid, f"【辅导】{last_query}", fallback, leak=0)

elif st.session_state.page_mode == "report" and st.session_state.user_role == "student":
    st.markdown("<h1 style='text-align: center;'>📊 个人学情中心与错题记录</h1>", unsafe_allow_html=True)
    st.divider()
    engine = get_database_engine()
    with engine.connect() as conn:
        study_res = conn.execute(text("SELECT SUM(duration_seconds) FROM study_sessions WHERE username = :u"),
                                 {"u": st.session_state.current_user}).fetchone()
        total_seconds = study_res[0] if study_res and study_res[0] else 0
        total_minutes = round(total_seconds / 60)

        ans_logs = conn.execute(text(
            "SELECT question_id, ai_response FROM interaction_logs WHERE student_id = :u AND user_query LIKE '【答案提交】%%'"),
            {"u": st.session_state.current_user}).fetchall()
        total_answered = len(ans_logs)
        total_correct = sum(1 for log in ans_logs if '正确' in str(log[1]) or 'PASS' in str(log[1]))
        accuracy = round((total_correct / total_answered * 100), 1) if total_answered > 0 else 0.0

        wrong_qids = set()
        for log in ans_logs:
            if '错误' in str(log[1]) or 'FAIL' in str(log[1]):
                try:
                    wrong_qids.add(int(log[0]))
                except Exception as e:
                    logging.error(f"Parse qid error: {e}")

    col1, col2, col3 = st.columns(3)
    col1.metric("⏱️ 累计专注学习", f"{total_minutes} 分钟")
    col2.metric("✅ 累计答对题数", f"{total_correct} 题")
    col3.metric("🎯 历史平均正确率", f"{accuracy} %")

    st.markdown("---")
    st.subheader("📓 错题记录与智能辅导")
    if not wrong_qids:
        st.info("你目前没有任何错题记录")
    else:
        db_ids = [int(qid) - 1000 for qid in wrong_qids]
        q_dict = {}
        if db_ids:
            with engine.connect() as conn:
                try:
                    res = fetch_custom_question_rows(conn, db_ids)
                    q_dict = {1000 + r[0]: {"category": r[1], "content": r[2]} for r in res}
                except Exception as e:
                    logging.error(f"Fetch wrong questions error: {e}")

        for qid in wrong_qids:
            if qid in q_dict:
                q_data = q_dict[qid]
                with st.expander(f"[{q_data['category']}] 错题回顾 (题号: {qid})"):
                    st.info(format_math(q_data['content']))
                    if qid in st.session_state.chat_histories and st.session_state.chat_histories[qid]:
                        st.markdown("##### 💬 智能辅导记录")
                        for m in st.session_state.chat_histories[qid]:
                            if m["role"] == "user":
                                st.markdown(f"**🧑‍🎓 你**: {m['content']}")
                            else:
                                st.markdown(f"**🤖 智能辅导员**: {m['content']}")
                    else:
                        st.caption("暂无针对此题的对话辅导记录。")
