from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz

from ipo_financial_agent.document.section_detector import detect_sections
from ipo_financial_agent.models import PageData
from ipo_financial_agent.text_normalization import normalize_search_text

from .models import EvalCase


TOPIC_TERMS = {
    "customer_concentration": ("前五大客户", "最大客户", "客户集中"),
    "loss_making": ("净亏损", "年内亏损", "期内亏损"),
    "litigation_penalty": ("诉讼", "仲裁", "行政处罚", "监管问询"),
    "related_party": ("关联交易", "关连交易", "关联方"),
    "controller_risk": ("实际控制人", "控股股东", "股权质押"),
}


def build_candidates(case: EvalCase, pdf_path: str | Path) -> dict[str, Any]:
    path = Path(pdf_path).resolve()
    if path.name != case.source_filename:
        raise ValueError(
            f"source filename mismatch: expected {case.source_filename!r}, got {path.name!r}"
        )
    pages: list[PageData] = []
    with fitz.open(path) as document:
        for index, page in enumerate(document):
            pages.append(
                PageData(
                    source_file=path.name,
                    page=index + 1,
                    text=page.get_text("text", sort=True),
                )
            )
    if len(pages) != case.expected_page_count:
        raise ValueError(
            f"page-count mismatch: expected {case.expected_page_count}, got {len(pages)}"
        )

    sections: dict[str, list[int]] = {}
    for hit in detect_sections(pages):
        sections.setdefault(hit.section_type, []).append(hit.page)

    findings: list[dict[str, Any]] = []
    for page in pages:
        if page.page <= 35:
            continue
        normalized = normalize_search_text(page.text)
        for topic, terms in TOPIC_TERMS.items():
            if sum(item["topic"] == topic for item in findings) >= 8:
                continue
            matched = next((term for term in terms if term in normalized), None)
            if not matched:
                continue
            compact = re.sub(r"\s+", " ", page.text).strip()
            index = normalized.find(matched)
            start = max(0, index - 120)
            findings.append(
                {
                    "topic": topic,
                    "page": page.page,
                    "matched_term": matched,
                    "evidence_excerpt": compact[start : start + 420],
                    "status": "candidate",
                }
            )

    return {
        "case_id": case.case_id,
        "company": case.company,
        "source_filename": path.name,
        "page_count": len(pages),
        "sections": {key: sorted(set(value)) for key, value in sections.items()},
        "finding_candidates": findings,
        "review_required": True,
    }
