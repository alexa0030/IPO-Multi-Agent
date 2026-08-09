from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from .challenge import Challenge
from .evidence import Evidence
from .financial_result import FinancialAgentResult
from .finding import Finding
from .follow_up import FollowUpRequest
from .research_task import ResearchTask
from ipo_financial_agent.runtime import ToolCallTrace
from .review_result import ReviewResult


class IPOResearchState(TypedDict, total=False):
    # Canonical cross-node state. Keep compatibility aliases while the
    # pipeline is migrated from the original orchestration contract.
    document_id: str
    job_id: str
    run_id: str
    company_name: str
    company: str
    pdf_path: str
    llm_mode: str
    document_manifest: dict[str, Any]
    document_index: dict[str, Any]
    pages: list[Any]
    section_hits: list[Any]
    topic_page_groups: dict[str, list[Any]]
    research_plan: dict[str, Any]
    research_tasks: list[ResearchTask]
    company_findings: Annotated[list[Finding], operator.add]
    financial_findings: Annotated[list[Finding], operator.add]
    industry_findings: Annotated[list[Finding], operator.add]
    legal_findings: Annotated[list[Finding], operator.add]
    evidences: Annotated[list[Evidence], operator.add]
    agent_messages: Annotated[list[dict[str, Any]], operator.add]
    follow_up_requests: list[FollowUpRequest]
    review_round: int
    review_result: ReviewResult | None
    final_report: str
    errors: Annotated[list[dict[str, Any]], operator.add]
    financial_agent_result: dict[str, Any]
    canonical_financial_result: FinancialAgentResult
    candidate_pages: list[Any]
    # Legacy Agent artifacts remain accepted here until every specialist uses
    # the canonical schemas. Boundary adapters validate them before review.
    research_evidence: Annotated[list[Any], operator.add]
    research_findings: Annotated[list[Any], operator.add]
    canonical_evidence: Annotated[list[Evidence], operator.add]
    canonical_findings: Annotated[list[Finding], operator.add]
    canonical_ledger_status: dict[str, Any]
    review_llm_budget: dict[str, int]
    tool_call_trace: Annotated[list[ToolCallTrace], operator.add]
    open_questions: Annotated[list[Any], operator.add]
    challenges: list[Any]
    canonical_challenges: list[Challenge]
    followup_round: int
    diligence_questions: list[Any]
    due_diligence_conclusion: Any
    raw_statements: list[Any]
    extraction_result: Any
    metrics: list[Any]
    risks: list[Any]
    rule_trigger_events: list[Any]
    analysis: Any
    prospectus_analysis: Any
    industry_analysis: Any
    legal_governance_analysis: Any
    risk_review: Any
    report_review: Any
    report_revision_performed: bool
    artifacts: Any
