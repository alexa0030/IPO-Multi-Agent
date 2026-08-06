from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from .evidence import Evidence
from .finding import Finding
from .follow_up import FollowUpRequest
from .research_task import ResearchTask
from .review_result import ReviewResult


class IPOResearchState(TypedDict, total=False):
    job_id: str
    company_name: str
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
