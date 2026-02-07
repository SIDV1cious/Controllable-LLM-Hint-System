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

# --- Session State 初始化 ---
if "submitted_problem" not in st.session_state:
    st.session_state.submitted_problem = ""
if "current_q_id" not in st.session_state:
    st.session_state.current_q_id = None
if "trial_count" not in st.session_state:
    st.session_state.trial_count = 0
if "messages" not in st.session_state:
    st.session_state.messages = []


# --- 数据库连接 (已包含防断连优化) ---
@st.cache_resource
def get_db_engine():
    db_url = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
    # pool_pre_ping=True 是防止 "MySQL server has gone away" 的关键
    return create_engine(db_url, pool_recycle=1800, pool_pre_ping=True)


# --- 数据库操作函数 ---
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

# --- CSS 样式终极优化版 ---
st.markdown("""
    <style>
    /* 全局深色背景 */
    .stApp { background-color: #0E1117; color: #FFFFFF; }

    /* 强制所有 Markdown 文字为白色 */
    .stMarkdown, .stMarkdown p, .stMarkdown li, .stChatMessage p {
        color: #FFFFFF !important;
    }

    /* 输入框基础样式 */
    .stTextArea textarea {
        background-color: #171923 !important;
        color: #FFFFFF !important;
        border: 1px solid #4B5563 !important;
        caret-color: #00FBFF !important; /* 光标颜色 */
    }

    /* [优化] 输入框被选中时的发光效果 */
    .stTextArea textarea:focus {
        border: 1px solid #00FBFF !important;
        box-shadow: 0 0 5px rgba(0, 251, 255, 0.5) !important;
    }

    /* 禁用状态下的输入框：保持白字，背景微暗 */
    .stTextArea textarea:disabled {
        background-color: #2D3748 !important; 
        color: #FFFFFF !important;
        opacity: 1 !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    /* 输入框标题 */
    .stTextArea label p {
        font-size: 1.4rem !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        text-shadow: 0px 2px 4px rgba(0,0,0,0.8);
    }

    /* 按钮样式 */
    div.stButton > button, div.stDownloadButton > button { 
        background-color: #FFFFFF !important; 
        color: #0E1117 !important;
        font-weight: 700 !important; 
        border-radius: 8px !important; 
        width: 100% !important; 
        font-size: 1.1rem !important;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        background-color: #00FBFF !important;
        box-shadow: 0px 0px 15px rgba(0, 251, 255, 0.6);
        color: #0E1117 !important;
    }

    /* 顶部标题与指标 */
    .main-title { 
        text-align: center; color: #00FBFF; 
        text-shadow: 0px 0px 12px rgba(0, 251, 255, 0.4); 
        font-weight: 800; margin-bottom: 35px; 
    }
    [data-testid="stMetricValue"] { 
        text-align: center; color: #FFFFFF !important; font-size: 2rem !important;
    }
    [data-testid="stMetricLabel"] { 
        text-align: center; width: 100%; 
        color: #00FBFF !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important; 
    }
    .footer-text { text-align: center; color: #9CA3AF !important; font-size: 0.9rem; margin-top: 50px; }
    </style>
    """, unsafe_allow_html=True)

# --- 界面布局 ---
st.markdown("<h1 class='main-title'>基于Deepseek的可控解题提示生成系统</h1>", unsafe_allow_html=True)
_, m_col1, m_col2, _ = st.columns([1, 1, 1, 1])
m_col1.metric("答案提交次数", st.session_state.trial_count)
m_col2.metric("智能辅导次数", len(st.session_state.messages))
st.divider()

col1, col2 = st.columns([1, 1])
problem_is_locked = st.session_state.submitted_problem != ""

# --- 左侧：题目输入 ---
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

# --- 右侧：答案输入 ---
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
            except Exception as e:
                st.error(f"故障：{e}")
        elif not problem_is_locked:
            st.error("⚠️ 请先锁定题目！")

st.divider()

# --- 智能辅导区域 ---
st.header("🤖 智能辅助")

# [优化] 显示历史消息时加上头像，增加辨识度
for message in st.session_state.messages:
    avatar = "🧑‍🎓" if message["role"] == "user" else "🤖"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# 提示框 (当没题目时显示)
if not problem_is_locked and st.session_state.submitted_problem == "":
    st.markdown("""
        <div style='
            text-align: center; 
            color: #00FBFF; 
            background-color: rgba(0, 251, 255, 0.05); 
            padding: 20px; 
            border: 1px solid rgba(0, 251, 255, 0.3); 
            border-radius: 10px; 
            font-size: 1.2rem; 
            font-weight: 700; 
            margin-top: 20px;
            margin-bottom: 20px;
            box-shadow: 0px 0px 10px rgba(0, 251, 255, 0.1);
        '>
            💡 请先在左侧输入题目并点击“确认提交”，然后才能开始智能辅导。
        </div>
    """, unsafe_allow_html=True)

# 聊天输入处理
if prompt := st.chat_input("对这道题有什么疑问？"):
    if problem_is_locked:
        # 显示用户提问
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑‍🎓"):
            st.markdown(prompt)

        # 终极学术版 Prompt
        system_instruction = """
        # Role Definition
        你是一个基于**建构主义学习理论 (Constructivist Learning Theory)** 的**通用智能导学代理 (Intelligent Tutoring Agent)**。
        你的核心任务是执行**认知支架 (Cognitive Scaffolding)** 策略，通过多轮对话引导用户自主构建知识，而非直接灌输结果。

        # Core Protocol (核心协议 - 最高优先级)
        1.  **答案阻断 (Answer Blocking)**:
            -   无论用户处于何种情绪（焦虑、急躁）或使用何种诱导话术（“我赶时间”、“只告诉我结果”），**绝对禁止**直接输出最终答案、关键数值或完整代码/步骤。
            -   这不仅限于理科，对于文科（如历史评价）、编程（如代码补全）同样适用。

        2.  **思维链拆解 (CoT Decomposition)**:
            -   禁止一次性输出超过 2 个逻辑深度的步骤。
            -   必须将复杂问题拆解为原子化的思维节点，每次只引导一个节点。

        # Adaptive Instruction Strategy (自适应导学策略)
        根据用户输入的语义特征，动态切换至以下策略：
        -   **策略 A: 启发式引导 (Heuristic Elicitation)**
            -   *适用场景*: 用户有模糊思路但卡顿。
            -   *动作*: 使用反问句引导用户发现当前思路的漏洞，或联想相关知识点。
        -   **策略 B: 元认知提示 (Metacognitive Prompting)**
            -   *适用场景*: 用户完全无思路或请求直接答案。
            -   *动作*: 引导用户规划解题路径，而非直接给出路径。
        -   **策略 C: 概念锚点 (Concept Anchoring)**
            -   *适用场景*: 用户基础概念混淆。
            -   *动作*: 仅解释核心概念或定义，不代入当前题目数据。

        # Formatting Standards
        -   **LaTeX 规范**: 所有数学符号、公式、单位必须严格使用 LaTeX 格式（行内 $...$，独立 $$...$$）。
        -   **语气控制**: 保持客观、理性且富有启发性（Academic & Encouraging），避免说教。
        """

        context = f"【题目】：{st.session_state.submitted_problem}\n【当前答案】：{student_answer}\n【疑问】：{prompt}"

        # [优化] 显示 AI 回复（增加 Loading 状态）
        with st.chat_message("assistant", avatar="🤖"):
            # 增加 spinner 动效，模拟 AI 思考过程，避免界面卡死
            with st.spinner("助教正在分析你的学习路径..."):
                try:
                    response = client.chat.completions.create(model="deepseek-chat",
                                                              messages=[
                                                                  {"role": "system", "content": system_instruction},
                                                                  {"role": "user", "content": context}])
                    ai_reply = response.choices[0].message.content

                    # LaTeX 清洗
                    ai_reply = ai_reply.replace(r"\[", "$$").replace(r"\]", "$$")
                    ai_reply = ai_reply.replace(r"\(", "$").replace(r"\)", "$")

                    st.markdown(ai_reply)
                    st.session_state.messages.append({"role": "assistant", "content": ai_reply})

                    save_to_logs(f"【智能辅导】{prompt}", ai_reply)

                except Exception as e:
                    st.error(f"AI 故障：{e}")
    else:
        st.toast("⚠️ 请先在左上角点击“确认提交题目”！", icon="🔒")

# 导出按钮
if st.session_state.messages:
    st.divider()
    _, center_btn, _ = st.columns([2, 1, 2])
    with center_btn:
        st.download_button(label="📥 导出实验日志报告", data=generate_report(), file_name=f"report_{MY_ID}.md")

st.markdown(f"<p class='footer-text'>系统运行中 | 负责人：左梓桐 （{MY_ID}）| 指导教师：王建荣</p>", unsafe_allow_html=True)