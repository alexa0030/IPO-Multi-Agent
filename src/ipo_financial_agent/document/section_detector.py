from __future__ import annotations

import re

from ipo_financial_agent.models import PageData, SectionHit
from ipo_financial_agent.text_normalization import normalize_search_text

SECTION_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "balance_sheet": [
        ("综合财务状况表", r"综合财务状况表"),
        ("合并财务状况表", r"合并财务状况表"),
        ("綜合財務狀況表", r"(?:綜合|合併)?財務狀況表"),
        ("statement of financial position", r"statement of financial position"),
    ],
    "income_statement": [
        ("综合损益及其他全面收益表", r"综合损益及其他全面收益表"),
        ("综合损益表", r"综合损益表"),
        ("綜合損益及其他全面收益表", r"綜合損益及其他全面收益表"),
        ("statement of profit or loss", r"statement of profit or loss"),
    ],
    "cash_flow_statement": [
        ("综合现金流量表", r"综合现金流量表"),
        ("綜合現金流量表", r"綜合現金流量表"),
        ("statement of cash flows", r"statement of cash flows"),
    ],
    "changes_in_equity": [
        ("综合权益变动表", r"综合权益变动表"),
        ("綜合權益變動表", r"綜合權益變動表"),
        ("statement of changes in equity", r"statement of changes in equity"),
    ],
    "financial_information": [
        ("财务资料", r"财务资料"),
        ("財務資料", r"財務資料"),
        ("financial information", r"financial information"),
    ],
    "accountants_report": [
        ("会计师报告", r"会计师报告"),
        ("會計師報告", r"會計師報告"),
        ("accountants' report", r"accountants[’']? report"),
    ],
    "financial_forecast": [
        ("财务预测", r"财务预测|財務預測|盈利预测|盈利預測"),
        ("profit forecast", r"profit forecast|financial forecast"),
    ],
}


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _is_actual_statement_match(section_type: str, compact_text: str, match: re.Match[str]) -> bool:
    if section_type not in {"balance_sheet", "income_statement", "cash_flow_statement", "changes_in_equity"}:
        return True
    after = compact_text[match.end() : match.end() + 90]
    if after.startswith(("中", "的", "与", "與", "之", "所列", "内", "內", "选定", "選定", "及", "或")):
        return False
    if match.start() <= 1500:
        return True
    return after.startswith(("截至", "于", "於", "附注", "附註", "下表", "本表"))


def detect_sections(pages: list[PageData]) -> list[SectionHit]:
    hits: list[SectionHit] = []
    for page in pages:
        head = normalize_search_text(page.text[:2200])
        compact = re.sub(r"\s+", "", head)
        for section_type, patterns in SECTION_PATTERNS.items():
            for title, pattern in patterns:
                if _has_cjk(pattern):
                    candidate_pattern = re.sub(r"\s+", "", pattern)
                    match = re.search(candidate_pattern, compact, flags=re.I)
                    match_text = compact
                else:
                    match = re.search(pattern, head, flags=re.I)
                    match_text = head
                if match and _is_actual_statement_match(section_type, match_text, match):
                    hits.append(
                        SectionHit(
                            section_type=section_type,
                            title=title,
                            page=page.page,
                            keyword=match.group(0),
                            score=1.0,
                        )
                    )
                    break
    unique: dict[tuple[str, int], SectionHit] = {}
    for hit in hits:
        unique[(hit.section_type, hit.page)] = hit
    return sorted(unique.values(), key=lambda item: (item.page, item.section_type))
