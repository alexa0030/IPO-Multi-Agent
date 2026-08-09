"""Explicit adapters from the legacy Agent ledger to canonical contracts.

Adapters are intentionally strict: missing provenance is reported instead of
being invented merely to make an old artifact pass validation.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .challenge import Challenge
from .evidence import Evidence
from .finding import Finding
from .research_task import (
    AgentName,
    FinancialResearchTopic,
    ResearchTopic,
    SpecialistResearchTopic,
)
from .specialist import SpecialistResearchResult


class ContractAdaptationError(ValueError):
    """Raised when a legacy artifact lacks required canonical provenance."""


_AGENT_NAMES: dict[str, AgentName] = {
    "company": "company_business",
    "company_business": "company_business",
    "prospectus": "company_business",
    "financial": "financial",
    "financial_dd": "financial",
    "industry": "industry_competition",
    "industry_competition": "industry_competition",
    "legal": "legal_governance",
    "legal_governance": "legal_governance",
}


def canonical_agent_name(value: str) -> AgentName:
    try:
        return _AGENT_NAMES[value.strip().lower()]
    except KeyError as exc:
        raise ContractAdaptationError(f"unsupported agent role: {value!r}") from exc


def adapt_legacy_evidence(item: Any, *, created_by: str) -> Evidence:
    """Convert one legacy Evidence without manufacturing missing lineage."""
    source_type = str(getattr(item, "source_type", "prospectus"))
    page_number = getattr(item, "page_number", None) or getattr(item, "page", None)
    source = str(getattr(item, "source", "") or "")
    source_url = getattr(item, "source_url", None)
    content = str(
        getattr(item, "content", "") or getattr(item, "detail", "") or ""
    )
    title = str(getattr(item, "title", "") or source or source_type)
    confidence = float(getattr(item, "confidence", 0.5))
    common = {
        "evidence_id": str(getattr(item, "evidence_id", "")),
        "title": title,
        "content": content,
        "published_at": getattr(item, "published_at", None),
        "raw_value": getattr(item, "metadata", {}).get("raw_value"),
        "created_by": canonical_agent_name(created_by),
    }

    if source_type in {"prospectus", "financial_statement"}:
        if not page_number:
            raise ContractAdaptationError(
                f"prospectus evidence {common['evidence_id']!r} has no page number"
            )
        return Evidence(
            **common,
            source_type="prospectus",
            page_number=page_number,
            section=source or None,
            source_quality="A",
        )
    if source_type in {"web", "news", "search"}:
        url = source_url or (source if source.startswith(("http://", "https://")) else None)
        if not url:
            raise ContractAdaptationError(
                f"web evidence {common['evidence_id']!r} has no URL"
            )
        return Evidence(
            **common,
            source_type="web",
            url=url,
            publisher=getattr(item, "metadata", {}).get("publisher"),
            source_quality="B" if confidence >= 0.8 else "C",
        )
    if source_type in {"calculation", "metric", "forensic_rule"}:
        metadata = getattr(item, "metadata", {})
        formula = metadata.get("formula")
        input_ids = metadata.get("input_evidence_ids", [])
        if not formula or not input_ids:
            raise ContractAdaptationError(
                f"calculation evidence {common['evidence_id']!r} lacks formula or inputs"
            )
        return Evidence(
            **common,
            source_type="calculation",
            formula=formula,
            input_evidence_ids=input_ids,
            source_quality="A",
        )
    raise ContractAdaptationError(f"unsupported evidence source type: {source_type!r}")


def adapt_legacy_finding(
    item: Any,
    *,
    task_id: str,
    topic: ResearchTopic = FinancialResearchTopic.OTHER_COMPANY_SPECIFIC,
    answered_question_ids: Iterable[str] = (),
) -> Finding:
    """Convert a legacy Agent Finding to the canonical review contract."""
    strength = str(getattr(item, "evidence_strength", "medium"))
    nature = str(getattr(item, "finding_nature", "neutral_observation"))
    risk_level = {
        "strength": "positive",
        "risk": "medium",
        "mixed": "medium",
        "neutral_observation": "low",
    }.get(nature, "low")
    conclusion = str(getattr(item, "conclusion", ""))
    risks = list(getattr(item, "risks", []))
    open_questions = list(getattr(item, "open_questions", []))
    return Finding(
        finding_id=str(getattr(item, "finding_id", "")),
        task_id=task_id,
        agent=canonical_agent_name(str(getattr(item, "agent_name", ""))),
        topic=topic,
        answered_question_ids=list(answered_question_ids),
        title=str(getattr(item, "question", "")),
        statement=conclusion,
        evidence_ids=list(getattr(item, "evidence_ids", [])),
        interpretation=conclusion,
        alternative_explanations=[],
        required_checks=open_questions,
        risk_level=risk_level,
        confidence={"strong": "high", "medium": "medium", "weak": "low"}.get(
            strength, "low"
        ),
        cross_check_topics=risks,
    )


def adapt_legacy_research_patch(
    patch: Any, *, task_id: str, agent: str
) -> SpecialistResearchResult:
    """Validate one old ResearchPatch at a specialist-to-graph boundary."""
    canonical_agent = canonical_agent_name(agent)
    topic_by_agent: dict[AgentName, ResearchTopic] = {
        "company_business": SpecialistResearchTopic.COMPANY_BUSINESS,
        "financial": FinancialResearchTopic.OTHER_COMPANY_SPECIFIC,
        "industry_competition": SpecialistResearchTopic.INDUSTRY_COMPETITION,
        "legal_governance": SpecialistResearchTopic.LEGAL_GOVERNANCE,
    }
    evidences = [
        adapt_legacy_evidence(item, created_by=canonical_agent)
        for item in getattr(patch, "evidence", [])
    ]
    findings = []
    for item in getattr(patch, "findings", []):
        finding_agent = canonical_agent_name(str(getattr(item, "agent_name", agent)))
        findings.append(
            adapt_legacy_finding(
                item,
                task_id=task_id,
                topic=topic_by_agent[finding_agent],
            )
        )
    return SpecialistResearchResult(
        task_id=task_id,
        agent=canonical_agent,
        evidences=evidences,
        findings=findings,
        open_questions=list(getattr(patch, "open_questions", [])),
    )


def adapt_legacy_challenge(item: Any) -> Challenge:
    finding_id = getattr(item, "challenged_finding_id", None)
    severity = str(getattr(item, "severity", "important"))
    return Challenge(
        challenge_id=str(getattr(item, "challenge_id", "")),
        target_agent=canonical_agent_name(str(getattr(item, "target_agent", ""))),
        finding_id=finding_id,
        question=str(getattr(item, "question", "")),
        reason=str(getattr(item, "reason", "")),
        required_evidence=list(getattr(item, "required_evidence", [])),
        priority={"critical": "P0", "important": "P1", "minor": "P2"}.get(
            severity, "P1"
        ),
        status="resolved" if getattr(item, "resolved", False) else "open",
        response_finding_ids=list(getattr(item, "response_finding_ids", [])),
        response_evidence_ids=[],
    )
