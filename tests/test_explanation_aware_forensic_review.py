from ipo_financial_agent.agents.risk_reviewer import RiskReviewerAgent
from ipo_financial_agent.models_agent import (
    Evidence,
    FinancialFinding,
    Finding,
    IndustryAnalysis,
    ProspectusAnalysis,
)


def test_forensic_observation_stays_pending_but_prevents_false_low_risk() -> None:
    finding = FinancialFinding(
        rule_id="RA-003",
        name="纳税额收入比背离",
        category="revenue_authenticity",
        layer=2,
        severity="high",
        triggered=True,
        description="revenue_growth=36.0%, tax_growth=-8.8%",
        assessment_status="observation",
        possible_explanations=["所得税支付时点差异", "并购并表口径"],
        required_evidence=["所得税费用与已付所得税桥接"],
    )
    prospectus = ProspectusAnalysis(
        company="测试公司",
        business_model="公司报告期内收入持续增长。",
    )

    review = RiskReviewerAgent().review(
        company="测试公司",
        prospectus_analysis=prospectus,
        financial_findings=[finding],
    )

    assert review.contradictions == []
    assert review.risk_level == "Medium"
    assert any("待核实财务异常" in item for item in review.major_risks)
    assert review.risk_matrix[0].category == "financial_observation"
    assert review.risk_matrix[0].probability == "Low"


def test_forensic_finding_defaults_to_observation() -> None:
    finding = FinancialFinding(rule_id="EQ-002", triggered=True)

    assert finding.assessment_status == "observation"


def test_competitors_do_not_automatically_refute_market_leadership() -> None:
    prospectus = ProspectusAnalysis(
        company="测试公司",
        competitive_advantages=["发行人称公司处于行业领先地位。"],
    )
    industry = IndustryAnalysis(competitors=["竞争者A", "竞争者B"])

    review = RiskReviewerAgent().review(
        company="测试公司",
        prospectus_analysis=prospectus,
        industry_analysis=industry,
    )

    assert review.contradictions == []


def test_unverified_legal_search_lead_is_not_treated_as_confirmed_high_risk() -> None:
    evidence = Evidence(
        source_type="web",
        source_url="https://example.com/lead",
        content="搜索摘要线索",
    )
    finding = Finding(
        agent_name="legal_governance",
        question="是否存在诉讼线索？",
        conclusion="检索到一条待核实线索。",
        evidence_ids=[evidence.evidence_id],
        evidence_strength="medium",
        risks=["待核实核查线索：litigation_and_penalties"],
    )

    review = RiskReviewerAgent().review(
        company="测试公司",
        research_findings=[finding],
    )

    assert review.risk_level == "Low"
    assert review.risk_matrix[0].probability == "Low"
    assert review.risk_matrix[0].category == "legal_governance_verification"
