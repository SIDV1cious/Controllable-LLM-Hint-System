# 基于LLM的可控解题提示生成系统

本项目是毕业设计“基于LLM的可控解题提示生成系统研究”的原型系统。系统面向数学与编程类课程的智能辅导场景，核心目标是在保持提示启发性和教学价值的同时，降低大语言模型在解题提示中泄露最终答案、关键数值或完整解法的风险。

## 核心能力

- 学生端：登录注册、课程测验、自动判题、错题回顾、智能辅导、个人学情报告。
- 管理端：登录日志、学习时长统计、正确率分析、AI辅导记录抽查、课程题库管理、Prompt热更新。
- 可控生成：私有提示计划、受控提示生成、答案泄露检测、自动重写、泄露指标记录与可视化。
- 数学输入：通过 Streamlit 自定义组件接入 MathLive，支持 LaTeX 公式输入。

## 工程优化亮点

- 稳定性：DeepSeek 调用统一设置超时、重试、模型名和并发参数，避免阅卷或辅导时长时间卡死。
- 运行速度：课程抽题不再使用数据库 `ORDER BY RAND()`，改为先查询题目 ID 后在应用层随机抽样，更适合题库扩容。
- 可维护性：泄露检测相关数据库字段只在进程内自检一次，减少每次辅导记录写入时的重复 DDL 开销。
- 使用体验：结果页默认定位到第一道错题，展示本次正确率，并支持导出本次测验结果 Markdown。
- 答辩展示：管理端保留泄露率、重写次数、泄露评分等指标，可直接支撑“可控生成闭环”的实验展示。

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
├── app.py                         # Streamlit 主应用
├── prompts.py                     # 判题、提示计划、泄露检测、重写等 Prompt
├── math_comp.py                   # MathLive 公式输入组件封装
├── questions.py                   # 离线备用题库，4类课程共240题
├── reset_db.py                    # 导入带答案解析的选择题数据
├── check_db.py                    # 数据库连接检查
├── 选择题_with_solutions.json       # 47道带标准答案和解析的选择题
├── requirements.txt               # Python依赖
├── docs/
│   ├── database_schema.sql         # MySQL建表脚本
│   ├── system_design.md            # 系统设计与研究链路说明
│   └── experiment_plan.md          # 实验设计与答辩指标建议
└── streamlit-component-x/          # MathLive 自定义组件
```

## 快速运行

1. 安装依赖：

```powershell
pip install -r requirements.txt
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
MY_ID=your_student_id
```

可选运行参数：

```text
LLM_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=45
LLM_MAX_RETRIES=2
ASSESS_CONCURRENCY=5
QUIZ_SIZE=10
MAX_REWRITE_ATTEMPTS=2
```

4. 导入题库：

```powershell
python reset_db.py
```

5. 启动系统：

```powershell
streamlit run app.py
```

## 公式组件开发

普通运行系统时不需要重新构建前端组件，仓库已保留 `streamlit-component-x/streamlit_component_x/frontend/build`。如果修改了公式输入组件源码，再执行：

```powershell
cd streamlit-component-x/streamlit_component_x/frontend
npm install
npm run build
```
