# IPO Financial Agent

面向港股 IPO 招股书的可追溯财务解析与分析项目。项目参考了用户提供的 `Financial-MCP-Agent` 中的 OpenAI-compatible 配置和 LangGraph 工作流思路，但将数据入口从股票 API 改造成招股书 PDF，并把“财务事实库”和“财务知识库”分开保存。

## 核心架构

```text
PDF
 └─ pages.json：每页 page + text + raw tables
        ├─ 原样财务报表抽取 → raw_statements.json / Excel主表
        └─ 第一次LLM任务：财务资料解析
                ├─ statement_facts
                └─ financial_notes
                        ↓
              Python指标 + 风险规则
                        ↓
              第二次LLM任务：财务分析
                        ↓
          Excel底稿 + Markdown报告 + SQLite
```

“调用一次财务解析模型”是一个逻辑阶段。招股书过长时，程序会按页分批调用同一套 Prompt，并自动合并去重。

## 当前功能

- PyMuPDF 提取逐页文本，pdfplumber 提取逐页原始表格；
- `pages.json` 保留整页内容，不提前强制拆分标题和段落；
- 自动定位综合财务状况表、损益表、现金流量表和权益变动表；
- 三大报表保持原始科目和原始行列，按表输出到 Excel；
- 每一行、每一条财务事实和每一条附注均保存 PDF 页码；
- 第一次大模型任务生成财务事实库与重点财务知识库；
- Python 计算增长率、毛利率、净利率、费用率、净现比、流动比率等；
- 规则引擎识别应收、存货、现金流、毛利率和偿债风险；
- 第二次大模型任务生成带页码引用的完整财务分析；
- LangGraph 串联流程，后续可增加公司、行业、估值、新闻和汇总 Agent；
- SQLite 保存文档、页面、原始报表、财务事实、附注、指标、风险和分析记录。

## 重点财务资料范围

包含但不限于：货币资金、存货、应收账款、其他应收款、固定资产、使用权资产、短期贷款/借款、长期借款、合同负债、应付账款、其他应付款、管理费用、研发费用、销售费用、财务费用、财务预测、毛利、毛利率、净利润、流动负债、应收票据和递延收益。

## 安装

建议 Python 3.10–3.12。

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -e .
```
本地 qwen3-0.6b vLLM 服务推荐命令：

```bash
vllm serve Qwen/Qwen3-0.6B \
  --host 0.0.0.0 \
  --port 8000 \
  --served-model-name qwen3-0.6b \
  --api-key localtestkey \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.70 \
  --reasoning-parser qwen3 \
  --default-chat-template-kwargs '{"enable_thinking": false}'
```

`vllm serve` 本身就是 OpenAI 兼容服务，不需要 `--openai` 参数。模型名称或模型路径直接放在 `serve` 后面。
配置大模型：

```bash
copy .env.example .env
```

`.env`：

```env
OPENAI_COMPATIBLE_API_KEY=localtestkey
OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:8000/v1
OPENAI_COMPATIBLE_MODEL=qwen3-0.6b

LLM_TEMPERATURE=0.3
LLM_TIMEOUT_SECONDS=300
LLM_MAX_RETRIES=2
PARSE_CHUNK_MAX_CHARS=12000
PARSE_CHUNK_OVERLAP_PAGES=1
CANDIDATE_CONTEXT_PAGES=1
```

本地 vLLM（Qwen3-0.6B）推荐在 Linux/WSL2 中运行。Windows Python 可以访问 WSL 中的 `8000` 端口，但 vLLM 服务端需在 Linux 里启动。

支持 OpenAI 兼容接口。`BASE_URL` 为空时使用 OpenAI 默认地址。

## 运行

完整两阶段大模型流程：

```bash
python main.py --pdf "data/uploads/招股书.pdf" --company "某公司" --llm-mode on
```

自动模式，有模型配置就调用，没有则只做离线抽取：

```bash
python main.py --pdf "data/uploads/招股书.pdf" --company "某公司" --llm-mode auto
```

不调用大模型：

```bash
python main.py --pdf "data/uploads/招股书.pdf" --company "某公司" --llm-mode off
```

## 输出

```text
data/extracted/<document_id>/
├── pages.json
├── raw_statements.json
├── financial_kb.json
├── metrics.json
├── risk_findings.json
└── run_summary.json

data/output/
├── <document_id>_financial_workbook.xlsx
└── <document_id>_financial_report.md

data/db/
└── ipo_financial_agent.sqlite3
```

Excel 包含：

- 目录；
- 原样财务报表，每张表独立 Sheet；
- 财务事实明细；
- 重点财务资料；
- 财务指标；
- 风险事项；
- 证据索引。

## 数据可信度设计

- `pages.json` 是唯一原始中间底稿；
- 三大报表展示层不修改原始科目；
- `canonical_tag` 仅用于计算，不替换原文；
- 页码从 PDF 物理页码直接读取，从 1 开始；
- LLM 输出中的页码必须属于当前输入页，否则程序会丢弃该记录；
- 指标由 Python 计算，不让模型自行运算；
- 规则命中只是分析线索，不直接当成确定性风险；
- 无 LLM 模式的事实候选置信度较低，不建议直接用于正式报告。

## 后续扩展 Agent

在 `src/ipo_financial_agent/agents/` 中增加新的 Agent，并在 `workflow/graph.py` 注册节点即可。推荐顺序：

1. Company Agent：公司、股权、管理层、子公司；
2. Business Agent：业务结构、产品、客户、供应商；
3. Industry Agent：行业空间、竞争格局、政策；
4. Market Agent：上市后股价、估值、异常波动；
5. News/Risk Agent：舆情和上市后风险预警；
6. Summary Agent：跨模块汇总与冲突校验。

## 已知边界

- 扫描版 PDF 需要先 OCR；
- pdfplumber 对无框表、复杂合并单元格和多栏排版可能错位；
- 大模型解析是高质量候选抽取，不是审计意见；
- 合并范围变化、收购子公司、非完整期间和单位变化必须人工复核；
- 生产环境应增加人工审核、版本修订、数据勾稽和模型评测集。
