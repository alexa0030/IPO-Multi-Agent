from __future__ import annotations

from pydantic import BaseModel, Field

from .research_task import AgentName, Priority


class FollowUpRequest(BaseModel):
    follow_up_id: str = Field(min_length=1)
    target_agent: AgentName
    related_finding_ids: list[str] = Field(min_length=1)
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    required_evidence: list[str] = Field(default_factory=list)
    priority: Priority
