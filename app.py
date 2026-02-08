import streamlit as st
import os
from sqlalchemy import create_engine, text
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import pytz
from prompts import SYSTEM_INSTRUCTION, JUDGE_PROMPT_SYSTEM

load_dotenv()


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

if "submitted_problem" not in st.session_state:
    st.session_state.submitted_problem = ""
if "current_q_id" not in st.session_state:
    st.session_state.current_q_id = None
if "trial_count" not in st.session_state:
    st.session_state.trial_count = 0
if "messages" not in st.session_state:
    st.session_state.messages = []


@st.cache_resource
def get_db_engine():
    db_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}"
    return create_engine(db_url, pool_recycle=1800, pool_pre_ping=True)


def save_problem_to_db(problem_text):
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            sql = text("INSERT INTO questions (content, created_at) VALUES (:content, :time)")
            conn.execute(sql, {
                "content": problem_text,
                "time": datetime.now(pytz.timezone('Asia/Shanghai'))
            })
            conn.commit()
            result = conn.execute(text("SELECT LAST_INSERT_ID()"))
            new_id = result.scalar()
            return new_id
    except Exception as e:
        st.error(f"题目入库失败：{e}")
        return None


def save_to_logs(user_query, ai_response, is_leaking=0):
    q_id = st.session_state.current_q_id if st.session_state.current_q_id else -1
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
        st.error(f"存证失败：{e}")


def generate_report():
    ai_reply_count = len([m for m in st.session_state.messages if m["role"] == "assistant"])
    report = f"# 毕设实验数据报告\n- **项目标题**：基于Deepseek的可控解题提示生成系统\n"
    report += f"- **负责人**：左梓桐 ({my_id})\n"
    report += f"- **导出时间**：{datetime.now(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')}\n"
    report += f"## 关键数据指标\n- **答案提交次数**：{st.session_state.trial_count} 次\n- **智能辅导次数**：{ai_reply_count} 次\n"
    return report


st.set_page_config(page_title="可控解题提示系统", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    .stMarkdown, .stMarkdown p, .stMarkdown li, .stChatMessage p { color: #FFFFFF !important; }
    .stTextArea textarea {
        background-color: #171923 !important; color: #FFFFFF !important;
        border: 1px solid #4B5563 !important; caret-color: #00FBFF !important;
    }
    .stTextArea textarea:focus {
        border: 1px solid #00FBFF !important;
        box-shadow: 0 0 5px rgba(0, 251, 255, 0.5) !important;
    }
    .stTextArea textarea:disabled {
        background-color: #2D3748 !important; color: #FFFFFF !important;
        opacity: 1 !important; -webkit-text-fill-color: #FFFFFF !important;
    }
    .stTextArea label p { font-size: 1.4rem !important; color: #FFFFFF !important; font-weight: 700 !important; }
    div.stButton > button, div.stDownloadButton > button { 
        background-color: #FFFFFF !important; color: #0E1117 !important; font-weight: 700 !important; border-radius: 8px !important; width: 100% !important; font-size: 1.1rem !important;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        background-color: #00FBFF !important; box-shadow: 0px 0px 15px rgba(0, 251, 255, 0.6); color: #0E1117 !important;
    }
    .main-title { text-align: center; color: #00FBFF; text-shadow: 0px 0px 12px rgba(0, 251, 255, 0.4); font-weight: 800; margin-bottom: 35px; }
    [data-testid="stMetricValue"] { text-align: center; color: #FFFFFF !important; font-size: 2rem !important; }
    [data-testid="stMetricLabel"] { text-align: center; width: 100%; color: #00FBFF !important; font-size: 1.1rem !important; font-weight: 700 !important; }
    .footer-text { text-align: center; color: #9CA3AF !important; font-size: 0.9rem; margin-top: 50px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>基于Deepseek的可控解题提示生成系统</h1>", unsafe_allow_html=True)

metrics_placeholder = st.empty()


def render_metrics():
    with metrics_placeholder.container():
        _, m_col1, m_col2, _ = st.columns([1, 1, 1, 1])
        m_col1.metric("答案提交次数", st.session_state.trial_count)
        ai_reply_count = len([m for m in st.session_state.messages if m["role"] == "assistant"])
        m_col2.metric("智能辅导次数", ai_reply_count)
        st.divider()


render_metrics()

col1, col2 = st.columns([1, 1])
problem_is_locked = st.session_state.submitted_problem != ""

with col1:
    st.header("🔍 题目输入")
    problem_text = st.text_area("在此输入题目：", value=st.session_state.submitted_problem, height=150,
                                disabled=problem_is_locked)

    if not problem_is_locked:
        if st.button("✅ 确认提交题目"):
            if problem_text.strip():
                st.session_state.submitted_problem = problem_text.strip()
                new_q_id = save_problem_to_db(problem_text.strip())
                if new_q_id:
                    st.session_state.current_q_id = new_q_id
                    st.toast(f"题目已入库，ID: {new_q_id}", icon="💾")
                st.session_state.answer_input = ""
                st.rerun()
    else:
        if st.button("🔓 修改/重置当前题目"):
            st.session_state.submitted_problem = ""
            st.session_state.messages = []
            st.session_state.trial_count = 0
            st.session_state.current_q_id = None
            st.session_state.answer_input = ""
            st.rerun()

with col2:
    st.header("📝 答案输入")
    student_answer = st.text_area("请写下你的计算过程或答案：", height=150, key="answer_input")

    if st.button("🚀 提交并判断对错"):
        if problem_is_locked and student_answer:
            judge_prompt = f"题目：{st.session_state.submitted_problem}\n学生答案：{student_answer}\n判断对错。只能输出'正确'或'错误'。"
            try:
                response = client.chat.completions.create(model="deepseek-chat", messages=[
                    {"role": "system", "content": JUDGE_PROMPT_SYSTEM},
                    {"role": "user", "content": judge_prompt}])
                result = response.choices[0].message.content.strip()

                st.session_state.trial_count += 1

                is_correct = "正确" in result
                if is_correct:
                    st.success("✅ 正确")
                    save_to_logs(f"【答案提交】{student_answer}", "正确")
                else:
                    st.error("❌ 错误")
                    save_to_logs(f"【答案提交】{student_answer}", "错误")

                render_metrics()

            except Exception as e:
                st.error(f"故障：{e}")
        elif not problem_is_locked:
            st.error("⚠️ 请先锁定题目！")

st.header("🤖 智能辅助")
for message in st.session_state.messages:
    avatar = "🧑‍🎓" if message["role"] == "user" else "🤖"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

if not problem_is_locked and st.session_state.submitted_problem == "":
    st.markdown("""
        <div style='text-align: center; color: #00FBFF; background-color: rgba(0, 251, 255, 0.05); padding: 20px; border: 1px solid rgba(0, 251, 255, 0.3); border-radius: 10px; font-size: 1.2rem; font-weight: 700; margin-top: 20px; margin-bottom: 20px; box-shadow: 0px 0px 10px rgba(0, 251, 255, 0.1);'>
            💡 请先在左侧输入题目并点击“确认提交”，然后才能开始智能辅导。
        </div>""", unsafe_allow_html=True)

if prompt := st.chat_input("对这道题有什么疑问？"):
    if problem_is_locked:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑‍🎓"):
            st.markdown(prompt)

        render_metrics()

        context = f"【题目】：{st.session_state.submitted_problem}\n【当前答案】：{student_answer}\n【疑问】：{prompt}"

        with st.chat_message("assistant", avatar="🤖"):
            response_placeholder = st.empty()
            full_response = ""

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

                final_text = full_response.replace(r"\[", "$$").replace(r"\]", "$$").replace(r"\(", "$").replace(r"\)",
                                                                                                                 "$")
                response_placeholder.markdown(final_text)

                st.session_state.messages.append({"role": "assistant", "content": final_text})
                save_to_logs(f"【智能辅导】{prompt}", final_text)

                render_metrics()

            except Exception as e:
                st.error(f"AI 故障：{e}")
    else:
        st.toast("⚠️ 请先在左上角点击“确认提交题目”！", icon="🔒")

if st.session_state.messages:
    st.divider()
    _, center_btn, _ = st.columns([2, 1, 2])
    with center_btn:
        st.download_button(label="📥 导出实验日志报告", data=generate_report(), file_name=f"report_{my_id}.md")

st.markdown(f"<p class='footer-text'>系统运行中 | 负责人：左梓桐 （{my_id}）| 指导教师：王建荣</p>", unsafe_allow_html=True)