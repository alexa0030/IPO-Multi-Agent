from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .follow_up import FollowUpRequest


class CrossAgentConflict(BaseModel):
    conflict_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    finding_ids: list[str] = Field(min_length=1)
    description: str = Field(min_length=1)
    status: Literal[
        "consistent",
        "partially_consistent",
        "conflicted",
        "insufficient_evidence",
    ]
    resolution: str | None = None


class Assessment(BaseModel):
    conclusion: str = Field(min_length=1)
    confidence: Literal["low", "medium", "high"]
    evidence_ids: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    review_status: Literal[
        "pass",
        "conditional_pass",
        "insufficient_evidence",
        "high_risk",
    ]
    historical_financial_assessment: Assessment
    future_earning_assessment: Assessment
    negative_matter_assessment: Assessment
    conflicts: list[CrossAgentConflict] = Field(default_factory=list)
    approved_finding_ids: list[str] = Field(default_factory=list)
    rejected_finding_ids: list[str] = Field(default_factory=list)
    follow_up_requests: list[FollowUpRequest] = Field(default_factory=list)
    key_strengths: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    p0_questions: list[str] = Field(default_factory=list)
    p1_questions: list[str] = Field(default_factory=list)
    p2_questions: list[str] = Field(default_factory=list)
