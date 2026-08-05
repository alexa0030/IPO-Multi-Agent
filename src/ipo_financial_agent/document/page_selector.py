from __future__ import annotations

from ipo_financial_agent.llm.prompts import FOCUS_TOPICS
from ipo_financial_agent.models import PageData, SectionHit


class FinancialPageSelector:
    """筛选第一次LLM任务的候选页，避免把整本招股书全部发送给模型。"""

    def __init__(self, context_pages: int = 1) -> None:
        self.context_pages = max(0, context_pages)

    def select(
        self,
        pages: list[PageData],
        section_hits: list[SectionHit],
    ) -> list[PageData]:
        page_map = {page.page: page for page in pages}
        hit_types: dict[int, set[str]] = {}
        for hit in section_hits:
            hit_types.setdefault(hit.page, set()).add(hit.section_type)

        selected: set[int] = set()
        has_financial_sections = any(
            hit.section_type in {"financial_information", "accountants_report"}
            for hit in section_hits
        )
        for page in pages:
            types = hit_types.get(page.page, set())
            contains_focus = any(topic.lower() in page.text.lower() for topic in FOCUS_TOPICS)

            # 章节识别失败时，用重点关键词作为兜底。
            if not has_financial_sections and contains_focus:
                selected.add(page.page)
                continue

            # 财务资料章节是管理层讨论，整段保留。
            if "financial_information" in types:
                selected.add(page.page)
                continue

            # 会计师报告很长，只选三大报表、重点科目附注及其上下文。
            if "accountants_report" in types and (
                contains_focus
                or bool(types & {"balance_sheet", "income_statement", "cash_flow_statement", "changes_in_equity"})
            ):
                selected.add(page.page)
                continue

            # 其他章节只保留财务预测和主表页面。
            if types & {
                "balance_sheet",
                "income_statement",
                "cash_flow_statement",
                "changes_in_equity",
                "financial_forecast",
            }:
                selected.add(page.page)

        expanded: set[int] = set()
        for page_number in selected:
            for offset in range(-self.context_pages, self.context_pages + 1):
                candidate = page_number + offset
                if candidate in page_map:
                    expanded.add(candidate)

        return [page_map[number] for number in sorted(expanded)]
