import pytest
from pydantic import ValidationError

from ipo_financial_agent.models_agent import (
    Evidence,
    FinancialFinding,
    Finding,
    IndustryAnalysis,
    ResearchTask,
)
from ipo_financial_agent.research import (
    financial_research_patch,
    industry_research_patch,
)
from ipo_financial_agent.storage.evidence_store import (
    EvidenceIntegrityError,
    EvidenceStore,
)


def test_evidence_id_is_stable_and_legacy_page_is_preserved() -> None:
    first = Evidence(
        source_type="prospectus",
        page=42,
        source="prospectus.pdf",
        detail="Top five customers represented 61% of revenue.",
    )
    second = Evidence(
        source_type="prospectus",
        page_number=42,
        source="prospectus.pdf",
        content="Top five customers represented 61% of revenue.",
    )

    assert first.evidence_id == second.evidence_id
    assert first.page_number == 42
    assert second.page == 42


def test_finding_requires_at_least_one_evidence_reference() -> None:
    with pytest.raises(ValidationError):
        Finding(
            agent_name="company_business",
            question="Is customer concentration material?",
            conclusion="Customer concentration is material.",
            evidence_ids=[],
        )


def test_ledger_rejects_unknown_evidence_reference() -> None:
    store = EvidenceStore()
    finding = Finding(
        agent_name="financial_dd",
        question="Is cash conversion weak?",
        conclusion="Cash conversion requires follow-up.",
        evidence_ids=["ev_missing"],
    )

    with pytest.raises(EvidenceIntegrityError, match="missing evidence"):
        store.add_findings([finding])


def test_research_task_normalizes_v03_fields() -> None:
    task = ResearchTask(agent="financial", objective="Review cash conversion")

    assert task.agent_name == "financial"
    assert task.question == "Review cash conversion"
    assert task.task_id.startswith("task_")


def test_financial_adapter_only_publishes_grounded_triggered_findings() -> None:
    evidence = Evidence(source_type="metric", source="cash_conversion", detail="0.41")
    patch = financial_research_patch(
        [
            FinancialFinding(
                rule_id="EQ-001",
                name="净现比偏低",
                triggered=True,
                description="净现比为 0.41。",
                evidence=[evidence],
            ),
            FinancialFinding(
                rule_id="AQ-001",
                name="未触发规则",
                triggered=False,
                evidence=[evidence],
            ),
        ]
    )

    assert len(patch.evidence) == 1
    assert len(patch.findings) == 1
    assert patch.findings[0].evidence_ids == [evidence.evidence_id]


def test_industry_adapter_does_not_publish_unverified_conclusion() -> None:
    patch = industry_research_patch(
        IndustryAnalysis(
            company="Example Holdings",
            industry_overview="外部搜索不可用。",
        )
    )

    assert patch.findings == []
    assert patch.open_questions
