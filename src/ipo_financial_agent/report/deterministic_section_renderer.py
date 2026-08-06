from __future__ import annotations
from ipo_financial_agent.schemas.report_sections import ReportSectionMaterial, GeneratedReportSection

def _id(item,key): return str(item.get(key,"")) if isinstance(item,dict) and item.get(key) else ""
def render_section(material: ReportSectionMaterial) -> GeneratedReportSection:
    lines=[f"## {material.title}"]
    if material.financial_tables: lines += ["", "### Financial tables", f"保留确定性财务表格 {len(material.financial_tables)} 项。"]
    if material.metrics: lines += ["", "### Deterministic metrics", f"保留确定性指标 {len(material.metrics)} 项。"]
    for label,items in (("Reviewed strengths",material.strength_points),("Reviewed risks",material.risk_points),("Reviewed mixed points",material.mixed_points)):
        if items:
            lines += ["", f"### {label}"]
            for item in items:
                d=item; lines.append(f"- {d.get('statement',d.get('title',''))} " + " ".join(f"[F:{x}]" for x in d.get("finding_ids",[])) + " " + " ".join(f"[E:{x}]" for x in d.get("evidence_ids",[])))
    if material.evidence_gaps: lines += ["", "### Evidence gaps", *[f"- {item}" for item in material.evidence_gaps]]
    if material.due_diligence_questions: lines += ["", "### Due diligence questions", *[f"- {item.get('priority','P1')}: {item.get('question','')}" for item in material.due_diligence_questions]]
    if len(lines)==1: lines += ["", "当前资料范围内未取得足以支撑本章节完整判断的材料。"]
    finding_ids=[x for item in [*material.strength_points,*material.risk_points,*material.mixed_points] for x in item.get("finding_ids",[])]
    evidence_ids=[x for item in [*material.strength_points,*material.risk_points,*material.mixed_points] for x in item.get("evidence_ids",[])]
    return GeneratedReportSection(section=material.section,title=material.title,markdown="\n".join(lines),used_finding_ids=list(dict.fromkeys(finding_ids)),used_evidence_ids=list(dict.fromkeys(evidence_ids)),generation_method="deterministic")
