from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AgentReport:
    agent_name: str
    markdown: str


class SummaryAgent:
    """为后续公司、行业、估值、新闻等Agent预留的汇总接口。"""

    def merge(self, company: str, reports: list[AgentReport]) -> str:
        sections = [f"# {company} IPO综合分析报告"]
        for report in reports:
            sections.append(f"\n## {report.agent_name}\n\n{report.markdown.strip()}")
        return "\n".join(sections).strip() + "\n"
