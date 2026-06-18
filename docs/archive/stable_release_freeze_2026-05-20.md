# 老师功能测试修复版冻结记录（2026-05-20）

## 冻结对象

- 线上地址：https://controllable-llm-hint-system-zzt.streamlit.app/
- 冻结标签：`teacher-function-test-stable-2026-05-20`
- 标签指向提交：`cdc182f Update online high-risk regression results`
- 冻结目的：保留一份已通过老师功能测试核心问题复核的稳定版本，后续继续扩展测试或改进策略时，可以清楚区分“已验收稳定版”和“继续演进版”。

## 冻结时已通过的核心验收

| 验收项 | 结果 |
| --- | --- |
| 老师文档中的提示词输入框问题 | 已修复并验收 |
| AI 交互五个核心高危问题 | 线上 `high_risk` 真实发送 `5/5 passed` |
| 输入框焦点与同步问题 | 线上专项 `16/16 passed` |
| 多轮聊天布局问题 | 已采用固定对话区、旧消息折叠和底部输入区 |
| GitHub 仓库状态 | `main` 与 `origin/main` 同步，论文资料类本地文件未纳入提交 |

## 使用方式

如需回到该稳定版本，可使用：

```powershell
git checkout teacher-function-test-stable-2026-05-20
```

如果只需要查看对应提交：

```powershell
git show teacher-function-test-stable-2026-05-20
```

## 后续策略

后续新增的高危场景回归包 v2、论文验收材料和进一步策略优化，属于稳定版之后的演进工作。若演进工作通过线上复核，可以再创建新的 v2 稳定标签。
