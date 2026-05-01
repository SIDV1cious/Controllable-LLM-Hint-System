from system_config import now_shanghai


def build_result_export(assessment_results: list) -> str:
    total = len(assessment_results)
    correct_count = sum(1 for item in assessment_results if item.get("is_correct"))
    accuracy = round(correct_count / total * 100, 1) if total else 0.0
    lines = [
        "# 本次测验结果",
        "",
        f"导出时间：{now_shanghai():%Y-%m-%d %H:%M:%S}",
        f"总题数：{total}",
        f"答对题数：{correct_count}",
        f"正确率：{accuracy}%",
        "",
    ]

    for index, item in enumerate(assessment_results, start=1):
        question = item.get("question_data", {})
        lines.extend(
            [
                f"## 第 {index} 题",
                "",
                f"结果：{'正确' if item.get('is_correct') else '错误'}",
                f"题目：{question.get('content', '')}",
                f"我的作答：{item.get('user_answer', '')}",
                "",
            ]
        )

    return "\n".join(lines)
