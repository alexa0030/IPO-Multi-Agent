from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field
from .final_synthesis import FinalAssessment, FinalPoint, FinalReviewResult, DueDiligenceQuestion
from .report import ReportSectionCoverage
from .topic_review import ReviewedTopicResult

class ReportMaterialPackV1(BaseModel):
    company_name: str = ""
    job_id: str = ""
    company_profile_facts: list[Any] = Field(default_factory=list)
    industry_profile_facts: list[Any] = Field(default_factory=list)
    legal_profile_facts: list[Any] = Field(default_factory=list)
    entity_registry: list[Any] = Field(default_factory=list)
    financial_tables: list[Any] = Field(default_factory=list)
    deterministic_metrics: list[Any] = Field(default_factory=list)
    reviewed_topics: list[ReviewedTopicResult] = Field(default_factory=list)
    reviewed_strengths: list[FinalPoint] = Field(default_factory=list)
    reviewed_risks: list[FinalPoint] = Field(default_factory=list)
    reviewed_mixed_points: list[FinalPoint] = Field(default_factory=list)
    historical_financial_assessment: FinalAssessment
    future_earning_assessment: FinalAssessment
    negative_matter_assessment: FinalAssessment
    evidence_gaps: list[Any] = Field(default_factory=list)
    due_diligence_questions: list[DueDiligenceQuestion] = Field(default_factory=list)
    finding_index: list[Any] = Field(default_factory=list)
    evidence_index: list[Any] = Field(default_factory=list)
    section_coverage: list[ReportSectionCoverage] = Field(default_factory=list)
    final_review_status: str
