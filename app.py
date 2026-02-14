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


# --- 1. 配置读取 ---
def get_config(key):
    if key in st.secrets:
        return st.secrets[key]
    return os.getenv(key)


api_key = get_config("LLM_API_KEY")
db_user = get_config("DB_USER")
db_password = get_config("DB_PASSWORD")
db_host = get_config("DB_HOST")
db_name = get_config("DB_NAME")
my_id = get_config("MY_ID")

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# --- 2. 状态初始化 ---
if "page_mode" not in st.session_state:
    st.session_state.page_mode = "home"

if "quiz_queue" not in st.session_state:
    st.session_state.quiz_queue = []
if "current_q_index" not in st.session_state:
    st.session_state.current_q_index = 0
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "exam_results" not in st.session_state:
    st.session_state.exam_results = []
if "review_q_index" not in st.session_state:
    st.session_state.review_q_index = None
if "chat_histories" not in st.session_state:
    st.session_state.chat_histories = {}
if "total_sessions" not in st.session_state:  # 改名：从 exam 改为 session
    st.session_state.total_sessions = 0


# --- 3. 数据库与工具函数 ---
@st.cache_resource
def get_db_engine():
    db_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}"
    return create_engine(db_url, pool_recycle=1800, pool_pre_ping=True)


def save_to_logs(q_id, user_query, ai_response, is_leaking=0):
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            sql = text("""
                       INSERT INTO interaction_logs
                       (question_id, student_id, user_query, ai_response, is_leaking_answer, created_at)
                       VALUES (:q_id, :s_id, :query, :resp, :leaking, :time)
                       """)
            conn.execute(sql, {
                "q_id": q_id,
                "s_id": my_id,
                "query": user_query,
                "resp": ai_response,
                "leaking": is_leaking,
                "time": datetime.now(pytz.timezone('Asia/Shanghai'))
            })
            conn.commit()
    except Exception as e:
        print(f"存证失败：{e}")


def start_new_session():
    # 随机抽取题目进行实验
    if len(QUESTION_BANK) >= 5:
        selected_questions = random.sample(QUESTION_BANK, 5)
    else:
        selected_questions = QUESTION_BANK

    st.session_state.quiz_queue = selected_questions
    st.session_state.current_q_index = 0
    st.session_state.user_answers = {i: "" for i in range(len(selected_questions))}
    st.session_state.exam_results = []
    st.session_state.chat_histories = {}
    st.session_state.page_mode = "quiz"
    st.rerun()


def submit_answers():
    results = []
    progress_bar = st.progress(0, text="正在分析答案并生成诊断报告...")

    total_q = len(st.session_state.quiz_queue)

    for i, question in enumerate(st.session_state.quiz_queue):
        user_ans = st.session_state.user_answers.get(i, "未作答")

        judge_prompt = f"题目：{question['content']}\n学生答案：{user_ans}\n判断对错。只能输出'正确'或'错误'。"
        try:
            response = client.chat.completions.create(model="deepseek-chat", messages=[
                {"role": "system", "content": JUDGE_PROMPT_SYSTEM},
                {"role": "user", "content": judge_prompt}])
            res_text = response.choices[0].message.content.strip()
            is_correct = "正确" in res_text
        except:
            is_correct = False

        results.append({
            "question": question,
            "user_answer": user_ans,
            "is_correct": is_correct
        })

        save_to_logs(question["id"], f"【答案提交】{user_ans}", "正确" if is_correct else "错误")
        progress_bar.progress((i + 1) / total_q)

    time.sleep(0.5)
    st.session_state.exam_results = results
    st.session_state.total_sessions += 1
    st.session_state.page_mode = "results"
    st.rerun()


# --- 4. 页面渲染逻辑 ---
st.set_page_config(page_title="可控解题提示生成系统", layout="wide")

# ================= 1. 首页 (System Entry) =================
if st.session_state.page_mode == "home":
    st.markdown("<br><br>", unsafe_allow_html=True)
    # 【修改点】系统标题更正
    st.title("🧩 基于Deepseek的可控解题提示生成系统")
    st.markdown("### Intelligent Tutoring & Hint Generation System")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.info(f"""
        **系统说明：**
        本系统旨在研究大语言模型在教育场景下的**认知支架**作用。
        1. 系统将加载 **5道实验题目**。
        2. 用户完成作答并提交。
        3. 系统将自动诊断正误，并针对错误点生成**启发式提示**（而非直接答案）。
        """)

    with col2:
        st.write("准备好开始实验了吗？")
        # 【修改点】按钮文案
        if st.button("🚀 进入解题实验", type="primary", use_container_width=True):
            start_new_session()

    st.markdown("---")
    st.caption(f"当前用户：{my_id} | 实验轮次：{st.session_state.total_sessions}")

# ================= 2. 解题进行中 (Problem Solving) =================
elif st.session_state.page_mode == "quiz":
    current_idx = st.session_state.current_q_index
    total_q = len(st.session_state.quiz_queue)
    current_q = st.session_state.quiz_queue[current_idx]

    st.progress((current_idx + 1) / total_q, text=f"当前进度：第 {current_idx + 1} / {total_q} 题")

    st.markdown(f"### 第 {current_idx + 1} 题")

    st.markdown(f"""
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 20px; font-size: 1.1em;">
        {current_q['content']}
    </div>
    """, unsafe_allow_html=True)

    st.write("✍️ **解题区域：**")
    prev_ans = st.session_state.user_answers.get(current_idx, "")
    val = st.text_area("请输入你的解题步骤或答案...", value=prev_ans, height=200, key=f"q_area_{current_idx}")

    col_prev, col_next = st.columns([1, 1])
    st.session_state.user_answers[current_idx] = val

    with col_prev:
        if current_idx > 0:
            if st.button("⬅️ 上一题"):
                st.session_state.current_q_index -= 1
                st.rerun()

    with col_next:
        if current_idx < total_q - 1:
            if st.button("下一题 ➡️", type="primary"):
                st.session_state.current_q_index += 1
                st.rerun()
        else:
            # 【修改点】提交按钮文案
            if st.button("✅ 提交答案", type="primary"):
                if not val.strip():
                    st.warning("最后一题尚未作答。")
                else:
                    submit_answers()

# ================= 3. 诊断与提示生成 (Diagnosis & Hints) =================
elif st.session_state.page_mode == "results":
    # 【修改点】去掉总分，改为诊断报告标题
    st.title("📊 解题诊断与提示生成报告")

    # 简单的操作栏
    col_info, col_act = st.columns([3, 1])
    with col_info:
        st.caption("请点击下方题目查看判题结果。若回答错误，系统将基于 DeepSeek 生成引导性提示。")
    with col_act:
        if st.button("🔄 开启新一轮实验"):
            start_new_session()

    st.divider()

    col_list, col_chat = st.columns([1, 1])

    with col_list:
        st.subheader("📑 题目列表")

        for i, res in enumerate(st.session_state.exam_results):
            q_id = res['question']['id']
            # 图标：只显示对错，不显示分数
            status_icon = "✅ 正确" if res['is_correct'] else "❌ 错误"
            btn_type = "secondary"
            if st.session_state.review_q_index == i:
                btn_type = "primary"

            # 【修改点】列表按钮显示
            if st.button(f"第 {i + 1} 题   |   {status_icon}",
                         key=f"review_btn_{i}",
                         type=btn_type,
                         use_container_width=True):
                st.session_state.review_q_index = i
                st.rerun()

    with col_chat:
        if st.session_state.review_q_index is not None:
            idx = st.session_state.review_q_index
            data = st.session_state.exam_results[idx]
            q_content = data['question']['content']
            q_id = data['question']['id']
            user_ans = data['user_answer']
            is_correct = data['is_correct']

            st.markdown(f"#### 第 {idx + 1} 题详情")
            st.info(q_content)

            # 显示用户答案
            st.write("**你的作答：**")
            if is_correct:
                st.success(user_ans)
            else:
                st.error(user_ans)

            st.divider()

            # 【修改点】区域标题改为“提示生成系统”
            st.subheader("🤖 可控提示生成 (Hint Generation)")

            if q_id not in st.session_state.chat_histories:
                st.session_state.chat_histories[q_id] = []
                if not is_correct:
                    # 初始提示
                    first_msg = "检测到答案存在偏差。我是你的智能导学助手，请告诉我你的思路卡在哪里？"
                    st.session_state.chat_histories[q_id].append({"role": "assistant", "content": first_msg})

            current_chat = st.session_state.chat_histories[q_id]
            for msg in current_chat:
                avatar = "🧑‍🎓" if msg["role"] == "user" else "🤖"
                with st.chat_message(msg["role"], avatar=avatar):
                    st.markdown(msg["content"])

            if prompt := st.chat_input(f"请求第 {idx + 1} 题的解题提示..."):
                current_chat.append({"role": "user", "content": prompt})
                st.session_state.chat_histories[q_id] = current_chat
                st.rerun()

            if current_chat and current_chat[-1]["role"] == "user":
                with st.chat_message("assistant", avatar="🤖"):
                    response_placeholder = st.empty()
                    full_response = ""
                    # Context 强调“提示生成”而非“讲评”
                    context = f"【题目】：{q_content}\n【学生答案】：{user_ans}\n【判题结果】：{'正确' if is_correct else '错误'}\n【学生请求】：{current_chat[-1]['content']}"

                    try:
                        stream = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[
                                {"role": "system", "content": SYSTEM_INSTRUCTION},
                                {"role": "user", "content": context}
                            ],
                            stream=True
                        )
                        for chunk in stream:
                            content = chunk.choices[0].delta.content
                            if content:
                                full_response += content
                                display_text = full_response.replace(r"\[", "$$").replace(r"\]", "$$").replace(r"\(",
                                                                                                               "$").replace(
                                    r"\)", "$")
                                response_placeholder.markdown(display_text + "▌")

                        final_text = full_response.replace(r"\[", "$$").replace(r"\]", "$$").replace(r"\(",
                                                                                                     "$").replace(r"\)",
                                                                                                                  "$")
                        response_placeholder.markdown(final_text)

                        current_chat.append({"role": "assistant", "content": final_text})
                        st.session_state.chat_histories[q_id] = current_chat
                        save_to_logs(q_id, f"【提示请求】{prompt}", final_text)

                    except Exception as e:
                        st.error(f"提示生成中断：{e}")

        else:
            st.info("👈 请点击左侧题目，启动提示生成模块。")

st.markdown("---")
# 【修改点】底部版权
st.caption(f"© 2026 基于Deepseek的可控解题提示生成系统 | 负责人：{my_id}")