"""
Financial Analyst Agent -- Tool-Augmented Multi-Agent Architecture

The Financial Analyst Agent is the *boss* of the financial branch.
It does NOT receive pre-computed results from a pipeline. Instead, it
autonomously orchestrates a set of internal tools:

    Tools available to this Agent:
      1. Raw Statement Extraction   -- extract three major financial statements from PDF tables
      2. Financial Fact Parser      -- parse line items into structured StatementFact objects
      3. Metric Engine              -- compute 15+ financial ratios and growth metrics
      4. Risk Rule Engine           -- 6-rule heuristic scan (backward-compatible alerts)
      5. Financial Forensic Engine  -- 20-rule IPO due-diligence framework (4 categories, 3 layers)

After calling tools, the Agent applies LLM reasoning (Layer 3) on the
forensic findings to produce investment-quality contextual analysis.

In offline mode (no LLM), the Agent assembles a structured summary from
tool outputs, ensuring the pipeline still produces useful results.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar

from ipo_financial_agent.extraction.fast_financial_parser import (
    RawStatementFactExtractor,
    TopicFinancialNoteParser,
)
from ipo_financial_agent.extraction.raw_statement_extractor import RawStatementExtractor
from ipo_financial_agent.finance.forensic_engine import FinancialForensicEngine
from ipo_financial_agent.finance.metric_engine import MetricEngine
from ipo_financial_agent.finance.risk_rules import RiskRuleEngine
from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.llm.prompts import FINANCIAL_ANALYSIS_SYSTEM_PROMPT
from ipo_financial_agent.models import (
    AnalysisResult,
    FinancialExtractionResult,
    MetricResult,
    RiskFinding,
    StatementFact,
)
from ipo_financial_agent.models_agent import FinancialFinding
from ipo_financial_agent.schemas import ResearchTask

T = TypeVar("T")


class FinancialAnalysisAgent:
    """
    Tool-Augmented Financial Analyst Agent.

    Unlike a pipeline step, this Agent *owns* the entire financial analysis
    workflow. It receives raw document data (pages, section hits) and
    autonomously decides which tools to call, in what order, and how to
    interpret the results.

    The Agent's tools are:
      - _tool_extract_raw_statements()  -> RawStatementTable[]
      - _tool_parse_facts()             -> StatementFact[]
      - _tool_parse_notes()             -> FinancialNote[]  (LLM)
      - _tool_calculate_metrics()       -> MetricResult[]
      - _tool_scan_risk_rules()         -> RiskFinding[]    (6-rule engine)
      - _tool_run_forensic_engine()     -> FinancialFinding[] (20-rule DD engine)

    The final _llm_reasoning() step is Layer 3 of the Forensic Engine:
    contextual interpretation of triggered rules using business context.
    """

    FACT_BUDGET_CHARS = 6500
    NOTE_BUDGET_CHARS = 5000
    METRIC_BUDGET_CHARS = 1600
    RISK_BUDGET_CHARS = 1600
    FINDING_BUDGET_CHARS = 3000

    def __init__(self, client: OpenAICompatibleClient | None = None) -> None:
        self.client = client
        # Tool instances (lazy-init within analyze)
        self._raw_extractor = RawStatementExtractor()
        self._fact_extractor = RawStatementFactExtractor()
        self._metric_engine = MetricEngine()
        self._risk_engine = RiskRuleEngine()
        self._forensic_engine = FinancialForensicEngine()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def analyze(
        self,
        *,
        document_id: str,
        company: str,
        pages: list[Any],
        section_hits: list[Any],
        topic_page_groups: dict[str, list[Any]] | None = None,
        llm_mode: str = "auto",
        task: ResearchTask | None = None,
    ) -> dict[str, Any]:
        """
        Run the full financial analysis as a Tool-Augmented Agent.

        Returns a dict with keys:
          - analysis: AnalysisResult (markdown report)
          - raw_statements: list[RawStatementTable]
          - extraction_result: FinancialExtractionResult (facts + notes)
          - metrics: list[MetricResult]
          - risks: list[RiskFinding]      (6-rule engine)
          - findings: list[FinancialFinding]  (20-rule forensic engine)
        """
        if task is not None and task.target_agent != "financial":
            raise ValueError(
                f"FinancialAnalysisAgent cannot execute task for {task.target_agent}"
            )

        # ---- Tool 1: Extract raw statements from PDF tables ----
        print("[financial-agent] Tool 1: Raw Statement Extraction", flush=True)
        raw_statements = self._tool_extract_raw_statements(
            pages=pages, section_hits=section_hits, company=company, document_id=document_id,
        )
        print(f"  -> {len(raw_statements)} statement tables extracted", flush=True)

        # ---- Tool 2: Parse financial facts ----
        print("[financial-agent] Tool 2: Financial Fact Parser", flush=True)
        facts = self._tool_parse_facts(
            document_id=document_id, company=company, raw_statements=raw_statements,
        )
        print(f"  -> {len(facts)} facts extracted", flush=True)

        # ---- Tool 3: Parse financial notes (LLM, optional) ----
        notes_result = FinancialExtractionResult()
        if self.client and topic_page_groups:
            print("[financial-agent] Tool 3: Financial Note Parser (LLM)", flush=True)
            notes_result = self._tool_parse_notes(
                document_id=document_id, company=company,
                topic_page_groups=topic_page_groups,
            )
            print(f"  -> {len(notes_result.financial_notes)} notes extracted", flush=True)
        else:
            notes_result.warnings.append("LLM not called: financial notes not extracted.")
            print("[financial-agent] Tool 3: Skipped (no LLM / no topic groups)", flush=True)

        extraction_result = FinancialExtractionResult(
            statement_facts=facts,
            financial_notes=notes_result.financial_notes,
            warnings=notes_result.warnings,
        )

        # ---- Tool 4: Calculate metrics ----
        print("[financial-agent] Tool 4: Metric Engine", flush=True)
        metrics = self._tool_calculate_metrics(document_id=document_id, facts=facts)
        print(f"  -> {len(metrics)} metrics computed", flush=True)

        # ---- Tool 5: Risk Rule Engine (6 rules, backward compat) ----
        print("[financial-agent] Tool 5: Risk Rule Engine (6 rules)", flush=True)
        risks = self._tool_scan_risk_rules(
            document_id=document_id, metrics=metrics, facts=facts,
        )
        print(f"  -> {len(risks)} risk alerts", flush=True)

        # ---- Tool 6: Financial Forensic Engine (20 rules) ----
        print("[financial-agent] Tool 6: Financial Forensic Engine (20 rules)", flush=True)
        findings = self._tool_run_forensic_engine(
            document_id=document_id, facts=facts, metrics=metrics,
            raw_statements=raw_statements,
        )
        triggered = [f for f in findings if f.triggered]
        print(
            f"  -> {len(findings)} findings ({len(triggered)} triggered, "
            f"{len([f for f in findings if f.severity == 'insufficient_data' or 'insufficient' in f.description.lower()])} insufficient)",
            flush=True,
        )

        # ---- Layer 3: LLM Reasoning on findings ----
        print("[financial-agent] Layer 3: LLM Reasoning on forensic findings", flush=True)
        if self.client:
            analysis = self._llm_reasoning(
                document_id=document_id, company=company,
                facts=facts, notes=extraction_result.financial_notes,
                metrics=metrics, risks=risks, findings=findings,
            )
        else:
            analysis = self._offline_reasoning(
                document_id=document_id, company=company,
                facts=facts, metrics=metrics, risks=risks, findings=findings,
            )

        print(
            f"[financial-agent] Analysis complete: {len(analysis.markdown)} chars, "
            f"{len(findings)} forensic findings ({len(triggered)} triggered)",
            flush=True,
        )

        return {
            "task": task,
            "analysis": analysis,
            "raw_statements": raw_statements,
            "extraction_result": extraction_result,
            "metrics": metrics,
            "risks": risks,
            "findings": findings,
        }

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def _tool_extract_raw_statements(
        self, *, pages, section_hits, company, document_id
    ) -> list:
        """Tool 1: Extract three major financial statements from PDF tables."""
        return self._raw_extractor.extract(
            pages=pages, section_hits=section_hits,
            company=company, document_id=document_id,
        )

    def _tool_parse_facts(
        self, *, document_id, company, raw_statements
    ) -> list[StatementFact]:
        """Tool 2: Parse line items into structured StatementFact objects."""
        return self._fact_extractor.extract(
            document_id=document_id, company=company,
            raw_statements=raw_statements,
        )

    def _tool_parse_notes(
        self, *, document_id, company, topic_page_groups
    ) -> FinancialExtractionResult:
        """Tool 3: Parse financial notes using LLM (optional)."""
        return TopicFinancialNoteParser(self.client, max_tokens=1400).parse(
            document_id=document_id, company=company,
            topic_page_groups=topic_page_groups,
        )

    def _tool_calculate_metrics(
        self, *, document_id, facts
    ) -> list[MetricResult]:
        """Tool 4: Compute financial ratios and growth metrics."""
        issuer = next((fact.company for fact in facts if fact.company), None)
        return self._metric_engine.calculate(document_id, facts, reporting_entity=issuer)

    def _tool_scan_risk_rules(
        self, *, document_id, metrics, facts
    ) -> list[RiskFinding]:
        """Tool 5: 6-rule heuristic risk scan (backward-compatible)."""
        return self._risk_engine.scan(document_id, metrics, facts)

    def _tool_run_forensic_engine(
        self, *, document_id, facts, metrics, raw_statements
    ) -> list[FinancialFinding]:
        """Tool 6: 20-rule IPO Financial Due Diligence Engine."""
        return self._forensic_engine.analyze(
            document_id=document_id,
            facts=facts, metrics=metrics, raw_statements=raw_statements,
        )

    # ------------------------------------------------------------------
    # Layer 3: LLM Reasoning
    # ------------------------------------------------------------------

    def _llm_reasoning(
        self, *, document_id, company, facts, notes, metrics, risks, findings
    ) -> AnalysisResult:
        """Layer 3: LLM contextual interpretation of forensic findings."""

        context = self._build_context(
            facts=facts, notes=notes, metrics=metrics,
            risks=risks, findings=findings,
        )
        context_json = json.dumps(context, ensure_ascii=False, separators=(",", ":"))

        print(
            f"[financial-agent] LLM context: "
            f"facts={len(context['facts'])}, notes={len(context['notes'])}, "
            f"metrics={len(context['metrics'])}, risks={len(context['risks'])}, "
            f"findings={len(context['findings'])}, chars={len(context_json)}",
            flush=True,
        )

        prompt = (
            f"Please generate a comprehensive IPO financial analysis report for {company}.\n"
            "Base all conclusions strictly on the structured data below.\n"
            "Cite source pages in P12 or P12-P14 format at the end of key judgments.\n"
            "Field guide: facts = financial statement line items; notes = prospectus note explanations; "
            "metrics = Python-computed ratios; risks = 6-rule heuristic alerts; "
            "findings = 20-rule Financial Forensic Engine results (4 categories).\n"
            "For each triggered forensic finding, provide contextual interpretation: "
            "WHY the anomaly exists, WHAT it means for investors, and WHAT to investigate further.\n"
            "Do not output raw data dumps -- synthesize and clearly distinguish facts, company explanations, and analytical judgments.\n\n"
            f"{context_json}"
        )

        markdown = self.client.complete_text(
            system_prompt=FINANCIAL_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=prompt, max_tokens=2400,
        )

        known_pages = {
            *(f.page for f in facts),
            *(p for n in notes for p in n.pages),
            *(p for m in metrics for p in m.source_pages),
            *(p for r in risks for p in r.source_pages),
            *(e.page for f in findings for e in f.evidence),
        }
        cited_pages = sorted(
            {int(v) for v in re.findall(r"P(\d+)", markdown, flags=re.I) if int(v) in known_pages}
        )

        return AnalysisResult(
            document_id=document_id, company=company,
            markdown=markdown, cited_pages=cited_pages,
            model=self.client.settings.llm_model,
        )

    # ------------------------------------------------------------------
    # Offline reasoning (no LLM)
    # ------------------------------------------------------------------

    def _offline_reasoning(
        self, *, document_id, company, facts, metrics, risks, findings
    ) -> AnalysisResult:
        """Assemble structured analysis from tool outputs without LLM."""

        triggered = [f for f in findings if f.triggered]
        by_cat: dict[str, list[FinancialFinding]] = defaultdict(list)
        for f in triggered:
            by_cat[f.category].append(f)

        cat_names = {
            "asset_quality": "A. Asset Quality Assessment",
            "earnings_quality": "B. Earnings Quality Assessment",
            "capital_structure": "C. Capital Structure Assessment",
            "revenue_authenticity": "D. Revenue Authenticity Assessment",
        }

        lines = [
            f"# {company} IPO Financial Forensic Analysis",
            "",
            "> LLM not active. Below is a structured summary of tool outputs:",
            "> extraction, metrics, 6-rule risk engine, and 20-rule forensic engine.",
            "",
            "## Tool Execution Summary",
            "",
            f"- Financial facts extracted: {len(facts)}",
            f"- Metrics computed: {len(metrics)}",
            f"- Risk rule alerts (6-rule engine): {len(risks)}",
            f"- Forensic findings (20-rule engine): {len(findings)} "
            f"({len(triggered)} triggered)",
            "",
            "## Financial Forensic Engine Results",
            "",
        ]

        if triggered:
            for cat_key in ["asset_quality", "earnings_quality", "capital_structure", "revenue_authenticity"]:
                cat_findings = by_cat.get(cat_key, [])
                if not cat_findings:
                    continue
                lines.append(f"### {cat_names.get(cat_key, cat_key)}")
                lines.append("")
                for f in cat_findings:
                    pages_str = ", ".join(f"P{e.page}" for e in f.evidence if e.page) or "N/A"
                    lines.append(f"- **[{f.rule_id}] {f.name}** (severity: {f.severity})")
                    lines.append(f"  - {f.description}")
                    if f.recommendation:
                        lines.append(f"  - Recommendation: {f.recommendation}")
                    lines.append(f"  - Evidence: {pages_str}")
                    lines.append("")
        else:
            lines.append("No forensic rules triggered. All 20 rules evaluated successfully.")
            lines.append("")

        # Also show insufficient data rules
        insufficient = [f for f in findings if "insufficient" in f.description.lower()]
        if insufficient:
            lines.append("### Rules with Insufficient Data")
            lines.append("")
            for f in insufficient:
                lines.append(f"- [{f.rule_id}] {f.name}: {f.description}")
            lines.append("")

        # 6-rule engine results
        if risks:
            lines.append("## 6-Rule Risk Engine Alerts")
            lines.append("")
            for r in risks:
                pages = ", ".join(f"P{p}" for p in r.source_pages)
                lines.append(f"- **{r.title}** ({r.severity}): {r.description} ({pages})")
            lines.append("")

        # Key metrics
        if metrics:
            lines.append("## Key Metrics")
            lines.append("")
            for m in sorted(metrics, key=lambda x: (x.period, x.metric_name)):
                lines.append(f"- {m.metric_name} ({m.period}): {m.display_value}")
            lines.append("")

        cited_pages = sorted({
            e.page for f in findings for e in f.evidence if e.page
        } | {p for r in risks for p in r.source_pages})

        return AnalysisResult(
            document_id=document_id, company=company,
            markdown="\n".join(lines), cited_pages=cited_pages, model=None,
        )

    # ------------------------------------------------------------------
    # Context building (for LLM mode)
    # ------------------------------------------------------------------

    def _build_context(
        self, *, facts, notes, metrics, risks, findings
    ) -> dict[str, Any]:
        fact_candidates = self._prepare_fact_candidates(facts)
        note_candidates = self._prepare_note_candidates(notes)

        compact_facts = self._take_with_budget(
            fact_candidates, self._compact_fact, self.FACT_BUDGET_CHARS)
        compact_notes = self._take_with_budget(
            note_candidates, self._compact_note, self.NOTE_BUDGET_CHARS)
        compact_metrics = self._take_with_budget(
            sorted(metrics, key=lambda x: (x.status != "warning", x.period, x.metric_name)),
            self._compact_metric, self.METRIC_BUDGET_CHARS)
        compact_risks = self._take_with_budget(
            sorted(risks, key=lambda x: (self._severity_order(x.severity), x.category, x.title)),
            self._compact_risk, self.RISK_BUDGET_CHARS)
        compact_findings = self._take_with_budget(
            sorted(findings, key=lambda x: (not x.triggered, x.severity != "critical", x.rule_id)),
            self._compact_finding, self.FINDING_BUDGET_CHARS)

        return {
            "facts": compact_facts,
            "notes": compact_notes,
            "metrics": compact_metrics,
            "risks": compact_risks,
            "findings": compact_findings,
        }

    @staticmethod
    def _prepare_fact_candidates(facts: list[StatementFact]) -> list[StatementFact]:
        best: dict[tuple, StatementFact] = {}
        for fact in facts:
            key = (fact.statement_name, fact.item_name, fact.period,
                   fact.raw_value, fact.entity_scope, fact.canonical_tag)
            cur = best.get(key)
            if cur is None or fact.confidence > cur.confidence:
                best[key] = fact
        deduped = sorted(best.values(), key=lambda x: (
            x.canonical_tag == "other", -x.confidence, x.page, x.period))
        return FinancialAnalysisAgent._round_robin(deduped, key=lambda x: x.canonical_tag)

    @staticmethod
    def _prepare_note_candidates(notes: list) -> list:
        ordered = sorted(notes, key=lambda x: (
            -x.confidence, min(x.pages) if x.pages else 999999, x.title))
        return FinancialAnalysisAgent._round_robin(ordered, key=lambda x: x.topic)

    @staticmethod
    def _round_robin(items: list[T], *, key: Callable[[T], str]) -> list[T]:
        groups: dict[str, list[T]] = defaultdict(list)
        for item in items:
            groups[str(key(item))].append(item)
        names = sorted(groups)
        output: list[T] = []
        idx = 0
        while True:
            added = False
            for name in names:
                grp = groups[name]
                if idx < len(grp):
                    output.append(grp[idx])
                    added = True
            if not added:
                break
            idx += 1
        return output

    @staticmethod
    def _take_with_budget(
        items: list[T], transform: Callable[[T], dict], budget: int
    ) -> list[dict]:
        output: list[dict] = []
        used = 2
        for item in items:
            compact = transform(item)
            encoded = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
            if used + len(encoded) + 1 > budget:
                continue
            output.append(compact)
            used += len(encoded) + 1
        return output

    @staticmethod
    def _compact_fact(fact: StatementFact) -> dict[str, Any]:
        return {
            "statement": fact.statement_name, "item": fact.item_name,
            "tag": fact.canonical_tag, "period": fact.period,
            "value": fact.value, "raw": fact.raw_value,
            "unit": fact.unit, "page": fact.page,
        }

    @staticmethod
    def _compact_note(note) -> dict[str, Any]:
        return {
            "topic": note.topic, "title": note.title,
            "type": note.information_type,
            "summary": note.summary[:180],
            "pages": note.pages,
            "explanations": [
                {"type": e.explanation_type, "text": e.content[:140], "page": e.page}
                for e in note.explanations[:3]
            ],
        }

    @staticmethod
    def _compact_metric(metric: MetricResult) -> dict[str, Any]:
        return {
            "name": metric.metric_name, "code": metric.metric_code,
            "period": metric.period, "value": metric.value,
            "display": metric.display_value, "pages": metric.source_pages,
        }

    @staticmethod
    def _compact_risk(risk: RiskFinding) -> dict[str, Any]:
        return {
            "category": risk.category, "title": risk.title,
            "severity": risk.severity,
            "description": risk.description[:240],
            "pages": risk.source_pages, "rule": risk.rule_code,
        }

    @staticmethod
    def _compact_finding(finding: FinancialFinding) -> dict[str, Any]:
        return {
            "rule_id": finding.rule_id, "name": finding.name,
            "category": finding.category, "layer": finding.layer,
            "severity": finding.severity, "triggered": finding.triggered,
            "description": finding.description[:300],
            "metrics": finding.metrics,
            "evidence": [{"page": e.page, "source": e.source, "detail": e.detail}
                         for e in finding.evidence[:3]],
            "recommendation": finding.recommendation[:200] if finding.recommendation else "",
        }

    @staticmethod
    def _severity_order(severity: str) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(severity, 3)
