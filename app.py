import streamlit as st
import os
import random
import time
import hashlib
import re
import pandas as pd
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


def format_math(text: str) -> str:
    text = re.sub(r"\\\(\s*", "$", text)
    text = re.sub(r"\s*\\\)", "$", text)
    text = re.sub(r"\\\[\s*", "$$", text)
    text = re.sub(r"\s*\\\]", "$$", text)
    return text


def authenticate_user(u: str, p: str):
    engine = get_database_engine()
    with engine.connect() as conn:
        res = conn.execute(text("SELECT role FROM users WHERE username = :u AND password_hash = :p"),
                           {"u": u, "p": hash_password(p)}).fetchone()
        if res:
            return True, res[0]
        return False, None


def register_user(u: str, p: str) -> bool:
    engine = get_database_engine()
    with engine.connect() as conn:
        if conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": u}).fetchone():
            return False
        conn.execute(text("INSERT INTO users (username, password_hash, role) VALUES (:u, :p, 'student')"),
                     {"u": u, "p": hash_password(p)})
        conn.commit()
        return True


def log_login(username: str):
    try:
        engine = get_database_engine()
        with engine.connect() as conn:
            ts = datetime.now(pytz.timezone('Asia/Shanghai'))
            conn.execute(text("INSERT INTO login_logs (username, login_time) VALUES (:u, :t)"),
                         {"u": username, "t": ts})
            conn.commit()
    except Exception as e:
        print(f"Login Log Error: {e}")


def log_interaction(qid: int, qry: str, rsp: str, leak: int = 0):
    try:
        engine = get_database_engine()
        with engine.connect() as conn:
            ts = datetime.now(pytz.timezone('Asia/Shanghai'))
            conn.execute(text(
                "INSERT INTO interaction_logs (question_id, student_id, user_query, ai_response, is_leaking_answer, created_at) VALUES (:qid, :sid, :qry, :rsp, :leak, :time)"),
                {"qid": qid, "sid": st.session_state.current_user, "qry": qry, "rsp": rsp, "leak": leak, "time": ts})
            conn.commit()
    except Exception as e:
        print(f"Interaction Log Error: {e}")


def init_session_state():
    defaults = {
        "logged_in": False, "current_user": None, "user_role": "student", "page_mode": "home",
        "quiz_queue": [], "current_question_index": 0, "user_answers": {},
        "assessment_results": [], "review_question_index": None,
        "chat_histories": {}, "session_count": 0, "study_session_id": None, "current_course": None
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v


init_session_state()


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


def start_experiment_session(course_name: str):
    # 筛选对应科目的题目
    course_questions = [q for q in QUESTION_BANK if q.get('category') == course_name]
    if not course_questions: course_questions = QUESTION_BANK

    selected = random.sample(course_questions, 10) if len(course_questions) >= 10 else course_questions
    q_ids = ",".join([str(q['id']) for q in selected])

    engine = get_database_engine()
    with engine.connect() as conn:
        conn.execute(text("UPDATE users SET current_quiz_ids = :ids WHERE username = :u"),
                     {"ids": q_ids, "u": st.session_state.current_user})
        # 记录学习开始时间
        ts = datetime.now(pytz.timezone('Asia/Shanghai'))
        res = conn.execute(text("INSERT INTO study_sessions (username, course_name, start_time) VALUES (:u, :c, :t)"),
                           {"u": st.session_state.current_user, "c": course_name, "t": ts})
        st.session_state.study_session_id = res.lastrowid
        conn.commit()

    st.session_state.current_course = course_name
    st.session_state.quiz_queue = selected
    st.session_state.user_answers = {i: "" for i in range(len(selected))}
    st.session_state.current_question_index = 0
    st.session_state.assessment_results = []
    st.session_state.review_question_index = None
    st.session_state.chat_histories = {}
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

    # 结束学习时长计算
    if st.session_state.study_session_id:
        engine = get_database_engine()
        with engine.connect() as conn:
            ts = datetime.now(pytz.timezone('Asia/Shanghai'))
            conn.execute(text(
                "UPDATE study_sessions SET end_time = :t, duration_seconds = TIMESTAMPDIFF(SECOND, start_time, :t) WHERE id = :id"),
                         {"t": ts, "id": st.session_state.study_session_id})
            conn.execute(text("UPDATE users SET current_quiz_ids = NULL WHERE username = :u"),
                         {"u": st.session_state.current_user})
            conn.commit()

    st.session_state.session_count += 1
    st.session_state.page_mode = "results"
    st.rerun()


# =============== 页面渲染逻辑 ===============

st.set_page_config(page_title="智能导学系统", layout="wide")

if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🎓 智能导学与测试系统</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        tab_l, tab_r = st.tabs(["🔑 登录", "📝 注册"])
        with tab_l:
            u_in, p_in = st.text_input("账号/学号"), st.text_input("密码", type="password")
            if st.button("进入系统", type="primary", use_container_width=True):
                is_auth, role = authenticate_user(u_in, p_in)
                if is_auth:
                    st.session_state.logged_in = True
                    st.session_state.current_user = u_in
                    st.session_state.user_role = role
                    log_login(u_in)
                    if role == 'admin':
                        st.session_state.page_mode = "admin"
                    else:
                        sync_user_data(u_in)
                    st.rerun()
                else:
                    st.error("账号或密码错误")
        with tab_r:
            ru, rp, rp2 = st.text_input("新学号"), st.text_input("新密码", type="password"), st.text_input("确认密码",
                                                                                                           type="password")
            if st.button("立即注册", use_container_width=True):
                if ru and rp == rp2 and register_user(ru, rp):
                    st.success("注册成功！请切换到登录页面。")
                else:
                    st.error("注册失败（学号已被占用或密码不一致）。")
    st.stop()

with st.sidebar:
    st.write(
        f"当前账号: `{st.session_state.current_user}` ({'管理员' if st.session_state.user_role == 'admin' else '学生'})")
    if st.session_state.user_role == 'student' and st.session_state.page_mode != "home":
        if st.button("🏠 返回大厅"):

            engine = get_database_engine()
            with engine.connect() as conn:
                conn.execute(text("UPDATE users SET current_quiz_ids = NULL WHERE username = :u"),
                             {"u": st.session_state.current_user})
                conn.commit()
            st.session_state.page_mode = "home"
            st.rerun()
    if st.button("🚪 退出登录"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# === 管理员后台 ===
if st.session_state.page_mode == "admin" and st.session_state.user_role == "admin":
    st.markdown("<h1>👨‍💻 教务管理控制台</h1>", unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["🕒 登录日志", "⏱️ 学习时长追踪", "💬 AI辅导监控"])
    engine = get_database_engine()
    with engine.connect() as conn:
        with tab1:
            st.subheader("学生活跃度监控")
            df_login = pd.read_sql(
                "SELECT username AS '学号', login_time AS '登录时间' FROM login_logs ORDER BY login_time DESC LIMIT 50",
                conn)
            st.dataframe(df_login, use_container_width=True)
        with tab2:
            st.subheader("各科课程学习时长分析")
            df_study = pd.read_sql(
                "SELECT username AS '学号', course_name AS '课程', start_time AS '开始时间', end_time AS '结束时间', duration_seconds AS '学习时长(秒)' FROM study_sessions ORDER BY start_time DESC LIMIT 50",
                conn)
            st.dataframe(df_study, use_container_width=True)
        with tab3:
            st.subheader("大模型交互质量抽查")
            df_chat = pd.read_sql(
                "SELECT student_id AS '学号', question_id AS '题号', user_query AS '学生提问', ai_response AS '系统反馈', created_at AS '交互时间' FROM interaction_logs ORDER BY created_at DESC LIMIT 50",
                conn)
            st.dataframe(df_chat, use_container_width=True)

# === 学生课程大厅 ===
elif st.session_state.page_mode == "home" and st.session_state.user_role == "student":
    st.markdown("<h1 style='text-align: center;'>🏫 课程学习大厅</h1>", unsafe_allow_html=True)
    st.write("请选择你要进行随堂测验的课程模块：")
    st.divider()

    col1, col2, col3 = st.columns(3)
    courses = [
        ("高等数学", "包含极限、导数、微积分等核心考点，重点测试逻辑推导能力。"),
        ("线性代数", "包含矩阵运算、特征值、二次型等，培养空间与代数转换思维。"),
        ("概率统计", "包含随机变量、分布规律、信息熵等，结合实际应用场景。")
    ]
    for idx, (c_name, c_desc) in enumerate(courses):
        with [col1, col2, col3][idx]:
            st.markdown(f"### 📘 {c_name}")
            st.caption(c_desc)
            if st.button(f"进入《{c_name}》测验", key=f"btn_{c_name}", use_container_width=True):
                start_experiment_session(c_name)

# === 学生答题区 ===
elif st.session_state.page_mode == "quiz":
    idx = st.session_state.current_question_index
    total = len(st.session_state.quiz_queue)
    q = st.session_state.quiz_queue[idx]
    st.progress((idx + 1) / total, text=f"【{st.session_state.current_course}】 进度：{idx + 1} / {total}")
    st.markdown(f"### 第 {idx + 1} 题")
    st.info(format_math(q['content']))

    ans = st.text_area("请作答", value=st.session_state.user_answers.get(idx, ""), height=200, key=f"ans_{idx}")
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
            if st.button("✅ 提交试卷", type="primary"):
                missing = [str(i + 1) for i in range(total) if not st.session_state.user_answers.get(i, "").strip()]
                if missing:
                    st.warning(f"⚠️ 第 {'、'.join(missing)} 题尚未作答，请完成后再提交。")
                else:
                    submit_and_assess()

# === 学生结果与辅导区 ===
elif st.session_state.page_mode == "results":
    st.title("📊 作答结果与辅导")
    if st.button("🔄 返回大厅开启新课程"):
        st.session_state.page_mode = "home"
        st.rerun()
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
            st.info(format_math(data['question_data']['content']))
            st.write(f"您的作答: {data['user_answer']}")
            st.divider()
            if qid not in st.session_state.chat_histories:
                st.session_state.chat_histories[qid] = []
                if not data['is_correct']: st.session_state.chat_histories[qid].append(
                    {"role": "assistant", "content": "智能辅导"})
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
                            h.markdown(format_math(f) + "▌")
                    final = format_math(f)
                    h.markdown(final)
                    st.session_state.chat_histories[qid].append({"role": "assistant", "content": final})
                    log_interaction(qid, f"【辅导】{query}", final)