"""Convert legacy v0.3 Agent outputs into the unified Research Ledger."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ipo_financial_agent.models_agent import (
    Evidence,
    Finding,
    IndustryAnalysis,
    LegalGovernanceAnalysis,
    ProspectusAnalysis,
    ResearchPatch,
)


def _deduplicate_evidence(items: Iterable[Evidence]) -> list[Evidence]:
    return list({item.evidence_id: item for item in items}.values())


def financial_research_patch(items: Iterable[Any]) -> ResearchPatch:
    """Ground triggered forensic conclusions in their existing evidence."""
    evidence: list[Evidence] = []
    findings: list[Finding] = []
    for item in items:
        if not getattr(item, "triggered", False):
            continue
        item_evidence = list(getattr(item, "evidence", []) or [])
        evidence.extend(item_evidence)
        if not item_evidence:
            continue
        rule_id = getattr(item, "rule_id", "")
        name = getattr(item, "name", "")
        conclusion = (
            getattr(item, "interpretation", "")
            or getattr(item, "description", "")
            or name
        )
        findings.append(
            Finding(
                finding_id=f"financial_{rule_id.lower()}",
                agent_name="financial_dd",
                question=f"财务取证规则 {rule_id} 是否触发？",
                conclusion=conclusion,
                evidence_ids=[entry.evidence_id for entry in item_evidence],
                evidence_strength="strong",
                risks=[name] if name else [],
                open_questions=[getattr(item, "recommendation", "")]
                if getattr(item, "recommendation", "")
                else [],
            )
        )
    return ResearchPatch(
        evidence=_deduplicate_evidence(evidence),
        findings=findings,
    )


def prospectus_research_patch(result: ProspectusAnalysis) -> ResearchPatch:
    """Collect traceable prospectus facts without inventing missing citations."""
    evidence = list(result.business_model_evidence)
    for group in (
        result.main_products,
        result.customers,
        result.suppliers,
        result.management_team,
    ):
        for entity in group:
            evidence.extend(entity.evidence)

    findings: list[Finding] = []
    if result.business_model and result.business_model_evidence:
        findings.append(
            Finding(
                agent_name="company_business",
                question="公司的核心商业模式是什么？",
                conclusion=result.business_model,
                evidence_ids=[
                    item.evidence_id for item in result.business_model_evidence
                ],
                evidence_strength="strong",
            )
        )
    return ResearchPatch(
        evidence=_deduplicate_evidence(evidence),
        findings=findings,
        open_questions=["招股书风险与竞争优势尚未逐条绑定证据。"]
        if (result.prospectus_risks or result.competitive_advantages)
        else [],
    )


def industry_research_patch(result: IndustryAnalysis) -> ResearchPatch:
    """Only publish market conclusions when external evidence is available."""
    if not result.evidence:
        return ResearchPatch(open_questions=["外部行业检索不可用，市场结论待补查。"])
    conclusion = result.industry_overview or result.market_growth
    findings = []
    if conclusion:
        findings.append(
            Finding(
                agent_name="industry_competition",
                question="公司所处行业和竞争环境如何？",
                conclusion=conclusion,
                evidence_ids=[item.evidence_id for item in result.evidence],
                evidence_strength="medium",
            )
        )
    return ResearchPatch(
        evidence=_deduplicate_evidence(result.evidence),
        findings=findings,
    )


def legal_governance_research_patch(
    result: LegalGovernanceAnalysis,
) -> ResearchPatch:
    """Publish legal review leads by category with their prospectus pages."""
    findings: list[Finding] = []
    by_category: dict[str, list[Evidence]] = {}
    for item in result.evidence:
        category = str(item.metadata.get("category", "legal_governance"))
        by_category.setdefault(category, []).append(item)
    for category, evidence in by_category.items():
        findings.append(
            Finding(
                agent_name="legal_governance",
                question=f"Does the prospectus disclose a {category} review lead?",
                conclusion=(
                    f"The prospectus contains {len(evidence)} page-level review "
                    f"lead(s) for {category}; specialist verification is required."
                ),
                evidence_ids=[item.evidence_id for item in evidence],
                evidence_strength="medium",
                risks=[category],
                open_questions=[
                    "Verify the legal effect, current status, and completeness of disclosure."
                ],
            )
        )
    return ResearchPatch(
        evidence=_deduplicate_evidence(result.evidence),
        findings=findings,
        open_questions=result.open_questions,
    )
