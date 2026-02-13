import streamlit as st
import os
import random
from sqlalchemy import create_engine, text
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import pytz
from prompts import SYSTEM_INSTRUCTION, JUDGE_PROMPT_SYSTEM

load_dotenv()


# --- 配置读取 ---
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

# --- 预设题库 (您可以随时在这里添加更多题目) ---
QUESTION_BANK = [
    {
        "id": 1,
        "category": "高等数学",
        "content": "已知函数 f(x) = x * ln(x)，求 f(x) 在 x = e 处的导数值。"
    },
    {
        "id": 2,
        "category": "线性代数",
        "content": "求矩阵 A = [[1, 2], [2, 1]] 的特征值。"
    },
    {
        "id": 3,
        "category": "微积分",
        "content": "计算不定积分 ∫ x * e^x dx。"
    },
    {
        "id": 4,
        "category": "导数应用",
        "content": "求函数 y = x^3 - 3x + 1 的单调递增区间。"
    }
]

# --- Session State 初始化 ---
if "current_question" not in st.session_state:
    st.session_state.current_question = QUESTION_BANK[0]  # 默认第一题
if "trial_count" not in st.session_state:
    st.session_state.trial_count = 0
if "messages" not in st.session_state:
    st.session_state.messages = []
if "answer_input" not in st.session_state:
    st.session_state.answer_input = ""
if "check_result" not in st.session_state:
    st.session_state.check_result = None  # 用于存储判题结果状态


# --- 数据库连接 ---
@st.cache_resource
def get_db_engine():
    db_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}"
    return create_engine(db_url, pool_recycle=1800, pool_pre_ping=True)


def save_to_logs(user_query, ai_response, is_leaking=0):
    # 记录当前题目ID（如果是在题库里的，就存题库ID）
    q_id = st.session_state.current_question["id"]
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
        print(f"存证失败：{e}")  # 生产环境不弹窗打扰用户


def generate_report():
    ai_reply_count = len([m for m in st.session_state.messages if m["role"] == "assistant"])
    report = f"# 毕设实验数据报告\n- **项目标题**：基于Deepseek的可控解题提示生成系统\n"
    report += f"- **负责人**：左梓桐 ({my_id})\n"
    report += f"- **导出时间**：{datetime.now(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')}\n"
    report += f"## 关键数据指标\n- **答案提交次数**：{st.session_state.trial_count} 次\n- **智能辅导次数**：{ai_reply_count} 次\n"
    return report


# --- 页面设置 (移除背景色CSS，回归默认亮色) ---
st.set_page_config(page_title="智能导学系统", layout="wide", initial_sidebar_state="expanded")

# --- 侧边栏：选题区 ---
with st.sidebar:
    st.header("📚 题库选择")
    st.info(f"当前用户：{my_id}")

    # 方式1：下拉选择
    selected_q_title = st.selectbox(
        "选择题目：",
        options=[f"[{q['category']}] 题目 {q['id']}" for q in QUESTION_BANK],
        index=QUESTION_BANK.index(st.session_state.current_question)
    )

    # 解析选择的题目ID
    selected_id = int(selected_q_title.split("题目 ")[1])

    # 检查是否切换了题目
    if selected_id != st.session_state.current_question["id"]:
        st.session_state.current_question = next(q for q in QUESTION_BANK if q["id"] == selected_id)
        # 切换题目时重置所有状态
        st.session_state.messages = []
        st.session_state.trial_count = 0
        st.session_state.answer_input = ""
        st.session_state.check_result = None
        st.rerun()

    st.divider()

    # 方式2：随机抽题
    if st.button("🎲 随机抽取一题"):
        new_q = random.choice(QUESTION_BANK)
        # 避免随机到同一题（如果是同一题就再随一次，简单处理）
        if new_q["id"] == st.session_state.current_question["id"]:
            new_q = random.choice(QUESTION_BANK)

        st.session_state.current_question = new_q
        st.session_state.messages = []
        st.session_state.trial_count = 0
        st.session_state.answer_input = ""
        st.session_state.check_result = None
        st.rerun()

    st.divider()
    st.download_button(label="📥 导出学习报告", data=generate_report(), file_name=f"report_{my_id}.md")

# --- 主界面 ---
st.title("🎓 智能导学与判题系统")

# 顶部指标栏
col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("当前科目", st.session_state.current_question["category"])
col_m2.metric("尝试次数", st.session_state.trial_count)
ai_count = len([m for m in st.session_state.messages if m["role"] == "assistant"])
col_m3.metric("获得辅导", f"{ai_count} 次")

st.divider()

# 题目显示区
st.subheader("📝 当前题目")
st.info(st.session_state.current_question["content"], icon="🧐")

# 答案输入区
st.subheader("✍️ 你的解答")
student_answer = st.text_area("在此输入你的解题过程或最终答案：", height=150, key="answer_input")

# 提交按钮区
col_submit, col_hint = st.columns([1, 4])
with col_submit:
    if st.button("🚀 提交判题", type="primary", use_container_width=True):
        if not student_answer.strip():
            st.warning("请先输入答案再提交！")
        else:
            # 判题逻辑
            st.session_state.trial_count += 1
            judge_prompt = f"题目：{st.session_state.current_question['content']}\n学生答案：{student_answer}\n判断对错。只能输出'正确'或'错误'。"

            try:
                response = client.chat.completions.create(model="deepseek-chat", messages=[
                    {"role": "system", "content": JUDGE_PROMPT_SYSTEM},
                    {"role": "user", "content": judge_prompt}])
                result = response.choices[0].message.content.strip()

                is_correct = "正确" in result
                if is_correct:
                    st.session_state.check_result = "correct"
                    st.toast("恭喜你，答案正确！", icon="✅")
                    save_to_logs(f"【答案提交】{student_answer}", "正确")
                else:
                    st.session_state.check_result = "wrong"
                    st.toast("答案有误，请参考下方智能辅导。", icon="❌")
                    save_to_logs(f"【答案提交】{student_answer}", "错误")

                st.rerun()  # 刷新以更新顶部指标和下方状态

            except Exception as e:
                st.error(f"判题服务连接失败：{e}")

# 显示判题结果反馈（持久化显示）
if st.session_state.check_result == "correct":
    st.success("✅ 回答正确！你已掌握该知识点。")
elif st.session_state.check_result == "wrong":
    st.error("❌ 回答错误。别灰心，在下方与 AI 助教讨论一下吧👇")

# --- 智能辅导区 (Chat) ---
st.divider()
st.subheader("🤖 智能助教 (AI Tutor)")

# 显示历史记录
for message in st.session_state.messages:
    avatar = "🧑‍🎓" if message["role"] == "user" else "🤖"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# 聊天输入框
if prompt := st.chat_input("对这道题有疑问？输入 '怎么做' 或 '给我点提示'"):
    # 存入用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(prompt)

    # 构造 Prompt
    context = f"【题目】：{st.session_state.current_question['content']}\n【学生当前错题本】：{student_answer}\n【学生疑问】：{prompt}"

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
                    display_text = full_response.replace(r"\[", "$$").replace(r"\]", "$$").replace(r"\(", "$").replace(
                        r"\)", "$")
                    response_placeholder.markdown(display_text + "▌")

            final_text = full_response.replace(r"\[", "$$").replace(r"\]", "$$").replace(r"\(", "$").replace(r"\)", "$")
            response_placeholder.markdown(final_text)

            st.session_state.messages.append({"role": "assistant", "content": final_text})
            save_to_logs(f"【智能辅导】{prompt}", final_text)

            # 刷新页面以更新顶部的“智能辅导次数”
            st.rerun()

        except Exception as e:
            st.error(f"AI 响应中断：{e}")

# 底部版权
st.markdown("---")
st.caption(f"© 2026 智能导学系统 | 学生：左梓桐 | 指导教师：王建荣")