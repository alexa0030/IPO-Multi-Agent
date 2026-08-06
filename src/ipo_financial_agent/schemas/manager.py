from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .research_task import ResearchTask


class ManagerTrendPoint(BaseModel):
    name: str
    period: str
    value: float | None = None
    display_value: str

    model_config = ConfigDict(frozen=True)


class ManagerObservation(BaseModel):
    rule_id: str
    name: str
    severity: str
    description: str

    model_config = ConfigDict(frozen=True)


class ManagerFinancialSummary(BaseModel):
    reporting_periods: tuple[str, ...] = ()
    revenue_trend: tuple[ManagerTrendPoint, ...] = ()
    gross_margin_trend: tuple[ManagerTrendPoint, ...] = ()
    net_profit_trend: tuple[ManagerTrendPoint, ...] = ()
    operating_cash_flow_trend: tuple[ManagerTrendPoint, ...] = ()
    balance_sheet_highlights: tuple[ManagerTrendPoint, ...] = ()
    triggered_observations: tuple[ManagerObservation, ...] = ()

    model_config = ConfigDict(frozen=True)


class ManagerContext(BaseModel):
    company_name: str = Field(min_length=1)
    company_overview: str = ""
    business_summary: str = ""
    document_outline: tuple[str, ...] = ()
    risk_factor_summary: tuple[str, ...] = ()
    financial_summary: ManagerFinancialSummary

    model_config = ConfigDict(frozen=True)


class CompanyResearchProfile(BaseModel):
    industry: str = Field(min_length=1)
    sub_industry: str | None = None
    business_type: str = Field(min_length=1)
    capital_intensity: Literal["low", "medium", "high", "unknown"] = "unknown"
    financial_characteristics: list[str] = Field(default_factory=list)


class ResearchPlan(BaseModel):
    company_name: str = Field(min_length=1)
    company_profile: CompanyResearchProfile
    key_research_focus: list[str] = Field(min_length=1)
    tasks: list[ResearchTask] = Field(min_length=1)
    planning_notes: list[str] = Field(default_factory=list)


class ManagerPlanArtifact(BaseModel):
    plan: ResearchPlan | None = None
    raw_response: str = ""
    parse_error: str | None = None


class ManagerValidationResult(BaseModel):
    plan_valid: bool
    fallback_used: bool
    validation_errors: list[str] = Field(default_factory=list)
    selected_task_id: str = Field(min_length=1)
    task_source: Literal["manager", "fixed"]
    manager_task_id: str | None = None
    baseline_topics_covered: list[str] = Field(default_factory=list)
    baseline_topics_missing: list[str] = Field(default_factory=list)
    raw_response: str | None = None


class ManagerFinancialRunResult(BaseModel):
    job_id: str
    pipeline_status: Literal["completed", "completed_with_fallback", "failed"]
    manager_status: Literal["completed", "failed_validation", "failed_parse", "failed_runtime"]
    financial_status: Literal["completed", "partial", "failed"]
    task_source: Literal["manager", "fixed"]
    manager_validation: ManagerValidationResult
