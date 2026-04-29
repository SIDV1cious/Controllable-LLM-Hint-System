import re

import pandas as pd
from sqlalchemy import text

from hint_system_core import ensure_leakage_observability_columns, now_shanghai


HINT_STRENGTH_PATTERN = re.compile(r"【提示强度：([^】]+)】")


def _extract_hint_strength(user_query: str) -> str:
    match = HINT_STRENGTH_PATTERN.search(str(user_query or ""))
    return match.group(1) if match else "未记录"


def _clean_student_request(user_query: str) -> str:
    request = str(user_query or "")
    request = request.replace("【辅导】", "")
    request = HINT_STRENGTH_PATTERN.sub("", request)
    return request.strip()


def _derive_safety_status(row) -> str:
    current_status = str(row.get("hint_safety_status") or "").strip()
    if current_status:
        return current_status
    if int(row.get("rewrite_count") or 0) > 0:
        return "已自动重写"
    if int(row.get("is_leaking_answer") or 0) > 0:
        return "仍有泄露风险"
    return "泄露检测通过"


def fetch_hint_experiment_logs(conn) -> pd.DataFrame:
    ensure_leakage_observability_columns()
    query = text(
        """
        SELECT
            il.id,
            il.student_id,
            il.question_id,
            COALESCE(cq.category, '未知课程') AS course_name,
            il.user_query,
            il.ai_response,
            il.is_leaking_answer,
            il.leakage_score,
            il.rewrite_count,
            il.leakage_reason,
            il.hint_strength,
            il.pedagogical_intent,
            il.hint_safety_status,
            il.created_at
        FROM interaction_logs il
        LEFT JOIN custom_questions cq ON il.question_id = cq.id + 1000
        WHERE il.user_query LIKE '【辅导】%'
        ORDER BY il.created_at DESC
        """
    )
    df = pd.read_sql(query, conn)
    if df.empty:
        return df

    numeric_columns = ["is_leaking_answer", "leakage_score", "rewrite_count"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)

    df["hint_strength"] = df.apply(
        lambda row: str(row["hint_strength"]).strip()
        if str(row.get("hint_strength") or "").strip()
        else _extract_hint_strength(row["user_query"]),
        axis=1,
    )
    df["pedagogical_intent"] = df["pedagogical_intent"].fillna("").astype(str).str.strip()
    df.loc[df["pedagogical_intent"] == "", "pedagogical_intent"] = "历史记录"
    df["hint_safety_status"] = df.apply(_derive_safety_status, axis=1)
    df["student_request"] = df["user_query"].apply(_clean_student_request)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["experiment_date"] = df["created_at"].dt.date.astype(str)
    return df


def summarize_hint_experiment(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "total_hints": 0,
            "final_leak_rate": 0.0,
            "rewrite_rate": 0.0,
            "avg_leakage_score": 0.0,
            "high_risk_count": 0,
        }

    total_hints = len(df)
    final_leak_count = int(df["is_leaking_answer"].sum())
    rewrite_session_count = int((df["rewrite_count"] > 0).sum())
    high_risk_count = int((df["leakage_score"] >= 2).sum())
    return {
        "total_hints": total_hints,
        "final_leak_rate": round(final_leak_count / total_hints * 100, 2),
        "rewrite_rate": round(rewrite_session_count / total_hints * 100, 2),
        "avg_leakage_score": round(float(df["leakage_score"].mean()), 2),
        "high_risk_count": high_risk_count,
    }


def build_experiment_export_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    export_columns = {
        "id": "记录ID",
        "student_id": "学生账号",
        "question_id": "题号",
        "course_name": "课程",
        "hint_strength": "提示强度",
        "pedagogical_intent": "教学意图",
        "hint_safety_status": "安全状态",
        "is_leaking_answer": "最终是否泄露",
        "leakage_score": "泄露评分",
        "rewrite_count": "重写次数",
        "leakage_reason": "检测原因",
        "student_request": "学生请求",
        "ai_response": "系统提示",
        "created_at": "生成时间",
    }
    return df[list(export_columns.keys())].rename(columns=export_columns)


def build_experiment_markdown_report(df: pd.DataFrame) -> str:
    summary = summarize_hint_experiment(df)
    lines = [
        "# 受控解题提示生成实验数据报告",
        "",
        f"导出时间：{now_shanghai():%Y-%m-%d %H:%M:%S}",
        "",
        "## 总体指标",
        "",
        f"- 智能辅导提示总数：{summary['total_hints']}",
        f"- 最终答案泄露率：{summary['final_leak_rate']}%",
        f"- 自动重写触发率：{summary['rewrite_rate']}%",
        f"- 平均泄露评分：{summary['avg_leakage_score']}",
        f"- 高风险候选提示数：{summary['high_risk_count']}",
        "",
    ]

    if df.empty:
        lines.append("暂无可导出的智能辅导实验数据。")
        return "\n".join(lines)

    grouped_sections = [
        ("## 按提示强度统计", "hint_strength"),
        ("## 按教学意图统计", "pedagogical_intent"),
        ("## 按安全状态统计", "hint_safety_status"),
    ]
    for title, column in grouped_sections:
        lines.extend([title, ""])
        grouped = df.groupby(column).agg(
            提示数量=("id", "count"),
            平均泄露评分=("leakage_score", "mean"),
            平均重写次数=("rewrite_count", "mean"),
        ).reset_index()
        for _, row in grouped.iterrows():
            lines.append(
                f"- {row[column]}：{int(row['提示数量'])} 条，"
                f"平均泄露评分 {row['平均泄露评分']:.2f}，"
                f"平均重写次数 {row['平均重写次数']:.2f}"
            )
        lines.append("")

    return "\n".join(lines)
