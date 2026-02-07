import streamlit as st
import os
from sqlalchemy import create_engine, text
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import pytz

load_dotenv()

client = OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url="https://api.deepseek.com")
MY_ID = os.getenv("MY_ID")

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
    db_url = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
    return create_engine(db_url, pool_recycle=3600)


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
    q_id = st.session_state.current_q_id if st.session_state.current_q_id else 1
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
                "s_id": MY_ID,
                "query": user_query,
                "resp": ai_response,
                "leaking": is_leaking,
                "time": datetime.now(pytz.timezone('Asia/Shanghai'))
            })
            conn.commit()
    except Exception as e:
        st.error(f"存证失败：{e}")


def generate_report():
    report = f"# 毕设实验数据报告\n- **项目标题**：基于Deepseek的可控解题提示生成系统\n"
    report += f"- **负责人**：左梓桐 ({MY_ID})\n"
    report += f"- **导出时间**：{datetime.now(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')}\n"
    report += f"## 关键数据指标\n- **答案提交次数**：{st.session_state.trial_count} 次\n- **智能辅导次数**：{len(st.session_state.messages)} 次\n"
    return report


st.set_page_config(page_title="可控解题提示系统", layout="wide")

# --- CSS 样式升级区 ---
st.markdown("""
    <style>
    /* 全局背景 */
    .stApp { background-color: #0E1117; color: #FFFFFF; }

    /* 大标题样式 */
    .main-title { 
        text-align: center; color: #00FBFF; 
        text-shadow: 0px 0px 12px rgba(0, 251, 255, 0.4); 
        font-weight: 800; margin-bottom: 35px; 
    }

    /* 指标卡片（提交次数等）的高亮优化 */
    [data-testid="stMetricValue"] { 
        text-align: center; color: #FFFFFF !important; font-size: 2rem !important;
    }
    [data-testid="stMetricLabel"] { 
        text-align: center; width: 100%; 
        color: #00FBFF !important; /* 把标签改成亮青色 */
        font-size: 1.1rem !important; /* 加大字号 */
        font-weight: 700 !important; 
    }

    /* 输入框标题的高亮优化 */
    .stTextArea label p {
        font-size: 1.4rem !important; /* 加大标题 */
        color: #FFFFFF !important;    /* 纯白 */
        font-weight: 700 !important;  /* 粗体 */
        text-shadow: 0px 2px 4px rgba(0,0,0,0.8); /* 文字投影，防背景吞字 */
    }

    /* 按钮样式 */
    div.stButton > button { 
        background-color: #FFFFFF !important; 
        color: #0E1117 !important; 
        font-weight: 700 !important; 
        border-radius: 8px !important; 
        width: 100% !important; 
        font-size: 1.1rem !important;
    }
    div.stButton > button:hover {
        background-color: #00FBFF !important;
        box-shadow: 0px 0px 15px rgba(0, 251, 255, 0.6);
    }

    /* 底部文字 */
    .footer-text { text-align: center; color: #9CA3AF !important; font-size: 0.9rem; margin-top: 50px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>基于Deepseek的可控解题提示生成系统</h1>", unsafe_allow_html=True)
_, m_col1, m_col2, _ = st.columns([1, 1, 1, 1])
m_col1.metric("答案提交次数", st.session_state.trial_count)
m_col2.metric("智能辅导次数", len(st.session_state.messages))
st.divider()

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
                st.rerun()
    else:
        if st.button("🔓 修改/重置当前题目"):
            st.session_state.submitted_problem = ""
            st.session_state.messages = []
            st.session_state.trial_count = 0
            st.session_state.current_q_id = None
            st.rerun()

with col2:
    st.header("📝 答案输入")
    student_answer = st.text_area("请写下你的计算过程或答案：", value="", height=150)
    if st.button("🚀 提交并判断对错"):
        if problem_is_locked and student_answer:
            judge_prompt = f"题目：{st.session_state.submitted_problem}\n学生答案：{student_answer}\n判断对错。只能输出'正确'或'错误'。"
            try:
                response = client.chat.completions.create(model="deepseek-chat", messages=[
                    {"role": "system", "content": "你是一个冷酷的判题系统。"},
                    {"role": "user", "content": judge_prompt}])
                result = response.choices[0].message.content.strip()

                is_correct = "正确" in result
                if is_correct:
                    st.success("✅ 正确")
                    save_to_logs(f"【答案提交】{student_answer}", "正确")
                else:
                    st.error("❌ 错误")
                    st.session_state.trial_count += 1
                    save_to_logs(f"【答案提交】{student_answer}", "错误")
                    st.rerun()
            except Exception as e:
                st.error(f"故障：{e}")
        elif not problem_is_locked:
            st.error("⚠️ 请先锁定题目！")

st.divider()

st.header("🤖 智能辅助")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("对这道题有什么疑问？"):
    if problem_is_locked:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        system_instruction = "你是一个专业的理科助教。绝对禁止直接给出最终答案或数值！使用 $ 包裹公式。"
        context = f"【题目】：{st.session_state.submitted_problem}\n【当前答案】：{student_answer}\n【疑问】：{prompt}"

        with st.chat_message("assistant"):
            try:
                response = client.chat.completions.create(model="deepseek-chat",
                                                          messages=[{"role": "system", "content": system_instruction},
                                                                    {"role": "user", "content": context}])
                ai_reply = response.choices[0].message.content
                st.markdown(ai_reply)
                st.session_state.messages.append({"role": "assistant", "content": ai_reply})

                save_to_logs(f"【智能辅导】{prompt}", ai_reply)

            except Exception as e:
                st.error(f"AI 故障：{e}")

if st.session_state.messages:
    _, center_btn, _ = st.columns([2, 1, 2])
    with center_btn:
        st.download_button(label="📥 导出实验日志报告", data=generate_report(), file_name=f"report_{MY_ID}.md")

st.markdown(f"<p class='footer-text'>系统运行中 | 负责人：左梓桐 （{MY_ID}）| 指导教师：王建荣</p>", unsafe_allow_html=True)