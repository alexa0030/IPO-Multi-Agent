from __future__ import annotations
from ipo_financial_agent.schemas.report_sections import ReportSectionMaterial,GeneratedReportSection,SectionValidationResult
def validate_section(result: GeneratedReportSection, material: ReportSectionMaterial) -> SectionValidationResult:
    bad_f=sorted(set(result.used_finding_ids)-set(material.allowed_finding_ids)); bad_e=sorted(set(result.used_evidence_ids)-set(material.allowed_evidence_ids)); errors=[]
    if bad_f: errors.append("unknown finding ids")
    if bad_e: errors.append("unknown evidence ids")
    return SectionValidationResult(section=result.section,valid=not errors,invalid_finding_ids=bad_f,invalid_evidence_ids=bad_e,errors=errors)
