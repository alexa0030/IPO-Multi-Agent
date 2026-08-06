from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class LegalResearchTopic(StrEnum):
    OWNERSHIP_CONTROL = "ownership_control"
    SUBSIDIARY_STRUCTURE = "subsidiary_structure"
    RELATED_PARTY = "related_party"
    LITIGATION_PENALTY = "litigation_penalty"
    LICENSE_IP = "license_ip"
    GOVERNANCE_INTERNAL_CONTROL = "governance_internal_control"


class LegalEntity(BaseModel):
    entity_id: str
    name_cn: str
    name_en: str | None = None
    aliases: list[str] = Field(default_factory=list)
    entity_type: Literal[
        "issuer", "controller", "controlling_shareholder", "shareholder",
        "subsidiary", "related_party", "director", "executive"
    ]
    registration_place: str | None = None
    registration_number: str | None = None
    ownership_percentage: float | None = None
    parent_entity_id: str | None = None
    importance: Literal["core", "major", "ordinary"] = "ordinary"
    search_enabled: bool = False
    prospectus_evidence_ids: list[str] = Field(default_factory=list)


class LegalProfileFact(BaseModel):
    profile_fact_id: str
    research_topic: LegalResearchTopic
    entity_ids: list[str] = Field(default_factory=list)
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)
    fact_status: Literal[
        "prospectus_disclosed", "externally_confirmed", "partially_confirmed", "unable_to_verify"
    ]


class LegalClaim(BaseModel):
    claim_id: str
    research_topic: LegalResearchTopic
    related_entity_ids: list[str] = Field(default_factory=list)
    claim: str
    verification_question: str
    prospectus_evidence_ids: list[str] = Field(default_factory=list)
    verification_status: Literal[
        "pending", "supported", "partially_supported", "contradicted", "insufficient_evidence"
    ] = "pending"


class LegalFinding(BaseModel):
    finding_id: str
    research_topic: LegalResearchTopic
    entity_ids: list[str] = Field(default_factory=list)
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)
    issue_status: Literal[
        "confirmed_issue", "potential_issue", "disclosed_and_remediated",
        "routine_or_immaterial", "no_material_issue_identified_in_reviewed_scope",
        "unable_to_verify",
    ]
    cross_check_topics: list[str] = Field(default_factory=list)
    legal_scope_note: str | None = None


class LegalSourceBlock(BaseModel):
    block_id: str
    page_number: int
    text: str
    section_path: list[str] = Field(default_factory=list)


class LegalSeedContext(BaseModel):
    company_name: str
    topic_blocks: dict[LegalResearchTopic, list[LegalSourceBlock]] = Field(default_factory=dict)
    company_profile_summary: dict = Field(default_factory=dict)
    financial_related_party_summary: dict = Field(default_factory=dict)
    industry_regulatory_summary: dict = Field(default_factory=dict)


class LegalResearchQuestion(BaseModel):
    question_id: str
    research_topic: LegalResearchTopic
    question: str
    priority: Literal["P0", "P1", "P2"]
    expected_evidence: list[str] = Field(min_length=1)


class LegalResearchTask(BaseModel):
    task_id: str
    target_agent: Literal["legal_governance"] = "legal_governance"
    objective: str
    questions: list[LegalResearchQuestion] = Field(min_length=1)


class LegalValidationResult(BaseModel):
    valid: bool
    task_valid: bool
    evidence_integrity: bool
    scope_valid: bool
    validation_errors: list[str] = Field(default_factory=list)
    checked_topics: list[LegalResearchTopic] = Field(default_factory=list)


class LegalStageResult(BaseModel):
    job_id: str
    pipeline_status: Literal["completed", "completed_with_fallback", "failed"]
    legal_status: Literal["completed", "partial", "failed"]
    task_source: Literal["fixed"] = "fixed"
    validation: LegalValidationResult
    paths: dict[str, str]
