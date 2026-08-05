from ipo_financial_agent.models_agent import (
    DiligenceQuestion,
    DueDiligenceConclusion,
)


def test_diligence_question_has_stable_identity_and_deduplicates() -> None:
    question = DiligenceQuestion(
        priority="P0",
        category="financial",
        question="Explain the divergence between profit and operating cash flow.",
        rationale="Cash conversion may undermine reported earnings quality.",
        current_evidence_ids=["ev_1", "ev_1"],
        requested_materials=["bank statements", "bank statements"],
        downside_if_unresolved="Pause diligence because earnings quality is unverified.",
    )

    assert question.question_id.startswith("ddq_")
    assert question.current_evidence_ids == ["ev_1"]
    assert question.requested_materials == ["bank statements"]


def test_due_diligence_conclusion_separates_three_assessments() -> None:
    conclusion = DueDiligenceConclusion(
        verdict="conditional_proceed",
        historical_financial_quality="moderate",
        future_earning_power="weak",
        material_risk_level="High",
        evidence_ids=["ev_1", "ev_1", "ev_2"],
        follow_up_question_ids=["ddq_1", "ddq_1"],
        confidence=0.65,
    )

    assert conclusion.evidence_ids == ["ev_1", "ev_2"]
    assert conclusion.follow_up_question_ids == ["ddq_1"]
