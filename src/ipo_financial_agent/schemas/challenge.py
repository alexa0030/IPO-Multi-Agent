from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .research_task import AgentName, Priority


class Challenge(BaseModel):
    """Canonical, routable evidence challenge emitted by the Skeptic."""

    challenge_id: str = Field(min_length=1)
    target_agent: AgentName
    finding_id: str | None = None
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    required_evidence: list[str] = Field(default_factory=list)
    priority: Priority
    status: Literal["open", "resolved", "unresolved"] = "open"
    response_finding_ids: list[str] = Field(default_factory=list)
    response_evidence_ids: list[str] = Field(default_factory=list)

    @field_validator(
        "required_evidence", "response_finding_ids", "response_evidence_ids"
    )
    @classmethod
    def deduplicate_lists(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))
