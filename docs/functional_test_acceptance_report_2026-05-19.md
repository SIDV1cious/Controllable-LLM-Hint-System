# 《功能测试》智能辅导问题验收报告

验收日期：2026-05-19

来源文档：`D:/桌面/【功能测试】智能辅导测试.docx`

## 文档覆盖确认

- 已解析 Word 文档文字与图片资源：共 30 个文档块、12 张图片。
- 已逐张查看 `image1.png` 到 `image12.png`，包括文字抽取时容易漏掉的浮动截图 `image5.png`、`image6.png`、`image10.png`、`image11.png`。
- 图片临时提取目录：`C:\Users\19269\AppData\Local\Temp\codex_docx_function_test_assets`

## 验收结论

| 报告问题 | 验收动作 | 实际结果 | 证据 |
| --- | --- | --- | --- |
| 分式与连分式重复 | 源码搜索工具栏菜单，确认重复入口移除 | 通过：源码中未检出 `连分式`，保留 `分式` | `rg "连分式|cfrac" streamlit-component-x/.../MyComponent.tsx` 无重复入口 |
| 反常积分定义狭隘 | 源码搜索积分菜单，确认狭窄入口移除 | 通过：源码中未检出 `反常积分` | `rg "反常积分" streamlit-component-x/.../MyComponent.tsx` 无结果 |
| 二重/三重积分无法完整填写，缺多重积分 | 源码搜索模板，浏览器输入冒烟复测 | 通过：`二重积分`、`三重积分`、`四重积分`、`五重积分` 均包含逐层上下限与对应 `d变量`；`区域多重积分` 单独用于 `∫⋯∫_D` 区域写法 | `MyComponent.tsx:80-100`；`functional_acceptance_input_smoke_report_rerun.json` |
| 回复位置不统一，输入框应在底部 | 本地登录真实发送，截图复核回复在输入区上方 | 通过：生成回复、历史回复在上方；输入框在下方可见 | `C:\Users\19269\AppData\Local\Temp\functional_acceptance_real_send.png` |
| AI 质疑学生正确的 `x=-1` 左右极限 | AI 定向服务层测试 | 通过：回复明确“结论本身是正确的”，再引导检查函数值 | `functional_acceptance_ai_targeted_report_utf8.json` |
| 忘记泰勒/等价无穷小时不应只让回想 | AI 定向服务层测试；发现缺平方根公式后已补修并复测 | 通过：回复直接给出 `1-cos x`、`tan x`、`sqrt(1-x^2)-1` 等通用公式 | `controlled_generation_service.py:207`、`tests/test_core_logic.py:218`、AI 报告 JSON |
| 学生已给 `a=2,b=-2` 时不应被错误重写 | AI 定向服务层测试 | 通过：识别为学生已给候选，`rewrite_count=0`，未出现“常数项也必须为0”的错误指令 | `functional_acceptance_ai_targeted_report_utf8.json` |
| `{}` 空公式不应被幻觉成具体导数 | AI 定向服务层测试 | 通过：回复要求重新发送/补全公式，未幻觉 `f'(x)=1/sqrt(...)` | `functional_acceptance_ai_targeted_report_utf8.json` |
| 多轮聊天后页面无限向下堆叠 | 源码确认聊天区固定高度与旧消息折叠；真实发送截图复核 | 通过：聊天区高度 `440`，默认保留最近 4 条，旧消息进入折叠区 | `controlled_hint_ui.py:37-38`、`controlled_hint_ui.py:537-539` |
| 每轮后输入中断、需要再次点击 | 焦点专项 E2E | 通过：快速输入、Tab 失焦、点击外部后继续输入、文本+公式+尾部文本全部保留 | `functional_acceptance_focus_report.json` |

## 自动化结果

| 检查项 | 结果 | 备注 |
| --- | --- | --- |
| `python -m py_compile controlled_hint_ui.py controlled_generation_service.py leakage_detection_service.py llm_gateway.py tests/test_core_logic.py` | 通过 | 核心文件语法通过 |
| 产品代码范围 `ruff check` | 通过 | 对本次涉及的产品文件与测试文件执行 |
| 产品代码范围 `black --check` | 通过 | 对本次涉及的产品文件与测试文件执行 |
| `pytest -q` | 通过 | `49 passed` |
| `npm.cmd run build` | 通过 | 前端组件成功打包 |
| `input_smoke` | 通过 | 首轮出现 1 次可恢复时序失败；失败场景单跑通过，整组复跑 `12/12 passed` |
| 焦点专项 | 通过 | `4/4 passed` |
| 真实发送专项 | 通过 | `3/3 passed`，每条均有生成开始、最终回复、泄露状态 |
| AI 定向四场景 | 通过 | 补充平方根公式后 `4/4 passed` |
| 线上 `input_smoke` | 通过 | 部署后复测 `12/12 passed` |
| 线上焦点专项 | 通过 | 部署后复测 `4/4 passed` |
| 线上真实发送专项 | 通过 | 部署后复测 `3/3 passed` |

## 证据文件

- 输入冒烟复跑报告：`C:\Users\19269\AppData\Local\Temp\functional_acceptance_input_smoke_report_rerun.json`
- 焦点专项报告：`C:\Users\19269\AppData\Local\Temp\functional_acceptance_focus_report.json`
- 真实发送报告：`C:\Users\19269\AppData\Local\Temp\functional_acceptance_real_send_report.json`
- AI 定向报告：`C:\Users\19269\AppData\Local\Temp\functional_acceptance_ai_targeted_report_utf8.json`
- 真实发送截图：`C:\Users\19269\AppData\Local\Temp\functional_acceptance_real_send.png`
- 线上输入冒烟报告：`C:\Users\19269\AppData\Local\Temp\online_acceptance_input_smoke_report.json`
- 线上焦点专项报告：`C:\Users\19269\AppData\Local\Temp\online_acceptance_focus_report.json`
- 线上真实发送报告：`C:\Users\19269\AppData\Local\Temp\online_acceptance_real_send_report.json`

## 注意事项

- `ruff check .` 和 `black --check .` 扫全仓库时会进入 `论文临时文件归档/`，该归档目录内存在旧脚本、非 UTF-8 文件和 Python 3.12 f-string 语法，因此全仓库检查失败。这是归档资料目录问题，不是当前系统产品代码问题。
- 已推送到 GitHub `main` 并完成线上复测。线上地址 `https://controllable-llm-hint-system-zzt.streamlit.app/` 当前可访问，且输入冒烟、焦点专项、真实发送专项均通过。
- 本次本地 Streamlit 验收端口：`http://localhost:18618`。
