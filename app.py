import streamlit as st
import os
import random
import time
from typing import List, Dict, Optional, Any
from sqlalchemy import create_engine, text, Engine
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import pytz
from prompts import SYSTEM_INSTRUCTION, JUDGE_PROMPT_SYSTEM
from questions import QUESTION_BANK

# 加载环境变量
load_dotenv()


# --- 配置管理 (Configuration) ---
class AppConfig:
    """应用配置类，负责加载系统环境变量与密钥"""
    LLM_API_KEY = st.secrets.get("LLM_API_KEY") or os.getenv("LLM_API_KEY")
    DB_USER = st.secrets.get("DB_USER") or os.getenv("DB_USER")
    DB_PASSWORD = st.secrets.get("DB_PASSWORD") or os.getenv("DB_PASSWORD")
    DB_HOST = st.secrets.get("DB_HOST") or os.getenv("DB_HOST")
    DB_NAME = st.secrets.get("DB_NAME") or os.getenv("DB_NAME")
    STUDENT_ID = st.secrets.get("MY_ID") or os.getenv("MY_ID")
    BASE_URL = "https://api.deepseek.com"


# 初始化 OpenAI 客户端
client = OpenAI(api_key=AppConfig.LLM_API_KEY, base_url=AppConfig.BASE_URL)


# --- 会话状态管理 (Session State Management) ---
def init_session_state():
    """初始化 Streamlit 会话状态变量"""
    default_states = {
        "page_mode": "home",  # 当前页面模式: home, quiz, results
        "quiz_queue": [],  # 当前轮次的题目队列
        "current_question_index": 0,  # 当前题目索引
        "user_answers": {},  # 用户作答记录 {index: answer_text}
        "assessment_results": [],  # 判题结果列表
        "review_question_index": None,  # 结果页当前回顾的题目索引
        "chat_histories": {},  # 题目对应的 AI 对话历史
        "session_count": 0  # 实验轮次计数
    }

    for key, value in default_states.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# --- 数据库服务 (Database Service) ---
@st.cache_resource
def get_database_engine() -> Engine:
    """获取数据库连接引擎（单例模式，带连接池配置）"""
    connection_url = (
        f"mysql+pymysql://{AppConfig.DB_USER}:{AppConfig.DB_PASSWORD}"
        f"@{AppConfig.DB_HOST}/{AppConfig.DB_NAME}"
    )
    return create_engine(
        connection_url,
        pool_recycle=1800,
        pool_pre_ping=True
    )


def log_interaction(question_id: int, query: str, response: str, is_leaking: int = 0) -> None:
    """
    记录用户交互日志到数据库。

    Args:
        question_id: 题目ID
        query: 用户输入（答案或提问）
        response: 系统/AI 响应
        is_leaking: 是否涉及答案泄露（0/1）
    """
    try:
        engine = get_database_engine()
        with engine.connect() as connection:
            timestamp = datetime.now(pytz.timezone('Asia/Shanghai'))
            insert_sql = text("""
                INSERT INTO interaction_logs 
                (question_id, student_id, user_query, ai_response, is_leaking_answer, created_at) 
                VALUES (:qid, :sid, :qry, :rsp, :leak, :time)
            """)
            connection.execute(insert_sql, {
                "qid": question_id,
                "sid": AppConfig.STUDENT_ID,
                "qry": query,
                "rsp": response,
                "leak": is_leaking,
                "time": timestamp
            })
            connection.commit()
    except Exception as e:
        # 在实际生产环境中应使用 logging 模块
        print(f"[Error] Database logging failed: {e}")


# --- 核心业务逻辑 (Core Business Logic) ---

def start_experiment_session():
    """启动新一轮实验：重置状态并随机抽取题目"""
    # 随机抽样5道题，模拟真实测试环境
    if len(QUESTION_BANK) >= 5:
        selected_questions = random.sample(QUESTION_BANK, 5)
    else:
        selected_questions = QUESTION_BANK

    # 重置会话状态
    st.session_state.quiz_queue = selected_questions
    st.session_state.current_question_index = 0
    st.session_state.user_answers = {i: "" for i in range(len(selected_questions))}
    st.session_state.assessment_results = []
    st.session_state.chat_histories = {}
    st.session_state.page_mode = "quiz"
    st.rerun()


def submit_and_assess():
    """提交答案并执行批量判题逻辑"""
    assessment_results = []
    progress_bar = st.progress(0, text="正在进行智能判卷分析...")
    total_questions = len(st.session_state.quiz_queue)

    for index, question in enumerate(st.session_state.quiz_queue):
        user_answer = st.session_state.user_answers.get(index, "未作答")

        # 构建判题 Prompt，强制要求结构化输出以确保解析准确性
        judge_prompt = (
            f"题目：{question['content']}\n"
            f"学生答案：{user_answer}\n"
            f"任务：判断学生答案是否在数学上正确。\n"
            f"输出约束：若正确仅输出 'PASS'，若错误仅输出 'FAIL'。禁止输出其他字符。"
        )

        is_correct = False
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": JUDGE_PROMPT_SYSTEM},
                    {"role": "user", "content": judge_prompt}
                ]
            )
            result_text = response.choices[0].message.content.strip()

            # 严格匹配逻辑，防止模型幻觉导致的误判
            if "PASS" in result_text and "FAIL" not in result_text:
                is_correct = True
        except Exception as e:
            st.error(f"判题服务异常: {e}")
            is_correct = False

        assessment_results.append({
            "question_data": question,
            "user_answer": user_answer,
            "is_correct": is_correct
        })

        # 异步记录日志
        log_interaction(
            question["id"],
            f"【答案提交】{user_answer}",
            "正确" if is_correct else "错误"
        )
        progress_bar.progress((index + 1) / total_questions)

    time.sleep(0.5)  # 优化用户体验的缓冲
    st.session_state.assessment_results = assessment_results
    st.session_state.session_count += 1
    st.session_state.page_mode = "results"
    st.rerun()


# --- 界面渲染 (UI Rendering) ---
st.set_page_config(
    page_title="可控解题提示生成系统",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ================= 视图 1: 系统首页 (Home View) =================
if st.session_state.page_mode == "home":
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>🧩 基于 DeepSeek 的可控解题提示生成系统</h1>", unsafe_allow_html=True)
    st.markdown(
        "<h3 style='text-align: center; color: grey; font-weight: 300;'>Intelligent Tutoring & Hint Generation System</h3>",
        unsafe_allow_html=True
    )
    st.markdown("<br><br>", unsafe_allow_html=True)

    col_spacer_left, col_button, col_spacer_right = st.columns([1, 1, 1])
    with col_button:
        if st.button("🚀 进入实验", type="primary", use_container_width=True):
            start_experiment_session()

    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    footer_html = (
        f"<div style='text-align: center; color: #888; font-size: 0.9em;'>"
        f"当前用户 ID：{AppConfig.STUDENT_ID} | 已完成实验轮次：{st.session_state.session_count}"
        f"</div>"
    )
    st.markdown(footer_html, unsafe_allow_html=True)

# ================= 视图 2: 答题界面 (Quiz View) =================
elif st.session_state.page_mode == "quiz":
    current_idx = st.session_state.current_question_index
    total_questions = len(st.session_state.quiz_queue)
    current_question = st.session_state.quiz_queue[current_idx]

    # 进度指示器
    st.progress(
        (current_idx + 1) / total_questions,
        text=f"实验进度：第 {current_idx + 1} / {total_questions} 题"
    )

    st.markdown(f"### 第 {current_idx + 1} 题")

    # 题目展示区
    st.markdown(
        f"""
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 5px solid #007bff; margin-bottom: 20px; font-size: 1.1em;">
            {current_question['content']}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.write("✍️ **解题区域：**")
    previous_answer = st.session_state.user_answers.get(current_idx, "")
    user_input = st.text_area(
        "请输入您的解题步骤或最终答案...",
        value=previous_answer,
        height=200,
        key=f"input_area_{current_idx}"
    )

    # 实时保存当前输入
    st.session_state.user_answers[current_idx] = user_input

    col_nav_prev, col_nav_next = st.columns([1, 1])

    with col_nav_prev:
        if current_idx > 0:
            if st.button("⬅️ 上一题"):
                st.session_state.current_question_index -= 1
                st.rerun()

    with col_nav_next:
        if current_idx < total_questions - 1:
            if st.button("下一题 ➡️", type="primary"):
                st.session_state.current_question_index += 1
                st.rerun()
        else:
            # 提交前的完整性检查
            if st.button("✅ 提交实验结果", type="primary"):
                missing_items = []
                for i in range(total_questions):
                    ans = st.session_state.user_answers.get(i, "")
                    if not ans or not ans.strip():
                        missing_items.append(str(i + 1))

                if missing_items:
                    st.warning(f"⚠️ 数据完整性校验失败：第 {'、'.join(missing_items)} 题尚未作答。")
                else:
                    submit_and_assess()

# ================= 视图 3: 结果与辅导界面 (Results & Tutoring View) =================
elif st.session_state.page_mode == "results":
    st.title("📊 答题结果与智能辅导")

    col_info, col_action = st.columns([3, 1])
    with col_info:
        st.caption("请点击左侧列表查看判题详情。针对错误回答，系统将激活“可控提示生成”模块进行干预。")
    with col_action:
        if st.button("🔄 开启新一轮实验"):
            start_experiment_session()

    st.divider()

    layout_col_list, layout_col_chat = st.columns([1, 1])

    # 左侧：题目列表
    with layout_col_list:
        st.subheader("📑 题目列表")
        for i, item in enumerate(st.session_state.assessment_results):
            status_icon = "✅ 正确" if item['is_correct'] else "❌ 错误"
            # 高亮当前选中的题目
            button_type = "primary" if st.session_state.review_question_index == i else "secondary"

            if st.button(
                    f"第 {i + 1} 题   |   {status_icon}",
                    key=f"nav_btn_{i}",
                    type=button_type,
                    use_container_width=True
            ):
                st.session_state.review_question_index = i
                st.rerun()

    # 右侧：详情与辅导交互
    with layout_col_chat:
        if st.session_state.review_question_index is not None:
            review_idx = st.session_state.review_question_index
            result_data = st.session_state.assessment_results[review_idx]
            question_id = result_data['question_data']['id']

            st.markdown(f"#### 第 {review_idx + 1} 题详情")
            st.info(result_data['question_data']['content'])

            st.write("**您的作答：**")
            if result_data['is_correct']:
                st.success(result_data['user_answer'])
            else:
                st.error(result_data['user_answer'])

            st.divider()
            st.subheader("🤖 解题辅导 (Problem Solving Assistant)")

            # 初始化对话历史
            if question_id not in st.session_state.chat_histories:
                st.session_state.chat_histories[question_id] = []
                # 仅对错题触发主动干预
                if not result_data['is_correct']:
                    st.session_state.chat_histories[question_id].append({
                        "role": "assistant",
                        "content": "检测到答案存在偏差。我是你的智能解题辅导助手，请告诉我你的思路卡在哪里？"
                    })

            # 渲染历史消息
            chat_history = st.session_state.chat_histories[question_id]
            for message in chat_history:
                avatar = "🧑‍🎓" if message["role"] == "user" else "🤖"
                with st.chat_message(message["role"], avatar=avatar):
                    st.markdown(message["content"])

            # 辅导交互逻辑
            if user_query := st.chat_input(f"请求第 {review_idx + 1} 题的解题辅导..."):
                chat_history.append({"role": "user", "content": user_query})
                st.session_state.chat_histories[question_id] = chat_history
                st.rerun()

            # 处理 AI 响应
            if chat_history and chat_history[-1]["role"] == "user":
                with st.chat_message("assistant", avatar="🤖"):
                    response_container = st.empty()
                    full_response = ""

                    # 构建上下文 Context
                    context_payload = (
                        f"【题目】：{result_data['question_data']['content']}\n"
                        f"【学生答案】：{result_data['user_answer']}\n"
                        f"【判题结果】：{'正确' if result_data['is_correct'] else '错误'}\n"
                        f"【学生请求】：{chat_history[-1]['content']}"
                    )

                    try:
                        stream_response = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[
                                {"role": "system", "content": SYSTEM_INSTRUCTION},
                                {"role": "user", "content": context_payload}
                            ],
                            stream=True
                        )

                        for chunk in stream_response:
                            delta_content = chunk.choices[0].delta.content
                            if delta_content:
                                full_response += delta_content
                                # 实时渲染 Markdown，处理 LaTeX 公式
                                render_text = full_response.replace(r"\[", "$$").replace(r"\]", "$$").replace(r"\(",
                                                                                                              "$").replace(
                                    r"\)", "$")
                                response_container.markdown(render_text + "▌")

                        final_text = full_response.replace(r"\[", "$$").replace(r"\]", "$$").replace(r"\(",
                                                                                                     "$").replace(r"\)",
                                                                                                                  "$")
                        response_container.markdown(final_text)

                        chat_history.append({"role": "assistant", "content": final_text})
                        st.session_state.chat_histories[question_id] = chat_history
                        log_interaction(question_id, f"【辅导请求】{user_query}", final_text)

                    except Exception as e:
                        st.error(f"辅导生成模块响应中断: {e}")

        else:
            st.info("👈 请点击左侧题目，启动辅助解题功能。")

st.markdown("---")
st.markdown(
    f"<div style='text-align: center; color: grey; font-size: 0.8em;'>"
    f"© 2026 基于 DeepSeek 的可控解题提示生成系统 | 负责人：{AppConfig.STUDENT_ID}</div>",
    unsafe_allow_html=True
)