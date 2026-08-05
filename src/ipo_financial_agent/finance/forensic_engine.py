"""
IPO Financial Due Diligence Engine

20 rules across 4 categories, 3 layers:

A. Asset Quality Assessment       (AQ-001 ~ AQ-009)  9 rules
B. Earnings Quality Assessment    (EQ-001 ~ EQ-003)  3 rules
C. Capital Structure Assessment   (CS-001 ~ CS-004)  4 rules
D. Revenue Authenticity Assessment (RA-001 ~ RA-004)  4 rules

Layers:
  Layer 1: Hard rules        -- deterministic threshold checks
  Layer 2: Trend analysis    -- multi-year comparison
  Layer 3: LLM Reasoning     -- contextual interpretation (handled by Financial Analyst Agent)

Each rule returns a FinancialFinding with rule_id, category, layer, severity,
triggered flag, metrics dict, and evidence list (page + source + detail).
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from ipo_financial_agent.models import MetricResult, RawStatementTable, StatementFact
from ipo_financial_agent.models_agent import Evidence, FinancialFinding

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
_NUM_RE = re.compile(r"^\(?-?\d[\d,]*(?:\.\d+)?\)?%?$")


def _parse_num(cell: str) -> float | None:
    """Parse a numeric cell, handling commas and parentheses (negatives)."""
    s = cell.strip().replace(",", "")
    if not _NUM_RE.match(s):
        return None
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


def _sort_periods(periods: list[str]) -> list[str]:
    return sorted(set(periods), key=lambda p: tuple(int(x) for x in re.findall(r"\d+", p)) or (9999,))


class FinancialForensicEngine:
    """
    IPO Financial Due Diligence Engine.

    Usage:
        engine = FinancialForensicEngine()
        findings = engine.analyze(document_id, facts, metrics, raw_statements)

    The engine runs all 20 rules and returns a list of FinancialFinding objects.
    Rules that cannot be evaluated due to missing data return triggered=False
    with severity='info' and a description explaining what data is needed.
    """

    CAT_ASSET = "asset_quality"
    CAT_EARNINGS = "earnings_quality"
    CAT_CAPITAL = "capital_structure"
    CAT_REVENUE = "revenue_authenticity"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        document_id: str,
        facts: list[StatementFact],
        metrics: list[MetricResult],
        raw_statements: list[RawStatementTable],
    ) -> list[FinancialFinding]:
        """Run all 20 due-diligence rules and return findings."""
        fact_map = self._build_fact_map(facts)
        metric_map = self._build_metric_map(metrics)
        raw_index = self._build_raw_index(raw_statements)

        findings: list[FinancialFinding] = []
        findings.extend(self._check_asset_quality(document_id, fact_map, metric_map, raw_index))
        findings.extend(self._check_earnings_quality(document_id, fact_map, metric_map))
        findings.extend(self._check_capital_structure(document_id, fact_map, metric_map, raw_index))
        findings.extend(self._check_revenue_authenticity(document_id, fact_map, metric_map, raw_index))
        return findings

    # ------------------------------------------------------------------
    # Lookup builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_fact_map(
        facts: list[StatementFact],
    ) -> dict[str, dict[str, StatementFact]]:
        """Return {canonical_tag: {period: StatementFact}}."""
        m: dict[str, dict[str, StatementFact]] = defaultdict(dict)
        for f in facts:
            if f.value is None:
                continue
            cur = m[f.canonical_tag].get(f.period)
            if cur is None or f.confidence > cur.confidence:
                m[f.canonical_tag][f.period] = f
        return dict(m)

    @staticmethod
    def _build_metric_map(
        metrics: list[MetricResult],
    ) -> dict[str, dict[str, MetricResult]]:
        """Return {metric_code: {period: MetricResult}}."""
        m: dict[str, dict[str, MetricResult]] = defaultdict(dict)
        for metric in metrics:
            if metric.value is not None:
                m[metric.metric_code][metric.period] = metric
        return dict(m)

    @staticmethod
    def _build_raw_index(
        raw_statements: list[RawStatementTable],
    ) -> dict[str, list[dict[str, Any]]]:
        """Index raw statement rows by normalized item name.

        Returns {item_name_lower: [{period, value, page, table_type}, ...]}.
        """
        index: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for table in raw_statements:
            # Find periods from header rows
            periods: list[str] = []
            for hdr in table.rows[:8]:
                for cell in hdr:
                    for match in _YEAR_RE.finditer(cell):
                        period = match.group(0)
                        if period not in periods:
                            periods.append(period)
            if not periods:
                continue
            for row_idx, row in enumerate(table.rows):
                if len(row) < 2:
                    continue
                name = row[0].strip()
                if not name:
                    continue
                nums: list[float] = []
                for cell in row[1:]:
                    v = _parse_num(cell)
                    if v is not None:
                        nums.append(v)
                if not nums:
                    continue
                page = (
                    table.row_pages[row_idx]
                    if row_idx < len(table.row_pages)
                    else (table.pages[0] if table.pages else 0)
                )
                paired = nums[-len(periods):]
                p_periods = periods[-len(paired):]
                for per, val in zip(p_periods, paired):
                    index[name.lower()].append({
                        "period": per,
                        "value": val,
                        "page": page,
                        "statement_type": table.statement_type,
                        "table_id": table.table_id,
                    })
        return dict(index)

    # ------------------------------------------------------------------
    # Value accessors
    # ------------------------------------------------------------------

    @staticmethod
    def _latest(fact_map: dict[str, dict[str, StatementFact]], tag: str) -> StatementFact | None:
        periods = _sort_periods(list(fact_map.get(tag, {}).keys()))
        if not periods:
            return None
        return fact_map[tag][periods[-1]]

    @staticmethod
    def _fact_series(
        fact_map: dict[str, dict[str, StatementFact]], tag: str
    ) -> list[tuple[str, StatementFact]]:
        periods = _sort_periods(list(fact_map.get(tag, {}).keys()))
        return [(p, fact_map[tag][p]) for p in periods]

    @staticmethod
    def _metric_val(metric_map: dict, code: str, period: str | None = None) -> float | None:
        m = metric_map.get(code, {})
        if not m:
            return None
        if period:
            r = m.get(period)
            return r.value if r else None
        periods = _sort_periods(list(m.keys()))
        if not periods:
            return None
        return m[periods[-1]].value

    @staticmethod
    def _metric_series(metric_map: dict, code: str) -> list[tuple[str, float]]:
        m = metric_map.get(code, {})
        periods = _sort_periods(list(m.keys()))
        return [(p, m[p].value) for p in periods if m[p].value is not None]

    def _raw_lookup(self, raw_index: dict, keywords: list[str]) -> list[dict[str, Any]]:
        """Search raw statement index for items matching any keyword."""
        results: list[dict[str, Any]] = []
        for name_lower, entries in raw_index.items():
            if any(kw.lower() in name_lower for kw in keywords):
                results.extend(entries)
        # Sort by period
        results.sort(key=lambda e: tuple(int(x) for x in re.findall(r"\d+", e["period"])) or (9999,))
        return results

    # ------------------------------------------------------------------
    # A. Asset Quality Assessment (9 rules)
    # ------------------------------------------------------------------

    def _check_asset_quality(
        self,
        doc_id: str,
        fact_map: dict,
        metric_map: dict,
        raw_index: dict,
    ) -> list[FinancialFinding]:
        return [
            self._aq001_cash_debt_dual_high(doc_id, fact_map),
            self._aq002_inventory_turnover_vs_margin(doc_id, metric_map),
            self._aq003_construction_in_progress(doc_id, raw_index, fact_map),
            self._aq004_receivable_inventory_ratio(doc_id, fact_map),
            self._aq005_prepayment_ratio(doc_id, raw_index, fact_map),
            self._aq006_other_receivable_large(doc_id, fact_map),
            self._aq007_goodwill_ratio(doc_id, raw_index, fact_map),
            self._aq008_development_expenditure(doc_id, raw_index, fact_map),
            self._aq009_fixed_asset_turnover_vs_profit(doc_id, fact_map, metric_map),
        ]

    def _aq001_cash_debt_dual_high(
        self, doc_id: str, fact_map: dict
    ) -> FinancialFinding:
        """AQ-001: Cash and interest-bearing debt both high (存贷双高)."""
        cash = self._latest(fact_map, "cash")
        short_debt = self._latest(fact_map, "short_term_borrowing")
        long_debt = self._latest(fact_map, "long_term_borrowing")
        assets = self._latest(fact_map, "total_assets")

        if not cash or not assets or assets.value == 0:
            return self._insufficient("AQ-001", "存贷双高", self.CAT_ASSET, 1,
                                      "Need cash and total_assets from balance sheet.")

        debt_val = 0.0
        debt_parts: list[str] = []
        if short_debt and short_debt.value:
            debt_val += short_debt.value
            debt_parts.append(f"short-term={short_debt.value:.0f}")
        if long_debt and long_debt.value:
            debt_val += long_debt.value
            debt_parts.append(f"long-term={long_debt.value:.0f}")

        cash_ratio = cash.value / assets.value if assets.value else 0
        debt_ratio = debt_val / assets.value if assets.value else 0
        triggered = cash_ratio > 0.15 and debt_ratio > 0.15

        evidence = [
            Evidence(page=cash.page, source="balance_sheet",
                     detail=f"cash={cash.value:.0f}, total_assets={assets.value:.0f}")
        ]
        if short_debt:
            evidence.append(Evidence(page=short_debt.page, source="balance_sheet",
                                     detail=f"short_term_borrowing={short_debt.value:.0f}"))
        if long_debt:
            evidence.append(Evidence(page=long_debt.page, source="balance_sheet",
                                     detail=f"long_term_borrowing={long_debt.value:.0f}"))

        return FinancialFinding(
            rule_id="AQ-001", name="存贷双高", category=self.CAT_ASSET, layer=1,
            severity="high" if triggered else "info",
            triggered=triggered,
            description=(
                f"cash/assets={cash_ratio:.1%}, interest_bearing_debt/assets={debt_ratio:.1%}"
                if triggered else
                f"cash/assets={cash_ratio:.1%}, debt/assets={debt_ratio:.1%} -- no dual-high pattern."
            ),
            metrics={"cash_ratio": round(cash_ratio, 4), "debt_ratio": round(debt_ratio, 4)},
            evidence=evidence,
            recommendation="Verify interest_income/cash ratio; if far below market rate, investigate fund restriction." if triggered else "",
        )

    def _aq002_inventory_turnover_vs_margin(
        self, doc_id: str, metric_map: dict
    ) -> FinancialFinding:
        """AQ-002: Inventory turnover declining while gross margin rising (Layer 2)."""
        gm_series = self._metric_series(metric_map, "gross_margin")
        inv_growth = self._metric_val(metric_map, "inventory_growth")
        rev_growth = self._metric_val(metric_map, "revenue_growth")

        if len(gm_series) < 2:
            return self._insufficient("AQ-002", "存货周转下降但毛利率上升", self.CAT_ASSET, 2,
                                      "Need >= 2 periods of gross_margin data.")

        gm_rising = gm_series[-1][1] > gm_series[-2][1]
        turnover_declining = (
            inv_growth is not None and rev_growth is not None and inv_growth > rev_growth
        )
        triggered = gm_rising and turnover_declining

        return FinancialFinding(
            rule_id="AQ-002", name="存货周转下降但毛利率上升", category=self.CAT_ASSET, layer=2,
            severity="high" if triggered else "info",
            triggered=triggered,
            description=(
                f"gross_margin: {gm_series[-2][1]:.1%} -> {gm_series[-1][1]:.1%} (rising); "
                f"inventory_growth={inv_growth:.1%} vs revenue_growth={rev_growth:.1%} (turnover declining). "
                "Possible under-statement of cost / over-statement of margin."
                if triggered else
                f"gross_margin trend: {'rising' if gm_rising else 'stable/declining'}; "
                f"inv_growth={inv_growth}, rev_growth={rev_growth}. No contradiction detected."
            ),
            metrics={
                "gm_latest": round(gm_series[-1][1], 4),
                "gm_previous": round(gm_series[-2][1], 4),
                "inventory_growth": round(inv_growth, 4) if inv_growth else None,
                "revenue_growth": round(rev_growth, 4) if rev_growth else None,
            },
            evidence=[Evidence(page=0, source="metric", detail="gross_margin + inventory/revenue growth")],
        )

    def _aq003_construction_in_progress(
        self, doc_id: str, raw_index: dict, fact_map: dict
    ) -> FinancialFinding:
        """AQ-003: Construction-in-progress not converted to fixed assets."""
        entries = self._raw_lookup(raw_index, ["在建工程"])
        if not entries:
            return self._insufficient("AQ-003", "在建工程长期不转固", self.CAT_ASSET, 1,
                                      "No construction-in-progress line item found in raw statements.")

        latest = entries[-1]
        assets = self._latest(fact_map, "total_assets")
        ratio = latest["value"] / assets.value if assets and assets.value else None

        triggered = ratio is not None and ratio > 0.05
        return FinancialFinding(
            rule_id="AQ-003", name="在建工程长期不转固", category=self.CAT_ASSET, layer=1,
            severity="warning" if triggered else "info",
            triggered=triggered,
            description=(
                f"construction_in_progress={latest['value']:.0f}, ratio={ratio:.1%} of total_assets."
                if ratio else f"construction_in_progress={latest['value']:.0f}."
            ),
            metrics={"cip_value": latest["value"], "cip_ratio": round(ratio, 4) if ratio else None},
            evidence=[Evidence(page=latest["page"], source="balance_sheet", detail=latest["period"])],
        )

    def _aq004_receivable_inventory_ratio(
        self, doc_id: str, fact_map: dict
    ) -> FinancialFinding:
        """AQ-004: (AR + Inventory) / Total Assets > 30%."""
        ar = self._latest(fact_map, "trade_receivable")
        inv = self._latest(fact_map, "inventory")
        assets = self._latest(fact_map, "total_assets")

        if not assets or assets.value == 0 or (not ar and not inv):
            return self._insufficient("AQ-004", "应收账款与存货占比超30%", self.CAT_ASSET, 1,
                                      "Need trade_receivable, inventory, total_assets.")

        ar_val = ar.value if ar else 0
        inv_val = inv.value if inv else 0
        ratio = (ar_val + inv_val) / assets.value
        triggered = ratio > 0.30

        evidence = []
        if ar:
            evidence.append(Evidence(page=ar.page, source="balance_sheet", detail=f"trade_receivable={ar_val:.0f}"))
        if inv:
            evidence.append(Evidence(page=inv.page, source="balance_sheet", detail=f"inventory={inv_val:.0f}"))

        return FinancialFinding(
            rule_id="AQ-004", name="应收账款与存货占比超30%", category=self.CAT_ASSET, layer=1,
            severity="high" if triggered else "info",
            triggered=triggered,
            description=f"(AR={ar_val:.0f} + Inv={inv_val:.0f}) / Assets={assets.value:.0f} = {ratio:.1%}",
            metrics={"ar_inventory_ratio": round(ratio, 4)},
            evidence=evidence,
        )

    def _aq005_prepayment_ratio(
        self, doc_id: str, raw_index: dict, fact_map: dict
    ) -> FinancialFinding:
        """AQ-005: Prepayments / Total Assets > 20%."""
        entries = self._raw_lookup(raw_index, ["预付款项", "预付账款", "预付款"])
        if not entries:
            return self._insufficient("AQ-005", "预付账款占比超20%", self.CAT_ASSET, 1,
                                      "No prepayment line item found in raw statements.")

        latest = entries[-1]
        assets = self._latest(fact_map, "total_assets")
        ratio = latest["value"] / assets.value if assets and assets.value else None
        triggered = ratio is not None and ratio > 0.20

        return FinancialFinding(
            rule_id="AQ-005", name="预付账款占比超20%", category=self.CAT_ASSET, layer=1,
            severity="high" if triggered else "info", triggered=triggered,
            description=f"prepayments={latest['value']:.0f}, ratio={ratio:.1%}" if ratio else f"prepayments={latest['value']:.0f}",
            metrics={"prepayment_value": latest["value"], "prepayment_ratio": round(ratio, 4) if ratio else None},
            evidence=[Evidence(page=latest["page"], source="balance_sheet", detail=latest["period"])],
        )

    def _aq006_other_receivable_large(
        self, doc_id: str, fact_map: dict
    ) -> FinancialFinding:
        """AQ-006: Other receivables disproportionately large."""
        other = self._latest(fact_map, "other_receivable")
        assets = self._latest(fact_map, "total_assets")

        if not other or not assets or assets.value == 0:
            return self._insufficient("AQ-006", "其他应收款余额过大", self.CAT_ASSET, 1,
                                      "Need other_receivable and total_assets.")

        ratio = other.value / assets.value
        triggered = ratio > 0.10

        return FinancialFinding(
            rule_id="AQ-006", name="其他应收款余额过大", category=self.CAT_ASSET, layer=1,
            severity="warning" if triggered else "info", triggered=triggered,
            description=f"other_receivable={other.value:.0f}, ratio={ratio:.1%} of total_assets",
            metrics={"other_receivable_ratio": round(ratio, 4)},
            evidence=[Evidence(page=other.page, source="balance_sheet", detail=f"period={other.period}")],
            recommendation="Investigate counterparty; common area for related-party fund occupation." if triggered else "",
        )

    def _aq007_goodwill_ratio(
        self, doc_id: str, raw_index: dict, fact_map: dict
    ) -> FinancialFinding:
        """AQ-007: Goodwill / Total Assets > 10%."""
        entries = self._raw_lookup(raw_index, ["商誉"])
        if not entries:
            return self._insufficient("AQ-007", "商誉占比超10%", self.CAT_ASSET, 1,
                                      "No goodwill line item found in raw statements.")

        latest = entries[-1]
        assets = self._latest(fact_map, "total_assets")
        ratio = latest["value"] / assets.value if assets and assets.value else None
        triggered = ratio is not None and ratio > 0.10

        return FinancialFinding(
            rule_id="AQ-007", name="商誉占比超10%", category=self.CAT_ASSET, layer=1,
            severity="high" if triggered else "info", triggered=triggered,
            description=f"goodwill={latest['value']:.0f}, ratio={ratio:.1%}" if ratio else f"goodwill={latest['value']:.0f}",
            metrics={"goodwill_value": latest["value"], "goodwill_ratio": round(ratio, 4) if ratio else None},
            evidence=[Evidence(page=latest["page"], source="balance_sheet", detail=latest["period"])],
            recommendation="High impairment risk if post-acquisition performance falls short." if triggered else "",
        )

    def _aq008_development_expenditure(
        self, doc_id: str, raw_index: dict, fact_map: dict
    ) -> FinancialFinding:
        """AQ-008: Development expenditure capitalized and large."""
        entries = self._raw_lookup(raw_index, ["开发支出", "研发支出"])
        if not entries:
            return self._insufficient("AQ-008", "开发支出余额大", self.CAT_ASSET, 1,
                                      "No development expenditure line item found.")

        latest = entries[-1]
        assets = self._latest(fact_map, "total_assets")
        ratio = latest["value"] / assets.value if assets and assets.value else None
        triggered = ratio is not None and ratio > 0.05

        return FinancialFinding(
            rule_id="AQ-008", name="开发支出余额大", category=self.CAT_ASSET, layer=1,
            severity="warning" if triggered else "info", triggered=triggered,
            description=f"development_expenditure={latest['value']:.0f}, ratio={ratio:.1%}" if ratio else f"value={latest['value']:.0f}",
            metrics={"dev_exp_value": latest["value"], "dev_exp_ratio": round(ratio, 4) if ratio else None},
            evidence=[Evidence(page=latest["page"], source="balance_sheet", detail=latest["period"])],
        )

    def _aq009_fixed_asset_turnover_vs_profit(
        self, doc_id: str, fact_map: dict, metric_map: dict
    ) -> FinancialFinding:
        """AQ-009: Fixed-asset turnover declining while net profit rising (Layer 2)."""
        fa_series = self._fact_series(fact_map, "fixed_assets")
        rev_series = self._fact_series(fact_map, "revenue")
        np_growth = self._metric_val(metric_map, "net_profit_growth")

        if len(fa_series) < 2 or len(rev_series) < 2:
            return self._insufficient("AQ-009", "固定资产周转率下降但净利润上升", self.CAT_ASSET, 2,
                                      "Need >= 2 periods of fixed_assets and revenue.")

        fa_growth = (fa_series[-1][1].value - fa_series[-2][1].value) / abs(fa_series[-2][1].value) if fa_series[-2][1].value else 0
        rev_growth = (rev_series[-1][1].value - rev_series[-2][1].value) / abs(rev_series[-2][1].value) if rev_series[-2][1].value else 0

        turnover_declining = fa_growth > rev_growth  # assets growing faster than revenue
        profit_rising = np_growth is not None and np_growth > 0
        triggered = turnover_declining and profit_rising

        return FinancialFinding(
            rule_id="AQ-009", name="固定资产周转率下降但净利润上升", category=self.CAT_ASSET, layer=2,
            severity="warning" if triggered else "info", triggered=triggered,
            description=(
                f"FA growth={fa_growth:.1%} > Rev growth={rev_growth:.1%} (turnover down); "
                f"net_profit_growth={np_growth:.1%} (profit up). Possible cost capitalization."
                if triggered else
                f"FA growth={fa_growth:.1%}, Rev growth={rev_growth:.1%}, NP growth={np_growth}. No contradiction."
            ),
            metrics={"fa_growth": round(fa_growth, 4), "rev_growth": round(rev_growth, 4),
                     "net_profit_growth": round(np_growth, 4) if np_growth else None},
            evidence=[Evidence(page=fa_series[-1][1].page, source="balance_sheet", detail="fixed_assets trend")],
        )

    # ------------------------------------------------------------------
    # B. Earnings Quality Assessment (3 rules)
    # ------------------------------------------------------------------

    def _check_earnings_quality(
        self, doc_id: str, fact_map: dict, metric_map: dict
    ) -> list[FinancialFinding]:
        return [
            self._eq001_low_cash_conversion(doc_id, metric_map),
            self._eq002_low_cash_to_revenue(doc_id, fact_map),
            self._eq003_long_cash_cycle(doc_id, fact_map),
        ]

    def _eq001_low_cash_conversion(
        self, doc_id: str, metric_map: dict
    ) -> FinancialFinding:
        """EQ-001: Operating cash flow far below net profit (net cash ratio < 0.5)."""
        ocf_ratio = self._metric_val(metric_map, "ocf_to_net_profit")
        if ocf_ratio is None:
            return self._insufficient("EQ-001", "经营现金流净额远低于净利润", self.CAT_EARNINGS, 1,
                                      "Need ocf_to_net_profit metric.")

        triggered = ocf_ratio < 0.5
        severity = "critical" if ocf_ratio < 0.3 else ("high" if triggered else ("warning" if ocf_ratio < 0.8 else "info"))

        return FinancialFinding(
            rule_id="EQ-001", name="经营现金流净额远低于净利润", category=self.CAT_EARNINGS, layer=1,
            severity=severity, triggered=triggered,
            description=f"ocf_to_net_profit={ocf_ratio:.2f}x",
            metrics={"ocf_to_net_profit": round(ocf_ratio, 4)},
            evidence=[Evidence(page=0, source="metric", detail="operating_cash_flow / net_profit")],
            recommendation="Profit not converting to cash; investigate AR/inventory buildup or revenue recognition." if triggered else "",
        )

    def _eq002_low_cash_to_revenue(
        self, doc_id: str, fact_map: dict
    ) -> FinancialFinding:
        """EQ-002: Cash-to-revenue ratio persistently below 0.5."""
        ocf_map = fact_map.get("operating_cash_flow", {})
        rev_map = fact_map.get("revenue", {})
        periods = _sort_periods([p for p in ocf_map.keys() if p in rev_map])

        if not periods:
            return self._insufficient("EQ-002", "收现比持续低于0.5", self.CAT_EARNINGS, 1,
                                      "Need operating_cash_flow and revenue for same periods.")

        ratios: list[tuple[str, float]] = []
        for p in periods:
            ocf = ocf_map[p].value
            rev = rev_map[p].value
            if rev and rev != 0:
                ratios.append((p, ocf / rev))

        if not ratios:
            return self._insufficient("EQ-002", "收现比持续低于0.5", self.CAT_EARNINGS, 1,
                                      "Could not compute cash-to-revenue ratio.")

        latest_ratio = ratios[-1][1]
        persistently_low = len(ratios) >= 2 and all(r < 0.5 for _, r in ratios)
        triggered = latest_ratio < 0.5

        return FinancialFinding(
            rule_id="EQ-002", name="收现比持续低于0.5", category=self.CAT_EARNINGS, layer=1,
            severity="high" if persistently_low else ("warning" if triggered else "info"),
            triggered=triggered,
            description=f"cash_to_revenue ratios: {', '.join(f'{p}={r:.2f}' for p, r in ratios)}",
            metrics={"latest_cash_to_revenue": round(latest_ratio, 4),
                     "periods_below_0.5": sum(1 for _, r in ratios if r < 0.5)},
            evidence=[Evidence(page=ocf_map[periods[-1]].page, source="cash_flow_statement",
                               detail=f"OCF={ocf_map[periods[-1]].value:.0f}, Rev={rev_map[periods[-1]].value:.0f}")],
        )

    def _eq003_long_cash_cycle(
        self, doc_id: str, fact_map: dict
    ) -> FinancialFinding:
        """EQ-003: Cash conversion cycle > 6 months (180 days) (Layer 2)."""
        inv = self._latest(fact_map, "inventory")
        ar = self._latest(fact_map, "trade_receivable")
        ap = self._latest(fact_map, "trade_payable")
        rev = self._latest(fact_map, "revenue")

        if not all([inv, ar, rev]) or rev.value == 0:
            return self._insufficient("EQ-003", "现金循环周期超6个月", self.CAT_EARNINGS, 2,
                                      "Need inventory, trade_receivable, trade_payable, revenue.")

        daily_rev = rev.value / 365
        dio = inv.value / daily_rev if daily_rev else 0  # Days Inventory Outstanding
        dso = ar.value / daily_rev if daily_rev else 0   # Days Sales Outstanding
        dpo = (ap.value / daily_rev) if ap and daily_rev else 0  # Days Payable Outstanding
        ccc = dio + dso - dpo

        triggered = ccc > 180
        return FinancialFinding(
            rule_id="EQ-003", name="现金循环周期超6个月", category=self.CAT_EARNINGS, layer=2,
            severity="high" if triggered else "info", triggered=triggered,
            description=f"CCC={ccc:.0f} days (DIO={dio:.0f}, DSO={dso:.0f}, DPO={dpo:.0f})",
            metrics={"ccc_days": round(ccc, 1), "dio": round(dio, 1), "dso": round(dso, 1), "dpo": round(dpo, 1)},
            evidence=[
                Evidence(page=inv.page, source="balance_sheet", detail=f"inventory={inv.value:.0f}"),
                Evidence(page=ar.page, source="balance_sheet", detail=f"trade_receivable={ar.value:.0f}"),
                Evidence(page=rev.page, source="income_statement", detail=f"revenue={rev.value:.0f}"),
            ],
        )

    # ------------------------------------------------------------------
    # C. Capital Structure Assessment (4 rules)
    # ------------------------------------------------------------------

    def _check_capital_structure(
        self, doc_id: str, fact_map: dict, metric_map: dict, raw_index: dict
    ) -> list[FinancialFinding]:
        return [
            self._cs001_other_payable_large(doc_id, fact_map),
            self._cs002_advance_receipts_declining(doc_id, fact_map),
            self._cs003_long_term_payables_large(doc_id, fact_map),
            self._cs004_capital_reserve_anomaly(doc_id, raw_index, fact_map),
        ]

    def _cs001_other_payable_large(
        self, doc_id: str, fact_map: dict
    ) -> FinancialFinding:
        """CS-001: Other payables disproportionately large."""
        other = self._latest(fact_map, "other_payable")
        liabilities = self._latest(fact_map, "total_liabilities")

        if not other or not liabilities or liabilities.value == 0:
            return self._insufficient("CS-001", "其他应付款余额大", self.CAT_CAPITAL, 1,
                                      "Need other_payable and total_liabilities.")

        ratio = other.value / liabilities.value
        triggered = ratio > 0.10

        return FinancialFinding(
            rule_id="CS-001", name="其他应付款余额大", category=self.CAT_CAPITAL, layer=1,
            severity="warning" if triggered else "info", triggered=triggered,
            description=f"other_payable={other.value:.0f}, ratio={ratio:.1%} of total_liabilities",
            metrics={"other_payable_ratio": round(ratio, 4)},
            evidence=[Evidence(page=other.page, source="balance_sheet", detail=f"period={other.period}")],
            recommendation="May hide off-balance-sheet borrowing or guarantees." if triggered else "",
        )

    def _cs002_advance_receipts_declining(
        self, doc_id: str, fact_map: dict
    ) -> FinancialFinding:
        """CS-002: Advance receipts (contract liability) continuously declining (Layer 2)."""
        series = self._fact_series(fact_map, "contract_liability")
        if len(series) < 2:
            return self._insufficient("CS-002", "预收账款持续下降", self.CAT_CAPITAL, 2,
                                      "Need >= 2 periods of contract_liability data.")

        values = [f.value for _, f in series]
        declining = all(values[i] > values[i + 1] for i in range(len(values) - 1))
        triggered = declining

        return FinancialFinding(
            rule_id="CS-002", name="预收账款持续下降", category=self.CAT_CAPITAL, layer=2,
            severity="warning" if triggered else "info", triggered=triggered,
            description=f"contract_liability trend: {', '.join(f'{v:.0f}' for v in values)}",
            metrics={"latest_value": values[-1], "declining_periods": len(values) - 1 if declining else 0},
            evidence=[Evidence(page=series[-1][1].page, source="balance_sheet", detail=f"period={series[-1][0]}")],
            recommendation="Advance receipts are a leading revenue indicator; decline may signal business contraction." if triggered else "",
        )

    def _cs003_long_term_payables_large(
        self, doc_id: str, fact_map: dict
    ) -> FinancialFinding:
        """CS-003: Long-term borrowings / payables large."""
        lt = self._latest(fact_map, "long_term_borrowing")
        assets = self._latest(fact_map, "total_assets")

        if not lt or not assets or assets.value == 0:
            return self._insufficient("CS-003", "长期应付款余额大", self.CAT_CAPITAL, 1,
                                      "Need long_term_borrowing and total_assets.")

        ratio = lt.value / assets.value
        triggered = ratio > 0.20

        return FinancialFinding(
            rule_id="CS-003", name="长期应付款余额大", category=self.CAT_CAPITAL, layer=1,
            severity="warning" if triggered else "info", triggered=triggered,
            description=f"long_term_borrowing={lt.value:.0f}, ratio={ratio:.1%} of total_assets",
            metrics={"lt_borrowing_ratio": round(ratio, 4)},
            evidence=[Evidence(page=lt.page, source="balance_sheet", detail=f"period={lt.period}")],
        )

    def _cs004_capital_reserve_anomaly(
        self, doc_id: str, raw_index: dict, fact_map: dict
    ) -> FinancialFinding:
        """CS-004: Capital reserve abnormally increased (Layer 2)."""
        entries = self._raw_lookup(raw_index, ["资本公积", "股份溢价", "储备"])
        if len(entries) < 2:
            return self._insufficient("CS-004", "资本公积异常增大", self.CAT_CAPITAL, 2,
                                      "Need >= 2 periods of capital reserve data from raw statements.")

        latest = entries[-1]
        previous = entries[-2]
        growth = (latest["value"] - previous["value"]) / abs(previous["value"]) if previous["value"] else 0
        triggered = growth > 0.50  # >50% increase

        return FinancialFinding(
            rule_id="CS-004", name="资本公积异常增大", category=self.CAT_CAPITAL, layer=2,
            severity="warning" if triggered else "info", triggered=triggered,
            description=f"capital_reserve: {previous['value']:.0f} -> {latest['value']:.0f} (growth={growth:.1%})",
            metrics={"capital_reserve_growth": round(growth, 4)},
            evidence=[Evidence(page=latest["page"], source="balance_sheet", detail=f"period={latest['period']}")],
            recommendation="Verify source of increase; may hide hidden liabilities or equity adjustments." if triggered else "",
        )

    # ------------------------------------------------------------------
    # D. Revenue Authenticity Assessment (4 rules)
    # ------------------------------------------------------------------

    def _check_revenue_authenticity(
        self, doc_id: str, fact_map: dict, metric_map: dict, raw_index: dict
    ) -> list[FinancialFinding]:
        return [
            self._ra001_selling_expense_rising(doc_id, metric_map),
            self._ra002_salary_revenue_anomaly(doc_id, raw_index, fact_map),
            self._ra003_tax_revenue_divergence(doc_id, raw_index, fact_map),
            self._ra004_per_capita_efficiency(doc_id, raw_index, fact_map),
        ]

    def _ra001_selling_expense_rising(
        self, doc_id: str, metric_map: dict
    ) -> FinancialFinding:
        """RA-001: Selling expense ratio continuously rising (Layer 2)."""
        series = self._metric_series(metric_map, "selling_expense_ratio")
        if len(series) < 2:
            return self._insufficient("RA-001", "销售费用率持续上升", self.CAT_REVENUE, 2,
                                      "Need >= 2 periods of selling_expense_ratio.")

        rising = all(series[i][1] < series[i + 1][1] for i in range(len(series) - 1))
        triggered = rising

        return FinancialFinding(
            rule_id="RA-001", name="销售费用率持续上升", category=self.CAT_REVENUE, layer=2,
            severity="warning" if triggered else "info", triggered=triggered,
            description=f"selling_expense_ratio trend: {', '.join(f'{p}={v:.1%}' for p, v in series)}",
            metrics={"latest_ratio": round(series[-1][1], 4), "rising_periods": len(series) - 1 if rising else 0},
            evidence=[Evidence(page=0, source="metric", detail="selling_expense / revenue")],
        )

    def _ra002_salary_revenue_anomaly(
        self, doc_id: str, raw_index: dict, fact_map: dict
    ) -> FinancialFinding:
        """RA-002: Salary-to-revenue ratio abnormal."""
        entries = self._raw_lookup(raw_index, ["职工薪酬", "工资", "薪酬", "员工福利"])
        rev = self._latest(fact_map, "revenue")

        if not entries or not rev or rev.value == 0:
            return self._insufficient("RA-002", "薪酬收入比异常增长", self.CAT_REVENUE, 1,
                                      "Need employee cost (raw) and revenue.")

        latest = entries[-1]
        ratio = latest["value"] / rev.value
        triggered = ratio < 0.02 or ratio > 0.50  # abnormally low or high

        return FinancialFinding(
            rule_id="RA-002", name="薪酬收入比异常增长", category=self.CAT_REVENUE, layer=1,
            severity="warning" if triggered else "info", triggered=triggered,
            description=f"employee_cost={latest['value']:.0f}, salary_to_revenue={ratio:.1%}",
            metrics={"salary_to_revenue": round(ratio, 4)},
            evidence=[
                Evidence(page=latest["page"], source="income_statement", detail=f"employee_cost period={latest['period']}"),
                Evidence(page=rev.page, source="income_statement", detail=f"revenue={rev.value:.0f}"),
            ],
            recommendation="If salary growth << revenue growth, revenue may be fabricated (hard to inflate headcount)." if ratio < 0.02 else "",
        )

    def _ra003_tax_revenue_divergence(
        self, doc_id: str, raw_index: dict, fact_map: dict
    ) -> FinancialFinding:
        """RA-003: Tax-to-revenue ratio diverging from revenue growth (Layer 2)."""
        grouped_tax: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for name, raw_entries in raw_index.items():
            if "已付所得税" not in name:
                continue
            for entry in raw_entries:
                if entry["statement_type"] == "cash_flow_statement":
                    grouped_tax[entry["table_id"]].append(entry)
        tax_groups = list(grouped_tax.values())
        entries = min(
            tax_groups,
            key=lambda group: min(entry["page"] for entry in group),
            default=[],
        )
        entries = sorted(
            entries,
            key=lambda entry: tuple(
                int(value) for value in re.findall(r"\d+", entry["period"])
            ),
        )
        rev_series = self._fact_series(fact_map, "revenue")

        if len(entries) < 2 or len(rev_series) < 2:
            return self._insufficient("RA-003", "纳税额收入比背离", self.CAT_REVENUE, 2,
                                      "Need >= 2 periods of tax and revenue data.")

        tax_latest = abs(entries[-1]["value"])
        tax_prev = abs(entries[-2]["value"])
        tax_growth = (tax_latest - tax_prev) / abs(tax_prev) if tax_prev else 0

        rev_latest = rev_series[-1][1].value
        rev_prev = rev_series[-2][1].value
        rev_growth = (rev_latest - rev_prev) / abs(rev_prev) if rev_prev else 0

        divergence = rev_growth - tax_growth
        triggered = rev_growth > 0.20 and divergence > 0.15  # Revenue growing fast but tax not keeping up

        return FinancialFinding(
            rule_id="RA-003", name="纳税额收入比背离", category=self.CAT_REVENUE, layer=2,
            severity="high" if triggered else "info", triggered=triggered,
            description=f"revenue_growth={rev_growth:.1%}, tax_growth={tax_growth:.1%}, divergence={divergence:.1%}",
            metrics={"revenue_growth": round(rev_growth, 4), "tax_growth": round(tax_growth, 4),
                     "divergence": round(divergence, 4)},
            evidence=[
                Evidence(page=entries[-1]["page"], source="cash_flow_statement", detail=f"tax period={entries[-1]['period']}"),
                Evidence(page=rev_series[-1][1].page, source="income_statement", detail=f"revenue period={rev_series[-1][0]}"),
            ],
            recommendation="Revenue can be manipulated; tax must be paid in cash. Divergence is a red flag." if triggered else "",
        )

    def _ra004_per_capita_efficiency(
        self, doc_id: str, raw_index: dict, fact_map: dict
    ) -> FinancialFinding:
        """RA-004: Per-capita efficiency severely deviating from industry."""
        emp_entries = self._raw_lookup(raw_index, ["员工人数", "雇员人数", "员工总数", "雇员"])
        rev = self._latest(fact_map, "revenue")

        if not emp_entries or not rev or rev.value == 0:
            return self._insufficient("RA-004", "人均效能严重偏离行业", self.CAT_REVENUE, 1,
                                      "Need employee count (from prospectus text) and revenue.")

        latest = emp_entries[-1]
        per_capita = rev.value / latest["value"] if latest["value"] else 0
        # Flag if per-capita revenue > 5M (unusually high for most industries)
        triggered = per_capita > 5_000_000

        return FinancialFinding(
            rule_id="RA-004", name="人均效能严重偏离行业", category=self.CAT_REVENUE, layer=1,
            severity="warning" if triggered else "info", triggered=triggered,
            description=f"revenue_per_capita={per_capita:,.0f} (employees={latest['value']:.0f}, revenue={rev.value:.0f})",
            metrics={"revenue_per_capita": round(per_capita, 2)},
            evidence=[
                Evidence(page=latest["page"], source="prospectus_text", detail=f"employee_count period={latest['period']}"),
                Evidence(page=rev.page, source="income_statement", detail=f"revenue={rev.value:.0f}"),
            ],
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _insufficient(
        rule_id: str, name: str, category: str, layer: int, reason: str
    ) -> FinancialFinding:
        return FinancialFinding(
            rule_id=rule_id, name=name, category=category, layer=layer,
            severity="info", triggered=False,
            description=f"[insufficient_data] {reason}",
            metrics={}, evidence=[],
        )
