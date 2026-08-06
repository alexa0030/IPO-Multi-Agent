from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from .research_task import AgentName


class Finding(BaseModel):
    finding_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    agent: AgentName
    topic: str = Field(min_length=1)
    title: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    interpretation: str = Field(min_length=1)
    alternative_explanations: list[str] = Field(default_factory=list)
    required_checks: list[str] = Field(default_factory=list)
    cross_check_topics: list[str] = Field(default_factory=list)
    risk_level: Literal["positive", "low", "medium", "high"]
    confidence: Literal["low", "medium", "high"]
    status: Literal[
        "pending_review",
        "approved",
        "rejected",
        "needs_follow_up",
    ] = "pending_review"

    @model_validator(mode="after")
    def deduplicate_lists(self) -> Self:
        self.evidence_ids = list(dict.fromkeys(self.evidence_ids))
        self.alternative_explanations = list(dict.fromkeys(self.alternative_explanations))
        self.required_checks = list(dict.fromkeys(self.required_checks))
        self.cross_check_topics = list(dict.fromkeys(self.cross_check_topics))
        return self
