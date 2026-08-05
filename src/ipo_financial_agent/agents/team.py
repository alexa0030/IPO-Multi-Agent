"""Public manifest for the IPO due-diligence virtual investment team."""

from __future__ import annotations

from typing import TypedDict


class AgentSpec(TypedDict):
    name: str
    role: str
    stage: str
    tools: list[str]
    output: str


AGENT_TEAM: list[AgentSpec] = [
    {
        "name": "ResearchManager",
        "role": "尽调负责人：拆解任务并提出公司特定假设",
        "stage": "plan",
        "tools": ["document summary", "research plan"],
        "output": "ResearchPlan",
    },
    {
        "name": "CompanyBusinessAgent",
        "role": "公司分析师：股权、产品、商业模式、客户供应商与管理层",
        "stage": "parallel_research",
        "tools": ["prospectus retrieval", "entity extraction", "Qwen"],
        "output": "ProspectusAnalysis",
    },
    {
        "name": "FinancialAgent",
        "role": "财务分析师：报表抽取、指标计算、异常解释与财务取证",
        "stage": "parallel_research",
        "tools": ["table extraction", "Python metrics", "forensic rules", "Qwen"],
        "output": "FinancialAnalysis",
    },
    {
        "name": "IndustryAgent",
        "role": "行业分析师：行业空间、竞争格局、上下游与持续增长",
        "stage": "parallel_research",
        "tools": ["prospectus retrieval", "optional web search", "Qwen"],
        "output": "IndustryAnalysis",
    },
    {
        "name": "LegalGovernanceAgent",
        "role": "风控分析师：关联交易、诉讼处罚、实控人与治理风险",
        "stage": "parallel_research",
        "tools": ["risk section retrieval", "optional web search"],
        "output": "LegalGovernanceAnalysis",
    },
    {
        "name": "RiskReviewer+Skeptic",
        "role": "反方研究员：跨 Agent 对照、发现矛盾并发起一轮补证",
        "stage": "debate_review",
        "tools": ["research ledger", "challenge router", "Qwen"],
        "output": "RiskReview + Challenges",
    },
    {
        "name": "DueDiligenceLead",
        "role": "投资经理：综合回答历史有无钱、未来会不会有钱及重大风险",
        "stage": "decision",
        "tools": ["validated findings", "risk matrix"],
        "output": "DueDiligenceConclusion",
    },
    {
        "name": "ReportWriter",
        "role": "报告撰写人：将专业 Agent 产物组织成完整 Markdown 尽调报告",
        "stage": "writing",
        "tools": ["research ledger", "deterministic assembly", "optional Qwen polish"],
        "output": "Markdown report",
    },
    {
        "name": "EvidenceComplianceReviewer",
        "role": "终审：检查必备章节、引用、越界建议和无依据结论",
        "stage": "final_review",
        "tools": ["citation audit", "scope audit", "Qwen"],
        "output": "ReportReview",
    },
]
