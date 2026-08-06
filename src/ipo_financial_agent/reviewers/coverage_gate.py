from __future__ import annotations

from typing import Any

from ipo_financial_agent.schemas.final_reviewer import CoverageGateResult


def evaluate_coverage_gate(audit: Any) -> CoverageGateResult:
    data = audit.model_dump(mode="json") if hasattr(audit, "model_dump") else audit
    blocking: list[str] = []
    retained: list[str] = []
    remediation: dict[str, str] = {}
    for section in data.get("sections", []):
        name = section.get("section", "")
        for missing in section.get("missing_material_types", []):
            item = f"{name}:{missing}"
            # Evidence gaps and optional external verification belong in the
            # final uncertainty channel, not in an Agent rerun gate.
            if missing in {"evidence_gap", "claim_assessment", "legal_claim"}:
                retained.append(item)
                continue
            blocking.append(item)
            remediation[name] = {
                "company_profile_fact": "company",
                "product_fact": "company",
                "financial_tables": "financial",
                "deterministic_metrics": "financial",
                "financial_finding": "financial",
                "industry_profile_fact": "industry",
                "legal_profile_fact": "legal",
                "legal_finding": "legal",
                "strength_finding": "financial_or_company",
                "risk_finding": "specialist_agent",
                "follow_up_request": "evidence_collection",
            }.get(missing, "corresponding_agent")
    return CoverageGateResult(allowed=not blocking, blocking_gaps=blocking, retained_gaps=retained, remediation_targets=remediation)
