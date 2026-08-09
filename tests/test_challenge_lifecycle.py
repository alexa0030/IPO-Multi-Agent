from __future__ import annotations

from types import SimpleNamespace

from ipo_financial_agent.models_agent import Challenge as LegacyChallenge
from ipo_financial_agent.pipeline import IPOFinancialPipeline
from ipo_financial_agent.schemas import Challenge


def test_second_skeptic_pass_marks_candidate_only_followup_unresolved():
    pipeline = object.__new__(IPOFinancialPipeline)
    challenge = Challenge(
        challenge_id="C-1",
        target_agent="industry_competition",
        finding_id="F-1",
        question="Find independent market data.",
        reason="Issuer evidence is insufficient.",
        required_evidence=["industry association"],
        priority="P0",
        response_evidence_ids=["E-NEW-1"],
        status="open",
    )

    update = pipeline._run_skeptic(
        {
            "research_findings": [],
            "open_questions": [],
            "risk_review": None,
            "followup_round": 1,
            "canonical_challenges": [challenge],
        }
    )

    assert update["canonical_challenges"][0].status == "unresolved"
    assert update["canonical_challenges"][0].response_evidence_ids == ["E-NEW-1"]


def test_response_finding_marks_challenge_resolved():
    pipeline = object.__new__(IPOFinancialPipeline)
    challenge = Challenge(
        challenge_id="C-2",
        target_agent="legal_governance",
        finding_id="F-2",
        question="Verify the licence.",
        reason="Current status is unclear.",
        priority="P1",
        response_finding_ids=["F-RESPONSE-1"],
    )

    update = pipeline._run_skeptic(
        {
            "research_findings": [],
            "open_questions": [],
            "risk_review": None,
            "followup_round": 1,
            "canonical_challenges": [challenge],
        }
    )

    assert update["canonical_challenges"][0].status == "resolved"


def test_followup_records_candidate_evidence_against_its_challenge():
    pipeline = object.__new__(IPOFinancialPipeline)
    legacy = LegacyChallenge(
        challenge_id="C-3",
        target_agent="company_business",
        challenged_finding_id="F-3",
        question="Which customer relationship requires verification?",
        reason="Customer evidence is incomplete.",
    )
    canonical = Challenge(
        challenge_id="C-3",
        target_agent="company_business",
        finding_id="F-3",
        question=legacy.question,
        reason=legacy.reason,
        priority="P1",
    )

    update = pipeline._run_targeted_followup(
        {
            "company": "Issuer",
            "challenges": [legacy],
            "canonical_challenges": [canonical],
            "pages": [
                SimpleNamespace(
                    page=27,
                    text="The customer relationship and customer contract require verification.",
                )
            ],
            "followup_round": 0,
        }
    )

    assert update["canonical_evidence"][0].page_number == 27
    assert update["canonical_challenges"][0].response_evidence_ids == [
        update["canonical_evidence"][0].evidence_id
    ]
    assert update["canonical_challenges"][0].status == "open"


def test_review_llm_escalation_is_materiality_gated():
    assert not IPOFinancialPipeline._review_needs_llm(
        {"canonical_findings": [], "financial_findings": [], "risks": []}
    )
    assert IPOFinancialPipeline._review_needs_llm(
        {
            "financial_findings": [
                SimpleNamespace(
                    severity="critical", assessment_status="unexplained"
                )
            ]
        }
    )
