from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from .evidence import Evidence
from .finding import Finding
from .research_task import FinancialResearchTopic


class CompletionCheck(BaseModel):
    criterion: str = Field(min_length=1)
    passed: bool
    evidence_ids: list[str] = Field(default_factory=list)
    note: str | None = None


class QuestionAnswerMapping(BaseModel):
    question_id: str = Field(min_length=1)
    research_topic: FinancialResearchTopic
    finding_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    completion_checks: list[CompletionCheck] = Field(default_factory=list)
    status: Literal["answered", "partially_answered", "unanswered"]
    gap_reason: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        self.finding_ids = list(dict.fromkeys(self.finding_ids))
        self.evidence_ids = list(dict.fromkeys(self.evidence_ids))
        all_checks_pass = bool(self.completion_checks) and all(
            item.passed for item in self.completion_checks
        )
        if self.status == "answered" and (
            not self.finding_ids or not self.evidence_ids or not all_checks_pass
        ):
            raise ValueError("answered mapping requires Findings, Evidence, and passed checks")
        if self.status == "unanswered" and not self.gap_reason:
            raise ValueError("unanswered mapping requires gap_reason")
        return self


class FinancialAgentResult(BaseModel):
    task_id: str = Field(min_length=1)
    evidences: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    question_answer_map: list[QuestionAnswerMapping] = Field(default_factory=list)
    completion_status: Literal["completed", "partial", "failed"]
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        evidence_ids = {item.evidence_id for item in self.evidences}
        for evidence in self.evidences:
            missing_inputs = set(evidence.input_evidence_ids) - evidence_ids
            if missing_inputs:
                raise ValueError(
                    f"calculation Evidence {evidence.evidence_id} has unknown inputs: {sorted(missing_inputs)}"
                )
        finding_by_id = {item.finding_id: item for item in self.findings}
        mapping_by_question = {item.question_id: item for item in self.question_answer_map}
        if len(mapping_by_question) != len(self.question_answer_map):
            raise ValueError("question_answer_map contains duplicate question_id")
        for finding in self.findings:
            missing = set(finding.evidence_ids) - evidence_ids
            if missing:
                raise ValueError(f"finding {finding.finding_id} references unknown Evidence: {sorted(missing)}")
            for question_id in finding.answered_question_ids:
                mapping = mapping_by_question.get(question_id)
                if mapping is None or finding.finding_id not in mapping.finding_ids:
                    raise ValueError(f"Finding/question mapping is not bidirectionally consistent: {finding.finding_id}/{question_id}")
        for mapping in self.question_answer_map:
            unknown_findings = set(mapping.finding_ids) - set(finding_by_id)
            unknown_evidence = set(mapping.evidence_ids) - evidence_ids
            if unknown_findings or unknown_evidence:
                raise ValueError(f"mapping {mapping.question_id} contains unknown references")
            for finding_id in mapping.finding_ids:
                finding = finding_by_id[finding_id]
                if mapping.question_id not in finding.answered_question_ids:
                    raise ValueError(f"Question/Finding mapping is not bidirectionally consistent: {mapping.question_id}/{finding_id}")
                if finding.topic != mapping.research_topic:
                    raise ValueError(f"Question/Finding topic mismatch: {mapping.question_id}/{finding_id}")
        if self.completion_status == "completed" and any(
            item.status != "answered" for item in self.question_answer_map
        ):
            raise ValueError("completed result requires every question to be answered")
        if self.completion_status == "failed" and not self.errors:
            raise ValueError("failed result requires at least one error")
        return self
