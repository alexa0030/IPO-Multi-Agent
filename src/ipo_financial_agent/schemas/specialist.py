from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator

from .evidence import Evidence
from .finding import Finding
from .research_task import AgentName


class SpecialistResearchResult(BaseModel):
    """Canonical boundary result produced by one specialist execution."""

    task_id: str = Field(min_length=1)
    agent: AgentName
    evidences: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence_references(self) -> Self:
        evidence_ids = {item.evidence_id for item in self.evidences}
        missing = {
            evidence_id
            for finding in self.findings
            for evidence_id in finding.evidence_ids
            if evidence_id not in evidence_ids
        }
        if missing:
            raise ValueError(f"specialist findings reference missing evidence: {sorted(missing)}")
        self.open_questions = list(
            dict.fromkeys(item.strip() for item in self.open_questions if item.strip())
        )
        return self
