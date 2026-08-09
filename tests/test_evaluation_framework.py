from __future__ import annotations

from pathlib import Path

from ipo_financial_agent.evaluation.io import load_case
from ipo_financial_agent.evaluation.models import (
    EvalCase,
    ExpectedFinding,
    ExpectedMetric,
)
from ipo_financial_agent.evaluation.scorer import score_prediction
from ipo_financial_agent.evaluation.prediction_builder import build_prediction


def test_all_versioned_case_manifests_are_valid():
    case_dir = Path(__file__).resolve().parents[1] / "evaluation" / "cases"
    cases = [load_case(path) for path in sorted(case_dir.glob("*.json"))]

    assert len(cases) == 4
    assert {case.split for case in cases} == {"development", "validation", "test"}
    assert sum(case.split == "test" for case in cases) == 2
    assert all(case.expected_page_count > 400 for case in cases)


def test_score_prediction_uses_verified_gold_and_evidence_pages():
    case = EvalCase(
        case_id="case-1",
        company="Issuer",
        industry="software",
        split="validation",
        language="simplified_zh",
        source_filename="issuer.pdf",
        expected_page_count=10,
        expected_metrics=[
            ExpectedMetric(
                metric_code="revenue",
                period="2025",
                value=100.0,
                page=8,
                status="verified",
            )
        ],
        expected_findings=[
            ExpectedFinding(
                topic="customer_concentration",
                expected_fact="Top five customers are concentrated.",
                risk_level="high",
                pages=[6],
                evidence_excerpt="Top five customers accounted for 70%.",
                status="verified",
            )
        ],
    )
    prediction = {
        "metrics": [{"metric_code": "revenue", "period": "2025", "value": 100.5}],
        "findings": [
            {
                "topic": "customer_concentration",
                "risk_level": "medium",
                "pages": [6],
                "evidence_ids": ["E-1"],
            }
        ],
    }

    score = score_prediction(case, prediction)

    assert score.metric_accuracy == 1.0
    assert score.finding_recall == 1.0
    assert score.finding_partial_matches == 1
    assert score.finding_weighted_score == 0.5
    assert score.evidence_page_accuracy == 1.0
    assert score.unsupported_finding_rate == 0.0


def test_absolute_tolerance_supports_percentage_points():
    metric = ExpectedMetric(
        metric_code="gross_margin",
        period="2025",
        value=54.5,
        page=3,
        tolerance=0.5,
        tolerance_mode="absolute",
        status="verified",
    )
    case = EvalCase(
        case_id="percentage-case",
        company="Issuer",
        industry="manufacturing",
        split="validation",
        language="simplified_zh",
        source_filename="issuer.pdf",
        expected_page_count=3,
        expected_metrics=[metric],
    )

    score = score_prediction(
        case,
        {"metrics": [{"metric_code": "gross_margin", "period": "2025", "value": 55.0}]},
    )

    assert score.metric_accuracy == 1.0


def test_prediction_builder_includes_grounded_prospectus_risks(tmp_path):
    import json

    (tmp_path / "financial_kb.json").write_text(
        json.dumps({"statement_facts": []}), encoding="utf-8"
    )
    (tmp_path / "metrics.json").write_text("[]", encoding="utf-8")
    (tmp_path / "risk_findings.json").write_text("[]", encoding="utf-8")
    (tmp_path / "prospectus_analysis.json").write_text(
        json.dumps(
            {
                "dossier": {
                    "topic_findings": {
                        "compliance": [
                            {
                                "statement": "公司未完全缴纳社会保险及住房公积金。",
                                "evidence": [
                                    {"evidence_id": "ev-social", "page_number": 52}
                                ],
                            }
                        ]
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    prediction = build_prediction(tmp_path)

    assert prediction["findings"] == [
        {
            "topic": "social_insurance_noncompliance",
            "risk_level": "high",
            "pages": [52],
            "evidence_ids": ["ev-social", "page:52"],
        }
    ]


def test_prediction_builder_does_not_add_ungrounded_keyword_hits(tmp_path):
    import json

    (tmp_path / "financial_kb.json").write_text(
        json.dumps({"statement_facts": []}), encoding="utf-8"
    )
    (tmp_path / "metrics.json").write_text("[]", encoding="utf-8")
    (tmp_path / "risk_findings.json").write_text("[]", encoding="utf-8")
    (tmp_path / "prospectus_analysis.json").write_text(
        json.dumps({"summary": "需要核查第三方付款"}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert build_prediction(tmp_path)["findings"] == []


def test_prediction_builder_keeps_summary_and_detail_risk_pages(tmp_path):
    import json

    for name, payload in (
        ("financial_kb.json", {"statement_facts": []}),
        ("metrics.json", []),
        ("risk_findings.json", []),
        (
            "pages.json",
            [
                {"page": 18, "text": "来自前五大客户的收入占比为28.6%。"},
                {"page": 139, "text": "前五大客户及最大客户的详细资料如下。"},
            ],
        ),
    ):
        (tmp_path / name).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    prediction = build_prediction(tmp_path)
    customer = next(
        item
        for item in prediction["findings"]
        if item["topic"] == "customer_concentration"
    )

    assert customer["pages"] == [18, 139]
