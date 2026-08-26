# 简历与面试表述

## 推荐项目名

**港股 IPO Evidence-grounded Multi-Agent 尽调平台（AI-assisted / Vibe Coding）** ｜ 独立项目

## 简历版本（推荐）

- **业务闭环：** 面向一级市场投研场景，独立设计港股 IPO 自动化尽调平台，使用 LangGraph 编排 Research Manager 与公司、财务、行业、法律 4 类 Expert Agents，经 Risk Reviewer、Skeptic 和 Final Reviewer 完成从招股书解析到投委会报告交付的闭环。
- **可信架构：** 将 PDF 原表、标准化财务事实、确定性指标与模型结论分层，通过 Pydantic `Evidence / Finding / Challenge` 契约建立可审计证据账本；所有 Finding 强制引用页码、计算过程或已登记 URL，缺证时显式降级，降低数字幻觉与悬空引用风险。
- **财务能力：** 在 504 页真实港股申请版本上完成端到端回归，提取 13 张报表、468 条财务事实并计算收入、毛利率、现金转化等 29 项指标，配置 20 条财务法证规则；交付 Markdown 报告、Excel 底稿、Evidence Ledger、Agent Trace 与 SQLite 审计数据。
- **质量验证：** 建立 4 公司版本化评测框架与 135 项自动化测试，覆盖财务抽取、证据完整性、搜索降级、跨 Agent 合约、Reviewer/Skeptic 补证闭环及多格式交付；当前 1 个案例具备人工 gold labels，其余案例按 validation/test 切分待独立标注。

**开发方式：** 采用 AI-assisted / Vibe Coding 工作流，使用 Codex 辅助代码生成、重构与文档协作；本人负责需求拆解、架构设计、金融规则、测试标准、结果复核和版本验收。

> 数字只描述当前仓库与单一已人工核验回归案例，不应表述为跨公司准确率。其余三个案例仍需补充人工 gold labels 后，才适合对外发布泛化指标。

## 30 秒项目介绍

传统 PDF Agent 往往把招股书切块后直接总结，但尽调最难的是数字不能算错、结论必须能回页码、不同研究员的判断还会冲突。我做的系统把确定性财务计算和大模型研究分开：代码负责三表、指标和规则，Agent 负责解释与跨来源验证；所有 Finding 必须引用 Evidence，Skeptic 只针对重大缺口触发一轮补证，最后输出可复核的报告和 Excel 底稿。

## 面试时主动说明的边界

- 当前是 Engineering MVP，不替代投资、审计或法律判断。
- 已人工标注并可量化评分的是 1 个开发回归案例；另外 3 个案例已完成清单与数据切分，但 gold labels 尚未补齐。
- 扫描型 PDF、复杂跨页表格和外部网页访问仍可能需要人工复核。
