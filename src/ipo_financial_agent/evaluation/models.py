from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ExpectedMetric(BaseModel):
    metric_code: str
    period: str
    value: float
    unit: str | None = None
    currency: str | None = None
    page: int = Field(ge=1)
    tolerance: float = Field(default=0.01, ge=0)
    tolerance_mode: Literal["relative", "absolute"] = "relative"
    status: Literal["candidate", "verified"] = "candidate"


class ExpectedFinding(BaseModel):
    topic: str
    expected_fact: str
    risk_level: Literal["low", "medium", "high"]
    pages: list[int] = Field(min_length=1)
    evidence_excerpt: str = Field(min_length=6)
    should_challenge: bool = False
    status: Literal["candidate", "verified"] = "candidate"


class EvalCase(BaseModel):
    case_id: str
    company: str
    company_en: str | None = None
    industry: str
    split: Literal["development", "validation", "test"]
    language: Literal["simplified_zh", "traditional_zh", "mixed"]
    source_filename: str
    source_url: str | None = None
    expected_page_count: int = Field(ge=1)
    expected_metrics: list[ExpectedMetric] = Field(default_factory=list)
    expected_findings: list[ExpectedFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def verified_gold_only_outside_development(self) -> "EvalCase":
        if self.split == "test":
            candidates = [
                item
                for item in [*self.expected_metrics, *self.expected_findings]
                if item.status != "verified"
            ]
            if candidates:
                raise ValueError("test cases may contain verified gold labels only")
        return self
