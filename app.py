import streamlit as st
import os
import random
import time
import hashlib
from typing import List, Dict, Optional, Any
from sqlalchemy import create_engine, text, Engine
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import pytz
from prompts import SYSTEM_INSTRUCTION, JUDGE_PROMPT_SYSTEM
from questions import QUESTION_BANK

load_dotenv()


class AppConfig:
    LLM_API_KEY = st.secrets.get("LLM_API_KEY") or os.getenv("LLM_API_KEY")
    DB_USER = st.secrets.get("DB_USER") or os.getenv("DB_USER")
    DB_PASSWORD = st.secrets.get("DB_PASSWORD") or os.getenv("DB_PASSWORD")
    DB_HOST = st.secrets.get("DB_HOST") or os.getenv("DB_HOST")
    DB_NAME = st.secrets.get("DB_NAME") or os.getenv("DB_NAME")
    BASE_URL = "https://api.deepseek.com"


client = OpenAI(api_key=AppConfig.LLM_API_KEY, base_url=AppConfig.BASE_URL)


@st.cache_resource
def get_database_engine() -> Engine:
    connection_url = f"mysql+pymysql://{AppConfig.DB_USER}:{AppConfig.DB_PASSWORD}@{AppConfig.DB_HOST}/{AppConfig.DB_NAME}"
    return create_engine(connection_url, pool_recycle=1800, pool_pre_ping=True)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def sync_user_data(username: str):
    engine = get_database_engine()
    with engine.connect() as conn:
        u_res = conn.execute(text("SELECT current_quiz_ids FROM users WHERE username = :u"), {"u": username}).fetchone()
        if u_res and u_res[0]:
            q_ids = [int(i) for i in u_res[0].split(",")]
            st.session_state.quiz_queue = [q for q in QUESTION_BANK if q['id'] in q_ids]
            st.session_state.page_mode = "quiz"

        logs = conn.execute(
            text("SELECT question_id, user_query, ai_response FROM interaction_logs WHERE student_id = :u"),
            {"u": username}).fetchall()
        for row in logs:
            qid, qry, rsp = row
            if qid not in st.session_state.chat_histories:
                st.session_state.chat_histories[qid] = []
            if "【辅导】" in qry:
                st.session_state.chat_histories[qid].append({"role": "user", "content": qry.replace("【辅导】", "")})
                st.session_state.chat_histories[qid].append({"role": "assistant", "content": rsp})


def authenticate_user(u: str, p: str) -> bool:
    engine = get_database_engine()
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id FROM users WHERE username = :u AND password_hash = :p"),
                           {"u": u, "p": hash_password(p)}).fetchone()
        return res is not None


def register_user(u: str, p: str) -> bool:
    engine = get_database_engine()
    with engine.connect() as conn:
        if conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": u}).fetchone():
            return False
        conn.execute(text("INSERT INTO users (username, password_hash) VALUES (:u, :p)"),
                     {"u": u, "p": hash_password(p)})
        conn.commit()
        return True


def init_session_state():
    defaults = {
        "logged_in": False, "current_user": None, "page_mode": "home",
        "quiz_queue": [], "current_question_index": 0, "user_answers": {},
        "assessment_results": [], "review_question_index": None,
        "chat_histories": {}, "session_count": 0
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v


init_session_state()


def log_interaction(qid: int, qry: str, rsp: str, leak: int = 0):
    try:
        engine = get_database_engine()
        with engine.connect() as conn:
            ts = datetime.now(pytz.timezone('Asia/Shanghai'))
            conn.execute(text(
                "INSERT INTO interaction_logs (question_id, student_id, user_query, ai_response, is_leaking_answer, created_at) VALUES (:qid, :sid, :qry, :rsp, :leak, :time)"),
                {"qid": qid, "sid": st.session_state.current_user, "qry": qry, "rsp": rsp, "leak": leak,
                 "time": ts})
            conn.commit()
    except Exception as e:
        print(f"Error: {e}")


def start_experiment_session():
    selected = random.sample(QUESTION_BANK, 10) if len(QUESTION_BANK) >= 10 else QUESTION_BANK
    q_ids = ",".join([str(q['id']) for q in selected])
    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(text("UPDATE users SET current_quiz_ids = :ids WHERE username = :u"),
                     {"ids": q_ids, "u": st.session_state.current_user})
        conn.commit()
    st.session_state.quiz_queue = selected
    st.session_state.user_answers = {i: "" for i in range(len(selected))}
    st.session_state.page_mode = "quiz"
    st.rerun()


def submit_and_assess():
    st.session_state.assessment_results = []
    p_bar = st.progress(0, text="分析中...")
    total = len(st.session_state.quiz_queue)
    for i, q in enumerate(st.session_state.quiz_queue):
        ans = st.session_state.user_answers.get(i, "未作答")
        prompt = f"题目：{q['content']}\n学生答案：{ans}\n任务：判断是否正确。正确输出PASS，错误输出FAIL。"
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": JUDGE_PROMPT_SYSTEM}, {"role": "user", "content": prompt}]
            )
            res_text = resp.choices[0].message.content.strip()
            is_ok = "PASS" in res_text and "FAIL" not in res_text
        except:
            is_ok = False

        st.session_state.assessment_results.append({"question_data": q, "user_answer": ans, "is_correct": is_ok})
        log_interaction(q["id"], f"【答案提交】{ans}", "正确" if is_ok else "错误")
        p_bar.progress((i + 1) / total)

    st.session_state.session_count += 1
    st.session_state.page_mode = "results"
    st.rerun()


st.set_page_config(page_title="可控解题提示生成系统", layout="wide")

if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🧩 可控解题提示生成系统</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        tab_l, tab_r = st.tabs(["🔑 登录", "📝 注册"])
        with tab_l:
            u_in, p_in = st.text_input("学号"), st.text_input("密码", type="password")
            if st.button("进入系统", type="primary", use_container_width=True):
                if authenticate_user(u_in, p_in):
                    st.session_state.logged_in, st.session_state.current_user = True, u_in
                    sync_user_data(u_in)
                    st.rerun()
                else:
                    st.error("验证失败")
        with tab_r:
            ru, rp, rp2 = st.text_input("新学号"), st.text_input("新密码", type="password"), st.text_input("确认密码",
                                                                                                           type="password")
            if st.button("立即注册", use_container_width=True):
                if ru and rp == rp2 and register_user(ru, rp):
                    st.success("注册成功，请切换到登录页面进行登录。")
                else:
                    st.error("注册失败（学号可能已被占用或密码不一致）。")
    st.stop()

with st.sidebar:
    st.write(f"当前用户: `{st.session_state.current_user}`")
    if st.button("退出"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

if st.session_state.page_mode == "home":
    st.markdown("<h1 style='text-align: center;'>🧩 智能辅导空间</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        if st.button("🚀 开始实验", type="primary", use_container_width=True): start_experiment_session()

elif st.session_state.page_mode == "quiz":
    idx = st.session_state.current_question_index
    total = len(st.session_state.quiz_queue)
    q = st.session_state.quiz_queue[idx]
    st.progress((idx + 1) / total, text=f"进度：{idx + 1} / {total}")
    st.markdown(f"### 第 {idx + 1} 题")

    # 修复处 1：答题页面的公式渲染
    st.info(q['content'].replace(r"\(", "$").replace(r"\)", "$").replace(r"\[", "$$").replace(r"\]", "$$"))

    ans = st.text_area("解题步骤", value=st.session_state.user_answers.get(idx, ""), height=200, key=f"ans_{idx}")
    st.session_state.user_answers[idx] = ans
    cols = st.columns(2)
    with cols[0]:
        if idx > 0 and st.button("⬅️ 上一题"):
            st.session_state.current_question_index -= 1
            st.rerun()
    with cols[1]:
        if idx < total - 1:
            if st.button("下一题 ➡️"):
                st.session_state.current_question_index += 1
                st.rerun()
        else:
            if st.button("✅ 提交", type="primary"):
                missing = [str(i + 1) for i in range(total) if not st.session_state.user_answers.get(i, "").strip()]
                if missing:
                    st.warning(f"⚠️ 第 {'、'.join(missing)} 题尚未作答，请完成后再提交。")
                else:
                    submit_and_assess()

elif st.session_state.page_mode == "results":
    st.title("📊 结果与辅导")
    if st.button("🔄 开启新一轮"): start_experiment_session()
    st.divider()
    l_col, r_col = st.columns([1, 1])
    with l_col:
        for i, res in enumerate(st.session_state.assessment_results):
            label = "✅ 正确" if res['is_correct'] else "❌ 错误"
            if st.button(f"题 {i + 1} | {label}", key=f"n_{i}", use_container_width=True):
                st.session_state.review_question_index = i
                st.rerun()
    with r_col:
        if st.session_state.review_question_index is not None:
            ridx = st.session_state.review_question_index
            data = st.session_state.assessment_results[ridx]
            qid = data['question_data']['id']

            # 修复处 2：结果辅导页面的公式渲染
            st.info(
                data['question_data']['content'].replace(r"\(", "$").replace(r"\)", "$").replace(r"\[", "$$").replace(
                    r"\]", "$$"))

            st.write(f"作答: {data['user_answer']}")
            st.divider()
            if qid not in st.session_state.chat_histories:
                st.session_state.chat_histories[qid] = []
                if not data['is_correct']: st.session_state.chat_histories[qid].append(
                    {"role": "assistant", "content": "发现思路偏差，哪里卡住了？"})
            for m in st.session_state.chat_histories[qid]:
                with st.chat_message(m["role"]): st.markdown(m["content"])
            if query := st.chat_input("请求提示..."):
                st.session_state.chat_histories[qid].append({"role": "user", "content": query})
                st.rerun()
            if st.session_state.chat_histories[qid] and st.session_state.chat_histories[qid][-1]["role"] == "user":
                with st.chat_message("assistant"):
                    h = st.empty()
                    f = ""
                    ctx = f"题目：{data['question_data']['content']}\n答案：{data['user_answer']}\n判题：{'正确' if data['is_correct'] else '错误'}\n请求：{query}"
                    stream = client.chat.completions.create(model="deepseek-chat",
                                                            messages=[{"role": "system", "content": SYSTEM_INSTRUCTION},
                                                                      {"role": "user", "content": ctx}], stream=True)
                    for chunk in stream:
                        c = chunk.choices[0].delta.content
                        if c:
                            f += c
                            h.markdown(f.replace(r"\[", "$$").replace(r"\]", "$$").replace(r"\(", "$").replace(r"\)",
                                                                                                               "$") + "▌")
                    final = f.replace(r"\[", "$$").replace(r"\]", "$$").replace(r"\(", "$").replace(r"\)", "$")
                    h.markdown(final)
                    st.session_state.chat_histories[qid].append({"role": "assistant", "content": final})
                    log_interaction(qid, f"【辅导】{query}", final)