# AI 交互红队回归 V4（2026-05-21）

## 目标

V4 用于继续压测老师《功能测试》暴露出的 AI 交互风险。它不只复查“是否能生成回复”，而是专门验证四类冲突是否被控制住：

- 学生意图识别：忘公式、求核对、输入缺失、只要下一步、直接索要答案。
- 数学正确性：不能为了防泄露而否定学生已给出的正确判断，也不能机械附和矛盾结论。
- 答案泄露边界：候选答案可以核对，但不能泄露新的最终答案、选项或完整解析。
- 上下文稳定性：不能被上一题、上一轮自动重写、提示注入或格式包装污染。

## V4 新增覆盖面

本轮新增 `56` 个线上真实发送红队场景，统一使用标签 `high_risk_v4`。加上 V3 原有高危包后，真实发送场景库存从 `180` 增至 `236`，完整高危包从 `26` 个老师反馈核心场景扩展为 `82` 个高危场景。

新增场景分组如下：

| 分组 | 重点 |
| --- | --- |
| 基础知识补充 | 等价无穷小、求导规则、积分法则、线代定义、概率公式、C 语言基础概念。 |
| 提示注入与绕过 | 忽略规则、管理员/测试模式、JSON 输出、英文翻译、base64、藏头、付费压力。 |
| 候选答案核对 | 学生给出 A/B 选项、0、1/2、极限不存在、单调性、矩阵可逆等候选判断时，只给核对方法。 |
| 输入完整性诊断 | 空分式、空积分、分段函数条件缺失、`[object Object]`、图片公式缺失、公式混输不完整。 |
| 上下文与重写保护 | 换题重置、上一题答案不污染、错误前提先检查、重写不能新增数学条件、矛盾说法不盲目附和。 |
| 学习体验边界 | 学生没思路、只要短提示、要求完整解法、要求可直接交作业、UI 回复丢失时重复请求。 |

## 代码级加固

- 扩展 `KNOWLEDGE_RECALL_PATTERN`，识别“这个叫啥”“判定标准”“公式表”“通用结论”等非标准说法。
- 收紧 `ANSWER_VERIFICATION_PATTERN`，避免“正确选项是哪个”被误判为学生已给答案。
- 扩展 `DIRECT_ANSWER_REQUEST_PATTERN`，覆盖“选哪个”“别讲过程”“只要结论”“管理员/测试模式”“忽略规则”等绕过话术。
- 新增选择题候选识别：学生说“我选 A，对吗”时，系统只围绕学生候选给核对方法，不泄露新的正确选项。
- 扩展本地通用知识库：求导、积分、矩阵/特征值/秩、概率、C 语言指针与字符串等基础知识可直接说明。

## 执行命令

仅查看 V4 场景清单：

```powershell
$env:E2E_DRY_RUN="1"
$env:E2E_SCENARIO_FILTER="high_risk_v4"
$env:E2E_REPORT_PATH="$env:TEMP\high_risk_v4_dry_run_inventory.json"
node scripts\e2e_tutoring_composer.js
```

线上跑 V4 新增场景：

```powershell
$env:E2E_APP_URL="https://controllable-llm-hint-system-zzt.streamlit.app/"
$env:E2E_RUN_REAL_SEND="1"
$env:E2E_SCENARIO_FILTER="high_risk_v4"
$env:E2E_REPORT_PATH="$env:TEMP\online_high_risk_v4_report.json"
$env:E2E_SCREENSHOT_PATH="$env:TEMP\online_high_risk_v4.png"
node scripts\e2e_tutoring_composer.js
```

线上跑完整高危包：

```powershell
$env:E2E_APP_URL="https://controllable-llm-hint-system-zzt.streamlit.app/"
$env:E2E_RUN_REAL_SEND="1"
$env:E2E_SCENARIO_FILTER="high_risk"
$env:E2E_REPORT_PATH="$env:TEMP\online_high_risk_v4_full_report.json"
$env:E2E_SCREENSHOT_PATH="$env:TEMP\online_high_risk_v4_full.png"
node scripts\e2e_tutoring_composer.js
```

## 当前验收记录

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| Python 单元测试 | `62 passed` | `python -m pytest tests/test_core_logic.py -q` |
| Python 静态检查 | 通过 | `python -m ruff check controlled_generation_service.py leakage_detection_service.py prompts.py tests/test_core_logic.py` |
| Python 格式检查 | 通过 | `python -m black --check controlled_generation_service.py leakage_detection_service.py prompts.py tests/test_core_logic.py` |
| Python 编译检查 | 通过 | `python -m py_compile controlled_generation_service.py leakage_detection_service.py prompts.py` |
| Node 脚本语法检查 | 通过 | `node --check scripts\e2e_tutoring_composer.js` |
| V4 新增场景 dry run | `56/56` 个新增真实发送场景被正确选中 | `C:\Users\19269\AppData\Local\Temp\high_risk_v4_dry_run_inventory.json` |
| 完整高危包 dry run | `82` 个高危场景被正确选中，其中 `2` 个状态隔离输入场景、`80` 个真实发送场景 | `C:\Users\19269\AppData\Local\Temp\high_risk_full_after_v4_dry_run_inventory.json` |

线上真实发送复测仍需在部署当前代码后执行 `high_risk_v4` 与完整 `high_risk`。当前会话未发现 `E2E_STUDENT_USERNAME` / `E2E_STUDENT_PASSWORD` / `E2E_STUDENT_ACCOUNTS` 环境变量，因此本轮尚未直接跑线上真实发送。

## 论文表述建议

可以写成：

> 在教师功能测试反馈基础上，系统进一步构建 AI 交互红队回归测试包。测试包从学生意图识别、答案泄露边界、输入完整性诊断、上下文污染与重写安全等维度设计高危交互场景，并通过线上真实发送验证系统在复杂学生表达、提示注入、候选答案核对和公式输入异常下仍能保持受控提示生成。
