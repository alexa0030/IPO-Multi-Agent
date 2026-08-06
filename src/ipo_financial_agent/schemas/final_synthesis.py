from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field
from .topic_review import ReviewedTopicResult

class FinalAssessment(BaseModel):
    title: str
    conclusion: str
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    related_topic_ids: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "low"

class FinalPoint(BaseModel):
    point_id: str
    title: str
    statement: str
    finding_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    involved_agents: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "low"

class DueDiligenceQuestion(BaseModel):
    question_id: str
    priority: Literal["P0", "P1", "P2"]
    question: str
    reason: str
    related_finding_ids: list[str] = Field(default_factory=list)
    related_topic_ids: list[str] = Field(default_factory=list)
    related_entity_ids: list[str] = Field(default_factory=list)
    required_materials: list[str] = Field(default_factory=list)
    decision_impact: str = ""
    target_owner: Literal["company", "financial", "industry", "legal", "management", "auditor", "legal_adviser"] = "company"

class FinalSynthesisContext(BaseModel):
    company_name: str = ""
    job_id: str = ""
    reviewed_topics: list[ReviewedTopicResult] = Field(default_factory=list)
    standalone_findings: list[Any] = Field(default_factory=list)
    evidence_gaps: list[Any] = Field(default_factory=list)
    existing_follow_up_requests: list[Any] = Field(default_factory=list)
    unresolved_p0_question_ids: list[str] = Field(default_factory=list)
    unresolved_p1_question_ids: list[str] = Field(default_factory=list)
    agent_statuses: list[Any] = Field(default_factory=list)
    deterministic_high_risk_finding_ids: list[str] = Field(default_factory=list)

class FinalSynthesisDraft(BaseModel):
    historical_financial_assessment: FinalAssessment
    future_earning_assessment: FinalAssessment
    negative_matter_assessment: FinalAssessment
    reviewed_strengths: list[FinalPoint] = Field(default_factory=list)
    reviewed_risks: list[FinalPoint] = Field(default_factory=list)
    reviewed_mixed_points: list[FinalPoint] = Field(default_factory=list)
    additional_evidence_gaps: list[Any] = Field(default_factory=list)
    due_diligence_question_candidates: list[DueDiligenceQuestion] = Field(default_factory=list)
    approved_finding_ids: list[str] = Field(default_factory=list)
    excluded_finding_ids: list[str] = Field(default_factory=list)

class FinalReviewResult(BaseModel):
    review_status: Literal["pass", "conditional_pass", "needs_follow_up", "high_risk", "failed"]
    historical_financial_assessment: FinalAssessment
    future_earning_assessment: FinalAssessment
    negative_matter_assessment: FinalAssessment
    reviewed_topics: list[ReviewedTopicResult] = Field(default_factory=list)
    reviewed_strengths: list[FinalPoint] = Field(default_factory=list)
    reviewed_risks: list[FinalPoint] = Field(default_factory=list)
    reviewed_mixed_points: list[FinalPoint] = Field(default_factory=list)
    evidence_gaps: list[Any] = Field(default_factory=list)
    p0_due_diligence_questions: list[DueDiligenceQuestion] = Field(default_factory=list)
    p1_due_diligence_questions: list[DueDiligenceQuestion] = Field(default_factory=list)
    p2_due_diligence_questions: list[DueDiligenceQuestion] = Field(default_factory=list)
    approved_finding_ids: list[str] = Field(default_factory=list)
    excluded_finding_ids: list[str] = Field(default_factory=list)
