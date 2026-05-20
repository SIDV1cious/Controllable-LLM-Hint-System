# 老师功能测试高危回归 v3 稳定版冻结记录（2026-05-20）

## 冻结对象

- 线上地址：https://controllable-llm-hint-system-zzt.streamlit.app/
- 冻结标签：`teacher-function-test-stable-v3-2026-05-20`
- 冻结目的：保留一份已通过老师功能测试修复、AI 高危语义回归、状态隔离专项和线上稳定性专项的版本，作为毕业设计系统当前推荐稳定基线。

## v3 相比 v2 的新增内容

| 方向 | 新增验证 |
| --- | --- |
| 跨题目状态隔离 | 题 1 草稿不能泄漏到题 2；题 2 草稿也不能覆盖题 1。 |
| 退出/重登缓存隔离 | 公式输入框 localStorage 增加登录会话命名空间，退出重登后不恢复旧草稿。 |
| 重复提交防护 | 快速三连点发送同一请求时，同一 marker 只能出现一次。 |
| 刷新后稳定性 | 页面刷新后仍能重新进入测验结果页、定位辅导区并发送请求。 |
| 长提示稳定性 | 长文本提示在线上能完成生成并展示泄露检测状态。 |

## 验收结果

| 环境 | 结果 | 平均耗时 | 最大耗时 | 证据 |
| --- | --- | --- | --- | --- |
| 本地 v3 全量 | `26/26 passed` | 6.88s | 28.68s | `C:\Users\19269\AppData\Local\Temp\local_high_risk_v3_report.json` |
| 线上 v3 新增专项 | `5/5 passed` | 26.36s | 53.96s | `C:\Users\19269\AppData\Local\Temp\online_high_risk_v3_new_only_report.json` |
| 线上 v3 全量 | `26/26 passed` | 10.91s | 57.41s | `C:\Users\19269\AppData\Local\Temp\online_high_risk_v3_full_report.json` |

## 配套检查

- `python -m pytest tests/test_core_logic.py -q`：`57 passed`
- `python -m ruff check session_keys.py session_state_manager.py math_comp.py controlled_hint_ui.py tests/test_core_logic.py`：通过
- `python -m black --check session_keys.py session_state_manager.py math_comp.py controlled_hint_ui.py tests/test_core_logic.py`：通过
- `python -m py_compile session_keys.py session_state_manager.py math_comp.py controlled_hint_ui.py`：通过

## 使用方式

查看 v3 稳定版：

```powershell
git show teacher-function-test-stable-v3-2026-05-20
```

回到 v3 稳定版：

```powershell
git checkout teacher-function-test-stable-v3-2026-05-20
```

后续如果继续改 AI 生成、公式输入框、登录状态或部署稳定性，必须重新运行：

```powershell
$env:E2E_RUN_REAL_SEND="1"
$env:E2E_SCENARIO_FILTER="high_risk"
node scripts/e2e_tutoring_composer.js
```

目标结果仍应为 `26/26 passed`。
