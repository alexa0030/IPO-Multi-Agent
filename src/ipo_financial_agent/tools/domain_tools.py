"""Initial IPO domain tool pool.

Handlers are thin adapters around existing services. They do not replace the
deterministic workflow and do not let an LLM write facts, metrics or findings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, Field

from ipo_financial_agent.tools.registry import DomainTool, DomainToolRegistry
from ipo_financial_agent.schemas import Evidence
from ipo_financial_agent.tools.search_tool import (
    search_industry_info,
    search_legal_governance_info,
    search_targeted_followup,
)


@dataclass(frozen=True)
class DomainToolContext:
    """Read-only runtime data and injectable service functions for tools."""

    pages: tuple[Any, ...] = ()
    metrics: tuple[Any, ...] = ()
    forensic_flags: tuple[Any, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    industry_search: Callable[..., list[dict[str, Any]]] | None = None
    legal_search: Callable[..., list[dict[str, Any]]] | None = None
    followup_search: Callable[..., list[dict[str, Any]]] | None = None


class IndustrySearchInput(BaseModel):
    company: str = Field(min_length=1)
    business_description: str = ""


class CompanySearchInput(BaseModel):
    company: str = Field(min_length=1)


class FollowUpSearchInput(BaseModel):
    company: str = Field(min_length=1)
    question: str = Field(min_length=2)


class SearchResultsOutput(BaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)


class ProspectusSearchInput(BaseModel):
    query: str = Field(min_length=2)
    max_results: int = Field(default=5, ge=1, le=10)


class ProspectusExcerpt(BaseModel):
    page_number: int = Field(ge=1)
    content: str = Field(min_length=1)
    score: int = Field(ge=1)


class ProspectusSearchOutput(BaseModel):
    results: list[ProspectusExcerpt] = Field(default_factory=list)


class FinancialMetricInput(BaseModel):
    metric_code: str = Field(min_length=1)
    periods: list[str] = Field(default_factory=list)


class FinancialMetricOutput(BaseModel):
    metrics: list[dict[str, Any]] = Field(default_factory=list)


class ForensicFlagsInput(BaseModel):
    severities: list[str] = Field(default_factory=list)
    triggered_only: bool = True


class ForensicFlagsOutput(BaseModel):
    flags: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceLookupInput(BaseModel):
    evidence_ids: list[str] = Field(min_length=1)


class EvidenceLookupOutput(BaseModel):
    evidence: list[Evidence] = Field(default_factory=list)
    missing_ids: list[str] = Field(default_factory=list)


class EvidenceVerifyOutput(BaseModel):
    valid: bool
    verified_ids: list[str] = Field(default_factory=list)
    missing_ids: list[str] = Field(default_factory=list)


def _search_industry(**arguments: Any) -> dict[str, Any]:
    return {"results": search_industry_info(**arguments)}


def _search_legal(**arguments: Any) -> dict[str, Any]:
    return {"results": search_legal_governance_info(**arguments)}


def _search_followup(**arguments: Any) -> dict[str, Any]:
    return {"results": search_targeted_followup(**arguments)}


def build_domain_tool_registry(
    context: DomainToolContext | None = None,
) -> DomainToolRegistry:
    context = context or DomainToolContext()
    industry_service = context.industry_search or search_industry_info
    legal_service = context.legal_search or search_legal_governance_info
    followup_service = context.followup_search or search_targeted_followup

    def industry_handler(**arguments: Any) -> dict[str, Any]:
        return {"results": industry_service(**arguments)}

    def legal_handler(**arguments: Any) -> dict[str, Any]:
        return {"results": legal_service(**arguments)}

    def followup_handler(**arguments: Any) -> dict[str, Any]:
        return {"results": followup_service(**arguments)}

    def prospectus_handler(query: str, max_results: int) -> dict[str, Any]:
        tokens = {
            token.lower()
            for token in re.findall(r"[\w\u4e00-\u9fff]{2,}", query)
        }
        ranked: list[dict[str, Any]] = []
        for page in context.pages:
            text = str(getattr(page, "text", "") or "")
            page_number = int(
                getattr(page, "page_number", None)
                or getattr(page, "page", 0)
                or 0
            )
            score = sum(text.lower().count(token) for token in tokens)
            if page_number > 0 and score > 0:
                ranked.append(
                    {
                        "page_number": page_number,
                        "content": " ".join(text.split())[:1200],
                        "score": score,
                    }
                )
        ranked.sort(key=lambda item: (-item["score"], item["page_number"]))
        return {"results": ranked[:max_results]}

    def metric_handler(metric_code: str, periods: list[str]) -> dict[str, Any]:
        selected = [
            item
            for item in context.metrics
            if getattr(item, "metric_code", "") == metric_code
            and (not periods or getattr(item, "period", "") in periods)
        ]
        return {
            "metrics": [
                item.model_dump() if hasattr(item, "model_dump") else dict(item)
                for item in selected
            ]
        }

    def flags_handler(
        severities: list[str], triggered_only: bool
    ) -> dict[str, Any]:
        flags = [
            item
            for item in context.forensic_flags
            if (not severities or getattr(item, "severity", "") in severities)
            and (not triggered_only or bool(getattr(item, "triggered", False)))
        ]
        return {
            "flags": [
                item.model_dump() if hasattr(item, "model_dump") else dict(item)
                for item in flags
            ]
        }

    def evidence_handler(evidence_ids: list[str]) -> dict[str, Any]:
        by_id = {item.evidence_id: item for item in context.evidence}
        return {
            "evidence": [by_id[item] for item in evidence_ids if item in by_id],
            "missing_ids": [item for item in evidence_ids if item not in by_id],
        }

    def verify_handler(evidence_ids: list[str]) -> dict[str, Any]:
        known = {item.evidence_id for item in context.evidence}
        missing = [item for item in evidence_ids if item not in known]
        return {
            "valid": not missing,
            "verified_ids": [item for item in evidence_ids if item in known],
            "missing_ids": missing,
        }

    registry = DomainToolRegistry()
    registry.register(
        DomainTool(
            name="search_industry_info",
            description="Search and fetch source-aware industry and competition material.",
            handler=industry_handler,
            allowed_roles=frozenset(
                {"company", "industry", "reviewer", "company_business", "industry_competition"}
            ),
            input_model=IndustrySearchInput,
            output_model=SearchResultsOutput,
        )
    )
    registry.register(
        DomainTool(
            name="search_legal_governance_info",
            description="Run bounded legal and governance public-information searches.",
            handler=legal_handler,
            allowed_roles=frozenset({"legal", "reviewer", "legal_governance"}),
            input_model=CompanySearchInput,
            output_model=SearchResultsOutput,
        )
    )
    registry.register(
        DomainTool(
            name="search_targeted_followup",
            description="Run one bounded follow-up query for an evidence gap.",
            handler=followup_handler,
            allowed_roles=frozenset(
                {
                    "research_manager",
                    "company_business",
                    "financial",
                    "industry",
                    "legal",
                    "reviewer",
                    "industry_competition",
                    "legal_governance",
                }
            ),
            input_model=FollowUpSearchInput,
            output_model=SearchResultsOutput,
        )
    )
    registry.register(
        DomainTool(
            name="search_prospectus",
            description="Retrieve bounded page excerpts from the loaded prospectus.",
            handler=prospectus_handler,
            allowed_roles=frozenset(
                {"company_business", "financial", "industry_competition", "legal_governance", "reviewer"}
            ),
            input_model=ProspectusSearchInput,
            output_model=ProspectusSearchOutput,
        )
    )
    registry.register(
        DomainTool(
            name="get_financial_metric",
            description="Read deterministic financial metrics without recalculation.",
            handler=metric_handler,
            allowed_roles=frozenset({"financial", "reviewer"}),
            input_model=FinancialMetricInput,
            output_model=FinancialMetricOutput,
        )
    )
    registry.register(
        DomainTool(
            name="get_forensic_flags",
            description="Read deterministic forensic flags and their rule traces.",
            handler=flags_handler,
            allowed_roles=frozenset({"financial", "reviewer"}),
            input_model=ForensicFlagsInput,
            output_model=ForensicFlagsOutput,
        )
    )
    for name, description, output_model, handler in (
        ("get_evidence", "Read canonical Evidence by identifier.", EvidenceLookupOutput, evidence_handler),
        ("verify_evidence", "Verify that Evidence identifiers exist in the canonical ledger.", EvidenceVerifyOutput, verify_handler),
    ):
        registry.register(
            DomainTool(
                name=name,
                description=description,
                handler=handler,
                allowed_roles=frozenset(
                    {"company_business", "financial", "industry_competition", "legal_governance", "reviewer"}
                ),
                input_model=EvidenceLookupInput,
                output_model=output_model,
            )
        )
    return registry


def get_agent_tools(
    role: str, context: DomainToolContext | None = None
) -> dict[str, DomainTool]:
    """Return only the least-privilege view intended for one agent role."""
    return build_domain_tool_registry(context).for_role(role)
