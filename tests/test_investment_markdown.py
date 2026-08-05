from ipo_financial_agent.models_agent import (
    DiligenceQuestion,
    DueDiligenceConclusion,
    Evidence,
    Finding,
    FinancialFinding,
)
from ipo_financial_agent.rendering import render_due_diligence_markdown


def test_markdown_renders_mainline_a_conclusion_and_follow_up() -> None:
    evidence = Evidence(
        source_type="prospectus",
        source_file="prospectus.pdf",
        page_number=78,
        title="Business model",
        content="The company sells industrial printing control systems.",
    )
    finding = Finding(
        agent_name="company_business",
        question="What does the company sell?",
        conclusion="The company sells industrial printing control systems.",
        evidence_ids=[evidence.evidence_id],
        evidence_strength="strong",
    )
    question = DiligenceQuestion(
        priority="P1",
        category="company_business",
        question="Provide top-five customer retention data.",
        rationale="Customer durability is not yet verified.",
        requested_materials=["customer retention schedule"],
        downside_if_unresolved="Future earning power may be overstated.",
    )

    report = render_due_diligence_markdown(
        {
            "company": "Example Holdings",
            "research_evidence": [evidence],
            "research_findings": [finding],
            "diligence_questions": [question],
            "due_diligence_conclusion": DueDiligenceConclusion(
                verdict="conditional_proceed",
                historical_financial_quality="moderate",
                future_earning_power="weak",
                material_risk_level="Medium",
            ),
            "metrics": [],
            "challenges": [],
        }
    )

    assert "# Example Holdings港股 IPO 公司尽调报告" in report
    assert f"{evidence.evidence_id} | 招股书 P78" in report
    assert "## 九、P0/P1/P2 补充尽调清单" in report
    assert "Provide top-five customer retention data." in report
    assert "投资金额、估值上限或退出建议" in report


def test_markdown_does_not_invent_industry_facts_without_external_evidence() -> None:
    report = render_due_diligence_markdown(
        {
            "company": "Example Holdings",
            "research_evidence": [],
            "research_findings": [],
            "diligence_questions": [],
            "metrics": [],
            "challenges": [],
        }
    )

    assert "尚无招股书之外的行业证据" in report
    assert "行业保持稳定增长" not in report


def test_financial_anomaly_is_not_rendered_as_company_strength() -> None:
    evidence = Evidence(source_type="calculation", source="metric", content="0.59")
    finding = Finding(
        agent_name="financial_dd",
        question="Is cash conversion weak?",
        conclusion="Cash conversion declined to 0.59.",
        evidence_ids=[evidence.evidence_id],
        risks=["weak cash conversion"],
    )
    report = render_due_diligence_markdown(
        {
            "company": "Example Holdings",
            "research_evidence": [evidence],
            "research_findings": [finding],
            "diligence_questions": [],
            "metrics": [],
            "challenges": [],
        }
    )

    conclusion_section = report.split("## 八、综合尽调判断", 1)[1].split(
        "## 九、P0/P1/P2 补充尽调清单", 1
    )[0]
    assert "Cash conversion declined to 0.59." not in conclusion_section


def test_financial_trigger_renders_as_hypothesis_with_escalation_conditions() -> None:
    report = render_due_diligence_markdown(
        {
            "company": "Example Holdings",
            "research_evidence": [],
            "research_findings": [],
            "financial_findings": [
                FinancialFinding(
                    rule_id="AQ-002",
                    name="存货增长较快",
                    triggered=True,
                    assessment_status="observation",
                    possible_explanations=["并购纳入报表范围"],
                    required_evidence=["合并口径桥接表"],
                    escalation_conditions=["剔除并购后存货仍显著快于收入"],
                )
            ],
            "diligence_questions": [],
            "metrics": [],
            "challenges": [],
        }
    )

    assert "财务异常的解释状态" in report
    assert "待解释观察" in report
    assert "可能解释（待验证）：并购纳入报表范围" in report
    assert "升级为风险的条件：剔除并购后存货仍显著快于收入" in report
