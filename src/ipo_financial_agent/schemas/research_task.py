from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

AgentName = Literal[
    "company_business",
    "financial",
    "industry_competition",
    "legal_governance",
]
Priority = Literal["P0", "P1", "P2"]


class ResearchQuestion(BaseModel):
    question_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    priority: Priority
    expected_evidence: list[str] = Field(default_factory=list)

    @field_validator("expected_evidence")
    @classmethod
    def deduplicate_expected_evidence(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class ResearchTask(BaseModel):
    task_id: str = Field(min_length=1)
    target_agent: AgentName
    objective: str = Field(min_length=1)
    questions: list[ResearchQuestion] = Field(min_length=1)
    pdf_topics: list[str] = Field(default_factory=list)
    web_topics: list[str] = Field(default_factory=list)
    completion_criteria: list[str] = Field(default_factory=list)

    @field_validator("pdf_topics", "web_topics", "completion_criteria")
    @classmethod
    def deduplicate_lists(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))
