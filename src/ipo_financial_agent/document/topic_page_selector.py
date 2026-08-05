from __future__ import annotations

from collections import defaultdict

from ipo_financial_agent.finance.topic_catalog import TOPIC_GROUPS
from ipo_financial_agent.models import PageData, SectionHit

STATEMENT_TYPES = {
    "balance_sheet",
    "income_statement",
    "cash_flow_statement",
    "changes_in_equity",
}


class TopicPageSelector:
    """按财务主题选最相关页面，避免把整个财务章节送入大模型。"""

    def __init__(self, pages_per_topic: int = 2, context_pages: int = 0) -> None:
        self.pages_per_topic = max(1, pages_per_topic)
        self.context_pages = max(0, context_pages)

    def select_groups(
        self,
        pages: list[PageData],
        section_hits: list[SectionHit],
    ) -> dict[str, list[PageData]]:
        page_map = {page.page: page for page in pages}
        hit_types: dict[int, set[str]] = defaultdict(set)
        for hit in section_hits:
            hit_types[hit.page].add(hit.section_type)

        groups: dict[str, list[PageData]] = {}
        for topic, aliases in TOPIC_GROUPS.items():
            scored: list[tuple[int, int]] = []
            for page in pages:
                types = hit_types.get(page.page, set())
                if types & STATEMENT_TYPES:
                    continue
                score = self._score_page(page, aliases)
                if "financial_forecast" in types and topic == "财务预测":
                    score += 20
                if score > 0:
                    scored.append((score, page.page))

            chosen = [
                page_no
                for _, page_no in sorted(scored, key=lambda item: (-item[0], item[1]))[
                    : self.pages_per_topic
                ]
            ]
            expanded: set[int] = set()
            for page_no in chosen:
                for offset in range(-self.context_pages, self.context_pages + 1):
                    candidate = page_no + offset
                    if candidate in page_map:
                        expanded.add(candidate)
            if expanded:
                groups[topic] = [page_map[number] for number in sorted(expanded)]
        return groups

    @staticmethod
    def _score_page(page: PageData, aliases: list[str]) -> int:
        text = page.text or ""
        head = text[:1800]
        table_text = "\n".join(
            "\n".join(" | ".join(row) for row in table.rows)
            for table in page.tables
        )
        score = 0
        for alias in aliases:
            alias_lower = alias.lower()
            score += min(text.lower().count(alias_lower), 3) * 2
            if alias_lower in head.lower():
                score += 3
            if alias_lower in table_text.lower():
                score += 5
        if len(text.strip()) < 350:
            score -= 5
        if "目录" in head[:200] or "目錄" in head[:200]:
            score -= 8
        return max(score, 0)

    @staticmethod
    def flatten(groups: dict[str, list[PageData]]) -> list[PageData]:
        by_page: dict[int, PageData] = {}
        for pages in groups.values():
            for page in pages:
                by_page[page.page] = page
        return [by_page[number] for number in sorted(by_page)]
