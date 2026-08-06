from __future__ import annotations
from datetime import datetime,timezone
from ipo_financial_agent.schemas.report_sections import GeneratedReportSection
from ipo_financial_agent.schemas.report import ReportSection
ORDER=list(ReportSection)
def assemble_final_report(company_name:str,sections:list[GeneratedReportSection],review_status:str="conditional_pass") -> str:
    by={item.section:item for item in sections}; lines=[f"# {company_name} IPO 尽调报告", "", f"- Review status: {review_status}", f"- Generated at: {datetime.now(timezone.utc).isoformat()}", "", "本报告基于已登记的招股书、财务和公开信息证据生成，不构成法律、审计或投资建议。"]
    for section in ORDER:
        item=by.get(section); lines += ["", item.markdown if item else f"## {section.value}\n\n当前资料不足。"]
    return "\n".join(lines)
