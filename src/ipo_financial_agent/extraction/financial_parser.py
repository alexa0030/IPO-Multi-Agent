from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ipo_financial_agent.llm.client import (
    LLMTruncatedError,
    OpenAICompatibleClient,
)
from ipo_financial_agent.llm.prompts import FINANCIAL_PARSE_SYSTEM_PROMPT, FOCUS_TOPICS
from ipo_financial_agent.models import (
    FinancialExtractionResult,
    FinancialNote,
    PageData,
    StatementFact,
)


@dataclass(frozen=True)
class PageChunk:
    chunk_index: int
    pages: list[PageData]

    @property
    def allowed_pages(self) -> set[int]:
        return {page.page for page in self.pages}


class FinancialParser:
    """第一次大模型任务：将候选整页JSON解析为报表事实与重点财务知识。"""

    def __init__(
        self,
        client: OpenAICompatibleClient,
        *,
        max_chars: int = 45000,
        overlap_pages: int = 1,
    ) -> None:
        self.client = client
        self.max_chars = max(2000, max_chars)
        self.overlap_pages = max(0, overlap_pages)

    def parse(
        self,
        *,
        document_id: str,
        company: str,
        pages: list[PageData],
    ) -> FinancialExtractionResult:
        chunks = self._build_chunks(pages)
        total_chunks = len(chunks)
        partial_results: list[FinancialExtractionResult] = []

        print(
            f"[financial-parser] 候选页 {len(pages)} 页，"
            f"共 {total_chunks} 个分块",
            flush=True,
        )

        for chunk in chunks:
            partial_results.extend(
                self._parse_chunk_with_split(
                    document_id=document_id,
                    company=company,
                    chunk=chunk,
                    label=str(chunk.chunk_index),
                    total_chunks=total_chunks,
                )
            )

        return self._merge(partial_results)

    def _parse_chunk_with_split(
        self,
        *,
        document_id: str,
        company: str,
        chunk: PageChunk,
        label: str,
        total_chunks: int,
    ) -> list[FinancialExtractionResult]:
        cache_path = self._chunk_cache_path(
            document_id,
            chunk,
            label,
        )

        if cache_path.exists():
            try:
                cached = FinancialExtractionResult.model_validate_json(
                    cache_path.read_text(encoding="utf-8")
                )

                print(
                    f"[financial-parser] 缓存命中 "
                    f"{label}/{total_chunks}，"
                    f"页码："
                    f"{','.join(map(str, sorted(chunk.allowed_pages)))}",
                    flush=True,
                )

                return [cached]

            except Exception:
                cache_path.unlink(missing_ok=True)

        started_at = time.perf_counter()

        pages_text = ",".join(
            map(str, sorted(chunk.allowed_pages))
        )

        print(
            f"[financial-parser] 开始 "
            f"{label}/{total_chunks}，"
            f"页码：{pages_text}",
            flush=True,
        )

        user_prompt = self._build_prompt(
            document_id,
            company,
            chunk,
        )

        try:
            result = self.client.complete_json(
                system_prompt=FINANCIAL_PARSE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=FinancialExtractionResult,
                max_tokens=5000,
            )

        except LLMTruncatedError as exc:
            if len(chunk.pages) == 1:
                print(
                    "[financial-parser] 单页仍被截断，"
                    "使用 7500 输出 token 重试："
                    f"P{chunk.pages[0].page}",
                    flush=True,
                )

                result = self.client.complete_json(
                    system_prompt=FINANCIAL_PARSE_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    response_model=FinancialExtractionResult,
                    max_tokens=7500,
                )

            else:
                midpoint = len(chunk.pages) // 2

                left = PageChunk(
                    chunk.chunk_index,
                    chunk.pages[:midpoint],
                )

                right = PageChunk(
                    chunk.chunk_index,
                    chunk.pages[midpoint:],
                )

                print(
                    f"[financial-parser] "
                    f"{label}/{total_chunks} 输出被截断，"
                    f"自动拆为 {label}a 和 {label}b。"
                    f"原因：{exc}",
                    flush=True,
                )

                results: list[FinancialExtractionResult] = []

                results.extend(
                    self._parse_chunk_with_split(
                        document_id=document_id,
                        company=company,
                        chunk=left,
                        label=f"{label}a",
                        total_chunks=total_chunks,
                    )
                )

                results.extend(
                    self._parse_chunk_with_split(
                        document_id=document_id,
                        company=company,
                        chunk=right,
                        label=f"{label}b",
                        total_chunks=total_chunks,
                    )
                )

                return results

        sanitized = self._sanitize_result(
            result=result,
            document_id=document_id,
            company=company,
            allowed_pages=chunk.allowed_pages,
            chunk_index=chunk.chunk_index,
        )

        cache_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        cache_path.write_text(
            sanitized.model_dump_json(indent=2),
            encoding="utf-8",
        )

        elapsed = time.perf_counter() - started_at

        print(
            f"[financial-parser] 完成 "
            f"{label}/{total_chunks}，"
            f"facts={len(sanitized.statement_facts)}，"
            f"notes={len(sanitized.financial_notes)}，"
            f"耗时={elapsed:.1f}s",
            flush=True,
        )

        return [sanitized]

    @staticmethod
    def _chunk_cache_path(
        document_id: str,
        chunk: PageChunk,
        label: str,
    ) -> Path:
        signature = "|".join(
            [
                "parser-v3",
                document_id,
                ",".join(
                    map(str, sorted(chunk.allowed_pages))
                ),
                str(
                    sum(
                        len(page.text)
                        for page in chunk.pages
                    )
                ),
            ]
        )

        digest = hashlib.sha1(
            signature.encode("utf-8")
        ).hexdigest()[:12]

        safe_label = re.sub(
            r"[^0-9A-Za-z_-]+",
            "_",
            label,
        )

        return (
            Path("data/extracted")
            / document_id
            / "llm_chunk_cache"
            / f"chunk_{safe_label}_{digest}.json"
        )

    def _build_chunks(self, pages: list[PageData]) -> list[PageChunk]:
        pages = sorted(pages, key=lambda item: item.page)
        chunks: list[PageChunk] = []
        current: list[PageData] = []
        current_chars = 0

        for page in pages:
            page_chars = len(page.text) + sum(
                len(json.dumps(table.rows, ensure_ascii=False)) for table in page.tables
            )
            if current and current_chars + page_chars > self.max_chars:
                chunks.append(PageChunk(len(chunks) + 1, list(current)))
                overlap = current[-self.overlap_pages :] if self.overlap_pages else []
                current = list(overlap)
                current_chars = sum(len(item.text) for item in current)
            current.append(page)
            current_chars += page_chars

        if current:
            chunks.append(PageChunk(len(chunks) + 1, list(current)))
        return chunks

    @staticmethod
    def _build_prompt(
        document_id: str,
        company: str,
        chunk: PageChunk,
    ) -> str:
        page_payload = []

        for page in chunk.pages:
            page_payload.append(
                {
                    "page": page.page,
                    "text": page.text,
                    "tables": [
                        table.model_dump()
                        for table in page.tables
                    ],
                }
            )

        return (
            f"document_id: {document_id}\n"
            f"company: {company}\n"
            f"重点主题: "
            f"{json.dumps(FOCUS_TOPICS, ensure_ascii=False)}\n"
            f"当前批次页码: "
            f"{sorted(chunk.allowed_pages)}\n\n"

            "三大财务报表原始表格已由程序另行保存，"
            "不要逐行复制整张报表。\n"

            "statement_facts 只抽取重点主题、核心指标，"
            "以及指标计算和风险判断必需的数字。\n"

            "financial_notes 重点抽取变动原因、账龄、"
            "构成、减值、借款期限、费用明细、"
            "信用政策和预测假设。\n"

            "同一事实不要重复；"
            "item_name 和 statement_name 必须保留原文；"
            "只能使用当前批次真实页码。\n\n"

            "页面JSON：\n"
            + json.dumps(
                page_payload,
                ensure_ascii=False,
            )
        )

    def _sanitize_result(
        self,
        *,
        result: FinancialExtractionResult,
        document_id: str,
        company: str,
        allowed_pages: set[int],
        chunk_index: int,
    ) -> FinancialExtractionResult:
        facts: list[StatementFact] = []
        for order, fact in enumerate(result.statement_facts, start=1):
            if fact.page not in allowed_pages:
                continue
            payload = fact.model_dump()
            payload["document_id"] = document_id
            payload["company"] = company
            payload["fact_id"] = self._fact_id(document_id, fact, chunk_index, order)
            payload["confidence"] = min(max(float(fact.confidence), 0.0), 1.0)
            facts.append(StatementFact.model_validate(payload))

        notes: list[FinancialNote] = []
        for order, note in enumerate(result.financial_notes, start=1):
            valid_pages = sorted(set(note.pages) & allowed_pages)
            if not valid_pages:
                continue
            payload = note.model_dump()
            payload["document_id"] = document_id
            payload["company"] = company
            payload["pages"] = valid_pages
            payload["note_id"] = self._note_id(document_id, note, chunk_index, order)
            payload["explanations"] = [
                explanation.model_dump()
                for explanation in note.explanations
                if explanation.page in allowed_pages
            ]
            payload["tables"] = [
                table.model_dump() for table in note.tables if table.page in allowed_pages
            ]
            payload["confidence"] = min(max(float(note.confidence), 0.0), 1.0)
            notes.append(FinancialNote.model_validate(payload))

        return FinancialExtractionResult(
            statement_facts=facts,
            financial_notes=notes,
            warnings=result.warnings,
        )

    @staticmethod
    def _fact_id(
        document_id: str,
        fact: StatementFact,
        chunk_index: int,
        order: int,
    ) -> str:
        seed = "|".join(
            [
                document_id,
                fact.statement_name,
                fact.item_name,
                fact.period,
                fact.raw_value,
                str(fact.page),
                str(chunk_index),
                str(order),
            ]
        )
        return "fact_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:14]

    @staticmethod
    def _note_id(
        document_id: str,
        note: FinancialNote,
        chunk_index: int,
        order: int,
    ) -> str:
        seed = "|".join(
            [
                document_id,
                note.topic,
                note.title,
                ",".join(map(str, note.pages)),
                str(chunk_index),
                str(order),
            ]
        )
        return "note_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:14]

    def _merge(self, results: Iterable[FinancialExtractionResult]) -> FinancialExtractionResult:
        fact_map: dict[tuple[str, str, str, str, int], StatementFact] = {}
        note_map: dict[tuple[str, str, tuple[int, ...]], FinancialNote] = {}
        warnings: list[str] = []

        for result in results:
            warnings.extend(result.warnings)
            for fact in result.statement_facts:
                key = (
                    fact.statement_name,
                    fact.item_name,
                    fact.period,
                    fact.raw_value,
                    fact.page,
                )
                existing = fact_map.get(key)
                if existing is None or fact.confidence > existing.confidence:
                    fact_map[key] = fact
            for note in result.financial_notes:
                key = (note.topic, note.title, tuple(note.pages))
                existing = note_map.get(key)
                if existing is None or note.confidence > existing.confidence:
                    note_map[key] = note

        facts = sorted(
            fact_map.values(),
            key=lambda item: (item.page, item.statement_name, item.row_order or 99999, item.period),
        )
        notes = sorted(note_map.values(), key=lambda item: (item.pages[0], item.topic))
        return FinancialExtractionResult(
            statement_facts=facts,
            financial_notes=notes,
            warnings=sorted(set(warnings)),
        )


class HeuristicStatementFactExtractor:
    """无LLM时的有限兜底，只从原始表格行抽取明显数字；不用于正式分析。"""

    PERIOD_RE = re.compile(r"(?:19|20)\d{2}(?:年\d{1,2}月\d{1,2}日)?")
    NUMBER_RE = re.compile(r"^\(?-?\d[\d,]*(?:\.\d+)?\)?%?$")

    def extract(self, *, document_id: str, company: str, pages: list[PageData]) -> FinancialExtractionResult:
        facts: list[StatementFact] = []
        for page in pages:
            for table in page.tables:
                periods = self._find_periods(table.rows[:6])
                if not periods:
                    continue
                for row_order, row in enumerate(table.rows[1:], start=1):
                    if len(row) < 2:
                        continue
                    item_name = row[0].strip()
                    if not item_name:
                        continue
                    numeric_cells = [cell for cell in row[1:] if self.NUMBER_RE.match(cell.replace(" ", ""))]
                    for period, raw_value in zip(periods, numeric_cells[-len(periods) :]):
                        value = self._to_float(raw_value)
                        seed = f"{document_id}|{page.page}|{table.table_index}|{row_order}|{period}|{raw_value}"
                        facts.append(
                            StatementFact(
                                fact_id="heur_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:14],
                                document_id=document_id,
                                company=company,
                                statement_name="未识别财务表",
                                item_name=item_name,
                                canonical_tag="other",
                                period=period,
                                value=value,
                                raw_value=raw_value,
                                page=page.page,
                                row_order=row_order,
                                source_table_id=f"page_{page.page}_table_{table.table_index}",
                                confidence=0.35,
                            )
                        )
        return FinancialExtractionResult(statement_facts=facts)

    def _find_periods(self, rows: list[list[str]]) -> list[str]:
        text = " ".join(" ".join(row) for row in rows)
        return list(dict.fromkeys(self.PERIOD_RE.findall(text)))

    @staticmethod
    def _to_float(raw: str) -> float | None:
        text = raw.replace(",", "").strip()
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
