from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class RawTable(BaseModel):
    table_index: int
    rows: list[list[str]] = Field(default_factory=list)
    bbox: list[float] | None = None


class PageData(BaseModel):
    source_file: str
    page: int
    text: str
    tables: list[RawTable] = Field(default_factory=list)


class SectionHit(BaseModel):
    section_type: str
    title: str
    page: int
    keyword: str
    score: float = 1.0


class RawStatementTable(BaseModel):
    table_id: str
    statement_name: str
    statement_type: str
    company: str
    reporting_entity: str | None = None
    entity_scope: str | None = None
    unit: str | None = None
    currency: str | None = None
    pages: list[int]
    rows: list[list[str]]
    row_pages: list[int] = Field(default_factory=list)
    source_file: str
    confidence: float = 0.7

    @field_validator("pages")
    @classmethod
    def validate_pages(cls, value: list[int]) -> list[int]:
        return sorted({int(page) for page in value})


CanonicalTag = Literal[
    "revenue",
    "cost_of_sales",
    "gross_profit",
    "net_profit",
    "selling_expense",
    "administrative_expense",
    "research_expense",
    "finance_expense",
    "cash",
    "inventory",
    "trade_receivable",
    "notes_receivable",
    "other_receivable",
    "fixed_assets",
    "right_of_use_assets",
    "current_assets",
    "total_assets",
    "trade_payable",
    "other_payable",
    "contract_liability",
    "short_term_borrowing",
    "long_term_borrowing",
    "current_liabilities",
    "total_liabilities",
    "net_assets",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "deferred_income",
    "gross_margin",
    "financial_forecast",
    "other",
]


class StatementFact(BaseModel):
    fact_id: str
    document_id: str
    company: str
    reporting_entity: str | None = None
    statement_name: str
    item_name: str
    canonical_tag: CanonicalTag = "other"
    period: str
    value: float | None = None
    raw_value: str
    unit: str | None = None
    currency: str | None = None
    page: int
    note: str | None = None
    entity_scope: str | None = None
    row_order: int | None = None
    source_table_id: str | None = None
    confidence: float = 0.7


class ExtractedNoteTable(BaseModel):
    table_name: str
    topic: str
    page: int
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    source_table_index: int | None = None


class FinancialExplanation(BaseModel):
    content: str
    page: int
    explanation_type: Literal[
        "change_reason",
        "accounting_policy",
        "composition",
        "credit_policy",
        "maturity",
        "impairment",
        "forecast_assumption",
        "risk",
        "other",
    ] = "other"
    confidence: float = 0.7


class FinancialNote(BaseModel):
    note_id: str
    document_id: str
    company: str
    topic: str
    title: str
    information_type: str
    summary: str
    pages: list[int]
    explanations: list[FinancialExplanation] = Field(default_factory=list)
    tables: list[ExtractedNoteTable] = Field(default_factory=list)
    related_fact_ids: list[str] = Field(default_factory=list)
    source_excerpt: str | None = None
    confidence: float = 0.7

    @field_validator("pages")
    @classmethod
    def validate_pages(cls, value: list[int]) -> list[int]:
        return sorted({int(page) for page in value})


class FinancialExtractionResult(BaseModel):
    statement_facts: list[StatementFact] = Field(default_factory=list)
    financial_notes: list[FinancialNote] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MetricResult(BaseModel):
    metric_id: str
    document_id: str
    metric_name: str
    metric_code: str
    period: str
    value: float | None
    display_value: str
    formula: str
    source_fact_ids: list[str] = Field(default_factory=list)
    source_pages: list[int] = Field(default_factory=list)
    status: Literal["ok", "insufficient_data", "warning"] = "ok"


class RiskFinding(BaseModel):
    risk_id: str
    document_id: str
    category: str
    title: str
    severity: Literal["low", "medium", "high"]
    description: str
    evidence_metric_ids: list[str] = Field(default_factory=list)
    evidence_fact_ids: list[str] = Field(default_factory=list)
    source_pages: list[int] = Field(default_factory=list)
    rule_code: str
    assessment_status: Literal[
        "observation", "partially_explained", "unexplained", "contradiction"
    ] = "observation"
    possible_explanations: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    escalation_conditions: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    document_id: str
    company: str
    markdown: str
    cited_pages: list[int] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    model: str | None = None


class PipelineArtifacts(BaseModel):
    document_id: str
    company: str
    pdf_path: str
    pages_json: str
    raw_statements_json: str
    financial_kb_json: str
    metrics_json: str
    risk_findings_json: str
    excel_path: str
    report_path: str | None = None
    document_json: str | None = None
    final_report_path: str | None = None
    due_diligence_workbook_path: str | None = None
    evidence_json: str | None = None
    agent_trace_json: str | None = None
    delivery_manifest_json: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
