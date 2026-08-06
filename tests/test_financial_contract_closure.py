import pytest
from pydantic import ValidationError

from ipo_financial_agent.agents.financial_agent import FinancialAnalysisAgent
from ipo_financial_agent.agents.research_manager import ResearchManagerAgent
from ipo_financial_agent.agents.research_reviewer import ResearchReviewerAgent
from ipo_financial_agent.ledger import EvidenceRegistry, FindingRegistry
from ipo_financial_agent.models import MetricResult, StatementFact
from ipo_financial_agent.models_agent import FinancialFinding as LegacyFinancialFinding
from ipo_financial_agent.nodes.generate_report import generate_financial_report
from ipo_financial_agent.research.financial_contract_adapter import (
    convert_selling_expense_rule,
    register_financial_evidence,
)
from ipo_financial_agent.schemas import Evidence, Finding, ResearchTask


def _facts_and_metrics() -> tuple[list[StatementFact], list[MetricResult]]:
    facts: list[StatementFact] = []
    metrics: list[MetricResult] = []
    for index, (period, expense, revenue, ratio) in enumerate(
        (("2023", 28.0, 1000.0, 0.028), ("2024", 36.0, 1200.0, 0.03), ("2025", 57.4, 1400.0, 0.041)),
        start=1,
    ):
        expense_fact = StatementFact(
            fact_id=f"expense_{index}",
            document_id="doc",
            company="示例公司",
            statement_name="利润表",
            item_name="销售费用",
            canonical_tag="selling_expense",
            period=period,
            value=expense,
            raw_value=str(expense),
            unit="百万元",
            page=20 + index,
        )
        revenue_fact = StatementFact(
            fact_id=f"revenue_{index}",
            document_id="doc",
            company="示例公司",
            statement_name="利润表",
            item_name="营业收入",
            canonical_tag="revenue",
            period=period,
            value=revenue,
            raw_value=str(revenue),
            unit="百万元",
            page=20 + index,
        )
        facts.extend([expense_fact, revenue_fact])
        metrics.append(
            MetricResult(
                metric_id=f"selling_ratio_{index}",
                document_id="doc",
                metric_name="销售费用率",
                metric_code="selling_expense_ratio",
                period=period,
                value=ratio,
                display_value=f"{ratio:.1%}",
                formula="销售费用/营业收入",
                source_fact_ids=[expense_fact.fact_id, revenue_fact.fact_id],
                source_pages=[20 + index],
            )
        )
    for index in range(4):
        facts.append(
            StatementFact(
                fact_id=f"extra_{index}",
                document_id="doc",
                company="示例公司",
                statement_name="财务状况表",
                item_name=f"补充科目{index}",
                period="2025",
                value=float(index),
                raw_value=str(index),
                page=30 + index,
            )
        )
    return facts, metrics


def _rule() -> LegacyFinancialFinding:
    return LegacyFinancialFinding(
        rule_id="RA-001",
        name="销售费用率持续上升",
        category="revenue_authenticity",
        layer=2,
        severity="warning",
        triggered=True,
        possible_explanations=["新市场拓展", "获客效率下降"],
        required_evidence=["销售费用分项", "新增客户与收入贡献"],
    )


def test_source_specific_evidence_validation() -> None:
    with pytest.raises(ValidationError, match="page_number"):
        Evidence(
            evidence_id="PDF_BAD",
            source_type="prospectus",
            title="缺页码",
            content="不可登记",
            source_quality="A",
            created_by="financial",
        )
    with pytest.raises(ValidationError, match="input_evidence_ids"):
        Evidence(
            evidence_id="CALC_BAD",
            source_type="calculation",
            title="无输入计算",
            content="不可登记",
            formula="A/B",
            source_quality="A",
            created_by="financial",
        )


def test_manager_task_drives_financial_contract_and_agent_rejects_other_task() -> None:
    task = ResearchManagerAgent.plan_financial_task("示例公司")
    assert task.target_agent == "financial"
    assert {item.priority for item in task.questions}.issuperset({"P0", "P1"})
    wrong = task.model_copy(update={"target_agent": "industry_competition"})
    with pytest.raises(ValueError, match="cannot execute"):
        FinancialAnalysisAgent().analyze(
            document_id="doc",
            company="示例公司",
            pages=[],
            section_hits=[],
            task=wrong,
        )


def test_one_financial_rule_closes_task_evidence_finding_review_report_chain() -> None:
    task = ResearchManagerAgent.plan_financial_task("示例公司")
    facts, metrics = _facts_and_metrics()
    evidence = register_financial_evidence(facts=facts, metrics=metrics)
    finding = convert_selling_expense_rule(
        task=task,
        rule_result=_rule(),
        metrics=metrics,
    )

    evidence_registry = EvidenceRegistry()
    evidence_registry.extend([item for item in evidence if item.source_type == "prospectus"])
    evidence_registry.extend([item for item in evidence if item.source_type == "calculation"])
    FindingRegistry(evidence_registry).add(finding)
    review = ResearchReviewerAgent().review_financial(
        task=task,
        evidences=evidence,
        findings=[finding],
    )
    report = generate_financial_report(
        {
            "review_result": review,
            "financial_findings": [finding],
        }
    )["final_report"]

    assert len([item for item in evidence if item.source_type == "prospectus"]) >= 10
    assert len([item for item in evidence if item.source_type == "calculation"]) == 3
    assert finding.task_id == task.task_id
    assert finding.risk_level == "medium"
    assert finding.alternative_explanations
    assert finding.required_checks
    assert review.approved_finding_ids == [finding.finding_id]
    assert review.rejected_finding_ids == []
    assert review.follow_up_requests
    for evidence_id in finding.evidence_ids:
        assert evidence_id in report


def test_registry_rejects_calculation_before_inputs() -> None:
    registry = EvidenceRegistry()
    with pytest.raises(ValueError, match="missing inputs"):
        registry.add(
            Evidence(
                evidence_id="CALC_1",
                source_type="calculation",
                title="销售费用率",
                content="4.1%",
                formula="销售费用/营业收入",
                input_evidence_ids=["PDF_1"],
                raw_value=0.041,
                source_quality="A",
                created_by="financial",
            )
        )


def test_reviewer_rejects_finding_with_unknown_evidence() -> None:
    task = ResearchManagerAgent.plan_financial_task("示例公司")
    finding = Finding(
        finding_id="FIN_BROKEN",
        task_id=task.task_id,
        agent="financial",
        topic="cash_flow_quality",
        title="缺失证据的判断",
        statement="该判断没有已登记证据。",
        evidence_ids=["CALC_NOT_REGISTERED"],
        interpretation="不可直接进入报告。",
        required_checks=["补齐底层财务事实和计算轨迹"],
        risk_level="medium",
        confidence="low",
    )

    review = ResearchReviewerAgent().review_financial(
        task=task,
        evidences=[],
        findings=[finding],
    )

    assert review.review_status == "insufficient_evidence"
    assert review.approved_finding_ids == []
    assert review.rejected_finding_ids == [finding.finding_id]
    assert review.follow_up_requests[0].priority == "P0"
