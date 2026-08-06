from __future__ import annotations
from typing import Any
from ipo_financial_agent.schemas.final_synthesis import FinalReviewResult

def validate_final_review(result: FinalReviewResult, *, finding_ids: set[str], evidence_ids: set[str], expected_status: str | None = None) -> dict:
    errors=[]
    for item in [*result.reviewed_strengths,*result.reviewed_risks,*result.reviewed_mixed_points]:
        if set(item.finding_ids)-finding_ids: errors.append(f"{item.point_id}: unknown finding")
        if set(item.evidence_ids)-evidence_ids: errors.append(f"{item.point_id}: unknown evidence")
    if set(result.approved_finding_ids)-finding_ids: errors.append("approved findings contain unknown ids")
    if expected_status and result.review_status != expected_status: errors.append("status differs from deterministic resolver")
    return {"valid": not errors, "errors": errors, "review_status": result.review_status}
