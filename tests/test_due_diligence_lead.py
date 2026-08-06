from ipo_financial_agent.agents.due_diligence_lead import DueDiligenceLeadAgent
from ipo_financial_agent.models_agent import Challenge, Evidence, Finding, RiskReview


def test_lead_turns_challenge_into_prioritized_question() -> None:
    evidence = Evidence(source_type="calculation", source="cash_conversion", content="0.4")
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


def test_future_earning_power_is_not_moderate_from_one_issuer_claim() -> None:
    evidence = Evidence(source_type="prospectus", page_number=10, content="业务说明")
    company_finding = Finding(
        agent_name="company_business",
        question="公司做什么？",
        conclusion="公司销售某产品。",
        evidence_ids=[evidence.evidence_id],
        evidence_strength="strong",
    )
    issuer_industry_finding = Finding(
        agent_name="industry_competition",
        question="行业如何？",
        conclusion="发行人称行业增长。",
        evidence_ids=[evidence.evidence_id],
        evidence_strength="weak",
    )
    conclusion, _ = DueDiligenceLeadAgent().synthesize(
        findings=[company_finding, issuer_industry_finding],
        challenges=[],
        risk_review=RiskReview(risk_level="Low"),
        metrics=[],
        financial_findings=[],
    )
    assert conclusion.future_earning_power == "weak"


def test_lead_keeps_risk_reviewer_questions_in_final_dd_list() -> None:
    review = RiskReview(
        risk_level="Medium",
        investment_questions=["请提供经营现金流与净利润桥接表，并核对期后回款。"],
    )

    conclusion, questions = DueDiligenceLeadAgent().synthesize(
        findings=[],
        challenges=[],
        risk_review=review,
        metrics=[],
        financial_findings=[],
    )

    assert conclusion.verdict == "conditional_proceed"
    assert len(questions) == 1
    assert questions[0].priority == "P0"
    assert questions[0].category == "financial"
    assert "财务科目明细" in questions[0].requested_materials[0]


def test_lead_can_grade_broad_independent_future_evidence_as_strong() -> None:
    findings = []
    for index in range(5):
        evidence = Evidence(
            source_type="prospectus", page_number=index + 1, content=f"公司证据{index}"
        )
        findings.append(
            Finding(
                agent_name="company_business",
                question=f"公司问题{index}",
                conclusion=f"公司结论{index}",
                evidence_ids=[evidence.evidence_id],
                evidence_strength="medium",
            )
        )
    for index in range(4):
        evidence = Evidence(
            source_type="web",
            source_url=f"https://example.com/{index}",
            content=f"行业证据{index}",
        )
        findings.append(
            Finding(
                agent_name="industry_competition",
                question=f"行业问题{index}",
                conclusion=f"行业结论{index}",
                evidence_ids=[evidence.evidence_id],
                evidence_strength="medium",
            )
        )

    conclusion, _ = DueDiligenceLeadAgent().synthesize(
        findings=findings,
        challenges=[],
        risk_review=RiskReview(risk_level="Low"),
        metrics=[],
        financial_findings=[],
    )

    assert conclusion.future_earning_power == "strong"
