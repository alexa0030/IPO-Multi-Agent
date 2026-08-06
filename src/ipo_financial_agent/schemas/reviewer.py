from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FindingReview(BaseModel):
    finding_id: str = Field(min_length=1)
    decision: Literal["approved", "rejected", "needs_follow_up"]
    reasons: list[str] = Field(default_factory=list)
    evidence_ids_checked: list[str] = Field(default_factory=list)


class ReviewerInputManifest(BaseModel):
    task_id: str = Field(min_length=1)
    question_ids: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    financial_completion_status: Literal["completed", "partial", "failed"]


class ReviewerValidationResult(BaseModel):
    input_valid: bool
    evidence_integrity: bool
    question_coverage_complete: bool
    finding_quality_complete: bool
    validation_errors: list[str] = Field(default_factory=list)
    reviewed_question_ids: list[str] = Field(default_factory=list)
    accepted_question_ids: list[str] = Field(default_factory=list)
    rejected_question_ids: list[str] = Field(default_factory=list)
    finding_reviews: list[FindingReview] = Field(default_factory=list)


class ManagerFinancialReviewerRunResult(BaseModel):
    job_id: str
    pipeline_status: Literal[
        "completed", "completed_with_fallback", "needs_follow_up", "failed"
    ]
    manager_status: Literal[
        "completed", "failed_validation", "failed_parse", "failed_runtime"
    ]
    financial_status: Literal["completed", "partial", "failed"]
    reviewer_status: Literal[
        "pass", "conditional_pass", "insufficient_evidence", "high_risk", "failed"
    ]
    task_source: Literal["manager", "fixed"]
