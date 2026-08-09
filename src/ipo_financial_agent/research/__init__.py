"""Research-ledger adapters and validation helpers."""

from ipo_financial_agent.research.ledger_builders import (
    financial_research_patch,
    industry_research_patch,
    legal_governance_research_patch,
    prospectus_research_patch,
)
from ipo_financial_agent.research.financial_contract_adapter import (
    build_financial_agent_result,
    register_financial_evidence,
)

__all__ = [
    "financial_research_patch",
    "industry_research_patch",
    "legal_governance_research_patch",
    "prospectus_research_patch",
    "build_financial_agent_result",
    "register_financial_evidence",
]
