from __future__ import annotations

import json
from pathlib import Path

import pytest

from ipo_financial_agent.finance.metric_engine import MetricEngine
from ipo_financial_agent.finance.risk_rules import RiskRuleEngine
from ipo_financial_agent.models import StatementFact


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "fixtures" / "hosonsoft-financial-facts.json"


def _load_contract():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    facts = [
        StatementFact(
            fact_id=item["factId"],
            document_id=payload["documentId"],
            company=payload["company"],
            reporting_entity=item.get("reportingEntity"),
            statement_name="verified_contract_fixture",
            item_name=item["metricCode"],
            canonical_tag=item["metricCode"],
            period=item["period"],
            value=item["value"],
            raw_value=str(item["value"]),
            unit=item.get("unit"),
            page=item.get("page") or 1,
            entity_scope="集团/合并",
            confidence=1.0,
        )
        for item in payload["facts"]
    ]
    return payload, facts


def test_shared_hosonsoft_contract_matches_verified_metrics():
    payload, facts = _load_contract()
    metrics = MetricEngine().calculate(
        payload["documentId"], facts, reporting_entity=payload["reportingEntity"]
    )
    values = {(metric.metric_code, metric.period): metric.value for metric in metrics}

    assert values[("gross_margin", "2025")] == pytest.approx(0.545, abs=0.0005)
    assert values[("net_margin", "2025")] == pytest.approx(0.238, abs=0.0005)
    assert values[("ocf_to_net_profit", "2025")] == pytest.approx(0.593, abs=0.0005)
    assert values[("current_ratio", "2025")] == pytest.approx(3.7, abs=0.01)


def test_shared_hosonsoft_contract_produces_expected_observations():
    payload, facts = _load_contract()
    metrics = MetricEngine().calculate(
        payload["documentId"], facts, reporting_entity=payload["reportingEntity"]
    )
    findings = RiskRuleEngine().scan(payload["documentId"], metrics, facts)
    codes = {finding.rule_code for finding in findings}

    assert {"inventory_vs_revenue", "receivable_vs_revenue", "weak_cash_conversion", "gross_margin_decline"} <= codes
    assert all(finding.assessment_status == "observation" for finding in findings)
