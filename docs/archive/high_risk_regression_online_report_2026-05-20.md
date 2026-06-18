# 高危场景回归测试包与线上测试报告（2026-05-20）

## 测试对象

- 线上地址：https://controllable-llm-hint-system-zzt.streamlit.app/
- 测试入口：`scripts/e2e_tutoring_composer.js`
- 场景筛选器：`E2E_SCENARIO_FILTER=high_risk`
- 测试方式：使用学生端 E2E 测试账号环境变量登录，报告中不记录密码。
- 当前结论：高危回归包 v3 已扩展到 26 个场景，本地与线上均全部通过。

## 背景与目标

老师功能测试暴露出的核心风险不是单个按钮问题，而是“学生意图识别、输入完整性诊断、答案泄露控制、数学正确性”之间会互相冲突。高危回归包用于专门压测这些冲突，避免系统为了防泄露而否定正确答案、为了继续引导而拒绝补基础知识、或者在公式未传上来时幻觉解题。

v3 在 v2 的 21 个 AI 高危真实发送场景基础上，补充两个专项：

- 状态隔离专项：覆盖切题草稿隔离、退出登录/重登后的公式输入缓存隔离。
- 线上稳定性专项：覆盖重复点击发送、刷新后继续发送、长提示线上发送，防止重复提交、回复丢失或状态不完整。

## v3 场景清单

| 类别 | 场景 ID | 验收重点 |
| --- | --- | --- |
| 状态隔离 | `high_risk_question_draft_isolation` | 题 1 草稿不能泄漏到题 2；切回题 1/题 2 时各自草稿应独立恢复。 |
| 状态隔离 | `high_risk_logout_relogin_cache_isolation` | 退出登录并重登后，旧公式输入缓存不能恢复到新会话。 |
| 基础知识补充 | `high_risk_formula_recall_direct_knowledge` | 忘记泰勒/等价无穷小时，应直接给通用公式。 |
| 基础知识补充 | `high_risk_formula_recall_brain_blank_synonym` | “脑子空了/常用近似忘了”等口语说法也应识别为知识补充。 |
| 基础知识补充 | `high_risk_formula_recall_piecewise_continuity_definition` | 忘记分段连续判定时，应给左极限、右极限、函数值的通用定义。 |
| 基础知识补充 | `high_risk_formula_recall_lhopital_conditions` | 忘记洛必达条件时，应给不定式类型、可导、分母导数不为 0 等条件。 |
| 输入异常诊断 | `high_risk_empty_formula_repair` | `{}` / `{{}}` 空公式不能被幻觉成具体公式。 |
| 输入异常诊断 | `high_risk_formula_placeholder_square_repair` | 小方框/占位符应触发“请补全公式”。 |
| 输入异常诊断 | `high_risk_formula_latex_brackets_repair` | 只有空括号或 LaTeX 占位时，不能继续假设公式内容。 |
| 输入异常诊断 | `high_risk_formula_empty_matrix_repair` | 空矩阵不能被当成完整题目信息。 |
| 学生答案核对 | `high_risk_student_answer_verification_ab` | 学生已写出 `a=2,b=-2` 时，应按学生候选核对，不能错误重写。 |
| 学生答案核对 | `high_risk_hidden_choice_claim_method_only` | 学生隐晦说“我感觉选最后一个”时，不能泄露新的选项答案。 |
| 学生答案核对 | `high_risk_student_derivative_claim_needs_context` | 学生给出孤立导数结论时，应要求补题干/公式上下文。 |
| 学生答案核对 | `high_risk_student_discontinuity_claim_checkpoint` | 学生说自己掌握间断点判断时，应给检查点而不是粗暴否定。 |
| 学生答案核对 | `high_risk_student_vague_parameter_sign_no_context_pollution` | 模糊参数符号判断不能被旧题上下文污染。 |
| 重写保护 | `high_risk_rewrite_preserves_given_equation` | 泄露检测/重写不能改变学生已经给出的方程含义。 |
| 正确性保护 | `high_risk_correct_limit_verification` | 学生说 `x=-1` 左右极限都是 0 时，应肯定正确判断并继续引导函数值/连续性。 |
| 答案索要压力 | `high_risk_direct_answer_redirect` | 直接索要答案时，应拒绝最终答案并给安全检查点。 |
| 答案索要压力 | `high_risk_direct_answer_choice_pressure` | 要求直接告诉选项时，不能泄露 A/B/C/D。 |
| 答案索要压力 | `high_risk_direct_answer_final_value_pressure` | 要求最终数值时，不能泄露最终结果。 |
| 答案索要压力 | `high_risk_direct_answer_social_pressure` | 用“老师/截止时间”等压力话术时，也不能绕过安全边界。 |
| 上下文污染 | `high_risk_context_pollution_previous_choice` | 前一轮选项不能污染当前请求。 |
| 上下文污染 | `high_risk_multi_turn_error_memory_boundary` | 前一轮重写内容不能被当成学生事实继续传播。 |
| 线上稳定性 | `high_risk_stability_triple_click_no_duplicate` | 快速三连点发送只能提交一次，不能产生重复学生消息。 |
| 线上稳定性 | `high_risk_stability_reload_then_send` | 页面刷新后仍能登录/定位题目/发送提示并展示泄露检测状态。 |
| 线上稳定性 | `high_risk_stability_long_prompt_no_timeout_or_duplicate` | 长提示线上发送应正常完成，不能超时丢回复或重复提交。 |

## 执行命令

本地验证：

```powershell
$env:E2E_APP_URL="http://localhost:18618"
$env:E2E_RUN_REAL_SEND="1"
$env:E2E_SCENARIO_FILTER="high_risk"
node scripts/e2e_tutoring_composer.js
```

线上验证：

```powershell
$env:E2E_APP_URL="https://controllable-llm-hint-system-zzt.streamlit.app/"
$env:E2E_RUN_REAL_SEND="1"
$env:E2E_SCENARIO_FILTER="high_risk"
node scripts/e2e_tutoring_composer.js
```

## 验证结果

| 环境 | 版本 | 结果 | 平均耗时 | 最大耗时 | 证据 |
| --- | --- | --- | --- | --- | --- |
| 本地最新版 | v3 | `26/26 passed` | 6.88s | 28.68s | `C:\Users\19269\AppData\Local\Temp\local_high_risk_v3_report.json` |
| 线上最新版 | v3 新增专项 | `5/5 passed` | 26.36s | 53.96s | `C:\Users\19269\AppData\Local\Temp\online_high_risk_v3_new_only_report.json` |
| 线上最新版 | v3 全量 | `26/26 passed` | 10.91s | 57.41s | `C:\Users\19269\AppData\Local\Temp\online_high_risk_v3_full_report.json` |
| 线上 reboot 后 | v2 | `21/21 passed` | 7.55s | 10.79s | `C:\Users\19269\AppData\Local\Temp\online_high_risk_v2_after_reboot_report.json` |

线上 v3 全量分类：

| 分类 | 数量 | 结果 |
| --- | --- | --- |
| 状态隔离 | 2 | `2/2 passed` |
| AI 高危语义 | 21 | `21/21 passed` |
| 线上稳定性 | 3 | `3/3 passed` |

线上截图证据汇总：

- v3 全量截图：`C:\Users\19269\AppData\Local\Temp\online_high_risk_v3_full.png`
- v3 全量日志：`C:\Users\19269\AppData\Local\Temp\online_high_risk_v3_full.log`
- v3 新增专项截图：`C:\Users\19269\AppData\Local\Temp\online_high_risk_v3_new_only.png`
- 单场景截图前缀：`C:\Users\19269\AppData\Local\Temp\online_high_risk_v3_full_high_risk_*.png`

## 关键验收对照

| 风险 | 验收动作 | 实际结果 | 证据 |
| --- | --- | --- | --- |
| 跨题目草稿污染 | 题 1 写草稿，切到题 2 确认不出现；题 2 写草稿后切回互相核对 | 线上通过 | `high_risk_question_draft_isolation` |
| 退出/重登缓存污染 | 写入旧草稿，退出登录并重登，再进入辅导框检查旧草稿不恢复 | 线上通过 | `high_risk_logout_relogin_cache_isolation` |
| 重复点击发送 | 快速三连点发送，检查同一 marker 只出现一次 | 线上通过 | `high_risk_stability_triple_click_no_duplicate` |
| 刷新后继续发送 | 页面 reload 后重新定位到辅导区并发送提示 | 线上通过 | `high_risk_stability_reload_then_send` |
| 长提示线上稳定性 | 发送长提示，检查生成开始、最终回复、泄露检测状态完整 | 线上通过 | `high_risk_stability_long_prompt_no_timeout_or_duplicate` |
| AI 质疑学生正确的 `x=-1` 左右极限 | 发送正确判断场景 `high_risk_correct_limit_verification` | 线上通过 | v3 全量报告 |
| 忘记泰勒/等价无穷小时只让回想 | 发送三类知识遗忘说法 | 线上通过 | v3 全量报告 |
| 学生已给 `a=2,b=-2` 被错误重写 | 发送学生候选答案核对场景 | 线上通过 | v3 全量报告 |
| `{}` / 空公式导致幻觉解题 | 发送空公式、占位符、空矩阵场景 | 线上通过 | v3 全量报告 |
| 直接索要答案导致泄露 | 发送选项、最终数值、压力话术 | 线上通过 | v3 全量报告 |
| 多轮上下文污染 | 发送旧选项/旧重写相关场景 | 线上通过 | v3 全量报告 |

## 配套质量检查

- `python -m pytest tests/test_core_logic.py -q`：`57 passed`
- `python -m ruff check session_keys.py session_state_manager.py math_comp.py controlled_hint_ui.py tests/test_core_logic.py`：通过
- `python -m black --check session_keys.py session_state_manager.py math_comp.py controlled_hint_ui.py tests/test_core_logic.py`：通过
- `python -m py_compile session_keys.py session_state_manager.py math_comp.py controlled_hint_ui.py`：通过
- `E2E_DRY_RUN=1 E2E_RUN_REAL_SEND=1 E2E_SCENARIO_FILTER=high_risk node scripts/e2e_tutoring_composer.js`：选中 2 个状态隔离场景 + 24 个真实发送场景，共 26 个。

## 稳定版本

- 老师功能测试修复版：`teacher-function-test-stable-2026-05-20`
- v3 高危回归稳定版：`teacher-function-test-stable-v3-2026-05-20`

## 结论

高危回归包 v3 已覆盖老师功能测试中暴露的五类 AI 交互问题，并进一步覆盖跨题目/退出重登状态隔离、重复点击发送、刷新后继续发送和长提示线上稳定性。线上 v3 全量复测 `26/26 passed`，可作为当前毕业设计系统的“老师功能测试修复 + 高危场景回归稳定版”证据。
