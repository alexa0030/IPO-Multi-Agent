"""Investment Committee Agent — cross-source synthesis, contradiction detection,
risk prioritization, and investment question generation.

This is the soul of the Multi-Agent system: it reads findings from all three
analyst agents (Prospectus, Financial, Industry) plus the agent message bus,
then performs:

1. Contradiction Detection — compares claims across agents
2. Risk Prioritization Matrix — probability x impact scoring
3. Investment Question Generation — buy-side due diligence questions
"""

from __future__ import annotations

import json
import re
from typing import Any, ClassVar

from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.llm.prompts_agents import RISK_REVIEW_SYSTEM_PROMPT
from ipo_financial_agent.models_agent import (
    AgentMessage,
    Contradiction,
    RiskMatrixItem,
    RiskReview,
)

# ==================== Contradiction Detection Rules (offline) ====================

# Keywords that signal claims in prospectus text
_CLAIM_KEYWORDS = {
    "growth": ["增长", "高速增长", "快速", "扩张", "growth", "rapid"],
    "leadership": ["领先", "龙头", "第一", "最大", "leader", "leading", "top"],
    "pricing_power": [
        "议价能力",
        "定价权",
        "竞争优势",
        "pricing",
        "competitive advantage",
    ],
    "cash_strong": ["资金充裕", "现金流充足", "现金充裕", "strong cash", "solid cash"],
    "customer_diverse": ["客户多元", "客户分散", "diversified customer", "no reliance"],
    "quality": ["高质量", "优质", "稳定", "high quality", "stable"],
}


def _has_claim(text: str, claim_type: str) -> bool:
    """Check if text contains keywords for a given claim type."""
    if not text:
        return False
    text_lower = text.lower()
    for kw in _CLAIM_KEYWORDS.get(claim_type, []):
        if kw.lower() in text_lower:
            return True
    return False


def _get_metric_value(metrics: list, name_pattern: str) -> float | None:
    """Find a metric by name pattern and return its numeric value."""
    if not metrics:
        return None
    for m in metrics:
        name = getattr(m, "metric_name", "") or getattr(m, "name", "") or str(m)
        if re.search(name_pattern, name, re.IGNORECASE):
            val = getattr(m, "value", None)
            if val is None:
                val = getattr(m, "raw_value", None)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
    return None


def _get_metric_trend(metrics: list, name_pattern: str) -> list[float]:
    """Get multi-year values for a metric to determine trend direction."""
    if not metrics:
        return []
    values = []
    for m in metrics:
        name = getattr(m, "metric_name", "") or getattr(m, "name", "") or str(m)
        if re.search(name_pattern, name, re.IGNORECASE):
            val = getattr(m, "value", None)
            if val is None:
                val = getattr(m, "raw_value", None)
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    pass
    return values


def _format_percent(value: float) -> str:
    normalized = value * 100 if abs(value) <= 1.5 else value
    return f"{normalized:.1f}%"


class RiskReviewerAgent:
    """Investment Committee Agent: cross-agent reasoning + contradiction detection.

    Upgraded from simple risk counting to:
    - Real contradiction detection between agent analyses
    - Risk prioritization matrix (probability x impact)
    - Investment committee question generation based on forensic findings
    - Consumption of agent message bus (finding-type messages)
    """

    def __init__(self, client: OpenAICompatibleClient | None = None) -> None:
        self.client = client

    def review(
        self,
        *,
        company: str,
        prospectus_analysis: Any | None = None,
        industry_analysis: Any | None = None,
        financial_markdown: str = "",
        financial_risks: list | None = None,
        financial_metrics: list | None = None,
        financial_findings: list | None = None,
        agent_messages: list[AgentMessage] | None = None,
    ) -> RiskReview:
        # --- Collect all inputs ---
        prospectus_text = self._get_prospectus_text(prospectus_analysis)
        industry_text = self._get_industry_text(industry_analysis)
        fin_risks = self._summarize_financial_risks(financial_risks)
        fin_findings = self._summarize_findings(financial_findings)
        triggered_findings = [f for f in fin_findings if f.get("triggered")]
        finding_messages = self._extract_finding_messages(agent_messages)

        if self.client is not None:
            return self._llm_review(
                company,
                prospectus_analysis,
                industry_analysis,
                financial_markdown,
                fin_risks,
                fin_findings,
                finding_messages,
            )

        # --- Offline mode: real analytical logic ---
        contradictions = self._detect_contradictions(
            prospectus_text,
            prospectus_analysis,
            financial_metrics,
            fin_findings,
            industry_text,
        )

        risk_matrix = self._build_risk_matrix(
            fin_risks, triggered_findings, contradictions
        )

        investment_questions = self._generate_questions(
            triggered_findings,
            contradictions,
            fin_risks,
        )

        risk_level = self._determine_risk_level(risk_matrix, contradictions)

        major_risks = self._extract_major_risks(
            fin_risks, triggered_findings, contradictions
        )

        markdown = self._build_markdown(
            company,
            risk_level,
            major_risks,
            contradictions,
            risk_matrix,
            investment_questions,
            fin_risks,
            triggered_findings,
        )

        return RiskReview(
            company=company,
            risk_level=risk_level,
            contradictions=contradictions,
            risk_matrix=risk_matrix,
            major_risks=major_risks,
            investment_questions=investment_questions,
            raw_markdown=markdown,
        )

    # ==================== Contradiction Detection (offline) ====================

    def _detect_contradictions(
        self,
        prospectus_text: str,
        prospectus_analysis: Any | None,
        financial_metrics: list | None,
        financial_findings: list[dict] | None,
        industry_text: str,
    ) -> list[Contradiction]:
        """Detect real contradictions between agent analyses."""
        contradictions: list[Contradiction] = []
        findings = financial_findings or []

        # --- Rule 1: Growth claim vs revenue trend ---
        if _has_claim(prospectus_text, "growth"):
            revenue_trend = _get_metric_trend(financial_metrics, r"revenue|收入|营业")
            if (
                revenue_trend
                and len(revenue_trend) >= 2
                and revenue_trend[-1] < revenue_trend[0]
            ):
                contradictions.append(
                    Contradiction(
                        type="contradiction",
                        source_1="ProspectusAgent",
                        statement_1="招股书声称业务快速增长",
                        source_2="FinancialAgent",
                        statement_2=f"营业收入从{revenue_trend[0]:.0f}降至{revenue_trend[-1]:.0f}",
                        severity="high",
                        question="请说明招股书所述增长趋势与财务数据不一致的原因。",
                    )
                )

        # --- Rule 2: Pricing power / competitive advantage vs gross margin decline ---
        if _has_claim(prospectus_text, "pricing_power"):
            gm_trend = _get_metric_trend(financial_metrics, r"gross_margin|毛利率")
            if (
                gm_trend
                and len(gm_trend) >= 2
                and gm_trend[-1] < gm_trend[0]
                and (gm_trend[-1] < 0.30 or gm_trend[0] - gm_trend[-1] >= 0.05)
            ):
                contradictions.append(
                    Contradiction(
                        type="contradiction",
                        source_1="ProspectusAgent",
                        statement_1="招股书声称具有竞争优势/议价能力",
                        source_2="FinancialAgent",
                        statement_2=(
                            f"毛利率从{_format_percent(gm_trend[0])}"
                            f"降至{_format_percent(gm_trend[-1])}"
                        ),
                        severity="warning",
                        question="请解释竞争优势与毛利率持续下降并存的原因。",
                    )
                )

        # --- Rule 3: Cash position claims vs cash flow quality ---
        if _has_claim(prospectus_text, "cash_strong"):
            # Check if net cash ratio finding triggered
            cash_finding = next(
                (
                    f
                    for f in findings
                    if f.get("rule_id") == "EQ-001" and f.get("triggered")
                ),
                None,
            )
            if cash_finding:
                contradictions.append(
                    Contradiction(
                        type="contradiction",
                        source_1="ProspectusAgent",
                        statement_1="招股书声称资金充裕/现金流充足",
                        source_2="FinancialAgent",
                        statement_2=f"净现比低于0.5 ({cash_finding.get('description', '')[:80]})",
                        severity="high",
                        question="请说明声称资金充裕但经营现金流远低于净利润的原因。",
                    )
                )

        # --- Rule 4: Customer diversification vs AR growth ---
        if _has_claim(prospectus_text, "customer_diverse"):
            ar_finding = next(
                (
                    f
                    for f in findings
                    if f.get("rule_id") == "AQ-001" and f.get("triggered")
                ),
                None,
            )
            if ar_finding:
                contradictions.append(
                    Contradiction(
                        type="contradiction",
                        source_1="ProspectusAgent",
                        statement_1="招股书声称客户多元化",
                        source_2="FinancialAgent",
                        statement_2="应收账款增速远超收入增速，存在大客户压货风险",
                        severity="warning",
                        question="请说明客户多元化声明与应收账款异常增长的矛盾。",
                    )
                )

        # --- Rule 5: Market leadership vs industry data ---
        if _has_claim(prospectus_text, "leadership") and industry_text:
            competitors_mentioned = bool(
                re.search(
                    r"竞争|对手|排名|rival|competitor", industry_text, re.IGNORECASE
                )
            )
            if competitors_mentioned:
                contradictions.append(
                    Contradiction(
                        type="red_flag",
                        source_1="ProspectusAgent",
                        statement_1="招股书声称行业领先/龙头地位",
                        source_2="IndustryAgent",
                        statement_2="行业分析显示存在多个主要竞争对手，市场地位需进一步验证",
                        severity="warning",
                        question="请提供市场份额数据验证行业领先地位的声明。",
                    )
                )

        # --- Rule 6: Forensic finding cross-checks ---
        for f in findings:
            if not f.get("triggered"):
                continue
            rule_id = f.get("rule_id", "")
            # Revenue authenticity issues contradict any growth claims
            if rule_id.startswith("RA-") and _has_claim(prospectus_text, "growth"):
                contradictions.append(
                    Contradiction(
                        type="red_flag",
                        source_1="ProspectusAgent",
                        statement_1="招股书声称业务增长",
                        source_2="FinancialAgent",
                        statement_2=f"[{rule_id}] {f.get('name', '')}: {f.get('description', '')[:100]}",
                        severity="high",
                        question=f"请说明收入增长真实性存疑的指标（{f.get('name', '')}）是否反映收入确认问题。",
                    )
                )

        return contradictions

    # ==================== Risk Prioritization Matrix ====================

    def _build_risk_matrix(
        self,
        fin_risks: list[dict],
        triggered_findings: list[dict],
        contradictions: list[Contradiction],
    ) -> list[RiskMatrixItem]:
        """Build a probability x impact risk matrix from all sources."""
        matrix: list[RiskMatrixItem] = []

        # --- From 6-rule risk engine ---
        for r in fin_risks:
            severity = r.get("severity", "medium")
            impact = self._severity_to_level(severity)
            is_observation = r.get("assessment_status") == "observation"
            # If trend data exists (multiple periods), probability is higher
            probability = "Low" if is_observation else "Medium"
            desc = r.get("description", "")
            if not is_observation and any(
                kw in desc for kw in ["连续", "持续", "三年", "declining", "persistent"]
            ):
                probability = "High"

            matrix.append(
                RiskMatrixItem(
                    risk_name=r.get("title", "Unknown"),
                    category=(
                        "financial_observation" if is_observation else "financial"
                    ),
                    probability=probability,
                    impact=impact,
                    score=self._calc_score(probability, impact),
                    evidence_refs=[r.get("title", "")],
                )
            )

        # --- From 20-rule forensic engine ---
        for f in triggered_findings:
            severity = f.get("severity", "info")
            impact = self._severity_to_level(severity)
            # Layer 2 (trend) findings have higher probability
            probability = "High" if f.get("layer", 1) == 2 else "Medium"

            matrix.append(
                RiskMatrixItem(
                    risk_name=f"[{f.get('rule_id', '')}] {f.get('name', '')}",
                    category=f.get("category", "financial"),
                    probability=probability,
                    impact=impact,
                    score=self._calc_score(probability, impact),
                    evidence_refs=[f.get("rule_id", "")],
                )
            )

        # --- From contradictions ---
        for c in contradictions:
            impact = self._severity_to_level(c.severity)
            matrix.append(
                RiskMatrixItem(
                    risk_name=f"Cross-agent contradiction: {c.statement_1[:40]}...",
                    category="governance",
                    probability="Medium",
                    impact=impact,
                    score=self._calc_score("Medium", impact),
                    evidence_refs=[c.question[:60]],
                )
            )

        # Sort by score descending
        matrix.sort(key=lambda x: x.score, reverse=True)
        return matrix[:15]  # Top 15

    # ==================== Investment Question Generation ====================

    # Question templates keyed by rule_id
    _QUESTION_TEMPLATES: ClassVar[dict[str, str]] = {
        "AQ-001": "请说明应收账款增速远超收入增速的原因，是否存在大客户压货或收入确认提前的情形？",
        "AQ-002": "请说明存货周转率下降但毛利率上升的合理性，是否少结转成本虚增毛利？",
        "AQ-003": "请说明在建工程长期不转固的原因，是否存在延迟计提折旧或通过工程款转移资金？",
        "AQ-004": "请说明应收账款及存货合计占比超30%的合理性，资产质量是否支撑IPO估值？",
        "AQ-005": "请说明预付账款占比超20%的具体构成，是否存在长期挂账未核销项目？",
        "AQ-006": "请说明其他应收款余额构成及对手方，是否存在关联方资金占用？",
        "AQ-007": "请说明商誉占比超10%的被收购方业绩达标情况，是否存在大额减值风险？",
        "AQ-008": "请说明开发支出资本化的依据及比例，是否符合会计准则？",
        "AQ-009": "请说明固定资产周转率下降但净利润上升的合理性，是否存在费用资本化？",
        "EQ-001": "请说明经营现金流净额长期低于净利润的原因，利润是否已转化为真实现金流入？",
        "EQ-002": "请说明销售回款率（收现比）持续偏低的理由，主要客户的信用期是否合理？",
        "EQ-003": "请说明现金循环周期过长的原因，公司在产业链中是否处于弱势地位？",
        "CS-001": "请说明其他应付款余额构成，是否存在民间借贷或表外负债？",
        "CS-002": "请说明预收账款持续下降的原因，是否预示业务萎缩或订单减少？",
        "CS-003": "请说明长期应付款的形成原因及融资成本，是否反映资金链紧张？",
        "CS-004": "请说明资本公积异常增大的形成原因，是否存在通过权益工具隐藏负债？",
        "RA-001": "请说明销售费用率持续上升的驱动因素，是否反映产品竞争力下降？",
        "RA-002": "请说明薪酬增速与收入增速的匹配性，收入增长是否真实？",
        "RA-003": "请说明收入增长与税金变动方向不一致的原因，收入确认与税务申报是否存在差异？",
        "RA-004": "请说明人均效能偏离行业水平的合理性，是否存在虚报员工人数或收入？",
    }

    def _generate_questions(
        self,
        triggered_findings: list[dict],
        contradictions: list[Contradiction],
        fin_risks: list[dict],
    ) -> list[str]:
        """Generate buy-side due diligence questions from all findings."""
        questions: list[str] = []
        seen = set()

        # 1. Questions from triggered forensic rules
        for f in triggered_findings:
            rule_id = f.get("rule_id", "")
            q = self._QUESTION_TEMPLATES.get(rule_id)
            if q and q not in seen:
                questions.append(q)
                seen.add(q)

        # 2. Questions from contradictions
        for c in contradictions:
            if c.question and c.question not in seen:
                questions.append(c.question)
                seen.add(c.question)

        # 3. Questions from 6-rule risk engine (if not already covered)
        for r in fin_risks[:5]:
            title = r.get("title", "")
            if title and not any(title[:20] in q for q in questions):
                q = f"请进一步说明'{title}'风险的具体影响及缓释措施。"
                if q not in seen:
                    questions.append(q)
                    seen.add(q)

        # 4. Standard IPO due diligence questions
        standard = [
            "请说明IPO募集资金的具体用途及预期回报率。",
            "请提供前五大客户及供应商的集中度数据及关联关系说明。",
        ]
        for q in standard:
            if q not in seen:
                questions.append(q)
                seen.add(q)

        return questions[:12]

    # ==================== Risk Level Determination ====================

    def _determine_risk_level(
        self,
        risk_matrix: list[RiskMatrixItem],
        contradictions: list[Contradiction],
    ) -> str:
        """Determine overall risk level from matrix and contradictions."""
        high_count = sum(1 for r in risk_matrix if r.score >= 6)
        critical_contradictions = sum(1 for c in contradictions if c.severity == "high")
        if high_count >= 3 or critical_contradictions >= 2:
            return "High"
        elif high_count >= 1 or critical_contradictions >= 1:
            return "Medium"
        else:
            return "Low"

    # ==================== Helper Methods ====================

    @staticmethod
    def _severity_to_level(severity: str) -> str:
        mapping = {
            "critical": "High",
            "high": "High",
            "warning": "Medium",
            "medium": "Medium",
            "info": "Low",
            "low": "Low",
        }
        return mapping.get(severity.lower(), "Medium")

    @staticmethod
    def _calc_score(probability: str, impact: str) -> int:
        rank = {"Low": 1, "Medium": 2, "High": 3}
        return rank.get(probability, 2) * rank.get(impact, 2)

    @staticmethod
    def _get_prospectus_text(prospectus_analysis: Any | None) -> str:
        if prospectus_analysis is None:
            return ""
        parts = []
        parts.append(getattr(prospectus_analysis, "business_model", "") or "")
        parts.append(getattr(prospectus_analysis, "raw_markdown", "") or "")
        claims = getattr(prospectus_analysis, "key_claims", []) or []
        parts.extend(claims)
        advantages = getattr(prospectus_analysis, "competitive_advantages", []) or []
        parts.extend(advantages)
        return " ".join(p for p in parts if p)

    @staticmethod
    def _get_industry_text(industry_analysis: Any | None) -> str:
        if industry_analysis is None:
            return ""
        parts = []
        parts.append(getattr(industry_analysis, "industry_overview", "") or "")
        parts.append(getattr(industry_analysis, "raw_markdown", "") or "")
        competitors = getattr(industry_analysis, "competitors", []) or []
        parts.extend(competitors)
        return " ".join(p for p in parts if p)

    @staticmethod
    def _summarize_financial_risks(risks: list | None) -> list[dict]:
        if not risks:
            return []
        return [
            {
                "title": getattr(r, "title", str(r)),
                "severity": getattr(r, "severity", ""),
                "description": getattr(r, "description", "")[:150],
                "assessment_status": getattr(r, "assessment_status", "observation"),
                "possible_explanations": getattr(r, "possible_explanations", []),
                "required_evidence": getattr(r, "required_evidence", []),
            }
            for r in risks[:10]
        ]

    @staticmethod
    def _summarize_findings(findings: list | None) -> list[dict]:
        if not findings:
            return []
        return [
            {
                "rule_id": getattr(f, "rule_id", ""),
                "name": getattr(f, "name", ""),
                "category": getattr(f, "category", ""),
                "layer": getattr(f, "layer", 1),
                "severity": getattr(f, "severity", ""),
                "triggered": getattr(f, "triggered", False),
                "description": getattr(f, "description", "")[:200],
                "recommendation": getattr(f, "recommendation", "")[:150],
            }
            for f in findings
        ]

    @staticmethod
    def _extract_finding_messages(
        agent_messages: list[AgentMessage] | None,
    ) -> list[dict]:
        """Extract finding-type messages from the agent message bus."""
        if not agent_messages:
            return []
        return [
            {
                "sender": msg.sender,
                "content": msg.content,
                "payload": msg.payload if hasattr(msg, "payload") else {},
            }
            for msg in agent_messages
            if msg.message_type == "finding"
        ]

    @staticmethod
    def _extract_major_risks(
        fin_risks: list[dict],
        triggered_findings: list[dict],
        contradictions: list[Contradiction],
    ) -> list[str]:
        major: list[str] = []
        for r in fin_risks[:5]:
            major.append(r["title"])
        for f in triggered_findings[:5]:
            name = f"[{f.get('rule_id', '')}] {f.get('name', '')}"
            if name not in major:
                major.append(name)
        for c in contradictions[:3]:
            desc = f"[矛盾] {c.statement_1[:30]} vs {c.statement_2[:30]}"
            if desc not in major:
                major.append(desc)
        return major[:10]

    @staticmethod
    def _build_markdown(
        company: str,
        risk_level: str,
        major_risks: list[str],
        contradictions: list[Contradiction],
        risk_matrix: list[RiskMatrixItem],
        investment_questions: list[str],
        fin_risks: list[dict],
        triggered_findings: list[dict],
    ) -> str:
        sections: list[str] = [
            f"# {company} Investment Committee Review",
            "",
            "> Auto-generated from cross-agent analysis (offline mode).",
            "",
            f"## Risk Level: {risk_level}",
            "",
        ]

        # Risk Matrix
        sections.append("## Risk Prioritization Matrix")
        sections.append("")
        sections.append("| Risk | Category | Probability | Impact | Score |")
        sections.append("|------|----------|-------------|--------|-------|")
        for r in risk_matrix[:10]:
            sections.append(
                f"| {r.risk_name[:50]} | {r.category} | {r.probability} | {r.impact} | {r.score} |"
            )
        sections.append("")

        # Contradictions
        sections.append("## Cross-Agent Contradiction Findings")
        if contradictions:
            for c in contradictions:
                sections.append(f"- **[{c.severity.upper()}]** {c.statement_1}")
                sections.append(f"  - vs {c.statement_2}")
                sections.append(f"  - Follow-up: {c.question}")
                sections.append("")
        else:
            sections.append("- No significant contradictions detected.")
            sections.append("")

        # Major Risks
        sections.append("## Major Risks")
        for r in major_risks:
            sections.append(f"- {r}")
        sections.append("")

        # Summary stats
        sections.append("## Analysis Summary")
        sections.append(f"- 6-rule engine alerts: {len(fin_risks)}")
        sections.append(
            f"- 20-rule forensic findings: {len(triggered_findings)} triggered"
        )
        sections.append(f"- Cross-agent contradictions: {len(contradictions)}")
        sections.append(f"- Total risk matrix items: {len(risk_matrix)}")
        sections.append("")

        # Investment Questions
        sections.append("## Investment Committee Questions")
        for i, q in enumerate(investment_questions, 1):
            sections.append(f"{i}. {q}")
        sections.append("")

        return "\n".join(sections)

    # ==================== LLM Mode ====================

    def _llm_review(
        self,
        company: str,
        prospectus_analysis: Any | None,
        industry_analysis: Any | None,
        financial_markdown: str,
        fin_risks: list[dict],
        fin_findings: list[dict],
        finding_messages: list[dict],
    ) -> RiskReview:
        """LLM-enhanced review: offline logic + LLM interpretation."""
        # Run offline logic first
        prospectus_text = self._get_prospectus_text(prospectus_analysis)
        industry_text = self._get_industry_text(industry_analysis)
        triggered = [f for f in fin_findings if f.get("triggered")]

        contradictions = self._detect_contradictions(
            prospectus_text,
            prospectus_analysis,
            None,
            fin_findings,  # metrics not available in this path
            industry_text,
        )
        risk_matrix = self._build_risk_matrix(fin_risks, triggered, contradictions)
        risk_level = self._determine_risk_level(risk_matrix, contradictions)

        # Build LLM context
        context = {
            "company": company,
            "prospectus_claims": getattr(prospectus_analysis, "key_claims", []),
            "prospectus_advantages": getattr(
                prospectus_analysis, "competitive_advantages", []
            ),
            "industry_overview": getattr(industry_analysis, "industry_overview", ""),
            "industry_competitors": getattr(industry_analysis, "competitors", []),
            "financial_risks": fin_risks[:5],
            "forensic_findings_triggered": triggered[:10],
            "offline_contradictions": [
                {"s1": c.statement_1, "s2": c.statement_2, "severity": c.severity}
                for c in contradictions
            ],
            "agent_finding_messages": finding_messages[:5],
        }

        prompt = (
            f"Please conduct cross-validation and investment risk review for {company}'s IPO.\n\n"
            f"Context from all analyst agents (JSON):\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            f"Financial analysis excerpt:\n{financial_markdown[:2000]}\n\n"
            f"Output (Markdown):\n"
            f"## Risk Level\n(Low / Medium / High, with justification)\n\n"
            f"## Contradiction Analysis\n"
            f"(Verify or refute the detected contradictions; identify new ones)\n\n"
            f"## Investment Committee Questions\n"
            f"(Buy-side due diligence questions, specific and actionable)"
        )

        markdown = self.client.complete_text(
            system_prompt=RISK_REVIEW_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=2000,
        )

        # Merge LLM output with offline analysis
        questions = self._generate_questions(triggered, contradictions, fin_risks)

        return RiskReview(
            company=company,
            risk_level=risk_level,
            contradictions=contradictions,
            risk_matrix=risk_matrix,
            major_risks=self._extract_major_risks(fin_risks, triggered, contradictions),
            investment_questions=questions,
            raw_markdown=markdown,
        )
