# HK IPO Intelligence Platform — Java V0.1

这是现有 Python `IPO Research Agent` 的 Java 服务化演进版本，不是另一个无关项目。

当前纵向切片：

```text
Structured Financial Facts
        -> Spring Boot Job API
        -> Deterministic Metric Engine
        -> Explainable Risk Rule Engine
        -> Evidence-aware Finding + Agent Trace
```

## 当前能力

- `POST /api/v1/ipo/jobs`：提交结构化财务事实并执行分析。
- `GET /api/v1/ipo/jobs/{jobId}`：读取状态、指标、风险观察和执行轨迹。
- `POST /api/v1/ipo/jobs/from-parser`：从现有 Python Parser 获取已核实事实后执行工作流。
- 首批迁移毛利率、净利率、净现比、流动比率、资产负债率和增长率计算。
- 首批迁移应收/存货增速背离、弱现金转化、低流动比率、高负债率和毛利率连续下降规则。
- 规则命中保持为 `observation`，不直接冒充投资结论。
- `JUnit 5 + MockMvc` 覆盖领域计算、风险规则及 REST 链路。
- GitHub Actions 使用 Temurin JDK 17 自动编译并运行 Java 测试。
- `ResearchTask` 显式记录依赖、状态、attempt 与 parent challenge，形成可审计任务 DAG。
- `InvestmentReviewGate` 将中高等级规则观察转成正式 Challenge，并限制最多一次 Replan。
- 补证能力未连接时使用 `UNABLE_TO_VERIFY`，不让模型或工作流自动补写结论。
- 接入 Spring AI Alibaba `1.1.2.2`；模型Planner通过配置开关启用，异常或非法JSON自动回退确定性Planner。

## 运行

需要 JDK 17+ 与 Maven 3.9+：

```bash
mvn test
mvn spring-boot:run
```

Python Parser 服务使用独立可选依赖启动：

```bash
pip install -e ".[api]"
uvicorn ipo_financial_agent.interop.parser_api:app --host 0.0.0.0 --port 8090
```

Parser只输出 `verified_fact_manifest.json` 明确列出的事实；没有人工/规则核实清单时返回错误，
不会在重复的发行人、母公司、子公司或现金流调整项目之间自行猜测。

模型Planner默认关闭。项目已内置 OpenAI-compatible `ChatModel` 自动配置，可连接
vLLM、Xinference、兼容网关或其他提供 `/v1/chat/completions` 的 Qwen 服务：

```bash
IPO_CHAT_MODEL=openai
IPO_LLM_PLANNER_ENABLED=true
IPO_LLM_BASE_URL=http://127.0.0.1:8000
OPENAI_COMPATIBLE_API_KEY=localtestkey
OPENAI_COMPATIBLE_MODEL=qwen3.5-4b
```

`IPO_LLM_BASE_URL` 填服务根地址，不追加 `/v1`；Python 侧仍使用带 `/v1` 的
`OPENAI_COMPATIBLE_BASE_URL`，避免 Spring AI 重复拼接路径。
两个开关必须同时启用：前者创建 `ChatModel`，后者才允许 Planner 调用模型。默认均关闭，
因此本地测试和规则分析不依赖模型服务，也不会产生意外调用。

模型只能从Reviewer生成的候选Challenge中选择最多3项补证任务；不能新增财务数字、
不能绕过确定性指标与风险规则。调用或JSON解析失败时自动回退固定Planner。

## 演进路线

1. ✅ 引入共享 JSON Schema 与 Python/Java parity tests。
2. 将内存任务存储替换为 MySQL，并增加异步队列、重试和幂等。
3. ✅ 定义 `ProspectusParserClient` HTTP 边界、响应校验与失败映射；待接通 Python 服务。
4. ✅ 已完成框架无关的 Planner、任务 DAG、Reviewer Challenge 与一次受限 Replan，并接入可关闭的 Spring AI Alibaba 模型Planner适配器。
5. 增加 Web Console、SSE 执行进度、Docker Compose 与 CI。

## 参考而非复制

- TradingAgents：并行专业研究与统一风险复核。
- Spring AI Alibaba / DataAgent：有状态工作流、重试、HITL 与可观测性。
- Azure Java Banking Assistant：Supervisor 与领域工具边界。
- FinRobot：确定性程序负责数字，模型负责解释，Agent 负责编排。

业务代码基于本项目原有 Python 指标与规则语义重构；未复制上述仓库源文件。

共享请求契约和首个经核实案例位于 `../contracts/`。Python 与 Java 测试读取同一份
Hosonsoft fixture，用于发现跨语言迁移、主体口径和规则阈值漂移。
