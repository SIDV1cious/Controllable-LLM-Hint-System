# 基于LLM的可控解题提示生成系统

本项目是毕业设计“基于LLM的可控解题提示生成系统研究”的原型系统。系统面向数学与编程类课程的智能辅导场景，核心目标是在保持提示启发性和教学价值的同时，降低大语言模型在解题提示中泄露最终答案、关键数值或完整解法的风险。

## 核心能力

- 学生端：登录注册、课程测验、自动判题、错题回顾、智能辅导、个人学情报告。
- 管理端：登录日志、学习时长统计、正确率分析、实验分析看板、AI辅导记录抽查、课程题库管理、Prompt热更新。
- 可控生成：私有提示计划、受控提示生成、答案泄露检测、自动重写、泄露指标记录与可视化。
- 数学输入：通过 Streamlit 自定义组件接入 MathLive，支持 LaTeX 公式输入。

## 可控提示生成链路

当前系统将智能辅导从“直接生成回复”升级为四阶段链路：

1. 私有提示计划：模型基于题目、学生答案、标准答案和解析生成不会展示给学生的安全提示计划。
2. 学生提示生成：学生可见模型只接收题目、学生答案、判题结果、学生请求和安全提示计划。
3. 泄露检测：检测候选提示是否泄露最终答案、选项、关键数值、关键中间结论或完整解法。
4. 自动重写：若检测到泄露，系统最多重写两次，并将最终结果与泄露评分写入交互日志。

这一链路对应论文中的“推理阶段内容约束与动态重写策略”，可用于支撑定量指标，如答案泄露率、重写次数、提示质量抽查结果等。

## 项目结构

```text
.
├── app.py                         # Streamlit 部署入口
├── controlled_hint_system_app.py   # 系统主流程与页面路由入口
├── app_constants.py                # 页面模式、用户角色、交互标记等全局常量
├── app_errors.py                   # 异常日志与用户友好错误提示
├── ui_feedback.py                  # Streamlit 成功、失败、警告反馈封装
├── session_keys.py                 # Streamlit session_state key 与动态组件 key
├── ui_texts.py                     # 智能辅导按钮、提示强度和用户可见文案
├── hint_policy.py                  # 提示强度策略、重写次数和安全兜底策略
├── hint_system_core.py            # 兼容旧调用的核心服务门面
├── system_config.py               # 环境变量、系统配置与时区工具
├── database_service.py            # 数据库连接、题目转换与日志字段兼容迁移
├── user_repository.py             # 用户账号、登录日志与未完成测验状态的数据访问层
├── question_repository.py         # 题目读取与公开题号/数据库题号转换的数据访问层
├── course_repository.py           # 课程目录合并与课程读取的数据访问层
├── admin_content_repository.py    # 管理端课程与题库增删改查数据访问层
├── admin_observability_repository.py # 管理端看板、日志与监控数据访问层
├── interaction_repository.py      # 智能辅导交互日志与泄露观测字段写入
├── prompt_config_repository.py    # 系统 Prompt 配置读取与热更新数据访问层
├── study_session_repository.py    # 学习会话开始、结束与学习时长记录
├── student_report_repository.py   # 学生报告所需学习时长、答题日志与错题详情读取
├── llm_gateway.py                 # 大模型客户端与通用调用网关
├── assessment_logic.py            # 选择题确定性判题与 LLM 判题 Prompt 构造
├── automated_assessment_service.py # 自动判题服务
├── leakage_detection_service.py    # 答案泄露检测服务
├── controlled_generation_service.py # 受控提示计划、生成与自动重写服务
├── hint_text_utils.py             # LaTeX 文本规范化与 JSON 解析工具
├── result_export_service.py       # 测验结果导出服务
├── student_report_service.py      # 学生报告统计指标与错题提取纯逻辑
├── session_state_manager.py       # Streamlit 会话状态初始化、跳转与测验状态管理
├── learning_session_service.py     # 学习会话、登录注册、抽题与交互记录服务
├── experiment_analytics_service.py # 提示强度、教学意图与泄露指标统计服务
├── admin_console_ui.py            # 管理端控制台路由
├── admin_dashboard_ui.py          # 管理端学情可视化大屏
├── admin_monitoring_ui.py         # 登录、学习时长与交互监控页面
├── admin_course_management_ui.py  # 课程与题库管理页面
├── admin_prompt_ui.py             # Prompt 热更新页面
├── sidebar_navigation.py          # 登录后侧边栏导航
├── student_report_ui.py           # 学生个人学情与错题报告
├── learning_platform_ui.py        # 登录注册、课程入口与平台通用视觉主题
├── assessment_ui.py               # 课程评测流程、阅卷页与结果仪表盘
├── controlled_hint_ui.py          # 受控解题提示面板、快捷请求与公式输入
├── experiment_admin_ui.py          # 管理端实验分析看板与数据导出
├── prompts.py                     # 判题、提示计划、泄露检测、重写等 Prompt
├── math_comp.py                   # MathLive 公式输入组件封装
├── questions.py                   # 离线备用题库，4类课程共240题
├── reset_db.py                    # 导入带答案解析的选择题数据
├── check_db.py                    # 数据库连接检查
├── 选择题_with_solutions.json       # 47道带标准答案和解析的选择题
├── requirements.txt               # Python依赖
├── requirements-dev.txt           # 本地测试、格式化与静态检查依赖
├── pyproject.toml                  # Ruff、Black 等代码质量工具配置
├── .github/workflows/              # GitHub Actions 自动质量检查
├── docs/
│   ├── database_schema.sql         # MySQL建表脚本
│   ├── migrations/                 # 数据库增量迁移脚本与执行说明
│   ├── system_design.md            # 系统设计与研究链路说明
│   └── experiment_plan.md          # 实验设计与答辩指标建议
├── tests/                          # 核心纯逻辑单元测试
└── streamlit-component-x/          # MathLive 自定义组件
```

## 快速运行

1. 安装依赖：

```powershell
pip install -r requirements.txt
```

如果需要在本地运行代码质量检查和单元测试，可额外安装开发依赖：

```powershell
pip install -r requirements-dev.txt
ruff check .
black --check .
pytest -q
```

2. 准备 MySQL 数据库，并执行：

```powershell
mysql -u <user> -p < docs/database_schema.sql
```

3. 配置环境变量，可参考 `.env.example`：

```text
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=llm_project
LLM_API_KEY=your_api_key
LLM_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=45
LLM_MAX_RETRIES=2
ASSESS_CONCURRENCY=5
QUIZ_SIZE=10
MY_ID=your_student_id
```

4. 导入题库：

```powershell
python reset_db.py
```

5. 启动系统：

```powershell
streamlit run app.py
```

## 智能辅导输入框 E2E 测试

智能辅导提示词输入框支持独立浏览器端测试脚本，适合每次改动公式输入、矩阵、发送链路后做回归验证：

```powershell
$env:E2E_APP_URL="http://localhost:8517"
$env:E2E_STUDENT_USERNAME="3021244094"
$env:E2E_STUDENT_PASSWORD="3021244094"
$env:E2E_SCENARIO_FILTER="input_smoke"
$env:E2E_RUN_REAL_SEND="0"
node scripts/e2e_tutoring_composer.js
```

也可以使用封装好的本地 smoke 脚本：

```powershell
$env:E2E_STUDENT_USERNAME="3021244094"
$env:E2E_STUDENT_PASSWORD="3021244094"
.\scripts\run_tutoring_composer_smoke.ps1 -AppUrl "http://localhost:8517"
```

常用环境变量：

- `E2E_SCENARIO_FILTER`：按场景 ID 或类型筛选测试；`input_smoke` 表示运行中文输入、回车、删除、粘贴、公式、矩阵、分段函数等输入框防回归场景；留空表示跑全部非真实发送场景。
- `E2E_RUN_REAL_SEND=1`：额外执行一次真实发送 smoke，请谨慎用于线上环境。
- `E2E_REPORT_PATH` / `E2E_SCREENSHOT_PATH`：指定 JSON 报告和截图输出位置。

GitHub Actions 中的 `Tutoring Composer E2E` 工作流为手动触发，默认 `E2E_RUN_REAL_SEND=0`，只做线上输入框防回归 smoke，不触发真实 LLM 生成。运行前需要在仓库 Secrets 中配置 `E2E_STUDENT_USERNAME` 和 `E2E_STUDENT_PASSWORD`。
