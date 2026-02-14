import streamlit as st
import os
import random
import time
from sqlalchemy import create_engine, text
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import pytz
from prompts import SYSTEM_INSTRUCTION, JUDGE_PROMPT_SYSTEM
from questions import QUESTION_BANK

load_dotenv()

api_key = st.secrets.get("LLM_API_KEY") or os.getenv("LLM_API_KEY")
db_user = st.secrets.get("DB_USER") or os.getenv("DB_USER")
db_pwd = st.secrets.get("DB_PASSWORD") or os.getenv("DB_PASSWORD")
db_host = st.secrets.get("DB_HOST") or os.getenv("DB_HOST")
db_name = st.secrets.get("DB_NAME") or os.getenv("DB_NAME")
my_id = st.secrets.get("MY_ID") or os.getenv("MY_ID")

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

if "page_mode" not in st.session_state:
    st.session_state.page_mode = "home"
if "quiz_queue" not in st.session_state:
    st.session_state.quiz_queue = []
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "results" not in st.session_state:
    st.session_state.results = []
if "review_idx" not in st.session_state:
    st.session_state.review_idx = None
if "chats" not in st.session_state:
    st.session_state.chats = {}
if "session_cnt" not in st.session_state:
    st.session_state.session_cnt = 0


@st.cache_resource
def get_conn():
    url = f"mysql+pymysql://{db_user}:{db_pwd}@{db_host}/{db_name}"
    return create_engine(url, pool_recycle=1800, pool_pre_ping=True)


def log_data(qid, query, response, leaking=0):
    try:
        engine = get_conn()
        with engine.connect() as conn:
            t = datetime.now(pytz.timezone('Asia/Shanghai'))
            s = text(
                "INSERT INTO interaction_logs (question_id, student_id, user_query, ai_response, is_leaking_answer, created_at) VALUES (:qid, :sid, :q, :r, :l, :t)")
            conn.execute(s, {"qid": qid, "sid": my_id, "q": query, "r": response, "l": leaking, "t": t})
            conn.commit()
    except Exception as e:
        print(e)


def start():
    if len(QUESTION_BANK) >= 5:
        q_list = random.sample(QUESTION_BANK, 5)
    else:
        q_list = QUESTION_BANK

    st.session_state.quiz_queue = q_list
    st.session_state.idx = 0
    st.session_state.answers = {i: "" for i in range(len(q_list))}
    st.session_state.results = []
    st.session_state.chats = {}
    st.session_state.page_mode = "quiz"
    st.rerun()


def submit():
    res = []
    bar = st.progress(0, text="正在分析答案...")
    total = len(st.session_state.quiz_queue)

    for i, q in enumerate(st.session_state.quiz_queue):
        ans = st.session_state.answers.get(i, "未作答")
        prompt = f"题目：{q['content']}\n学生答案：{ans}\n判断对错。只能输出'正确'或'错误'。"
        try:
            resp = client.chat.completions.create(model="deepseek-chat", messages=[
                {"role": "system", "content": JUDGE_PROMPT_SYSTEM},
                {"role": "user", "content": prompt}])
            txt = resp.choices[0].message.content.strip()
            ok = "正确" in txt
        except:
            ok = False

        res.append({"q": q, "ans": ans, "ok": ok})
        log_data(q["id"], f"【答案提交】{ans}", "正确" if ok else "错误")
        bar.progress((i + 1) / total)

    time.sleep(0.5)
    st.session_state.results = res
    st.session_state.session_cnt += 1
    st.session_state.page_mode = "results"
    st.rerun()


st.set_page_config(page_title="可控解题提示生成系统", layout="wide")

if st.session_state.page_mode == "home":
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>🧩 基于Deepseek的可控解题提示生成系统</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: grey;'>Intelligent Tutoring & Hint Generation System</h3>",
                unsafe_allow_html=True)
    st.markdown("<br><br>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        if st.button("🚀 开始做题", type="primary", use_container_width=True):
            start()

    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='text-align: center; color: grey;'>当前用户：{my_id} | 实验轮次：{st.session_state.session_cnt}</div>",
        unsafe_allow_html=True)

elif st.session_state.page_mode == "quiz":
    idx = st.session_state.idx
    total = len(st.session_state.quiz_queue)
    curr = st.session_state.quiz_queue[idx]

    st.progress((idx + 1) / total, text=f"当前进度：第 {idx + 1} / {total} 题")
    st.markdown(f"### 第 {idx + 1} 题")

    st.markdown(
        f"<div style='background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 20px; font-size: 1.1em;'>{curr['content']}</div>",
        unsafe_allow_html=True)

    st.write("✍️ **解题区域：**")
    old_ans = st.session_state.answers.get(idx, "")
    val = st.text_area("请输入你的解题步骤或答案...", value=old_ans, height=200, key=f"area_{idx}")

    c_prev, c_next = st.columns([1, 1])
    st.session_state.answers[idx] = val

    with c_prev:
        if idx > 0:
            if st.button("⬅️ 上一题"):
                st.session_state.idx -= 1
                st.rerun()

    with c_next:
        if idx < total - 1:
            if st.button("下一题 ➡️", type="primary"):
                st.session_state.idx += 1
                st.rerun()
        else:
            if st.button("✅ 提交答案", type="primary"):
                miss = []
                for i in range(total):
                    a = st.session_state.answers.get(i, "")
                    if not a or not a.strip():
                        miss.append(str(i + 1))

                if miss:
                    st.warning(f"⚠️ 无法提交！以下题目尚未作答：第 {'、'.join(miss)} 题。")
                else:
                    submit()

elif st.session_state.page_mode == "results":
    st.title("📊 答题结果与智能辅导")

    c1, c2 = st.columns([3, 1])
    with c1:
        st.caption("请点击下方题目查看判题结果。若回答错误，系统将基于 DeepSeek 提供智能辅导。")
    with c2:
        if st.button("🔄 开启新一轮实验"):
            start()

    st.divider()

    left, right = st.columns([1, 1])

    with left:
        st.subheader("📑 题目列表")
        for i, item in enumerate(st.session_state.results):
            icon = "✅ 正确" if item['ok'] else "❌ 错误"
            b_type = "primary" if st.session_state.review_idx == i else "secondary"

            if st.button(f"第 {i + 1} 题   |   {icon}", key=f"btn_{i}", type=b_type, use_container_width=True):
                st.session_state.review_idx = i
                st.rerun()

    with right:
        if st.session_state.review_idx is not None:
            ridx = st.session_state.review_idx
            data = st.session_state.results[ridx]
            qid = data['q']['id']

            st.markdown(f"#### 第 {ridx + 1} 题详情")
            st.info(data['q']['content'])

            st.write("**你的作答：**")
            if data['ok']:
                st.success(data['ans'])
            else:
                st.error(data['ans'])

            st.divider()
            st.subheader("🤖 解题辅导 (Problem Solving Assistant)")

            if qid not in st.session_state.chats:
                st.session_state.chats[qid] = []
                if not data['ok']:
                    st.session_state.chats[qid].append({"role": "assistant",
                                                        "content": "检测到答案存在偏差。我是你的智能解题辅导助手，请告诉我你的思路卡在哪里？"})

            hist = st.session_state.chats[qid]
            for m in hist:
                role = "🧑‍🎓" if m["role"] == "user" else "🤖"
                with st.chat_message(m["role"], avatar=role):
                    st.markdown(m["content"])

            if user_in := st.chat_input(f"请求第 {ridx + 1} 题的解题辅导..."):
                hist.append({"role": "user", "content": user_in})
                st.session_state.chats[qid] = hist
                st.rerun()

            if hist and hist[-1]["role"] == "user":
                with st.chat_message("assistant", avatar="🤖"):
                    holder = st.empty()
                    full = ""
                    ctx = f"【题目】：{data['q']['content']}\n【学生答案】：{data['ans']}\n【判题结果】：{'正确' if data['ok'] else '错误'}\n【学生请求】：{hist[-1]['content']}"

                    try:
                        chunks = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[
                                {"role": "system", "content": SYSTEM_INSTRUCTION},
                                {"role": "user", "content": ctx}
                            ],
                            stream=True
                        )
                        for chunk in chunks:
                            c = chunk.choices[0].delta.content
                            if c:
                                full += c
                                holder.markdown(
                                    full.replace(r"\[", "$$").replace(r"\]", "$$").replace(r"\(", "$").replace(r"\)",
                                                                                                               "$") + "▌")

                        final = full.replace(r"\[", "$$").replace(r"\]", "$$").replace(r"\(", "$").replace(r"\)", "$")
                        holder.markdown(final)

                        hist.append({"role": "assistant", "content": final})
                        st.session_state.chats[qid] = hist
                        log_data(qid, f"【辅导请求】{user_in}", final)

                    except Exception as e:
                        st.error(f"Error: {e}")

        else:
            st.info("👈 请点击左侧题目，启动辅助解题功能。")

st.markdown("---")
st.markdown(
    f"<div style='text-align: center; color: grey;'>© 2026 基于Deepseek的可控解题提示生成系统 | 负责人：{my_id}</div>",
    unsafe_allow_html=True)