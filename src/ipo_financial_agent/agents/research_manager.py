"""Mainline A research manager for company due diligence planning."""

from __future__ import annotations

import json
import re
from typing import Any, ClassVar

from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.llm.prompts_agents import RESEARCH_MANAGER_SYSTEM_PROMPT
from ipo_financial_agent.models_agent import ResearchPlan, ResearchTask


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
    def _default_plan(
        company: str,
        document_summary: dict[str, Any],
    ) -> ResearchPlan:
        tasks = [
            ResearchTask(
                agent_name="company_business",
                question=(
                    f"{company} sells what, to whom, under which commercial model, "
                    "and with what ownership and management structure?"
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
                    "deteriorating working capital or leverage?"
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
                    "support future earning power?"
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
                    "controller, licensing, or adverse-information risks?"
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
        )

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
        )
