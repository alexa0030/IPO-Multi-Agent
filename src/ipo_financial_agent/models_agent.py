"""Multi-Agent collaboration models: research plans, agent messaging,
forensic findings, analysis results, and investment committee artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

RiskLevel = Literal["Low", "Medium", "High"]
MessageType = Literal["plan", "finding", "question", "challenge", "decision", "info"]
EvidenceSourceType = Literal[
    "prospectus",
    "financial_statement",
    "web",
    "news",
    "calculation",
    "forensic_rule",
    "metric",
    "search",
]
EvidenceStrength = Literal["strong", "medium", "weak"]
ResearchPriority = Literal["high", "medium", "low", "normal"]
DiligencePriority = Literal["P0", "P1", "P2"]
DiligenceVerdict = Literal["proceed", "conditional_proceed", "pause", "stop"]
AssessmentGrade = Literal["strong", "moderate", "weak", "insufficient_evidence"]


# ==================== Agent Messaging (Event Bus) ====================


class AgentMessage(BaseModel):
    """Inter-agent communication message — a research artifact, not a chat log.

    message_type semantics:
        plan:      Research Manager task assignment
        finding:   Agent reports a discovery/anomaly
        question:  Agent asks another agent for clarification
        challenge: Reviewer challenges an agent's conclusion
        decision:  Final decision (e.g. risk level)
        info:      General status update
    """

    sender: str = ""
    receiver: str = "all"
    content: str = ""
    message_type: MessageType = "info"
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = ""


# ==================== Research Plan ====================


class ResearchTask(BaseModel):
    """A single task assigned by the Research Manager to a specialist agent."""

    task_id: str = ""
    agent_name: str = ""
    question: str = ""
    reason: str = ""
    expected_evidence: list[str] = Field(default_factory=list)

    # Backward-compatible names used by the v0.3 pipeline.
    agent: str = ""
    objective: str = ""
    priority: ResearchPriority = "normal"
    sources: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_legacy_fields(self) -> Self:
        self.agent_name = self.agent_name or self.agent
        self.agent = self.agent or self.agent_name
        self.question = self.question or self.objective
        self.objective = self.objective or self.question
        if not self.task_id:
            payload = f"{self.agent_name}|{self.question}".encode()
            self.task_id = f"task_{hashlib.sha1(payload).hexdigest()[:12]}"
        return self


class ResearchPlan(BaseModel):
    """Research plan output by the Research Manager Agent."""

    company: str = ""
    tasks: list[ResearchTask] = Field(default_factory=list)
    manager_notes: str = ""
    focus_areas: list[str] = Field(default_factory=list)
    company_specific_hypotheses: list[str] = Field(default_factory=list)


# ==================== Evidence (Unified) ====================


class Evidence(BaseModel):
    """Evidence item linking a finding to its source data.

    Supports multiple source types:
        - prospectus: page number from IPO prospectus PDF
        - web: URL from external search
        - financial_statement: statement type + line item
        - metric: computed metric reference
        - search: search result reference
    """

    evidence_id: str = ""
    source_type: EvidenceSourceType = "prospectus"
    title: str = ""
    content: str = ""
    source_file: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    source_url: str | None = None
    published_at: str | None = None
    retrieved_at: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Backward-compatible fields. They remain until the financial engine and
    # renderers have migrated to the unified Research Ledger.
    page: int = Field(default=0, ge=0)
    source: str = ""
    detail: str = ""

    @model_validator(mode="after")
    def normalize_and_identify(self) -> Self:
        if self.source_type == "prospectus":
            if self.source == "metric":
                self.source_type = "calculation"
            elif self.source in {
                "balance_sheet",
                "income_statement",
                "cash_flow_statement",
                "changes_in_equity",
            }:
                self.source_type = "financial_statement"
        if self.page_number is None and self.page > 0:
            self.page_number = self.page
        if self.page == 0 and self.page_number is not None:
            self.page = self.page_number
        if not self.source_url and self.source.startswith(("http://", "https://")):
            self.source_url = self.source
        if not self.source:
            self.source = self.source_url or self.source_file or ""
        self.content = self.content or self.detail
        self.detail = self.detail or self.content
        self.title = self.title or self.source or self.source_type
        if not self.evidence_id:
            payload = json.dumps(
                {
                    "source_type": self.source_type,
                    "source": self.source,
                    "page": self.page_number,
                    "content": self.content,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
            self.evidence_id = f"ev_{hashlib.sha256(payload).hexdigest()[:16]}"
        return self


class Finding(BaseModel):
    """A research conclusion whose supporting evidence is explicit."""

    finding_id: str = ""
    agent_name: str
    question: str
    conclusion: str
    evidence_ids: list[str] = Field(min_length=1)
    evidence_strength: EvidenceStrength = "medium"
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    finding_nature: Literal["strength", "risk", "mixed", "neutral_observation"] = "neutral_observation"

    @model_validator(mode="after")
    def identify_and_deduplicate(self) -> Self:
        self.evidence_ids = list(dict.fromkeys(self.evidence_ids))
        if not self.finding_id:
            payload = f"{self.agent_name}|{self.question}|{self.conclusion}".encode()
            self.finding_id = f"finding_{hashlib.sha1(payload).hexdigest()[:12]}"
        return self


class ResearchPatch(BaseModel):
    """Append-only result returned by every specialist Agent."""

    task_id: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class Challenge(BaseModel):
    """A routable request from the Skeptic for targeted follow-up research."""

    challenge_id: str = ""
    target_agent: str
    challenged_finding_id: str | None = None
    question: str
    reason: str
    severity: Literal["critical", "important", "minor"] = "important"
    required_evidence: list[str] = Field(default_factory=list)
    resolved: bool = False
    response_finding_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def identify(self) -> Self:
        if not self.challenge_id:
            payload = f"{self.target_agent}|{self.question}|{self.reason}".encode()
            self.challenge_id = f"challenge_{hashlib.sha1(payload).hexdigest()[:12]}"
        return self


class DiligenceQuestion(BaseModel):
    """A prioritized, actionable request for follow-up due diligence."""

    question_id: str = ""
    priority: DiligencePriority
    category: Literal[
        "company_business",
        "financial",
        "industry_competition",
        "legal_governance",
        "other",
    ]
    question: str
    rationale: str
    current_evidence_ids: list[str] = Field(default_factory=list)
    requested_materials: list[str] = Field(default_factory=list)
    downside_if_unresolved: str = ""
    status: Literal["open", "answered", "waived"] = "open"

    @model_validator(mode="after")
    def identify_and_deduplicate(self) -> Self:
        self.current_evidence_ids = list(dict.fromkeys(self.current_evidence_ids))
        self.requested_materials = list(dict.fromkeys(self.requested_materials))
        if not self.question_id:
            payload = f"{self.priority}|{self.category}|{self.question}".encode()
            self.question_id = f"ddq_{hashlib.sha1(payload).hexdigest()[:12]}"
        return self


class DueDiligenceConclusion(BaseModel):
    """Final Mainline A conclusion; not an investment sizing decision."""

    verdict: DiligenceVerdict
    historical_financial_quality: AssessmentGrade = "insufficient_evidence"
    future_earning_power: AssessmentGrade = "insufficient_evidence"
    material_risk_level: RiskLevel = "Medium"
    company_profile: str = ""
    key_strengths: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    follow_up_question_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)

    @model_validator(mode="after")
    def deduplicate_references(self) -> Self:
        self.evidence_ids = list(dict.fromkeys(self.evidence_ids))
        self.follow_up_question_ids = list(dict.fromkeys(self.follow_up_question_ids))
        return self


class ReportReview(BaseModel):
    """Evidence/compliance review emitted after the report writer."""

    passed: bool = False
    score: int = Field(default=0, ge=0, le=100)
    missing_sections: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    citation_issues: list[str] = Field(default_factory=list)
    scope_violations: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
    summary: str = ""


class InvestmentDecision(BaseModel):
    """Deprecated compatibility model for pre-Mainline-A artifacts."""

    recommendation: Literal[
        "recommend",
        "conditional_recommend",
        "watch",
        "not_recommend",
    ]
    investment_thesis: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    valuation_view: str = ""
    financial_view: str = ""
    business_view: str = ""
    evidence_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


# ==================== Financial Forensic Engine ====================


class FinancialFinding(BaseModel):
    """A single finding from the Financial Forensic Engine (20-rule DD framework).

    Attributes:
        rule_id: Rule identifier, e.g. "AQ-001" (Asset Quality rule 1)
        name: Rule name in Chinese
        category: One of asset_quality / earnings_quality / capital_structure / revenue_authenticity
        layer: 1=hard rule, 2=trend analysis, 3=LLM reasoning (filled by Agent)
        severity: info / warning / high / critical
        triggered: Whether the rule condition was met
        metrics: Relevant computed metric values
        evidence: List of source evidence (page + source + detail)
        interpretation: LLM interpretation (Layer 3, filled by Financial Analyst Agent)
        recommendation: Suggested follow-up investigation
    """

    rule_id: str = ""
    name: str = ""
    category: str = ""
    layer: int = 1
    severity: str = "info"
    triggered: bool = False
    description: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    interpretation: str = ""
    recommendation: str = ""
    assessment_status: Literal[
        "observation", "partially_explained", "unexplained", "contradiction"
    ] = "observation"
    possible_explanations: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    escalation_conditions: list[str] = Field(default_factory=list)


# ==================== Prospectus Analysis (Tool-Augmented) ====================


class ProspectusEntity(BaseModel):
    """A structured entity extracted from the prospectus (customer, supplier, product, etc.)."""

    name: str = ""
    detail: str = ""  # e.g. "revenue_ratio: 35%", "role: Chairman"
    evidence: list[Evidence] = Field(default_factory=list)


class CompanyBusinessDossier(BaseModel):
    """Universal company/business DD context before narrative report writing."""

    company: str = ""
    topic_page_map: dict[str, list[int]] = Field(default_factory=dict)
    industry_profiles: list[str] = Field(default_factory=list)
    company_specific_signals: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    topic_findings: dict[str, list["CompanyDossierFinding"]] = Field(default_factory=dict)
    open_questions: list[str] = Field(default_factory=list)


class CompanyDossierFinding(BaseModel):
    """A page-grounded company/business fact, explanation, or cautious inference."""

    topic: str
    statement: str
    finding_type: Literal["fact", "company_explanation", "analyst_inference"] = "fact"
    evidence: list[Evidence] = Field(min_length=1)
    confidence: float = Field(default=0.8, ge=0, le=1)


class ProspectusAnalysis(BaseModel):
    """Structured output from the Prospectus Analyst Agent.

    Every field carries evidence (page numbers) so downstream agents
    can trace claims back to the prospectus source.
    """

    company: str = ""
    dossier: CompanyBusinessDossier = Field(default_factory=CompanyBusinessDossier)
    business_model: str = ""
    business_model_evidence: list[Evidence] = Field(default_factory=list)

    main_products: list[ProspectusEntity] = Field(default_factory=list)
    customers: list[ProspectusEntity] = Field(default_factory=list)
    suppliers: list[ProspectusEntity] = Field(default_factory=list)
    management_team: list[ProspectusEntity] = Field(default_factory=list)
    competitive_advantages: list[str] = Field(default_factory=list)
    prospectus_risks: list[str] = Field(default_factory=list)

    # Claims extracted for cross-validation by Investment Committee
    key_claims: list[str] = Field(default_factory=list)

    raw_markdown: str = ""


# ==================== Industry / Market Intelligence ====================


class IndustryAnalysis(BaseModel):
    """Structured output from the Market Intelligence Agent."""

    company: str = ""
    industry_overview: str = ""
    market_growth: str = ""
    competitors: list[str] = Field(default_factory=list)
    industry_trends: list[str] = Field(default_factory=list)
    industry_risks: list[str] = Field(default_factory=list)
    value_chain: list[str] = Field(default_factory=list)
    customer_industries: list[str] = Field(default_factory=list)
    competitive_dimensions: list[str] = Field(default_factory=list)
    barriers_to_entry: list[str] = Field(default_factory=list)
    growth_drivers: list[str] = Field(default_factory=list)
    expansion_paths: list[str] = Field(default_factory=list)
    structured_findings: list[Finding] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    raw_markdown: str = ""


class LegalGovernanceAnalysis(BaseModel):
    """Structured legal, compliance, governance, and adverse-information review."""

    company: str = ""
    special_shareholder_rights: list[str] = Field(default_factory=list)
    related_party_matters: list[str] = Field(default_factory=list)
    controller_and_ownership_risks: list[str] = Field(default_factory=list)
    litigation_and_penalties: list[str] = Field(default_factory=list)
    licensing_ip_data_risks: list[str] = Field(default_factory=list)
    financial_reporting_integrity: list[str] = Field(default_factory=list)
    financing_debt_guarantees: list[str] = Field(default_factory=list)
    listing_filings: list[str] = Field(default_factory=list)
    adverse_information: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    raw_markdown: str = ""


# ==================== Investment Committee Artifacts ====================


class Contradiction(BaseModel):
    """A contradiction detected by the Investment Committee Agent.

    Represents a conflict between two agents' analyses, e.g.:
    - Prospectus claims "strong pricing power" but Financial shows declining gross margin
    - Prospectus claims "market leader" but Industry shows no top-3 ranking
    """

    type: str = "contradiction"  # contradiction / inconsistency / red_flag
    source_1: str = ""  # e.g. "ProspectusAgent"
    statement_1: str = ""  # e.g. "strong pricing power"
    source_2: str = ""  # e.g. "FinancialAgent"
    statement_2: str = ""  # e.g. "gross margin declining 3 years"
    severity: str = "warning"  # info / warning / high
    question: str = ""  # follow-up question for the company


class RiskMatrixItem(BaseModel):
    """A single item in the risk prioritization matrix.

    probability x impact => score (1-9)
    """

    risk_name: str = ""
    category: str = ""  # financial / business / industry / governance
    probability: RiskLevel = "Medium"  # likelihood of materializing
    impact: RiskLevel = "Medium"  # severity if it materializes
    score: int = 4  # 1-9, probability_rank * impact_rank
    evidence_refs: list[str] = Field(
        default_factory=list
    )  # rule_ids or finding references


class RiskReview(BaseModel):
    """Investment Committee Agent output: cross-source synthesis + risk judgment."""

    company: str = ""
    risk_level: RiskLevel = "Medium"

    # Structured artifacts (not just string lists)
    contradictions: list[Contradiction] = Field(default_factory=list)
    risk_matrix: list[RiskMatrixItem] = Field(default_factory=list)

    # Backward-compatible string lists
    major_risks: list[str] = Field(default_factory=list)
    investment_questions: list[str] = Field(default_factory=list)

    raw_markdown: str = ""
