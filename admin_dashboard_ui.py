import plotly.express as px
import streamlit as st

from admin_observability_repository import (
    build_leakage_score_distribution,
    fetch_cached_active_user_trend,
    fetch_cached_course_accuracy_summary,
    fetch_cached_course_study_duration_summary,
    fetch_cached_hint_leakage_records,
    summarize_hint_leakage_records,
)
from app_errors import log_exception


def _apply_plotly_panel_theme(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248,251,255,0.68)",
        font={"family": "Arial, sans-serif", "color": "#334155"},
        margin={"l": 20, "r": 20, "t": 18, "b": 20},
        hoverlabel={"bgcolor": "white", "bordercolor": "#dbe4f0", "font_size": 13},
    )
    fig.update_xaxes(showgrid=False, linecolor="#dbe4f0", tickfont={"color": "#64748b"})
    fig.update_yaxes(gridcolor="#e8eef7", zerolinecolor="#dbe4f0", tickfont={"color": "#64748b"})
    return fig


def render_learning_overview_dashboard():
    with st.container(border=True):
        st.markdown("#### 🕒 最近7天系统活跃人数趋势")
        try:
            df_active = fetch_cached_active_user_trend()
            if not df_active.empty:
                fig_active = px.line(
                    df_active,
                    x="login_date",
                    y="user_count",
                    markers=True,
                    labels={"login_date": "日期", "user_count": "活跃人数"},
                    color_discrete_sequence=["#2563eb"],
                )
                fig_active.update_traces(line_width=3, marker_size=8)
                st.plotly_chart(_apply_plotly_panel_theme(fig_active), use_container_width=True)
            else:
                st.info("最近7天暂无登录记录。")
        except Exception as e:
            log_exception("Dashboard active users", e)

    st.markdown("---")
    with st.container(border=True):
        st.markdown("#### 📘 各科课程学习时长占比")
        col_chart1, col_data1 = st.columns([2, 1])
        try:
            df_duration = fetch_cached_course_study_duration_summary()
            if not df_duration.empty:
                fig_pie = px.pie(
                    df_duration,
                    values="total_minutes",
                    names="course_name",
                    hole=0.48,
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                )
                fig_pie.update_traces(textposition="inside", textinfo="percent+label", marker_line_color="white")
                fig_pie.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin={"l": 20, "r": 20, "t": 12, "b": 12},
                    legend={"orientation": "h", "y": -0.12},
                )
                with col_chart1:
                    st.plotly_chart(fig_pie, use_container_width=True)
                with col_data1:
                    st.dataframe(df_duration[["course_name", "total_minutes"]], hide_index=True)
            else:
                st.info("暂无课程学习时长记录。")
        except Exception as e:
            log_exception("Dashboard duration", e)

    st.markdown("---")
    with st.container(border=True):
        st.markdown("#### ✅ 全系统题目平均正确率统计")
        try:
            df_accuracy, has_answer_records = fetch_cached_course_accuracy_summary()
            if not has_answer_records:
                st.info("暂无答题提交数据，无法计算正确率。")
            elif df_accuracy.empty:
                st.warning("⚠️ 无法生成图表：题号映射失败！")
            else:
                fig_bar = px.bar(
                    df_accuracy,
                    x="course_name",
                    y="accuracy_percent",
                    text="accuracy_percent",
                    labels={"course_name": "课程名称", "accuracy_percent": "正确率 (%)"},
                    color_discrete_sequence=["#2563eb"],
                )
                fig_bar.update_traces(width=0.36 if len(df_accuracy) == 1 else 0.55, texttemplate="%{text}%")
                st.plotly_chart(_apply_plotly_panel_theme(fig_bar), use_container_width=True)
        except Exception as e:
            st.error(f"⚠️ 图表加载报错: {e}")

    st.markdown("---")
    with st.container(border=True):
        st.markdown("#### 🛡️ 智能辅导答案泄露控制统计")
        try:
            df_leak = fetch_cached_hint_leakage_records()
            if not df_leak.empty:
                leakage_summary = summarize_hint_leakage_records(df_leak)
                c_leak1, c_leak2, c_leak3 = st.columns(3)
                c_leak1.metric("辅导提示总数", leakage_summary["total_hints"])
                c_leak2.metric("最终泄露率", f"{leakage_summary['leak_rate']} %")
                c_leak3.metric("自动重写次数", leakage_summary["rewrite_total"])
                score_df = build_leakage_score_distribution(df_leak)
                fig_leak = px.bar(
                    score_df,
                    x="risk_level",
                    y="count",
                    text="count",
                    labels={"risk_level": "泄露风险等级", "count": "提示数量"},
                    color="risk_level",
                    color_discrete_map={
                        "0 安全": "#22c55e",
                        "1 轻微风险": "#84cc16",
                        "2 中等风险": "#f59e0b",
                        "3 高风险": "#ef4444",
                    },
                )
                fig_leak.update_traces(width=0.45, textposition="outside", cliponaxis=False)
                fig_leak.update_layout(
                    showlegend=False,
                    bargap=0.45,
                    yaxis_title="提示数量",
                    xaxis_title="泄露风险等级",
                )
                st.plotly_chart(_apply_plotly_panel_theme(fig_leak), use_container_width=True)
            else:
                st.info("暂无智能辅导提示数据，无法计算泄露控制指标。")
        except Exception as e:
            log_exception("Leakage dashboard", e)
            st.info("当前数据库尚未记录泄露控制扩展指标。")
