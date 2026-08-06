from __future__ import annotations
from typing import Any
from ipo_financial_agent.schemas.report import ReportSectionCoverage
from ipo_financial_agent.schemas.report_v1 import ReportMaterialPackV1
from ipo_financial_agent.schemas.final_synthesis import FinalReviewResult

def _dump(x): return x.model_dump(mode="json") if hasattr(x,"model_dump") else x
def build_report_material_pack_v1(pack_v0: Any, final_review: FinalReviewResult, *, company_name: str = "", job_id: str = "") -> ReportMaterialPackV1:
    data=_dump(pack_v0)
    questions=[*final_review.p0_due_diligence_questions,*final_review.p1_due_diligence_questions,*final_review.p2_due_diligence_questions]
    return ReportMaterialPackV1(company_name=company_name or data.get("company", ""),job_id=job_id,company_profile_facts=data.get("company_profile_facts",[]),industry_profile_facts=data.get("industry_profile_facts",[]),legal_profile_facts=data.get("legal_profile_facts",[]),entity_registry=data.get("entity_registry",[]),financial_tables=data.get("financial_tables",[]),deterministic_metrics=data.get("deterministic_metrics",[]),reviewed_topics=final_review.reviewed_topics,reviewed_strengths=final_review.reviewed_strengths,reviewed_risks=final_review.reviewed_risks,reviewed_mixed_points=final_review.reviewed_mixed_points,historical_financial_assessment=final_review.historical_financial_assessment,future_earning_assessment=final_review.future_earning_assessment,negative_matter_assessment=final_review.negative_matter_assessment,evidence_gaps=final_review.evidence_gaps,due_diligence_questions=questions,finding_index=data.get("finding_index",[]),evidence_index=data.get("evidence_index",[]),section_coverage=data.get("section_coverage",[]),final_review_status=final_review.review_status)
