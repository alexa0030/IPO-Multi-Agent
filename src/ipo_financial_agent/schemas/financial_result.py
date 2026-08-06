from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .evidence import Evidence
from .finding import Finding


class FinancialAgentResult(BaseModel):
    task_id: str = Field(min_length=1)
    answered_question_ids: list[str] = Field(default_factory=list)
    unanswered_questions: list[str] = Field(default_factory=list)
    evidences: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    completion_status: Literal["completed", "partial", "failed"]
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> "FinancialAgentResult":
        self.answered_question_ids = list(dict.fromkeys(self.answered_question_ids))
        known_evidence = {item.evidence_id for item in self.evidences}
        for finding in self.findings:
            missing = set(finding.evidence_ids) - known_evidence
            if missing:
                raise ValueError(
                    f"finding {finding.finding_id} references unknown Evidence: {sorted(missing)}"
                )
        if self.completion_status == "completed" and self.unanswered_questions:
            raise ValueError("completed result cannot contain unanswered questions")
        if self.completion_status == "failed" and not self.errors:
            raise ValueError("failed result requires at least one error")
        return self
