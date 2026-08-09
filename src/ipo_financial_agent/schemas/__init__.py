"""Authoritative PRD v2 contracts for the staged research workflow."""

from .adapters import (
    ContractAdaptationError,
    adapt_legacy_challenge,
    adapt_legacy_evidence,
    adapt_legacy_finding,
    adapt_legacy_research_patch,
    canonical_agent_name,
)
from .challenge import Challenge
from .evidence import Evidence
from .financial_result import CompletionCheck, FinancialAgentResult, QuestionAnswerMapping
from .finding import Finding
from .manager import (
    CompanyResearchProfile,
    ManagerContext,
    ManagerFinancialRunResult,
    ManagerFinancialSummary,
    ManagerObservation,
    ManagerPlanArtifact,
    ManagerTrendPoint,
    ManagerValidationResult,
    ResearchPlan,
)
from .follow_up import FollowUpRequest
from .research_task import (
    BASELINE_FINANCIAL_TOPICS,
    FinancialResearchTopic,
    ResearchQuestion,
    ResearchTask,
    ResearchTopic,
    SpecialistResearchTopic,
)
from .specialist import SpecialistResearchResult
from .review_result import Assessment, CrossAgentConflict, ReviewResult
from .reviewer import (
    FindingReview,
    ManagerFinancialReviewerRunResult,
    ReviewerInputManifest,
    ReviewerValidationResult,
)
from .state import IPOResearchState

__all__ = [
    "Assessment",
    "Challenge",
    "ContractAdaptationError",
    "CrossAgentConflict",
    "Evidence",
    "FinancialAgentResult",
    "CompletionCheck",
    "QuestionAnswerMapping",
    "Finding",
    "CompanyResearchProfile",
    "ManagerContext",
    "ManagerFinancialRunResult",
    "ManagerFinancialSummary",
    "ManagerObservation",
    "ManagerPlanArtifact",
    "ManagerTrendPoint",
    "ManagerValidationResult",
    "ResearchPlan",
    "FollowUpRequest",
    "IPOResearchState",
    "ResearchQuestion",
    "ResearchTask",
    "ResearchTopic",
    "SpecialistResearchResult",
    "SpecialistResearchTopic",
    "FinancialResearchTopic",
    "BASELINE_FINANCIAL_TOPICS",
    "ReviewResult",
    "FindingReview",
    "ManagerFinancialReviewerRunResult",
    "ReviewerInputManifest",
    "ReviewerValidationResult",
    "adapt_legacy_challenge",
    "adapt_legacy_evidence",
    "adapt_legacy_finding",
    "adapt_legacy_research_patch",
    "canonical_agent_name",
]
