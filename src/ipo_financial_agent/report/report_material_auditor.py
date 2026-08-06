from __future__ import annotations

from typing import Any

from ipo_financial_agent.schemas.report import ReportCoverageAudit, ReportSection, ReportSectionCoverage, ReportSectionRequirement


REPORT_SECTION_REQUIREMENTS = {
    ReportSection.EXECUTIVE_SUMMARY: ([], ["strength_finding", "risk_finding", "neutral_finding"], 1),
    ReportSection.COMPANY_DEVELOPMENT: (["company_profile_fact"], ["company_finding"], 1),
    ReportSection.OWNERSHIP_AND_GROUP: (["legal_profile_fact"], ["company_profile_fact", "legal_finding"], 1),
    ReportSection.BUSINESS_AND_PRODUCTS: (["company_profile_fact"], ["product_fact", "application_fact", "company_finding"], 1),
    ReportSection.BUSINESS_MODEL_CUSTOMERS_SUPPLIERS: (["company_profile_fact"], ["company_finding", "financial_finding"], 1),
    ReportSection.INDUSTRY_AND_COMPETITION: (["industry_profile_fact"], ["claim_assessment", "industry_finding"], 1),
    ReportSection.FINANCIAL_ANALYSIS: (["financial_tables", "deterministic_metrics", "financial_finding"], ["mixed_finding"], 1),
    ReportSection.LEGAL_AND_GOVERNANCE: (["legal_profile_fact", "legal_finding"], ["legal_claim"], 1),
    ReportSection.INVESTMENT_LOGIC: (["strength_finding"], ["mixed_finding", "financial_finding", "industry_finding"], 1),
    ReportSection.RISKS_AND_UNCERTAINTIES: (["risk_finding"], ["evidence_gap", "legal_finding"], 1),
    ReportSection.DUE_DILIGENCE_QUESTIONS: (["follow_up_request"], ["evidence_gap"], 0),
    ReportSection.EVIDENCE_APPENDIX: (["evidence"], [], 1),
}


def _dump(value: Any) -> Any:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _items(value: Any, *names: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, dict):
        for name in names:
            if isinstance(value.get(name), list):
                return value[name]
        return []
    for name in names:
        found = getattr(value, name, None)
        if isinstance(found, list):
            return found
    return []


def _material(company_result: Any, financial_result: Any, industry_result: Any, legal_result: Any) -> dict[str, list[Any]]:
    company_facts = _items(company_result, "profile_facts", "company_profile_facts", "dossier", "topic_findings")
    if isinstance(company_result, dict) and isinstance(company_result.get("topic_findings"), dict):
        company_facts = [item for values in company_result["topic_findings"].values() for item in values]
    industry_profile = _items(industry_result, "profile_facts", "industry_profile_facts")
    if not industry_profile and industry_result is not None:
        industry_profile = [{"material_id": "INDUSTRY_PROFILE", "industry_overview": getattr(industry_result, "industry_overview", ""), "market_growth": getattr(industry_result, "market_growth", "")}]
    legal_profile = _items(legal_result, "profile_facts", "legal_profile_facts")
    financial_tables = _items(financial_result, "financial_tables", "raw_statements", "tables")
    metrics = _items(financial_result, "deterministic_metrics", "metrics")
    findings = _items(company_result, "findings", "structured_findings") + _items(financial_result, "findings", "financial_findings") + _items(industry_result, "findings", "structured_findings") + _items(legal_result, "findings", "legal_findings")
    evidence = _items(company_result, "evidence", "evidences", "company_evidences") + _items(financial_result, "evidence", "evidences", "financial_evidences") + _items(industry_result, "evidence") + _items(legal_result, "evidence", "evidences", "legal_evidences")
    followups = _items(financial_result, "follow_up_requests", "open_questions") + _items(legal_result, "follow_up_requests", "open_questions") + _items(company_result, "open_questions")
    return {"company_profile_fact": company_facts, "industry_profile_fact": industry_profile, "legal_profile_fact": legal_profile, "financial_tables": financial_tables, "deterministic_metrics": metrics, "finding": findings, "evidence": evidence, "follow_up_request": followups}


def _nature(item: Any) -> str:
    value = item.get("finding_nature") if isinstance(item, dict) else getattr(item, "finding_nature", None)
    if value:
        return str(value)
    risks = item.get("risks", []) if isinstance(item, dict) else getattr(item, "risks", [])
    if risks:
        return "risk"
    return "neutral_observation"


def audit_report_material_coverage(company_result: Any, financial_result: Any, industry_result: Any, legal_result: Any, *, company: str = "") -> ReportCoverageAudit:
    material = _material(company_result, financial_result, industry_result, legal_result)
    nature_counts = {"strength": 0, "risk": 0, "mixed": 0, "neutral_observation": 0}
    for item in material["finding"]:
        nature_counts[_nature(item) if _nature(item) in nature_counts else "neutral_observation"] += 1
    sections: list[ReportSectionCoverage] = []
    for section, (required, optional, minimum_evidence) in REPORT_SECTION_REQUIREMENTS.items():
        available_types: list[str] = []
        available_ids: list[str] = []
        for kind in required + optional:
            values = material.get(kind, [])
            if kind.endswith("finding"):
                values = [item for item in material["finding"] if (_nature(item) == kind.replace("_finding", "") or kind == "financial_finding" or kind == "company_finding" or kind == "industry_finding" or kind == "legal_finding")]
            if values:
                available_types.append(kind)
                for index, value in enumerate(values):
                    raw = _dump(value)
                    if isinstance(raw, dict):
                        available_ids.append(str(raw.get("finding_id") or raw.get("evidence_id") or raw.get("profile_fact_id") or raw.get("material_id") or f"{kind}_{index+1}"))
        missing = [kind for kind in required if kind not in available_types]
        evidence_count = len(material["evidence"])
        if evidence_count < minimum_evidence and "evidence" not in missing:
            missing.append("evidence")
        status = "complete" if not missing else ("partial" if available_types else "incomplete")
        sections.append(ReportSectionCoverage(section=section, status=status, available_material_ids=list(dict.fromkeys(available_ids)), available_material_types=list(dict.fromkeys(available_types)), missing_material_types=missing, evidence_count=evidence_count))
    return ReportCoverageAudit(company=company, sections=sections, complete_count=sum(item.status == "complete" for item in sections), partial_count=sum(item.status == "partial" for item in sections), incomplete_count=sum(item.status == "incomplete" for item in sections), positive_finding_count=nature_counts["strength"], risk_finding_count=nature_counts["risk"], mixed_finding_count=nature_counts["mixed"], neutral_finding_count=nature_counts["neutral_observation"], evidence_gap_count=len(material["evidence"]) == 0, follow_up_count=len(material["follow_up_request"]))


def material_for_pack(company_result: Any, financial_result: Any, industry_result: Any, legal_result: Any) -> dict[str, list[Any]]:
    return _material(company_result, financial_result, industry_result, legal_result)
