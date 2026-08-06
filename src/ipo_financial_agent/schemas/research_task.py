from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

AgentName = Literal[
    "company_business",
    "financial",
    "industry_competition",
    "legal_governance",
]
Priority = Literal["P0", "P1", "P2"]


class FinancialResearchTopic(StrEnum):
    PROFIT_CASH_CONVERSION = "profit_cash_conversion"
    RECEIVABLE_REVENUE_MATCH = "receivable_revenue_match"
    INVENTORY_REVENUE_MATCH = "inventory_revenue_match"
    GROSS_MARGIN_QUALITY = "gross_margin_quality"
    DEBT_LIQUIDITY = "debt_liquidity"
    ASSET_QUALITY = "asset_quality"
    CAPEX_CAPACITY = "capex_capacity"
    RELATED_PARTY_FINANCIAL = "related_party_financial"
    EARNINGS_SUSTAINABILITY = "earnings_sustainability"
    SELLING_EXPENSE_QUALITY = "selling_expense_quality"
    REVENUE_TAX_CONSISTENCY = "revenue_tax_consistency"
    CASH_FLOW_QUALITY = "cash_flow_quality"
    OTHER_COMPANY_SPECIFIC = "other_company_specific"


BASELINE_FINANCIAL_TOPICS = {
    FinancialResearchTopic.PROFIT_CASH_CONVERSION,
    FinancialResearchTopic.RECEIVABLE_REVENUE_MATCH,
    FinancialResearchTopic.INVENTORY_REVENUE_MATCH,
}


class ResearchQuestion(BaseModel):
    question_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    priority: Priority
    expected_evidence: list[str] = Field(min_length=1)
    research_topic: FinancialResearchTopic
    completion_criteria: list[str] = Field(min_length=1)

    @field_validator("expected_evidence")
    @classmethod
    def deduplicate_expected_evidence(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class ResearchTask(BaseModel):
    task_id: str = Field(min_length=1)
    target_agent: AgentName
    objective: str = Field(min_length=1)
    questions: list[ResearchQuestion] = Field(min_length=1)
    pdf_topics: list[str] = Field(default_factory=list)
    web_topics: list[str] = Field(default_factory=list)
    completion_criteria: list[str] = Field(default_factory=list)

    @field_validator("pdf_topics", "web_topics", "completion_criteria")
    @classmethod
    def deduplicate_lists(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))
