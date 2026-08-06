"""Serial Manager -> Financial -> Reviewer -> Company workflow.

This is the integration boundary used while the Company stage is being
stabilised.  It deliberately keeps the fixed Company task downstream of the
financial reviewer; Manager-generated Company tasks are a later phase.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from ipo_financial_agent.config import Settings, get_settings
from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.storage.json_store import write_json
from ipo_financial_agent.workflow.stage_company import CompanyBusinessStage

ReviewerStage = None


class CompanyPipelineRunResult(BaseModel):
    job_id: str
    pipeline_status: Literal[
        "completed", "completed_with_fallback", "needs_follow_up", "failed"
    ]
    manager_status: str
    financial_status: str
    reviewer_status: str
    company_status: Literal["completed", "failed", "not_run"]
    financial_task_source: Literal["manager", "fixed"]
    company_task_source: Literal["fixed"] = "fixed"
    stage_outputs: dict[str, str]
    errors: list[str] = []


class ManagerFinancialReviewerCompanyStage:
    """Run the currently approved stages in a debuggable serial order."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(
        self,
        *,
        pdf_path: str | Path,
        company_name: str,
        manager_client: OpenAICompatibleClient | None = None,
        company_llm_mode: str = "auto",
    ) -> CompanyPipelineRunResult:
        global ReviewerStage
        if ReviewerStage is None:
            from ipo_financial_agent.workflow.stage_reviewer import ReviewerStage as _ReviewerStage

            ReviewerStage = _ReviewerStage
        upstream = ReviewerStage(self.settings).run(
            pdf_path=pdf_path,
            company_name=company_name,
            manager_client=manager_client,
        )
        root = self.settings.output_dir / upstream.job_id
        stage_outputs = {
            "manager": str(root / "stage_manager"),
            "financial": str(root / "stage_financial"),
            "reviewer": str(root / "stage_reviewer"),
        }
        errors: list[str] = []
        company_status: Literal["completed", "failed", "not_run"] = "not_run"

        # A structurally failed upstream contract is not safe input for the
        # Company/Financial cross-review path. Other reviewer outcomes still
        # run Company so missing evidence remains visible and auditable.
        if upstream.pipeline_status != "failed":
            try:
                company = CompanyBusinessStage(self.settings).run(
                    pdf_path=pdf_path,
                    company_name=company_name,
                    llm_mode=company_llm_mode,
                )
                if company["job_id"] != upstream.job_id:
                    raise RuntimeError("Company stage job_id differs from upstream job_id")
                company_status = "completed"
                stage_outputs["company"] = str(root / "stage_company")
            except Exception as exc:
                company_status = "failed"
                errors.append(f"Company stage failed: {type(exc).__name__}: {exc}")

        if upstream.pipeline_status == "failed" or company_status == "failed":
            pipeline_status = "failed"
        else:
            pipeline_status = upstream.pipeline_status

        result = CompanyPipelineRunResult(
            job_id=upstream.job_id,
            pipeline_status=pipeline_status,
            manager_status=upstream.manager_status,
            financial_status=upstream.financial_status,
            reviewer_status=upstream.reviewer_status,
            company_status=company_status,
            financial_task_source=upstream.task_source,
            stage_outputs=stage_outputs,
            errors=errors,
        )
        write_json(root / "company_pipeline_run_result.json", result)
        return result
