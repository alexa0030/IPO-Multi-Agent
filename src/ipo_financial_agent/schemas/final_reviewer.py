from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CoverageGateResult(BaseModel):
    allowed: bool
    blocking_gaps: list[str] = Field(default_factory=list)
    retained_gaps: list[str] = Field(default_factory=list)
    remediation_targets: dict[str, str] = Field(default_factory=dict)


class FinalReviewInput(BaseModel):
    strength_findings: list[Any] = Field(default_factory=list)
    risk_findings: list[Any] = Field(default_factory=list)
    mixed_findings: list[Any] = Field(default_factory=list)
    important_neutral_findings: list[Any] = Field(default_factory=list)
    claim_assessments: list[Any] = Field(default_factory=list)
    evidence_gaps: list[Any] = Field(default_factory=list)
    follow_up_requests: list[Any] = Field(default_factory=list)
    finding_index: list[Any] = Field(default_factory=list)
    evidence_index: list[Any] = Field(default_factory=list)
    agent_validation_summaries: list[Any] = Field(default_factory=list)


class TopicReviewPacket(BaseModel):
    review_topic: str
    review_question: str
    finding_ids: list[str] = Field(default_factory=list)
    findings: list[Any] = Field(default_factory=list)
    evidence_summaries: list[Any] = Field(default_factory=list)
    positive_material_ids: list[str] = Field(default_factory=list)
    negative_material_ids: list[str] = Field(default_factory=list)
    mixed_material_ids: list[str] = Field(default_factory=list)
    evidence_gaps: list[Any] = Field(default_factory=list)
    follow_up_requests: list[Any] = Field(default_factory=list)


class TopicPacketValidation(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    checked_topics: list[str] = Field(default_factory=list)
