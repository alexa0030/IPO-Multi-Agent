from __future__ import annotations

from types import SimpleNamespace

from ipo_financial_agent.models_agent import ReportReview
from ipo_financial_agent.pipeline import IPOFinancialPipeline


class _Writer:
    def __init__(self, client: object) -> None:
        self.client = client

    def revise_diligence_draft(self, **_: object) -> str:
        return "revised report"


class _Reviewer:
    def __init__(self, client: object) -> None:
        self.client = client

    def review(self, **_: object) -> ReportReview:
        return ReportReview(passed=True, score=95, summary="quality target met")


def test_passed_report_below_quality_target_is_revised(monkeypatch) -> None:
    monkeypatch.setattr("ipo_financial_agent.pipeline.OpenAICompatibleClient", lambda _: object())
    monkeypatch.setattr("ipo_financial_agent.pipeline.ReportWriterAgent", _Writer)
    monkeypatch.setattr("ipo_financial_agent.pipeline.EvidenceComplianceReviewerAgent", _Reviewer)
    pipeline = IPOFinancialPipeline(SimpleNamespace(llm_configured=True))
    result = pipeline._run_report_revision({
        "company": "Issuer",
        "llm_mode": "on",
        "final_report": "draft",
        "report_review": ReportReview(
            passed=True,
            score=80,
            revision_instructions=["add evidence id"],
        ),
    })
    assert result["report_revision_performed"] is True
    assert result["final_report"] == "revised report"
    assert result["report_review"].score == 95


def test_report_at_quality_target_is_not_rewritten() -> None:
    pipeline = IPOFinancialPipeline(SimpleNamespace())
    result = pipeline._run_report_revision({
        "report_review": ReportReview(
            passed=True,
            score=90,
            revision_instructions=["optional wording"],
        )
    })
    assert result == {"report_revision_performed": False}


def test_writer_revises_only_targeted_markdown_section() -> None:
    class Client:
        def __init__(self) -> None:
            self.calls = 0

        def complete_text(self, **kwargs: object) -> str:
            self.calls += 1
            prompt = str(kwargs["user_prompt"])
            section = prompt.split("待修订章节：\n", 1)[1]
            return section.replace("缺少引用", "已补充待核查标记")

    from ipo_financial_agent.agents.report_writer import ReportWriterAgent

    client = Client()
    report = "# Report\n\n## 一、投资摘要\n缺少引用\n\n## 二、公司基本情况\n保持原文\n"
    revised = ReportWriterAgent(client).revise_diligence_draft(
        report=report,
        revision_instructions=["修订投资摘要中的缺少引用"],
    )
    assert client.calls == 1
    assert "已补充待核查标记" in revised
    assert "## 二、公司基本情况\n保持原文" in revised


def test_revision_candidate_without_score_gain_is_rejected(monkeypatch) -> None:
    class SameScoreReviewer(_Reviewer):
        def review(self, **_: object) -> ReportReview:
            return ReportReview(passed=True, score=80, revision_instructions=["still open"])

    monkeypatch.setattr("ipo_financial_agent.pipeline.OpenAICompatibleClient", lambda _: object())
    monkeypatch.setattr("ipo_financial_agent.pipeline.ReportWriterAgent", _Writer)
    monkeypatch.setattr("ipo_financial_agent.pipeline.EvidenceComplianceReviewerAgent", SameScoreReviewer)
    pipeline = IPOFinancialPipeline(SimpleNamespace(llm_configured=True))
    result = pipeline._run_report_revision({
        "company": "Issuer",
        "llm_mode": "on",
        "final_report": "original report",
        "report_review": ReportReview(
            passed=True, score=80, revision_instructions=["add evidence id"]
        ),
    })
    assert result["report_revision_attempted"] is True
    assert result["report_revision_performed"] is False
    assert "final_report" not in result
