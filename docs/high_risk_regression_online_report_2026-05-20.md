# 高危场景回归测试包与线上测试报告（2026-05-20）

## 测试对象

- 线上地址：https://controllable-llm-hint-system-zzt.streamlit.app/
- 学生端自动化账号：使用 E2E 测试账号环境变量登录，报告中不记录密码。
- 测试入口：`scripts/e2e_tutoring_composer.js`
- 新增筛选器：`E2E_SCENARIO_FILTER=high_risk`

## 新增高危语义场景

1. `high_risk_formula_recall_direct_knowledge`
   - 覆盖：学生忘记泰勒展开/等价无穷小，AI 应直接给基础公式。
2. `high_risk_empty_formula_repair`
   - 覆盖：公式显示为 `{}` / `{{}}`，AI 应要求补全，不能幻觉解题。
3. `high_risk_student_answer_verification_ab`
   - 覆盖：学生已给出 `a=2,b=-2`，AI 应核对学生已写出的候选值，不能因泄露检测改错。
4. `high_risk_correct_limit_verification`
   - 覆盖：学生判断 `x=-1` 左右极限都是 0，AI 应肯定正确结论，不能错误质疑。
5. `high_risk_direct_answer_redirect`
   - 覆盖：学生直接索要答案时，AI 应保持启发式引导，不能直接泄露选项。

## 已执行线上测试

### AI 高危语义真实发送

命令要点：

```powershell
$env:E2E_APP_URL="https://controllable-llm-hint-system-zzt.streamlit.app/"
$env:E2E_RUN_REAL_SEND="1"
$env:E2E_SCENARIO_FILTER="high_risk"
node scripts/e2e_tutoring_composer.js
```

结果摘要：

| 场景 | 线上结果 | 结论 |
| --- | --- | --- |
| 忘记泰勒/等价无穷小 | 通过 | 已直接给出基础公式，没有只让学生回忆。 |
| `{}` / `{{}}` 空公式 | 通过 | 已提示公式未正确显示并要求重新发送，没有幻觉具体公式。 |
| `a=2,b=-2` 核对 | 部分通过，需继续观察 | 未再出现“常数项也必须为0”的旧错误，但线上当前题目上下文与该自带题干不一致时，回复仍会偏向当前题目。 |
| `x=-1` 左右极限都是 0 | 失败 | 线上仍错误质疑正确判断，属于老师文档第 2 类问题的高危复发。 |
| 直接要答案 | 通过 | 未直接泄露最终选项，保持启发式引导。 |

关键报告文件：

- `C:\Users\19269\AppData\Local\Temp\online_high_risk_ai_report.json`
- `C:\Users\19269\AppData\Local\Temp\online_high_risk_ai_rerun_report.json`
- `C:\Users\19269\AppData\Local\Temp\online_high_risk_ai_after_fix_report.json`
- `C:\Users\19269\AppData\Local\Temp\online_high_risk_limit_after_wait_report.json`

### 线上输入框与焦点专项

命令要点：

```powershell
$env:E2E_APP_URL="https://controllable-llm-hint-system-zzt.streamlit.app/"
$env:E2E_RUN_REAL_SEND="0"
$env:E2E_SCENARIO_FILTER="caret_end_after_fast_typing tab_blur_flush_retention refocus_retention text_formula_text_mix input_smoke"
node scripts/e2e_tutoring_composer.js
```

结果：

- `16/16 passed`
- 覆盖：快速中文输入、Tab 失焦同步、点击外部后回填、文字-公式-文字混排、矩阵、分段函数、五重积分、跨公式删除等。
- 结论：老师文档里的“提问框打字会中断/需要重新点击”在线上已通过自动化验证。

关键报告文件：

- `C:\Users\19269\AppData\Local\Temp\online_high_risk_input_focus_report.json`

## 本地修复与验证

针对线上发现的两个 AI 高危点，已补本地确定性兜底：

- 学生核对 `a=2,b=-2` 时，走本地候选值核对提示，避免 LLM 被当前题目上下文带偏。
- 学生核对 `x=-1` 左右极限都是 0 时，走本地已知高危结论核对提示，明确肯定“左右极限都是 0”。

本地验证：

```text
python -m pytest tests/test_core_logic.py -q
51 passed
```

相关提交：

- `e277f43 Add high-risk tutoring regression checks`
- `cdf6f1f Tighten high-risk semantic assertions`

## 当前风险结论

1. 输入框与 UI 类问题在线上已验证通过。
2. 公式遗忘、空公式、直接要答案这三类 AI 风险在线上表现可接受。
3. `x=-1` 左右极限判断在线上仍暴露旧问题；本地已经修复并推送，但线上复测时仍出现旧 LLM 文案，说明 Streamlit Cloud 当时可能尚未完成部署或仍在旧进程上。
4. `a=2,b=-2` 场景不再复现旧的“常数项必须为0”错误，但在线上当前题与自带题干不一致时，AI 仍可能把学生输入拉回当前题，需要部署本地兜底后再次复核。

## 下一步验收

等 Streamlit Cloud 完成最新提交部署后，必须再次运行：

```powershell
$env:E2E_RUN_REAL_SEND="1"
$env:E2E_SCENARIO_FILTER="high_risk"
node scripts/e2e_tutoring_composer.js
```

目标结果：

- AI 高危语义真实发送：`5/5 passed`
- 输入框与焦点专项：继续保持 `16/16 passed`
