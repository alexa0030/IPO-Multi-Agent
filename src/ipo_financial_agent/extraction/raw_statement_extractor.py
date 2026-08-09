from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from ipo_financial_agent.models import PageData, RawStatementTable, SectionHit
from ipo_financial_agent.text_normalization import to_simplified

STATEMENT_TYPES = {
    "balance_sheet",
    "income_statement",
    "cash_flow_statement",
    "changes_in_equity",
}


def _infer_unit(text: str) -> str | None:
    patterns = [
        r"人民币百万元",
        r"人民幣百萬元",
        r"人民币千元",
        r"人民幣千元",
        r"港币百万元",
        r"港幣百萬元",
        r"港币千元",
        r"港幣千元",
        r"RMB\s*million",
        r"RMB\s*thousand",
        r"HK\$\s*million",
        r"HK\$\s*thousand",
        r"百万元",
        r"百萬元",
        r"千元",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(0)
    return None


def _infer_currency(text: str) -> str | None:
    if re.search(r"人民币|人民幣|\bRMB\b", text, flags=re.I):
        return "人民币"
    if re.search(r"港币|港幣|HK\$", text, flags=re.I):
        return "港币"
    if re.search(r"美元|US\$|USD", text, flags=re.I):
        return "美元"
    return None


def _dedupe_repeated_header(rows: list[list[str]]) -> list[list[str]]:
    result: list[list[str]] = []
    seen_first_rows: set[str] = set()
    for index, row in enumerate(rows):
        key = "|".join(cell.strip() for cell in row)
        if index > 0 and key in seen_first_rows:
            continue
        result.append(row)
        if index < 8:
            seen_first_rows.add(key)
    return result


class RawStatementExtractor:
    """识别三大报表及权益变动表，保留PDF原始行列，不做科目映射。"""

    def __init__(self, max_following_pages: int = 3) -> None:
        self.max_following_pages = max(0, max_following_pages)

    def extract(
        self,
        *,
        pages: list[PageData],
        section_hits: list[SectionHit],
        company: str,
        document_id: str,
    ) -> list[RawStatementTable]:
        page_map = {page.page: page for page in pages}
        statement_hits = [hit for hit in section_hits if hit.section_type in STATEMENT_TYPES]
        statement_hits.sort(key=lambda item: item.page)
        results: list[RawStatementTable] = []
        used_start_pages: set[tuple[str, int]] = set()

        for index, hit in enumerate(statement_hits):
            if (hit.section_type, hit.page) in used_start_pages:
                continue
            start_page = hit.page
            # 目录页通常没有可用表格，跳过。
            if not page_map.get(start_page) or not page_map[start_page].tables:
                continue

            next_statement_page = None
            for future in statement_hits[index + 1 :]:
                if future.page > start_page:
                    next_statement_page = future.page
                    break

            end_page = start_page + self.max_following_pages
            if next_statement_page is not None:
                end_page = min(end_page, next_statement_page - 1)

            collected_rows: list[list[str]] = []
            collected_row_pages: list[int] = []
            source_pages: list[int] = []
            expected_columns: int | None = None
            for page_number in range(start_page, end_page + 1):
                page = page_map.get(page_number)
                if page is None:
                    break
                if page_number > start_page and self._looks_like_new_major_section(page.text):
                    break
                page_rows = self._select_statement_rows(page, hit.section_type)
                if not page_rows:
                    break
                dominant_columns = self._dominant_column_count(page_rows)
                if expected_columns is None:
                    expected_columns = dominant_columns
                elif dominant_columns != expected_columns:
                    break
                collected_rows.extend(page_rows)
                collected_row_pages.extend([page_number] * len(page_rows))
                source_pages.append(page_number)

            if not collected_rows:
                continue

            collected_rows, collected_row_pages = self._dedupe_rows_with_pages(collected_rows, collected_row_pages)
            context_pages = range(max(min(page_map), start_page - 4), source_pages[-1] + 1)
            metadata_text = "\n".join(
                page_map[p].text[:2400] for p in context_pages if p in page_map
            )
            table_id = self._table_id(document_id, hit.section_type, source_pages)
            results.append(
                RawStatementTable(
                    table_id=table_id,
                    statement_name=hit.title,
                    statement_type=hit.section_type,
                    company=company,
                    reporting_entity=self._infer_reporting_entity(metadata_text, company),
                    entity_scope=self._infer_scope(metadata_text),
                    unit=_infer_unit(metadata_text),
                    currency=_infer_currency(metadata_text),
                    pages=source_pages,
                    rows=collected_rows,
                    row_pages=collected_row_pages,
                    source_file=page_map[start_page].source_file,
                    confidence=0.8,
                )
            )
            used_start_pages.add((hit.section_type, hit.page))

        return self._dedupe_tables(results)


    @staticmethod
    def _dedupe_rows_with_pages(rows: list[list[str]], row_pages: list[int]) -> tuple[list[list[str]], list[int]]:
        result_rows: list[list[str]] = []
        result_pages: list[int] = []
        seen_header_keys: set[str] = set()
        for index, (row, page) in enumerate(zip(rows, row_pages)):
            key = "|".join(cell.strip() for cell in row)
            if index > 0 and key in seen_header_keys:
                continue
            result_rows.append(row)
            result_pages.append(page)
            if index < 8:
                seen_header_keys.add(key)
        return result_rows, result_pages

    @classmethod
    def _select_statement_rows(cls, page: PageData, statement_type: str) -> list[list[str]]:
        if not page.tables:
            return []
        scored = [(cls._table_score(table.rows, statement_type), table) for table in page.tables]
        best_score = max(score for score, _ in scored)
        if best_score <= 0:
            return []
        # 同页可能同时出现利润表和资产负债表，只保留当前类型得分最高的表。
        selected = [table for score, table in scored if score == best_score]
        rows: list[list[str]] = []
        for table in sorted(selected, key=lambda item: item.table_index):
            rows.extend(table.rows)
        return rows

    @staticmethod
    def _table_score(rows: list[list[str]], statement_type: str) -> int:
        text = "".join("".join(row) for row in rows)
        keyword_map = {
            "balance_sheet": ["非流动资产", "非流動資產", "流动资产", "流動資產", "流动负债", "流動負債", "资产总值", "資產總值", "权益总额", "權益總額"],
            "income_statement": ["收入", "销售成本", "銷售成本", "毛利", "除税前利润", "除稅前利潤", "年内利润", "年內利潤"],
            "cash_flow_statement": ["经营活动", "經營活動", "投资活动", "投資活動", "融资活动", "融資活動", "现金及现金等价物", "現金及現金等價物"],
            "changes_in_equity": ["股本", "股份溢价", "股份溢價", "保留盈利", "权益总额", "權益總額"],
        }
        return sum(1 for keyword in keyword_map.get(statement_type, []) if keyword in text)


    @staticmethod
    def _dominant_column_count(rows: list[list[str]]) -> int:
        counts: dict[int, int] = {}
        for row in rows:
            counts[len(row)] = counts.get(len(row), 0) + 1
        return max(counts, key=counts.get) if counts else 0

    @staticmethod
    def _looks_like_new_major_section(text: str) -> bool:
        head = re.sub(r"\s+", "", text[:1200])
        start_patterns = ["财务资料", "財務資料", "风险因素", "風險因素", "业务", "業務"]
        stop_phrases = [
            "综合损益及其他全面收益表中选定项目的说明",
            "綜合損益及其他全面收益表中選定項目的說明",
        ]
        return any(head.startswith(pattern) for pattern in start_patterns) or any(
            phrase in head for phrase in stop_phrases
        )

    @staticmethod
    def _infer_scope(text: str) -> str | None:
        compact = re.sub(r"\s+", "", text)
        if "母公司" in compact or "本公司财务状况表" in compact or "本公司財務狀況表" in compact:
            return "母公司"
        if "综合" in compact or "綜合" in compact or "合并" in compact or "合併" in compact:
            return "集团/合并"
        return None

    @staticmethod
    def _infer_reporting_entity(text: str, issuer_company: str) -> str:
        """Identify whose accounts these are, independently of consolidation scope."""
        normalized = to_simplified(text)
        patterns = [
            r"(?m)^[ \t]*附录\s*[一二三四五六七八九十]+[A-Z\d]*[ \t]*(?P<entity>[\u4e00-\u9fffA-Za-z（）()·]{2,30})[ \t]*会计师报告[ \t]*$",
        ]
        issuer_normalized = to_simplified(issuer_company)
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if not match:
                continue
            entity = match.group("entity").strip("：:，,。")
            if entity and entity not in {"会计师", "申报会计师"}:
                return issuer_company if entity in issuer_normalized else entity
        return issuer_company

    @staticmethod
    def _table_id(document_id: str, statement_type: str, pages: list[int]) -> str:
        seed = f"{document_id}|{statement_type}|{','.join(map(str, pages))}"
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
        return f"{statement_type}_{digest}"

    @staticmethod
    def _dedupe_tables(tables: list[RawStatementTable]) -> list[RawStatementTable]:
        grouped: dict[tuple[str, tuple[int, ...]], RawStatementTable] = {}
        for table in tables:
            key = (table.statement_type, tuple(table.pages))
            current = grouped.get(key)
            if current is None or len(table.rows) > len(current.rows):
                grouped[key] = table
        return sorted(grouped.values(), key=lambda item: item.pages[0])
