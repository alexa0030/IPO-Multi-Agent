"""Mainline A research manager for company due diligence planning."""

from __future__ import annotations

import re
import json
from typing import Any, ClassVar

from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.llm.prompts_agents import RESEARCH_MANAGER_SYSTEM_PROMPT
from ipo_financial_agent.models_agent import ResearchPlan, ResearchTask
from ipo_financial_agent.schemas import (
    ResearchQuestion as ContractResearchQuestion,
    ResearchTask as ContractResearchTask,
)


class ResearchManagerAgent:
    """Assign bounded evidence questions to four specialist roles."""

    ALLOWED_AGENTS: ClassVar[set[str]] = {
        "company_business",
        "financial_dd",
        "industry_competition",
        "legal_governance",
    }

    def __init__(self, client: OpenAICompatibleClient | None = None) -> None:
        self.client = client

    def plan(
        self,
        *,
        company: str,
        document_summary: dict[str, Any],
    ) -> ResearchPlan:
        if self.client is None:
            return self._default_plan(company, document_summary)
        return self._plan_with_llm(company, document_summary)

    @staticmethod
    def plan_financial_task(company: str) -> ContractResearchTask:
        """Phase-one task contract: one bounded Financial Agent assignment."""
        return ContractResearchTask(
            task_id="TASK_FA_01",
            target_agent="financial",
            objective=f"验证{company}的盈利质量、资产质量和现金流质量",
            questions=[
                ContractResearchQuestion(
                    question_id="Q_FA_01",
                    question="营业收入和净利润增长是否能够转化为经营现金流？",
                    reason="利润增长不一定代表实际现金创造能力。",
                    priority="P0",
                    expected_evidence=[
                        "利润表",
                        "现金流量表",
                        "经营现金流与净利润比率",
                    ],
                    research_topic="profit_cash_conversion",
                ),
                ContractResearchQuestion(
                    question_id="Q_FA_02",
                    question="应收账款增长是否与收入增长匹配？",
                    reason="识别收入质量和回款风险。",
                    priority="P0",
                    expected_evidence=["应收账款", "营业收入", "应收账款增长率"],
                    research_topic="receivable_revenue_match",
                ),
                ContractResearchQuestion(
                    question_id="Q_FA_03",
                    question="存货增长是否与收入增长匹配？",
                    reason="识别资产积压和跌价风险。",
                    priority="P0",
                    expected_evidence=["存货", "营业收入", "存货增长率"],
                    research_topic="inventory_revenue_match",
                ),
                ContractResearchQuestion(
                    question_id="Q_FA_04",
                    question="销售费用率变化是否由可验证的市场拓展活动支持？",
                    reason="区分增长投入与获客效率恶化。",
                    priority="P1",
                    expected_evidence=["销售费用", "营业收入", "销售费用率"],
                    research_topic="selling_expense_quality",
                ),
            ],
            pdf_topics=["财务资料", "贸易应收款项", "存货", "现金流量表"],
            web_topics=[],
            completion_criteria=[
                "生成核心财务指标",
                "所有异常具有 Evidence",
                "每项异常包含可能解释和补证要求",
            ],
        )

    @staticmethod
    def _default_plan(
        company: str,
        document_summary: dict[str, Any],
    ) -> ResearchPlan:
        hypotheses = ResearchManagerAgent._derive_hypotheses(document_summary)
        hypothesis_suffix = (
            " Priority company-specific hypotheses: " + "; ".join(hypotheses)
            if hypotheses
            else ""
        )
        tasks = [
            ResearchTask(
                agent_name="company_business",
                question=(
                    f"{company} sells what, to whom, under which commercial model, "
                    "and with what ownership and management structure?" + hypothesis_suffix
                ),
                reason="Establish the inside-out company and business case.",
                expected_evidence=[
                    "prospectus business pages",
                    "ownership and management pages",
                    "customer and supplier disclosures",
                ],
                priority="high",
            ),
            ResearchTask(
                agent_name="financial_dd",
                question=(
                    f"Has {company} generated sustainable earnings and cash without "
                    "deteriorating working capital or leverage?" + hypothesis_suffix
                ),
                reason="Test historical financial quality with deterministic calculations.",
                expected_evidence=[
                    "primary financial statements",
                    "financial notes",
                    "calculation traces",
                ],
                priority="high",
            ),
            ResearchTask(
                agent_name="industry_competition",
                question=(
                    f"Does {company}'s industry structure and competitive position "
                    "support future earning power?" + hypothesis_suffix
                ),
                reason="Validate company claims with non-prospectus evidence.",
                expected_evidence=[
                    "dated external industry source",
                    "competitor evidence",
                    "market-share methodology",
                ],
                priority="high",
            ),
            ResearchTask(
                agent_name="legal_governance",
                question=(
                    f"Does {company} disclose material legal, governance, related-party, "
                    "controller, licensing, or adverse-information risks?" + hypothesis_suffix
                ),
                reason="Identify non-financial matters that may pause diligence.",
                expected_evidence=[
                    "prospectus legal and governance pages",
                    "official registry, regulator, or court source",
                ],
                priority="high",
            ),
        ]
        page_count = document_summary.get("page_count", 0)
        section_count = document_summary.get("section_count", 0)
        return ResearchPlan(
            company=company,
            tasks=tasks,
            manager_notes=(
                f"Mainline A plan for {page_count} pages and {section_count} detected "
                "sections. Four specialists must return structured evidence and findings."
            ),
            focus_areas=[
                "past and present financial quality",
                "future earning power",
                "material negative risk",
            ],
            company_specific_hypotheses=hypotheses,
        )

    @staticmethod
    def _derive_hypotheses(document_summary: dict[str, Any]) -> list[str]:
        """Turn prospectus signals into questions, never conclusions."""
        text = " ".join(document_summary.get("signal_texts", [])).lower()
        rules = (
            (("收购", "并购", "acquisition"), "并购是否改变报表口径、业务结构及商誉风险"),
            (("研发", "research and development", "r&d"), "研发投入变化能否形成可持续产品与收入"),
            (("客户集中", "五大客户", "largest customers"), "客户集中度及主要客户收入真实性是否可验证"),
            (("存货", "inventory"), "存货变化能否由产销节奏、备货或并购范围合理解释"),
            (("应收", "trade receivable"), "应收账款增长、账期与收入增长是否匹配"),
            (("关联交易", "related party"), "关联交易是否具有必要性、公允性及持续影响"),
            (("债务", "借款", "borrowings"), "短长期债务与现金偿付能力是否匹配"),
        )
        return [question for keywords, question in rules if any(k in text for k in keywords)][:5]

    def _plan_with_llm(
        self,
        company: str,
        document_summary: dict[str, Any],
    ) -> ResearchPlan:
        context = json.dumps(
            {
                "company": company,
                "page_count": document_summary.get("page_count", 0),
                "section_count": document_summary.get("section_count", 0),
                "section_names": document_summary.get("section_names", []),
            },
            ensure_ascii=False,
        )
        prompt = f"""Create a bounded Mainline A Hong Kong IPO due diligence plan.
Available agents: company_business, financial_dd, industry_competition, legal_governance.
Every task must ask an evidence question and name expected evidence. Do not request an
investment amount, valuation ceiling, exit plan, or post-listing price forecast.

Document context:
{context}

Return JSON with a tasks array. Each task contains agent, objective, priority.
"""
        markdown = self.client.complete_text(
            system_prompt=RESEARCH_MANAGER_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=1000,
        )
        return self._parse_llm_plan(company, markdown, document_summary)

    @classmethod
    def _parse_llm_plan(
        cls,
        company: str,
        markdown: str,
        document_summary: dict[str, Any],
    ) -> ResearchPlan:
        tasks: list[ResearchTask] = []
        try:
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", markdown.strip())
            payload = json.loads(text)
            for item in payload.get("tasks", []):
                agent = str(item.get("agent", ""))
                objective = str(item.get("objective", ""))
                if agent not in cls.ALLOWED_AGENTS or not objective:
                    continue
                tasks.append(
                    ResearchTask(
                        agent_name=agent,
                        question=objective,
                        priority=item.get("priority", "normal"),
                    )
                )
        except (TypeError, ValueError, json.JSONDecodeError):
            tasks = []
        if len({item.agent_name for item in tasks}) != len(cls.ALLOWED_AGENTS):
            return cls._default_plan(company, document_summary)
        return ResearchPlan(
            company=company,
            tasks=tasks,
            manager_notes=markdown[:500],
            focus_areas=[item.agent_name for item in tasks],
            company_specific_hypotheses=cls._derive_hypotheses(document_summary),
        )
