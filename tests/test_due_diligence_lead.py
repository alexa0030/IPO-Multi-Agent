from ipo_financial_agent.agents.due_diligence_lead import DueDiligenceLeadAgent
from ipo_financial_agent.models_agent import Challenge, Evidence, Finding, RiskReview


def test_lead_turns_challenge_into_prioritized_question() -> None:
    evidence = Evidence(
        source_type="calculation", source="cash_conversion", content="0.4"
    )
    finding = Finding(
        agent_name="financial_dd",
        question="Is cash conversion weak?",
        conclusion="Cash conversion is weak.",
        evidence_ids=[evidence.evidence_id],
        risks=["earnings quality"],
    )
    challenge = Challenge(
        target_agent="financial_dd",
        challenged_finding_id=finding.finding_id,
        question="Reconcile profit to operating cash flow.",
        reason="Reported profit is not supported by cash conversion.",
        severity="critical",
        required_evidence=["bank statements", "cash-flow reconciliation"],
    )

    conclusion, questions = DueDiligenceLeadAgent().synthesize(
        findings=[finding],
        challenges=[challenge],
        risk_review=RiskReview(risk_level="High"),
        metrics=[object()],
        financial_findings=[],
    )

    assert conclusion.verdict == "pause"
    assert conclusion.material_risk_level == "High"
    assert questions[0].priority == "P0"
    assert questions[0].current_evidence_ids == [evidence.evidence_id]
