from __future__ import annotations

from pathlib import Path

from ipo_financial_agent.schemas import ManagerFinancialReviewerRunResult
from ipo_financial_agent.workflow.stage_company_pipeline import (
    CompanyPipelineRunResult,
    ManagerFinancialReviewerCompanyStage,
)


class _Settings:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir


def _upstream(status: str = "completed") -> ManagerFinancialReviewerRunResult:
    return ManagerFinancialReviewerRunResult(
        job_id="issuer_abcd1234",
        pipeline_status=status,
        manager_status="completed",
        financial_status="completed",
        reviewer_status="pass" if status != "failed" else "failed",
        task_source="manager",
    )


def test_company_stage_runs_after_reviewer(monkeypatch):
    output_dir = Path(__file__).resolve().parents[1] / "work" / "stage_company_pipeline_test"
    calls: list[str] = []

    def fake_reviewer(*args, **kwargs):
        calls.append("reviewer")
        return _upstream()

    def fake_company(*args, **kwargs):
        calls.append("company")
        return {"job_id": "issuer_abcd1234", "output_status": "completed"}

    monkeypatch.setattr(
        "ipo_financial_agent.workflow.stage_company_pipeline.ReviewerStage",
        type("FakeReviewer", (), {"__init__": lambda self, settings: None, "run": fake_reviewer}),
        raising=False,
    )
    monkeypatch.setattr(
        "ipo_financial_agent.workflow.stage_company_pipeline.CompanyBusinessStage.run",
        fake_company,
    )
    result = ManagerFinancialReviewerCompanyStage(_Settings(output_dir)).run(
        pdf_path="issuer.pdf", company_name="Issuer", company_llm_mode="off"
    )
    assert calls == ["reviewer", "company"]
    assert result.pipeline_status == "completed"
    assert result.company_status == "completed"
    assert result.company_task_source == "fixed"
    saved = output_dir / result.job_id / "company_pipeline_run_result.json"
    assert CompanyPipelineRunResult.model_validate_json(saved.read_text("utf-8")) == result


def test_company_stage_is_not_run_after_structural_failure(monkeypatch):
    output_dir = Path(__file__).resolve().parents[1] / "work" / "stage_company_pipeline_test"
    monkeypatch.setattr(
        "ipo_financial_agent.workflow.stage_company_pipeline.ReviewerStage",
        type(
            "FakeReviewer",
            (),
            {
                "__init__": lambda self, settings: None,
                "run": lambda *args, **kwargs: _upstream("failed"),
            },
        ),
        raising=False,
    )
    monkeypatch.setattr(
        "ipo_financial_agent.workflow.stage_company_pipeline.CompanyBusinessStage.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    result = ManagerFinancialReviewerCompanyStage(_Settings(output_dir)).run(
        pdf_path="issuer.pdf", company_name="Issuer"
    )
    assert result.pipeline_status == "failed"
    assert result.company_status == "not_run"
