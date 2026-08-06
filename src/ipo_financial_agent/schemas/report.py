from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReportSection(StrEnum):
    EXECUTIVE_SUMMARY = "executive_summary"
    COMPANY_DEVELOPMENT = "company_development"
    OWNERSHIP_AND_GROUP = "ownership_and_group"
    BUSINESS_AND_PRODUCTS = "business_and_products"
    BUSINESS_MODEL_CUSTOMERS_SUPPLIERS = "business_model_customers_suppliers"
    INDUSTRY_AND_COMPETITION = "industry_and_competition"
    FINANCIAL_ANALYSIS = "financial_analysis"
    LEGAL_AND_GOVERNANCE = "legal_and_governance"
    INVESTMENT_LOGIC = "investment_logic"
    RISKS_AND_UNCERTAINTIES = "risks_and_uncertainties"
    DUE_DILIGENCE_QUESTIONS = "due_diligence_questions"
    EVIDENCE_APPENDIX = "evidence_appendix"


class FindingNature(StrEnum):
    STRENGTH = "strength"
    RISK = "risk"
    MIXED = "mixed"
    NEUTRAL_OBSERVATION = "neutral_observation"


class ReportSectionRequirement(BaseModel):
    section: ReportSection
    required_material_types: list[str] = Field(default_factory=list)
    optional_material_types: list[str] = Field(default_factory=list)
    minimum_evidence_count: int = Field(default=0, ge=0)


class ReportSectionCoverage(BaseModel):
    section: ReportSection
    status: Literal["complete", "partial", "incomplete"]
    available_material_ids: list[str] = Field(default_factory=list)
    available_material_types: list[str] = Field(default_factory=list)
    missing_material_types: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    notes: list[str] = Field(default_factory=list)


class ReportCoverageAudit(BaseModel):
    company: str = ""
    sections: list[ReportSectionCoverage] = Field(default_factory=list)
    complete_count: int = 0
    partial_count: int = 0
    incomplete_count: int = 0
    positive_finding_count: int = 0
    risk_finding_count: int = 0
    mixed_finding_count: int = 0
    neutral_finding_count: int = 0
    evidence_gap_count: int = 0
    follow_up_count: int = 0


class ReportMaterialPackV0(BaseModel):
    company: str = ""
    company_profile_facts: list[Any] = Field(default_factory=list)
    industry_profile_facts: list[Any] = Field(default_factory=list)
    legal_profile_facts: list[Any] = Field(default_factory=list)
    financial_tables: list[Any] = Field(default_factory=list)
    deterministic_metrics: list[Any] = Field(default_factory=list)
    strength_findings: list[Any] = Field(default_factory=list)
    risk_findings: list[Any] = Field(default_factory=list)
    mixed_findings: list[Any] = Field(default_factory=list)
    neutral_findings: list[Any] = Field(default_factory=list)
    claim_assessments: list[Any] = Field(default_factory=list)
    evidence_gaps: list[Any] = Field(default_factory=list)
    follow_up_requests: list[Any] = Field(default_factory=list)
    evidence_index: list[Any] = Field(default_factory=list)
    finding_index: list[Any] = Field(default_factory=list)
    section_coverage: list[ReportSectionCoverage] = Field(default_factory=list)
