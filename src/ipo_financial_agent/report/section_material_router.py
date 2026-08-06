from __future__ import annotations
from typing import Any
from ipo_financial_agent.schemas.report import ReportSection
from ipo_financial_agent.schemas.report_sections import ReportSectionMaterial

ORDER=list(ReportSection)
TITLES={s:s.value.replace("_"," ").title() for s in ReportSection}

def _dump(x): return x.model_dump(mode="json") if hasattr(x,"model_dump") else x
def route_report_sections(pack: Any) -> list[ReportSectionMaterial]:
    p=_dump(pack); facts=p.get("company_profile_facts",[])+p.get("industry_profile_facts",[])+p.get("legal_profile_facts",[]); topics=p.get("reviewed_topics",[]); strengths=p.get("reviewed_strengths",[]); risks=p.get("reviewed_risks",[]); mixed=p.get("reviewed_mixed_points",[]); gaps=p.get("evidence_gaps",[]); questions=p.get("due_diligence_questions",[])
    output=[]
    for section in ORDER:
        if section in {ReportSection.FINANCIAL_ANALYSIS}: sf=p.get("financial_tables",[]); sm=p.get("deterministic_metrics",[])
        else: sf=[]; sm=[]
        if section in {ReportSection.INVESTMENT_LOGIC}: sr=strengths; rr=[]; mm=mixed
        elif section in {ReportSection.RISKS_AND_UNCERTAINTIES,ReportSection.LEGAL_AND_GOVERNANCE}: sr=[]; rr=risks; mm=mixed
        else: sr=[]; rr=[]; mm=[]
        selected_questions=questions if section==ReportSection.DUE_DILIGENCE_QUESTIONS else []
        allowed_f=[]; allowed_e=[]
        for item in [*sr,*rr,*mm,*facts,*topics]:
            d=_dump(item); allowed_f.extend([str(d[k]) for k in ("finding_id","point_id") if d.get(k)])
            allowed_e.extend([str(x) for x in d.get("evidence_ids",[])])
        output.append(ReportSectionMaterial(section=section,title=TITLES[section],profile_facts=facts if section not in {ReportSection.FINANCIAL_ANALYSIS,ReportSection.EVIDENCE_APPENDIX} else [],financial_tables=sf,metrics=sm,reviewed_topics=topics if section not in {ReportSection.BUSINESS_AND_PRODUCTS,ReportSection.COMPANY_DEVELOPMENT} else [],strength_points=sr,risk_points=rr,mixed_points=mm,evidence_gaps=gaps if section==ReportSection.RISKS_AND_UNCERTAINTIES else [],due_diligence_questions=selected_questions,allowed_finding_ids=list(dict.fromkeys(allowed_f)),allowed_evidence_ids=list(dict.fromkeys(allowed_e))))
    return output
