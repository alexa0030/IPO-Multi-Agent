from __future__ import annotations

import pytest

from ipo_financial_agent.models_agent import (
    Challenge as LegacyChallenge,
    Evidence as LegacyEvidence,
    Finding as LegacyFinding,
)
from ipo_financial_agent.ledger import EvidenceRegistry, FindingRegistry
from ipo_financial_agent.schemas import (
    ContractAdaptationError,
    adapt_legacy_challenge,
    adapt_legacy_evidence,
    adapt_legacy_finding,
)


def test_adapt_prospectus_evidence_preserves_trace():
    legacy = LegacyEvidence(
        source_type="prospectus",
        page_number=12,
        content="Customer concentration was 52%.",
    )
    canonical = adapt_legacy_evidence(legacy, created_by="company")

    assert canonical.evidence_id == legacy.evidence_id
    assert canonical.page_number == 12
    assert canonical.source_quality == "A"
    assert canonical.created_by == "company_business"


def test_adapt_calculation_refuses_to_invent_lineage():
    legacy = LegacyEvidence(source_type="metric", source="gross_margin", detail="37%")

    with pytest.raises(ContractAdaptationError, match="lacks formula or inputs"):
        adapt_legacy_evidence(legacy, created_by="financial")


def test_adapt_finding_preserves_evidence_references():
    legacy = LegacyFinding(
        agent_name="industry_competition",
        question="Is the claimed ranking independently supported?",
        conclusion="Only issuer evidence is available.",
        evidence_ids=["E1", "E1"],
        evidence_strength="weak",
        finding_nature="risk",
        open_questions=["Find an independent source"],
    )
    canonical = adapt_legacy_finding(legacy, task_id="T-IND-1")

    assert canonical.agent == "industry_competition"
    assert canonical.evidence_ids == ["E1"]
    assert canonical.risk_level == "medium"
    assert canonical.confidence == "low"


def test_adapt_challenge_creates_routable_contract():
    legacy = LegacyChallenge(
        target_agent="industry_competition",
        challenged_finding_id="F1",
        question="Find independent market-share evidence.",
        reason="The current source is issuer-authored.",
        severity="critical",
        required_evidence=["industry association"],
    )
    canonical = adapt_legacy_challenge(legacy)

    assert canonical.finding_id == "F1"
    assert canonical.priority == "P0"
    assert canonical.status == "open"


def test_unlinked_open_question_can_still_be_routed():
    legacy = LegacyChallenge(
        target_agent="company_business",
        question="Clarify the customer relationship.",
        reason="The ledger contains an unlinked open question.",
    )

    canonical = adapt_legacy_challenge(legacy)

    assert canonical.finding_id is None
    assert canonical.status == "open"


def test_legacy_artifacts_enter_registry_only_after_adaptation():
    evidence = LegacyEvidence(
        evidence_id="E-PDF-1",
        source_type="prospectus",
        page_number=8,
        content="Revenue disclosure",
    )
    finding = LegacyFinding(
        finding_id="F-1",
        agent_name="financial",
        question="What supports revenue?",
        conclusion="The prospectus contains a revenue disclosure.",
        evidence_ids=["E-PDF-1"],
    )

    evidence_registry = EvidenceRegistry.from_legacy([evidence], created_by="financial")
    canonical = FindingRegistry(evidence_registry).add_legacy(
        finding,
        task_id="T-FIN-1",
        answered_question_ids=["Q-FIN-1"],
    )

    assert canonical.finding_id == "F-1"
    assert canonical.answered_question_ids == ["Q-FIN-1"]
