from __future__ import annotations
from typing import Any
from ipo_financial_agent.schemas.report_v1 import ReportMaterialPackV1

def validate_report_material_pack_v1(pack_v0: Any, pack_v1: ReportMaterialPackV1) -> dict:
    before=pack_v0.model_dump(mode="json") if hasattr(pack_v0,"model_dump") else pack_v0
    errors=[]; warnings=[]
    for field in ("company_profile_facts","industry_profile_facts","legal_profile_facts","financial_tables","deterministic_metrics","finding_index","evidence_index"):
        if len(getattr(pack_v1,field,[])) < len(before.get(field,[])): errors.append(f"v1 dropped v0 material: {field}")
    if len(pack_v1.section_coverage) != 12: errors.append("section coverage must contain 12 sections")
    if not pack_v1.reviewed_topics: warnings.append("no reviewed topics")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "final_review_status": pack_v1.final_review_status}
