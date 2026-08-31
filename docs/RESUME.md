# 简历与面试表述

## 推荐简历版本

### 港股 IPO 投研 Multi-Agent 系统（Vibe Coding）｜独立开发

- **项目介绍：** 面向一级市场 IPO 投研场景，独立设计并开发港股招股书自动化尽调系统，实现 PDF 解析、财务取证、公司/行业/法律研究、风险复核及投委会报告生成的完整流程。
- **技术栈：** Python、LangGraph、Pydantic、PyMuPDF、pdfplumber、OpenPyXL、SQLite、Streamlit、Qwen3.5-4B、vLLM、Pytest。
- **个人工作：** 1）基于 LangGraph 编排 Research Manager、公司/财务/行业/法律 4 类 Expert Agents 及 Reviewer/Skeptic，通过 Evidence/Finding 契约实现结论到 PDF 页码与计算依据的追溯；2）在 **504 页**真实申请版本上重建 **13 张财务报表**、提取 **462 条财务事实**并计算 **32 项指标**，执行 **20 条财务法证规则**；3）建立 4 公司评测框架并验证 **141 项自动化测试**，人工核验案例实现 **8/8 核心指标、6/6 风险标签命中及 100% 证据页准确率**；4）完成离线与本地 Qwen3.5-4B 双链路运行，交付 Streamlit 工作台、Markdown、Excel、Evidence Ledger 与 Agent Trace；5）项目采用 Vibe Coding，由 Codex 辅助实现，本人负责需求、架构、金融规则、测试标准及结果验收。

## 一页简历精简版

如果版面只能放 3 条，建议保留：

- **架构与可信性：** 使用 LangGraph 编排 Research Manager、公司/财务/行业/法律 4 类 Expert Agents 及 Reviewer/Skeptic 复核闭环；以 Pydantic `Evidence / Finding / Challenge` 契约强制结论关联 PDF 页码、计算过程或真实 URL，缺证时显式降级。
- **真实端到端复现：** 在 504 页港股申请版本上跑通离线与本地 Qwen3.5-4B 双链路，提取 13 张报表、462 条财务事实、33 条模型附注及 32 项指标，执行 20 条财务法证规则并交付 Markdown、Excel、Evidence Ledger 与 Agent Trace。
- **工程质量与产品化：** 建立 4 公司评测框架并验证 141 项自动化测试；开发可加载真实产物的 Streamlit 投委会工作台，并实现 32K 上下文预检、分章节修订和复审不增分回滚机制。

## 30 秒面试介绍

传统 PDF Agent 通常是切块后直接总结，但 IPO 尽调最难的是数字不能算错、结论必须能回到原页，而且不同研究角色会产生冲突。我的系统把确定性财务计算与大模型研究分开：Python 负责三表、指标和风险规则，Agent 负责解释、跨来源验证和反方质疑；所有 Finding 必须引用 Evidence，最后输出可复核的报告、Excel 底稿和 Agent Trace。我用 504 页真实申请版本分别跑通离线与 Qwen3.5-4B 链路，并用人工标签和 141 项已验证测试验证核心能力。

## 面试时主动说明的边界

- 当前是 Engineering MVP，不替代投资、审计或法律判断。
- 量化成绩来自 1 个已人工核验的 development 案例，不表述为跨公司准确率。
- 另外 3 个案例已完成数据切分，但仍需补齐独立人工 gold labels。
- 扫描型 PDF、复杂跨页表格和外部法律数据仍可能需要人工复核。
