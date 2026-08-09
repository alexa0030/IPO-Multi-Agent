from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RISK_TOPIC_MAP = {
    "毛利率连续下降": "margin_decline",
    "存货增长过快": "inventory_growth",
    "客户集中度较高": "customer_concentration",
}

RISK_TOPIC_PATTERNS = {
    "customer_concentration": ("前五大客户", "最大客户", "客户集中"),
    "margin_decline": ("毛利率连续下降", "毛利率下降", "净利润率降"),
    "inventory_growth": ("存货增长", "存货增至", "存货积压", "存货过时"),
    "third_party_payment": ("第三方付款", "第三方回款"),
    "social_insurance_noncompliance": ("社会保险", "住房公积金", "社保公积金"),
    "raw_material_supply": ("原材料成本", "原材料供应", "原材料价格"),
}

DEFAULT_RISK_LEVELS = {
    "customer_concentration": "medium",
    "margin_decline": "medium",
    "inventory_growth": "high",
    "third_party_payment": "high",
    "social_insurance_noncompliance": "high",
    "raw_material_supply": "high",
}


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional(path: Path, default: Any) -> Any:
    return _read(path) if path.exists() else default


def _iter_grounded_text_items(value: Any):
    """Yield text-bearing objects from heterogeneous agent artifacts."""
    if isinstance(value, list):
        for item in value:
            yield from _iter_grounded_text_items(item)
        return
    if not isinstance(value, dict):
        return
    text = " ".join(
        str(value.get(key, ""))
        for key in ("title", "statement", "conclusion", "description", "content")
    ).strip()
    if text:
        yield value, text
    for key, child in value.items():
        if key not in {"evidence", "evidences"} and isinstance(child, (list, dict)):
            yield from _iter_grounded_text_items(child)


def _pages_and_evidence(item: dict[str, Any]) -> tuple[list[int], list[str]]:
    pages: set[int] = set()
    evidence_ids: set[str] = set()
    for key in ("page", "page_number"):
        try:
            page = int(item.get(key) or 0)
        except (TypeError, ValueError):
            page = 0
        if page > 0:
            pages.add(page)
    for key in ("pages", "source_pages"):
        for value in item.get(key, []) or []:
            try:
                page = int(value)
            except (TypeError, ValueError):
                continue
            if page > 0:
                pages.add(page)
    for evidence in item.get("evidence", []) or item.get("evidences", []) or []:
        if not isinstance(evidence, dict):
            continue
        try:
            page = int(evidence.get("page_number") or evidence.get("page") or 0)
        except (TypeError, ValueError):
            page = 0
        if page > 0:
            pages.add(page)
        if evidence.get("evidence_id"):
            evidence_ids.add(str(evidence["evidence_id"]))
    evidence_ids.update(str(value) for value in item.get("evidence_ids", []) or [])
    evidence_ids.update(f"page:{page}" for page in pages)
    return sorted(pages), sorted(evidence_ids)


def _topic_for_text(text: str) -> str | None:
    for topic, patterns in RISK_TOPIC_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            return topic
    return None


def _scan_disclosure_risk_pages(directory: Path) -> list[dict[str, Any]]:
    """Recover summary and detailed disclosure pages for common IPO risks.

    Agent page selection intentionally stays small, but evaluation and audit
    lineage need both the prospectus summary page and the detailed section.
    This deterministic pass scans source text only and does not infer facts.
    """
    pages = _read_optional(directory / "pages.json", [])
    found: dict[str, list[int]] = {topic: [] for topic in RISK_TOPIC_PATTERNS}
    for page in pages:
        if not isinstance(page, dict):
            continue
        text = str(page.get("text", ""))
        try:
            page_number = int(page.get("page") or 0)
        except (TypeError, ValueError):
            continue
        if page_number < 1:
            continue
        for topic, patterns in RISK_TOPIC_PATTERNS.items():
            if any(pattern in text for pattern in patterns):
                found[topic].append(page_number)
    output: list[dict[str, Any]] = []
    for topic, matched_pages in found.items():
        if not matched_pages:
            continue
        selected = sorted(dict.fromkeys(matched_pages))[:8]
        output.append(
            {
                "topic": topic,
                "risk_level": DEFAULT_RISK_LEVELS[topic],
                "pages": selected,
                "evidence_ids": [f"page:{page}" for page in selected],
            }
        )
    return output


def build_prediction(extracted_dir: str | Path) -> dict[str, Any]:
    directory = Path(extracted_dir)
    kb = _read(directory / "financial_kb.json")
    calculated = _read(directory / "metrics.json")
    risks = _read(directory / "risk_findings.json")
    prospectus = _read_optional(directory / "prospectus_analysis.json", {})
    ledger = _read_optional(directory / "research_ledger.json", {})

    metrics: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for fact in kb.get("statement_facts", []):
        code = fact.get("canonical_tag")
        period = str(fact.get("period", ""))
        key = (str(code), period)
        if code == "other" or fact.get("value") is None or key in seen:
            continue
        seen.add(key)
        metrics.append(
            {
                "metric_code": code,
                "period": period,
                "value": fact["value"],
                "pages": [fact.get("page")],
            }
        )
    for metric in calculated:
        code = str(metric.get("metric_code"))
        period = str(metric.get("period", ""))
        value = metric.get("value")
        if value is None:
            continue
        if code in {"gross_margin", "net_margin"} and abs(float(value)) <= 1.5:
            value = float(value) * 100
        metrics.append(
            {
                "metric_code": code,
                "period": period,
                "value": value,
                "pages": metric.get("source_pages", []),
            }
        )

    findings = []
    finding_keys: set[tuple[str, tuple[int, ...]]] = set()
    for risk in risks:
        title = str(risk.get("title", ""))
        topic = RISK_TOPIC_MAP.get(title) or _topic_for_text(
            f"{title} {risk.get('description', '')}"
        )
        if not topic:
            continue
        pages = list(risk.get("source_pages", []))
        finding_keys.add((topic, tuple(sorted(pages))))
        findings.append(
            {
                "topic": topic,
                "risk_level": risk.get("severity", "medium"),
                "pages": pages,
                "evidence_ids": [f"page:{page}" for page in pages],
            }
        )

    # Prospectus and ledger agents often identify non-financial risks that do
    # not belong to the six-rule financial scanner. Include only grounded
    # items; this fixes systematic under-counting without inventing findings.
    for artifact in (prospectus, ledger.get("findings", [])):
        for item, text in _iter_grounded_text_items(artifact):
            topic = _topic_for_text(text)
            if not topic:
                continue
            pages, evidence_ids = _pages_and_evidence(item)
            if not evidence_ids:
                continue
            key = (topic, tuple(pages))
            if key in finding_keys:
                continue
            finding_keys.add(key)
            findings.append(
                {
                    "topic": topic,
                    "risk_level": DEFAULT_RISK_LEVELS[topic],
                    "pages": pages,
                    "evidence_ids": evidence_ids,
                }
            )
    for candidate in _scan_disclosure_risk_pages(directory):
        key = (candidate["topic"], tuple(candidate["pages"]))
        if key not in finding_keys:
            finding_keys.add(key)
            findings.append(candidate)
    return {"metrics": metrics, "findings": findings}
