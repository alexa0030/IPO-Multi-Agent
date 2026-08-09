from __future__ import annotations

import pytest

from ipo_financial_agent.models_agent import Evidence, Finding, ResearchPatch
from ipo_financial_agent.schemas import adapt_legacy_research_patch
from ipo_financial_agent.agents.risk_reviewer import RiskReviewerAgent


def test_industry_patch_becomes_canonical_boundary_result():
    evidence = Evidence(
        evidence_id="E-IND-1",
        source_type="web",
        title="Industry association",
        content="Published market data",
        source_url="https://example.com/market",
        confidence=0.9,
    )
    patch = ResearchPatch(
        evidence=[evidence],
        findings=[
            Finding(
                finding_id="F-IND-1",
                agent_name="industry_competition",
                question="Is the market claim independently supported?",
                conclusion="An external source is available.",
                evidence_ids=["E-IND-1"],
            )
        ],
    )

    result = adapt_legacy_research_patch(
        patch, task_id="T-IND-1", agent="industry_competition"
    )

    assert result.agent == "industry_competition"
    assert result.evidences[0].url == "https://example.com/market"
    assert result.findings[0].topic == "industry_competition"


def test_specialist_boundary_rejects_missing_evidence_reference():
    patch = ResearchPatch(
        findings=[
            Finding(
                agent_name="legal_governance",
                question="Is there a regulatory issue?",
                conclusion="A lead requires verification.",
                evidence_ids=["E-MISSING"],
            )
        ]
    )

    with pytest.raises(ValueError, match="missing evidence"):
        adapt_legacy_research_patch(
            patch, task_id="T-LEGAL-1", agent="legal_governance"
        )


def test_risk_reviewer_reads_canonical_findings():
    evidence = Evidence(
        evidence_id="E-LEGAL-1",
        source_type="prospectus",
        page_number=18,
        content="A licence renewal is pending.",
    )
    patch = ResearchPatch(
        evidence=[evidence],
        findings=[
            Finding(
                agent_name="legal_governance",
                question="Is the licence current?",
                conclusion="Licence renewal requires verification.",
                evidence_ids=["E-LEGAL-1"],
                finding_nature="risk",
                open_questions=["Obtain the renewed licence"],
            )
        ],
    )
    canonical = adapt_legacy_research_patch(
        patch, task_id="T-LEGAL-1", agent="legal_governance"
    )

    risks = RiskReviewerAgent._summarize_ledger_risks(canonical.findings)

    assert risks[0]["agent_name"] == "legal_governance"
    assert risks[0]["risks"] == ["Obtain the renewed licence"]
