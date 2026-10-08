from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    size_bytes: int


class JobCreateRequest(BaseModel):
    document_id: str = Field(min_length=1)
    company: str = Field(min_length=1, max_length=200)
    llm_mode: Literal["auto", "on", "off"] = "auto"


class JobResponse(BaseModel):
    job_id: str
    document_id: str
    company: str
    llm_mode: Literal["auto", "on", "off"]
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None
    error_message: str | None = None


class ReportResponse(BaseModel):
    job_id: str
    markdown: str
