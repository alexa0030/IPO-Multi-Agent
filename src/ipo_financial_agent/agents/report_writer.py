"""Report Writer Agent — generates the final IPO investment research report.

Integrates prospectus analysis, industry analysis, financial analysis,
and investment committee review into a structured report with evidence
citations and cross-agent findings.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.llm.prompts_agents import REPORT_WRITER_SYSTEM_PROMPT


class ReportWriterAgent:
    """Final report generation Agent."""

    def __init__(self, client: OpenAICompatibleClient | None = None) -> None:
        self.client = client

    def write_diligence_draft(
        self,
        *,
        company: str,
        grounded_draft: str,
        agent_messages: list[Any] | None = None,
    ) -> str:
        """Rewrite a grounded draft; never research or invent new facts."""
        if self.client is None:
            return grounded_draft
        # Large financial tables are deterministic artifacts, not prose for an
        # LLM to regenerate.  Rewriting them is slow and can silently alter or
        # truncate figures, so the writer acts as an assembler for long drafts.
        if len(grounded_draft) > 12000 or "三大财务报表（招股书原表还原）" in grounded_draft:
            return grounded_draft
        message_summary = [
            {
                "sender": getattr(item, "sender", ""),
                "type": getattr(item, "message_type", ""),
                "content": getattr(item, "content", "")[:500],
            }
            for item in (agent_messages or [])
        ]
        prompt = f"""你是投资机构港股 IPO 尽调报告撰写人。
请把下方确定性底稿整理成完整、专业、详细的中文 Markdown 公司尽调报告。

强制规则：
1. 只能重组和解释底稿已有内容，绝对不得新增公司、人物、客户、竞争对手、数字或事件。
2. 所有 Evidence ID、招股书页码和 URL 必须原样保留。
3. 必须保留公司股权与业务、行业与竞争、财务、未来盈利、法务负面、跨 Agent 冲突、综合判断和补充尽调清单。
4. 清楚区分披露事实、公司解释、分析判断和待核查事项。
5. 不建议投资金额，不给估值上限、退出期限或目标收益率。
6. 这是公司尽调报告，不是买卖建议或股票交易报告。

Agent 执行摘要：
{json.dumps(message_summary, ensure_ascii=False)}

确定性底稿：
{grounded_draft[:50000]}
"""
        rewritten = self.client.complete_text(
            system_prompt=(
                "你只负责基于已给证据写港股 IPO 公司尽调报告；禁止补充外部事实。"
            ),
            user_prompt=prompt,
            max_tokens=7000,
        )
        protected = ("资产负债表", "利润表", "现金流量表")
        if any(token in grounded_draft and token not in rewritten for token in protected):
            return grounded_draft
        if grounded_draft.count("|") and rewritten.count("|") < grounded_draft.count("|"):
            return grounded_draft
        return rewritten

    def revise_diligence_draft(
        self,
        *,
        report: str,
        revision_instructions: list[str],
    ) -> str:
        """Apply one bounded reviewer round while preserving citations."""
        if self.client is None or not revision_instructions:
            return report
        matches = list(re.finditer(r"^##\s+.+$", report, re.MULTILINE))
        if not matches:
            return report
        chunks = [report[: matches[0].start()]]
        keyword_aliases = {
            "投资摘要": ("投资摘要", "核心优势"),
            "财务分析": ("财务分析", "收现比", "销售费用率", "其他应付款"),
            "风险分析": ("风险分析", "风险项", "待解释观察"),
            "综合判断": ("综合判断",),
            "补充尽调": ("补充尽调", "诉讼", "处罚"),
            "财务报表附录": ("财务报表附录", "银行借款", "认沽期权"),
        }
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(report)
            section = report[match.start() : end]
            title = match.group(0)
            aliases = next(
                (values for key, values in keyword_aliases.items() if key in title),
                (),
            )
            instructions = [
                item for item in revision_instructions
                if aliases and any(alias in item for alias in aliases)
            ]
            # Long deterministic appendices are not safe for prose rewriting.
            if not instructions or len(section) > 16000:
                chunks.append(section)
                continue
            prompt = f"""根据终审意见只修订下方一个 Markdown 章节。
不得新增事实；必须保留该章节已有 Evidence ID、页码、URL、标题和表格。
无法用已有内容完成的意见，应改写为明确的待核查事项，不得猜测补齐。

终审意见：
{json.dumps(instructions, ensure_ascii=False)}

待修订章节：
{section}
"""
            try:
                candidate = self.client.complete_text(
                    system_prompt="你是尽调报告章节修订编辑，只执行终审意见，不新增研究结论。",
                    user_prompt=prompt,
                    max_tokens=4000,
                )
            except Exception:
                chunks.append(section)
                continue
            if title not in candidate or candidate.count("|") < section.count("|"):
                chunks.append(section)
            else:
                chunks.append(candidate.rstrip() + "\n\n")
        revised = "".join(chunks).rstrip() + "\n"
        protected = ("资产负债表", "利润表", "现金流量表")
        if any(token in report and token not in revised for token in protected):
            return report
        if report.count("|") and revised.count("|") < report.count("|"):
            return report
        return revised

    def write(
        self,
        *,
        company: str,
        prospectus_analysis: Any | None = None,
        industry_analysis: Any | None = None,
        financial_markdown: str = "",
        risk_review: Any | None = None,
    ) -> str:
        if self.client is None:
            return self._template_report(
                company,
                prospectus_analysis,
                industry_analysis,
                financial_markdown,
                risk_review,
            )

        # Build context with structured data
        context = self._build_context(
            company, prospectus_analysis, industry_analysis,
            financial_markdown, risk_review,
        )

        prompt = (
            f"Please generate a comprehensive IPO investment research report for {company}.\n\n"
            f"Below are the analysis results from all specialist agents (JSON):\n\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            f"The report must include the following sections:\n"
            f"1. Company Overview\n2. Business Model Analysis\n3. Industry Analysis\n"
            f"4. Financial Quality Analysis\n5. Risk Analysis (with risk matrix)\n"
            f"6. Investment Committee Findings (contradictions + questions)\n"
            f"7. Investment View\n\n"
            f"Append a disclaimer at the end."
        )

        markdown = self.client.complete_text(
            system_prompt=REPORT_WRITER_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=3000,
        )

        return markdown

    @staticmethod
    def _build_context(
        company: str,
        prospectus: Any | None,
        industry: Any | None,
        financial_md: str,
        risk_review: Any | None,
    ) -> dict:
        """Build structured context for LLM."""
        # Handle ProspectusEntity lists
        def entity_names(entities: list) -> list[str]:
            return [getattr(e, "name", str(e)) for e in (entities or [])]

        return {
            "company": company,
            "prospectus": {
                "business_model": getattr(prospectus, "business_model", "") if prospectus else "",
                "main_products": entity_names(getattr(prospectus, "main_products", []) if prospectus else []),
                "customers": entity_names(getattr(prospectus, "customers", []) if prospectus else []),
                "suppliers": entity_names(getattr(prospectus, "suppliers", []) if prospectus else []),
                "management_team": entity_names(getattr(prospectus, "management_team", []) if prospectus else []),
                "competitive_advantages": getattr(prospectus, "competitive_advantages", []) if prospectus else [],
                "prospectus_risks": getattr(prospectus, "prospectus_risks", []) if prospectus else [],
                "key_claims": getattr(prospectus, "key_claims", []) if prospectus else [],
            },
            "industry": {
                "industry_overview": getattr(industry, "industry_overview", "") if industry else "",
                "market_growth": getattr(industry, "market_growth", "") if industry else "",
                "competitors": getattr(industry, "competitors", []) if industry else [],
                "industry_trends": getattr(industry, "industry_trends", []) if industry else [],
                "industry_risks": getattr(industry, "industry_risks", []) if industry else [],
            },
            "financial_analysis": financial_md[:4000] if financial_md else "",
            "risk_review": {
                "risk_level": getattr(risk_review, "risk_level", "Medium") if risk_review else "Medium",
                "major_risks": getattr(risk_review, "major_risks", []) if risk_review else [],
                "contradictions": [
                    {
                        "source_1": getattr(c, "source_1", ""),
                        "statement_1": getattr(c, "statement_1", ""),
                        "source_2": getattr(c, "source_2", ""),
                        "statement_2": getattr(c, "statement_2", ""),
                        "severity": getattr(c, "severity", ""),
                        "question": getattr(c, "question", ""),
                    }
                    for c in (getattr(risk_review, "contradictions", []) or [])
                ] if risk_review else [],
                "risk_matrix": [
                    {
                        "risk_name": getattr(r, "risk_name", ""),
                        "probability": getattr(r, "probability", ""),
                        "impact": getattr(r, "impact", ""),
                        "score": getattr(r, "score", 0),
                    }
                    for r in (getattr(risk_review, "risk_matrix", []) or [])
                ] if risk_review else [],
                "investment_questions": getattr(risk_review, "investment_questions", []) if risk_review else [],
            },
        }

    @staticmethod
    def _template_report(
        company: str,
        prospectus: Any | None,
        industry: Any | None,
        financial_md: str,
        risk_review: Any | None,
    ) -> str:
        """Offline mode: structured template with evidence citations."""
        sections: list[str] = [
            f"# {company} IPO Investment Research Report",
            "",
            f"> Generated by Multi-Agent Collaboration System (offline mode).",
            f"> Agents: ResearchManager, ProspectusAgent, FinancialAgent, IndustryAgent, InvestmentCommittee",
            "",
        ]

        # Helper for ProspectusEntity lists
        def entity_lines(entities: list, prefix: str = "") -> list[str]:
            lines = []
            for e in (entities or []):
                name = getattr(e, "name", str(e))
                detail = getattr(e, "detail", "")
                ev_list = getattr(e, "evidence", [])
                ref = ""
                if ev_list:
                    ev = ev_list[0]
                    ref = f" [{getattr(ev, 'source', '')}]"
                d = f" ({detail})" if detail else ""
                lines.append(f"- {prefix}{name}{d}{ref}")
            return lines

        # 1. Company Overview
        sections.append("## 1. Company Overview")
        if prospectus and getattr(prospectus, "business_model", ""):
            bm_ev = getattr(prospectus, "business_model_evidence", [])
            ref = f" [{getattr(bm_ev[0], 'source', '')}]" if bm_ev else ""
            sections.append(f"\n{prospectus.business_model[:500]}{ref}")
        else:
            sections.append("\nProspectus analysis data insufficient; further due diligence recommended.")
        sections.append("")

        # 2. Business Model Analysis
        sections.append("## 2. Business Model Analysis")
        if prospectus:
            products = getattr(prospectus, "main_products", [])
            if products:
                sections.append("\n**Main Products/Services:**")
                sections.extend(entity_lines(products))
            customers = getattr(prospectus, "customers", [])
            if customers:
                sections.append("\n**Key Customers:**")
                sections.extend(entity_lines(customers))
            suppliers = getattr(prospectus, "suppliers", [])
            if suppliers:
                sections.append("\n**Key Suppliers:**")
                sections.extend(entity_lines(suppliers))
            mgmt = getattr(prospectus, "management_team", [])
            if mgmt:
                sections.append("\n**Management Team:**")
                sections.extend(entity_lines(mgmt))
            advantages = getattr(prospectus, "competitive_advantages", [])
            if advantages:
                sections.append("\n**Competitive Advantages:**")
                for a in advantages:
                    sections.append(f"- {a}")
        sections.append("")

        # 3. Industry Analysis
        sections.append("## 3. Industry Analysis")
        if industry:
            if getattr(industry, "industry_overview", ""):
                sections.append(f"\n{industry.industry_overview[:500]}")
            if getattr(industry, "market_growth", ""):
                sections.append(f"\n**Market Growth:** {industry.market_growth[:300]}")
            competitors = getattr(industry, "competitors", [])
            if competitors:
                sections.append("\n**Competitors:**")
                for c in competitors:
                    sections.append(f"- {c}")
            trends = getattr(industry, "industry_trends", [])
            if trends:
                sections.append("\n**Industry Trends:**")
                for t in trends:
                    sections.append(f"- {t}")
        else:
            sections.append("\nIndustry analysis data insufficient.")
        sections.append("")

        # 4. Financial Quality Analysis
        sections.append("## 4. Financial Quality Analysis")
        if financial_md:
            sections.append(f"\n{financial_md[:3000]}")
        else:
            sections.append("\nFinancial analysis data insufficient.")
        sections.append("")

        # 5. Risk Analysis (with risk matrix)
        sections.append("## 5. Risk Analysis")
        if risk_review:
            level = getattr(risk_review, "risk_level", "Medium")
            sections.append(f"\n**Overall Risk Level: {level}**")
            sections.append("")

            # Risk Matrix
            matrix = getattr(risk_review, "risk_matrix", []) or []
            if matrix:
                sections.append("### Risk Prioritization Matrix")
                sections.append("")
                sections.append("| Risk | Category | Probability | Impact | Score |")
                sections.append("|------|----------|-------------|--------|-------|")
                for r in matrix[:10]:
                    sections.append(
                        f"| {getattr(r, 'risk_name', '')[:50]} "
                        f"| {getattr(r, 'category', '')} "
                        f"| {getattr(r, 'probability', '')} "
                        f"| {getattr(r, 'impact', '')} "
                        f"| {getattr(r, 'score', 0)} |"
                    )
                sections.append("")

            # Major Risks
            major = getattr(risk_review, "major_risks", []) or []
            if major:
                sections.append("### Major Risks")
                for r in major:
                    sections.append(f"- {r}")
                sections.append("")
        sections.append("")

        # 6. Investment Committee Findings
        sections.append("## 6. Investment Committee Findings")
        if risk_review:
            # Contradictions
            contradictions = getattr(risk_review, "contradictions", []) or []
            if contradictions:
                sections.append("### Cross-Agent Contradiction Findings")
                sections.append("")
                for c in contradictions:
                    severity = getattr(c, "severity", "warning").upper()
                    s1 = getattr(c, "statement_1", "")
                    s2 = getattr(c, "statement_2", "")
                    q = getattr(c, "question", "")
                    sections.append(f"- **[{severity}]** {s1}")
                    sections.append(f"  - vs: {s2}")
                    sections.append(f"  - Follow-up: {q}")
                    sections.append("")
            else:
                sections.append("### Cross-Agent Contradiction Findings")
                sections.append("- No significant contradictions detected.")
                sections.append("")

            # Investment Questions
            questions = getattr(risk_review, "investment_questions", []) or []
            if questions:
                sections.append("### Investment Committee Questions")
                for i, q in enumerate(questions, 1):
                    sections.append(f"{i}. {q}")
                sections.append("")
        sections.append("")

        # 7. Investment View
        sections.append("## 7. Investment View")
        level = getattr(risk_review, "risk_level", "Medium") if risk_review else "Medium"
        if level == "Low":
            sections.append("\nComprehensive risk assessment indicates low overall risk. "
                            "The company demonstrates stable financial performance with no "
                            "significant cross-agent contradictions. Recommend further monitoring.")
        elif level == "High":
            sections.append("\nComprehensive risk assessment indicates **high overall risk**. "
                            "Multiple financial anomalies and/or cross-agent contradictions "
                            "were identified. The Investment Committee recommends thorough "
                            "additional due diligence before any investment decision.")
        else:
            sections.append("\nComprehensive risk assessment indicates medium overall risk. "
                            "Some financial anomalies or uncertainties were identified. "
                            "Recommend further investigation on specific issues raised "
                            "by the Investment Committee.")
        sections.append("")

        # Disclaimer
        sections.append("---")
        sections.append("")
        sections.append("*Disclaimer: This report was auto-generated by the IPO Multi-Agent "
                        "Collaboration System. It is for reference only and does not constitute "
                        "investment advice.*")

        return "\n".join(sections)
