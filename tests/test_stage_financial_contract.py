import json

from ipo_financial_agent.models import MetricResult, StatementFact
from ipo_financial_agent.models_agent import Evidence as LegacyEvidence
from ipo_financial_agent.models_agent import FinancialFinding as LegacyFinding
from ipo_financial_agent.research.financial_contract_adapter import (
    build_financial_agent_result,
    register_financial_evidence,
)
from ipo_financial_agent.research.fixed_financial_task import build_fixed_financial_task
from ipo_financial_agent.schemas import FinancialAgentResult


def _inputs():
    facts = []
    metrics = []
    for index, (period, expense, revenue, ratio) in enumerate(
        (("2023", 28, 1000, .028), ("2024", 36, 1200, .03), ("2025", 57.4, 1400, .041)), 1
    ):
        expense_fact = StatementFact(fact_id=f"expense_{index}", document_id="doc", company="公司", statement_name="利润表", item_name="销售费用", canonical_tag="selling_expense", period=period, value=expense, raw_value=str(expense), page=20 + index)
        revenue_fact = StatementFact(fact_id=f"revenue_{index}", document_id="doc", company="公司", statement_name="利润表", item_name="营业收入", canonical_tag="revenue", period=period, value=revenue, raw_value=str(revenue), page=20 + index)
        facts.extend([expense_fact, revenue_fact])
        metrics.append(MetricResult(metric_id=f"ratio_{index}", document_id="doc", metric_name="销售费用率", metric_code="selling_expense_ratio", period=period, value=ratio, display_value=f"{ratio:.1%}", formula="销售费用/营业收入", source_fact_ids=[expense_fact.fact_id, revenue_fact.fact_id], source_pages=[20 + index]))
    for code, name, value, display in (
        ("ocf_to_net_profit", "净现比", .59, "0.59x"),
        ("revenue_growth", "收入增长率", .36, "36.0%"),
        ("receivable_growth", "应收账款增长率", .933, "93.3%"),
        ("inventory_growth", "存货增长率", .035, "3.5%"),
    ):
        metrics.append(MetricResult(metric_id=f"metric_{code}", document_id="doc", metric_name=name, metric_code=code, period="2025", value=value, display_value=display, formula="确定性财务计算", source_fact_ids=["revenue_2", "revenue_3"], source_pages=[22, 23]))
    rules = [
        LegacyFinding(rule_id="EQ-002", name="收现比持续低于0.5", severity="high", triggered=True, description="2023=0.43, 2024=0.32, 2025=0.14", metrics={"latest_cash_to_revenue": .14}, evidence=[LegacyEvidence(page=23, source="cash_flow_statement", detail="OCF and revenue")], possible_explanations=["结算周期"], required_evidence=["期后回款"]),
        LegacyFinding(rule_id="RA-001", name="销售费用率持续上升", severity="warning", triggered=True, description="2.8%, 3.0%, 4.1%", metrics={"latest_ratio": .041}, evidence=[LegacyEvidence(page=0, source="metric", detail="selling expense / revenue")], possible_explanations=["新市场拓展"], required_evidence=["销售费用分项"]),
        LegacyFinding(rule_id="RA-003", name="纳税额收入比背离", severity="high", triggered=True, description="收入增长36%，税款增长-8.8%", metrics={"divergence": .448}, evidence=[LegacyEvidence(page=287, source="cash_flow_statement", detail="tax"), LegacyEvidence(page=21, source="income_statement", detail="revenue")], possible_explanations=["支付时点差异"], required_evidence=["税费桥接"]),
    ]
    return facts, metrics, rules


def test_financial_stage_contract_meets_acceptance_and_is_deterministic():
    task = build_fixed_financial_task()
    facts, metrics, rules = _inputs()
    evidence = register_financial_evidence(facts=facts, metrics=metrics)
    first = build_financial_agent_result(task=task, rules=rules, evidence=evidence, metrics=metrics)
    second = build_financial_agent_result(task=task, rules=rules, evidence=evidence, metrics=metrics)
    assert first.completion_status == "completed"
    assert [item.question_id for item in first.question_answer_map] == [
        "FA_Q001", "FA_Q002", "FA_Q003"
    ]
    assert all(item.status == "answered" for item in first.question_answer_map)
    assert all(item.completion_checks for item in first.question_answer_map)
    assert len(first.findings) >= 3
    assert {item.source_type for item in first.evidences}.issuperset({"prospectus", "calculation"})
    assert all(item.alternative_explanations and item.required_checks for item in first.findings if item.risk_level in {"medium", "high"})
    prohibited = ("造假", "违规", "违法", "欺诈")
    assert not any(word in item.statement + item.interpretation for item in first.findings for word in prohibited)
    payload = first.model_dump(mode="json")
    assert FinancialAgentResult.model_validate_json(json.dumps(payload, ensure_ascii=False)) == first
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_question_finding_evidence_links_are_bidirectionally_consistent():
    task = build_fixed_financial_task()
    facts, metrics, rules = _inputs()
    result = build_financial_agent_result(
        task=task,
        rules=rules,
        evidence=register_financial_evidence(facts=facts, metrics=metrics),
        metrics=metrics,
    )
    finding_by_id = {item.finding_id: item for item in result.findings}
    evidence_ids = {item.evidence_id for item in result.evidences}
    for mapping in result.question_answer_map:
        for finding_id in mapping.finding_ids:
            assert mapping.question_id in finding_by_id[finding_id].answered_question_ids
        assert set(mapping.evidence_ids) <= evidence_ids
