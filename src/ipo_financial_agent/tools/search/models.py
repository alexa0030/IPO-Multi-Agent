"""Data contracts for reproducible web research."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SearchQuery(BaseModel):
    query: str = Field(min_length=2)
    topic: str
    domains: list[str] = Field(default_factory=list)
    max_results: int = Field(default=5, ge=1, le=10)
    priority: Literal["P0", "P1", "P2"] = "P1"
    purpose: str = ""
    required: bool = True


class SearchResult(BaseModel):
    query: str
    topic: str
    title: str
    content: str
    url: str
    publisher: str = ""
    published_at: str | None = None
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source_tier: Literal["official", "primary", "secondary", "unknown"] = (
        "unknown"
    )
    confidence: float = Field(default=0.5, ge=0, le=1)

    @field_validator("url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("search result URL must use HTTP(S)")
        return value


class SearchRun(BaseModel):
    provider: str
    cost_mode: str
    queries: list[SearchQuery] = Field(default_factory=list)
    results: list[SearchResult] = Field(default_factory=list)
    covered_topics: list[str] = Field(default_factory=list)
    missing_topics: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
