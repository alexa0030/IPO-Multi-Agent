from __future__ import annotations

from typing import Any

from ipo_financial_agent.report.report_material_auditor import audit_report_material_coverage, material_for_pack
from ipo_financial_agent.schemas.report import ReportMaterialPackV0


def _dump_list(items: list[Any]) -> list[Any]:
    return [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in items]


def build_report_material_pack_v0(company_result: Any, financial_result: Any, industry_result: Any, legal_result: Any, *, company: str = "") -> tuple[ReportMaterialPackV0, Any]:
    material = material_for_pack(company_result, financial_result, industry_result, legal_result)
    findings = material["finding"]
    by_nature = {nature: [item for item in findings if (item.get("finding_nature") if isinstance(item, dict) else getattr(item, "finding_nature", None)) == nature] for nature in ("strength", "risk", "mixed", "neutral_observation")}
    pack = ReportMaterialPackV0(company=company, company_profile_facts=_dump_list(material["company_profile_fact"]), industry_profile_facts=_dump_list(material["industry_profile_fact"]), legal_profile_facts=_dump_list(material["legal_profile_fact"]), financial_tables=_dump_list(material["financial_tables"]), deterministic_metrics=_dump_list(material["deterministic_metrics"]), strength_findings=_dump_list(by_nature["strength"]), risk_findings=_dump_list(by_nature["risk"]), mixed_findings=_dump_list(by_nature["mixed"]), neutral_findings=_dump_list(by_nature["neutral_observation"]), evidence_index=_dump_list(material["evidence"]), finding_index=_dump_list(findings), follow_up_requests=_dump_list(material["follow_up_request"]))
    audit = audit_report_material_coverage(company_result, financial_result, industry_result, legal_result, company=company)
    pack.section_coverage = audit.sections
    return pack, audit
