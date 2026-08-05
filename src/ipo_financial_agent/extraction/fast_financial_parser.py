from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from pydantic import BaseModel, Field

from ipo_financial_agent.finance.topic_catalog import TOPIC_GROUPS, canonical_tag_for_item
from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.models import (
    FinancialExtractionResult,
    FinancialNote,
    PageData,
    RawStatementTable,
    StatementFact,
)


class NoteExtractionResult(BaseModel):
    financial_notes: list[FinancialNote] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


NOTE_SYSTEM_PROMPT = """
你是一名港股IPO招股书财务附注抽取专家。仅抽取当前指定主题的附注解释，不要重复抄写三大财务报表。
硬性规则：
1. 只能使用输入内容，禁止猜测、补充或自行计算。
2. 每条内容必须绑定输入中的真实页码。
3. 最多返回3条financial_notes；每条summary不超过120个汉字。
4. 每条note最多3条explanations；每条解释不超过100个汉字。
5. 每条note最多保留1张关键表，最多8行、6列。
6. source_excerpt不超过80个汉字。
7. fact_id、document_id、company等标识可使用简短占位符，程序会在本地覆盖。
8. 不得输出Markdown、思考过程或JSON之外的文字。
""".strip()


class RawStatementFactExtractor:
    """从原始三大报表确定性提取关键事实，不调用LLM。"""

    YEAR_RE = re.compile(r"(?:19|20)\d{2}")
    NUMBER_RE = re.compile(r"^\(?-?\d[\d,]*(?:\.\d+)?\)?%?$")

    def extract(
        self,
        *,
        document_id: str,
        company: str,
        raw_statements: list[RawStatementTable],
    ) -> list[StatementFact]:
        facts: list[StatementFact] = []
        seen: set[tuple[str, str, str, str, int]] = set()
        for table in raw_statements:
            periods = self._find_periods(table.rows[:8])
            if not periods:
                continue
            for row_index, row in enumerate(table.rows):
                if len(row) < 2:
                    continue
                item_name = self._item_name(row)
                if not item_name:
                    continue
                tag = canonical_tag_for_item(item_name)
                if tag == "other":
                    continue
                numeric_cells = [cell.strip() for cell in row[1:] if self._is_number(cell)]
                if not numeric_cells:
                    continue
                values = numeric_cells[-len(periods) :]
                paired_periods = periods[-len(values) :]
                page = (
                    table.row_pages[row_index]
                    if row_index < len(table.row_pages)
                    else table.pages[0]
                )
                for period, raw_value in zip(paired_periods, values):
                    key = (table.table_id, item_name, period, raw_value, page)
                    if key in seen:
                        continue
                    seen.add(key)
                    seed = "|".join(
                        map(
                            str,
                            [document_id, table.table_id, item_name, period, raw_value, page],
                        )
                    )
                    facts.append(
                        StatementFact(
                            fact_id="fact_"
                            + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:14],
                            document_id=document_id,
                            company=company,
                            statement_name=table.statement_name,
                            item_name=item_name,
                            canonical_tag=tag,
                            period=period,
                            value=self._to_float(raw_value),
                            raw_value=raw_value,
                            unit=table.unit,
                            currency=table.currency,
                            page=page,
                            entity_scope=table.entity_scope,
                            row_order=row_index,
                            source_table_id=table.table_id,
                            confidence=0.88,
                        )
                    )
        return sorted(
            facts,
            key=lambda item: (
                item.page,
                item.statement_name,
                item.row_order or 99999,
                item.period,
            ),
        )

    def _find_periods(self, rows: list[list[str]]) -> list[str]:
        periods: list[str] = []
        for row in rows:
            for cell in row:
                match = self.YEAR_RE.search(cell)
                if match and match.group(0) not in periods:
                    periods.append(match.group(0))
        return periods

    def _item_name(self, row: list[str]) -> str:
        for cell in row[:3]:
            text = cell.strip()
            if text and not self._is_number(text) and not self.YEAR_RE.fullmatch(text):
                return text
        return ""

    def _is_number(self, value: str) -> bool:
        return bool(self.NUMBER_RE.match(value.replace(" ", "")))

    @staticmethod
    def _to_float(raw: str) -> float | None:
        text = raw.replace(",", "").replace(" ", "").strip()
        if text.endswith("%"):
            try:
                return float(text[:-1]) / 100
            except ValueError:
                return None
        negative = text.startswith("(") and text.endswith(")")
        text = text.strip("()")
        try:
            value = float(text)
        except ValueError:
            return None
        return -value if negative else value


class TopicFinancialNoteParser:
    """每个主题只调用一次LLM，并只抽取附注解释。"""

    def __init__(self, client: OpenAICompatibleClient, max_tokens: int = 1400) -> None:
        self.client = client
        self.max_tokens = max_tokens

    def parse(
        self,
        *,
        document_id: str,
        company: str,
        topic_page_groups: dict[str, list[PageData]],
    ) -> FinancialExtractionResult:
        notes: list[FinancialNote] = []
        warnings: list[str] = []
        total = len(topic_page_groups)
        for index, (topic, pages) in enumerate(topic_page_groups.items(), start=1):
            cache_path = self._cache_path(document_id, topic, pages)
            if cache_path.exists():
                try:
                    cached = NoteExtractionResult.model_validate_json(
                        cache_path.read_text(encoding="utf-8")
                    )
                    notes.extend(cached.financial_notes)
                    warnings.extend(cached.warnings)
                    print(f"[note-parser] 缓存命中 {index}/{total}：{topic}", flush=True)
                    continue
                except Exception:
                    cache_path.unlink(missing_ok=True)

            started = time.perf_counter()
            print(
                f"[note-parser] 开始 {index}/{total}：{topic}，"
                f"页码={[page.page for page in pages]}",
                flush=True,
            )
            result = self._request_topic(
                document_id=document_id,
                company=company,
                topic=topic,
                pages=pages,
                max_tokens=self.max_tokens,
            )
            sanitized = self._sanitize(
                result,
                document_id,
                company,
                topic,
                {page.page for page in pages},
            )
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(sanitized.model_dump_json(indent=2), encoding="utf-8")
            notes.extend(sanitized.financial_notes)
            warnings.extend(sanitized.warnings)
            print(
                f"[note-parser] 完成 {index}/{total}：{topic}，"
                f"notes={len(sanitized.financial_notes)}，"
                f"耗时={time.perf_counter() - started:.1f}s",
                flush=True,
            )
        return FinancialExtractionResult(
            financial_notes=self._dedupe_notes(notes),
            warnings=sorted(set(warnings)),
        )

    def _request_topic(
        self,
        *,
        document_id: str,
        company: str,
        topic: str,
        pages: list[PageData],
        max_tokens: int,
    ) -> NoteExtractionResult:
        payload = [self._compact_page(page, TOPIC_GROUPS[topic]) for page in pages]
        prompt = (
            f"document_id: {document_id}\n"
            f"company: {company}\n"
            f"当前主题: {topic}\n"
            f"允许页码: {[page.page for page in pages]}\n\n"
            "只抽取与当前主题直接相关的变动原因、构成、账龄、减值、"
            "信用政策、期限或预测假设。\n页面证据：\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        try:
            return self.client.complete_json(
                system_prompt=NOTE_SYSTEM_PROMPT,
                user_prompt=prompt,
                response_model=NoteExtractionResult,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            if "truncated" not in str(exc).lower():
                raise
            if len(pages) > 1:
                print(f"[note-parser] {topic} 输出截断，按单页重试", flush=True)
                merged_notes: list[FinancialNote] = []
                merged_warnings: list[str] = []
                for page in pages:
                    part = self._request_topic(
                        document_id=document_id,
                        company=company,
                        topic=topic,
                        pages=[page],
                        max_tokens=1200,
                    )
                    merged_notes.extend(part.financial_notes)
                    merged_warnings.extend(part.warnings)
                return NoteExtractionResult(
                    financial_notes=merged_notes,
                    warnings=merged_warnings,
                )
            if max_tokens < 2200:
                print(f"[note-parser] {topic} 单页截断，提升到2200 tokens重试", flush=True)
                return self._request_topic(
                    document_id=document_id,
                    company=company,
                    topic=topic,
                    pages=pages,
                    max_tokens=2200,
                )
            raise

    @staticmethod
    def _compact_page(page: PageData, aliases: list[str]) -> dict:
        text = page.text or ""
        lower = text.lower()
        snippets: list[str] = []
        for alias in aliases:
            start = lower.find(alias.lower())
            if start >= 0:
                left = max(0, start - 500)
                right = min(len(text), start + len(alias) + 1000)
                snippet = text[left:right].strip()
                if snippet and snippet not in snippets:
                    snippets.append(snippet)
            if len(snippets) >= 3:
                break
        if not snippets:
            snippets = [text[:1800]]

        relevant_tables = []
        for table in page.tables:
            table_text = " ".join(" ".join(row) for row in table.rows)
            if any(alias.lower() in table_text.lower() for alias in aliases):
                relevant_tables.append(
                    {
                        "table_index": table.table_index,
                        "rows": [row[:6] for row in table.rows[:12]],
                    }
                )
            if len(relevant_tables) >= 2:
                break
        return {"page": page.page, "snippets": snippets, "tables": relevant_tables}

    @staticmethod
    def _sanitize(
        result: NoteExtractionResult,
        document_id: str,
        company: str,
        topic: str,
        allowed_pages: set[int],
    ) -> NoteExtractionResult:
        clean: list[FinancialNote] = []
        for order, note in enumerate(result.financial_notes[:3], start=1):
            pages = sorted(set(note.pages) & allowed_pages)
            if not pages:
                continue
            payload = note.model_dump()
            payload["document_id"] = document_id
            payload["company"] = company
            payload["topic"] = topic
            payload["pages"] = pages
            payload["note_id"] = "note_" + hashlib.sha1(
                f"{document_id}|{topic}|{pages}|{order}|{note.title}".encode("utf-8")
            ).hexdigest()[:14]
            payload["summary"] = note.summary[:180]
            payload["source_excerpt"] = (note.source_excerpt or "")[:120] or None
            payload["related_fact_ids"] = []
            payload["explanations"] = [
                item.model_dump()
                for item in note.explanations[:3]
                if item.page in allowed_pages
            ]
            payload["tables"] = [
                {
                    **table.model_dump(),
                    "headers": table.headers[:6],
                    "rows": [row[:6] for row in table.rows[:8]],
                }
                for table in note.tables[:1]
                if table.page in allowed_pages
            ]
            clean.append(FinancialNote.model_validate(payload))
        return NoteExtractionResult(financial_notes=clean, warnings=result.warnings)

    @staticmethod
    def _dedupe_notes(notes: list[FinancialNote]) -> list[FinancialNote]:
        best: dict[tuple[str, str, tuple[int, ...]], FinancialNote] = {}
        for note in notes:
            key = (note.topic, note.title, tuple(note.pages))
            current = best.get(key)
            if current is None or note.confidence > current.confidence:
                best[key] = note
        return sorted(best.values(), key=lambda item: (item.pages[0], item.topic, item.title))

    @staticmethod
    def _cache_path(document_id: str, topic: str, pages: list[PageData]) -> Path:
        signature = (
            f"fast-v1|{document_id}|{topic}|"
            + ",".join(str(page.page) for page in pages)
        )
        digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:12]
        safe_topic = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", topic)
        return (
            Path("data/extracted")
            / document_id
            / "fast_note_cache"
            / f"{safe_topic}_{digest}.json"
        )
