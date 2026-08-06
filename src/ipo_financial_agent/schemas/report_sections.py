from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from .report import ReportSection

class ReportSectionMaterial(BaseModel):
    section: ReportSection
    title: str
    profile_facts: list[dict] = Field(default_factory=list)
    financial_tables: list[dict] = Field(default_factory=list)
    metrics: list[dict] = Field(default_factory=list)
    reviewed_topics: list[dict] = Field(default_factory=list)
    strength_points: list[dict] = Field(default_factory=list)
    risk_points: list[dict] = Field(default_factory=list)
    mixed_points: list[dict] = Field(default_factory=list)
    evidence_gaps: list[dict] = Field(default_factory=list)
    due_diligence_questions: list[dict] = Field(default_factory=list)
    allowed_finding_ids: list[str] = Field(default_factory=list)
    allowed_evidence_ids: list[str] = Field(default_factory=list)
    generation_method: Literal["deterministic", "qwen", "hybrid"] = "deterministic"

class GeneratedReportSection(BaseModel):
    section: ReportSection
    title: str
    markdown: str
    used_profile_fact_ids: list[str] = Field(default_factory=list)
    used_table_ids: list[str] = Field(default_factory=list)
    used_metric_ids: list[str] = Field(default_factory=list)
    used_topic_ids: list[str] = Field(default_factory=list)
    used_finding_ids: list[str] = Field(default_factory=list)
    used_evidence_ids: list[str] = Field(default_factory=list)
    generation_method: Literal["deterministic", "qwen", "hybrid"] = "deterministic"
    generation_status: Literal["completed", "fallback", "failed"] = "completed"

class SectionValidationResult(BaseModel):
    section: ReportSection
    valid: bool
    invalid_finding_ids: list[str] = Field(default_factory=list)
    invalid_evidence_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
