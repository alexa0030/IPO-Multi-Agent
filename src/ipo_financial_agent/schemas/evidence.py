from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator


class Evidence(BaseModel):
    evidence_id: str = Field(min_length=1)
    source_type: Literal["prospectus", "web", "calculation", "company_official"]
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None
    url: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    formula: str | None = None
    input_evidence_ids: list[str] = Field(default_factory=list)
    raw_value: Any | None = None
    source_quality: Literal["A", "B", "C", "D"]
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_source_trace(self) -> Self:
        if self.source_type == "prospectus" and self.page_number is None:
            raise ValueError("prospectus evidence requires page_number")
        if self.source_type in {"web", "company_official"}:
            if not self.url or not self.url.startswith(("http://", "https://")):
                raise ValueError("web evidence requires a real http(s) URL")
        if self.source_type == "calculation":
            if not self.formula:
                raise ValueError("calculation evidence requires formula")
            if not self.input_evidence_ids:
                raise ValueError("calculation evidence requires input_evidence_ids")
        self.input_evidence_ids = list(dict.fromkeys(self.input_evidence_ids))
        return self
