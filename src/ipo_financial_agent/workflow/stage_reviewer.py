"""Manager -> Financial -> deterministic Reviewer staged workflow."""

from __future__ import annotations

from pathlib import Path

from ipo_financial_agent.agents.research_reviewer import ResearchReviewerAgent
from ipo_financial_agent.config import Settings, get_settings
from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.schemas import (
    FinancialAgentResult,
    ManagerFinancialReviewerRunResult,
    ResearchTask,
    ReviewerInputManifest,
)
from ipo_financial_agent.storage.json_store import write_json
from ipo_financial_agent.workflow.stage_manager_financial import ManagerFinancialStage


class ReviewerStage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(
        self, *, pdf_path: str | Path, company_name: str,
        manager_client: OpenAICompatibleClient | None = None,
    ) -> ManagerFinancialReviewerRunResult:
        upstream = ManagerFinancialStage(self.settings).run(
            pdf_path=pdf_path,
            company_name=company_name,
            llm_mode="on",
            manager_client=manager_client,
        )
        root = self.settings.output_dir / upstream.job_id
        task = ResearchTask.model_validate_json(
            (root / "stage_financial/financial_task.json").read_text(encoding="utf-8")
        )
        financial = FinancialAgentResult.model_validate_json(
            (root / "stage_financial/financial_agent_result.json").read_text(encoding="utf-8")
        )
        review, validation = ResearchReviewerAgent().review_financial_contract(
            task=task, result=financial
        )
        reviewer_dir = root / "stage_reviewer"
        reviewer_dir.mkdir(parents=True, exist_ok=True)
        manifest = ReviewerInputManifest(
            task_id=task.task_id,
            question_ids=[item.question_id for item in task.questions],
            finding_ids=[item.finding_id for item in financial.findings],
            evidence_ids=[item.evidence_id for item in financial.evidences],
            financial_completion_status=financial.completion_status,
        )
        write_json(reviewer_dir / "reviewer_input.json", manifest)
        write_json(reviewer_dir / "review_result.json", review)
        write_json(reviewer_dir / "follow_up_requests.json", review.follow_up_requests)
        write_json(reviewer_dir / "reviewer_validation.json", validation)
        if review.review_status == "pass":
            pipeline_status = (
                "completed_with_fallback"
                if upstream.manager_validation.fallback_used else "completed"
            )
        elif review.review_status in {"conditional_pass", "high_risk"}:
            pipeline_status = "needs_follow_up"
        else:
            pipeline_status = "failed"
        result = ManagerFinancialReviewerRunResult(
            job_id=upstream.job_id,
            pipeline_status=pipeline_status,
            manager_status=upstream.manager_status,
            financial_status=upstream.financial_status,
            reviewer_status=review.review_status,
            task_source=upstream.task_source,
        )
        write_json(root / "manager_financial_reviewer_run_result.json", result)
        return result
