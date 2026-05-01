import logging

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text


def render_learning_overview_dashboard(conn):
    st.subheader("🎓 全系统学情实时监控看板")
    st.markdown("---")
    st.markdown("#### 🕒 最近7天系统活跃人数趋势")
    try:
        sql_active = text(
            "SELECT DATE(login_time) as login_date, COUNT(DISTINCT username) as user_count "
            "FROM login_logs WHERE login_time >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) "
            "GROUP BY login_date ORDER BY login_date;"
        )
        df_active = pd.read_sql(sql_active, conn)
        if not df_active.empty:
            df_active["login_date"] = pd.to_datetime(df_active["login_date"])
            st.line_chart(df_active, x="login_date", y="user_count", use_container_width=True)
    except Exception as e:
        logging.error(f"Dashboard Active Users Error: {e}")

    st.markdown("---")
    st.markdown("#### 📘 各科课程学习时长占比")
    col_chart1, col_data1 = st.columns([2, 1])
    try:
        sql_duration = text(
            "SELECT course_name, SUM(duration_seconds) as total_seconds "
            "FROM study_sessions WHERE duration_seconds IS NOT NULL GROUP BY course_name;"
        )
        df_duration = pd.read_sql(sql_duration, conn)
        if not df_duration.empty:
            df_duration["total_minutes"] = (df_duration["total_seconds"] / 60).round(1)
            fig_pie = px.pie(
                df_duration,
                values="total_minutes",
                names="course_name",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            with col_chart1:
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_data1:
                st.markdown("<div style='margin-top: 100px;'></div>", unsafe_allow_html=True)
                st.dataframe(df_duration[["course_name", "total_minutes"]], hide_index=True)
    except Exception as e:
        logging.error(f"Dashboard Duration Error: {e}")

    st.markdown("---")
    st.markdown("#### ✅ 全系统题目平均正确率统计")
    try:
        df_interact_raw = pd.read_sql(
            "SELECT question_id, ai_response FROM interaction_logs WHERE user_query LIKE '【答案提交】%%'",
            conn,
        )
        if not df_interact_raw.empty:
            q_df = pd.read_sql("SELECT id, category FROM custom_questions", conn)
            q_id_map = {str(1000 + int(row["id"])): str(row["category"]) for _, row in q_df.iterrows()}
            df_interact_raw["clean_id"] = pd.to_numeric(
                df_interact_raw["question_id"], errors="coerce"
            ).fillna(-1).astype(int).astype(str)
            df_interact_raw["course_name"] = df_interact_raw["clean_id"].map(q_id_map)
            df_valid = df_interact_raw.dropna(subset=["course_name"]).copy()
            if not df_valid.empty:
                df_valid["is_correct"] = df_valid["ai_response"].apply(
                    lambda x: 1 if ("正确" in str(x) or "PASS" in str(x)) else 0
                )
                df_accuracy = df_valid.groupby("course_name")["is_correct"].mean().reset_index()
                df_accuracy["accuracy_percent"] = (df_accuracy["is_correct"] * 100).round(1)
                fig_bar = px.bar(
                    df_accuracy,
                    x="course_name",
                    y="accuracy_percent",
                    labels={"course_name": "课程名称", "accuracy_percent": "正确率 (%)"},
                    color_discrete_sequence=["#1f77b4"],
                )
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
            "SELECT is_leaking_answer, leakage_score, rewrite_count "
            "FROM interaction_logs WHERE user_query LIKE '【辅导】%%'",
            conn,
        )
        if not df_leak.empty:
            total_hints = len(df_leak)
            leaked_hints = int(df_leak["is_leaking_answer"].fillna(0).astype(int).sum())
            rewrite_total = int(df_leak.get("rewrite_count", pd.Series([0] * total_hints)).fillna(0).astype(int).sum())
            leak_rate = round(leaked_hints / total_hints * 100, 1)
            c_leak1, c_leak2, c_leak3 = st.columns(3)
            c_leak1.metric("辅导提示总数", total_hints)
            c_leak2.metric("最终泄露率", f"{leak_rate} %")
            c_leak3.metric("自动重写次数", rewrite_total)
            score_df = df_leak.groupby("leakage_score").size().reset_index(name="count")
            fig_leak = px.bar(
                score_df,
                x="leakage_score",
                y="count",
                labels={"leakage_score": "泄露评分", "count": "提示数量"},
                color_discrete_sequence=["#2ca02c"],
            )
            st.plotly_chart(fig_leak, use_container_width=True)
        else:
            st.info("暂无智能辅导提示数据，无法计算泄露控制指标。")
    except Exception as e:
        logging.error(f"Leakage dashboard error: {e}")
        st.info("当前数据库尚未记录泄露控制扩展指标。")
