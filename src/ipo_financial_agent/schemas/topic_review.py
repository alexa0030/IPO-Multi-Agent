from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

class ReviewedTopicResult(BaseModel):
    topic_id: str
    topic_name: str
    reviewed_finding_ids: list[str] = Field(default_factory=list)
    reviewed_evidence_ids: list[str] = Field(default_factory=list)
    conclusion_nature: Literal["strength", "risk", "mixed", "neutral", "insufficient_evidence"]
    consistency_status: Literal["consistent", "partially_consistent", "conflicted", "insufficient_evidence"]
    integrated_statement: str
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    required_checks: list[str] = Field(default_factory=list)
    assessment_axes: list[Literal["historical_financial", "future_earning", "negative_matter"]] = Field(default_factory=list)
    suggested_severity: Literal["positive", "low", "medium", "high"] = "medium"
    confidence: Literal["low", "medium", "high"] = "low"

class TopicReviewValidation(BaseModel):
    topic_id: str
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
