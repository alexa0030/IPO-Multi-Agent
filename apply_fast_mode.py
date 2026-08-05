from __future__ import annotations

from pathlib import Path
import re
import shutil

root = Path.cwd()

required = [
    root / "src/ipo_financial_agent/pipeline.py",
    root / "src/ipo_financial_agent/agents/financial_agent.py",
    root / "src/ipo_financial_agent/workflow/graph.py",
]
for path in required:
    if not path.exists():
        raise SystemExit(f"请在 ipo_financial_agent_full 根目录运行。找不到：{path}")

for path in required:
    backup = path.with_suffix(path.suffix + ".before_fast_mode")
    if not backup.exists():
        shutil.copy2(path, backup)
        print(f"已备份：{backup}")

# -----------------------------------------------------------------------------
# 1. 财务主题目录
# -----------------------------------------------------------------------------
(root / "src/ipo_financial_agent/finance/topic_catalog.py").write_text(
r'''from __future__ import annotations

TOPIC_GROUPS: dict[str, list[str]] = {
    "货币资金": ["货币资金", "現金及現金等價物", "现金及现金等价物", "銀行結餘及現金", "银行结余及现金", "现金及银行结余"],
    "应收账款及票据": ["应收账款", "應收賬款", "贸易应收款项", "貿易應收款項", "应收票据", "應收票據", "账龄", "賬齡"],
    "其他应收款": ["其他应收款", "其他應收款", "其他应收款项", "其他應收款項"],
    "存货": ["存货", "存貨", "存货跌价", "存貨撇減", "存货减值", "存貨減值"],
    "固定资产及使用权资产": ["固定资产", "固定資產", "物业、厂房及设备", "物業、廠房及設備", "使用权资产", "使用權資產"],
    "借款及流动性": ["短期借款", "短期贷款", "短期貸款", "长期借款", "長期借款", "银行借款", "銀行借款", "计息借款", "計息借款", "流动负债", "流動負債"],
    "合同负债及递延收益": ["合同负债", "合同負債", "合约负债", "合約負債", "递延收益", "遞延收益", "递延收入", "遞延收入"],
    "应付账款及其他应付款": ["应付账款", "應付賬款", "贸易应付款项", "貿易應付款項", "其他应付款", "其他應付款"],
    "收入毛利及净利润": ["收入", "收益", "毛利", "毛利率", "净利润", "淨利潤", "年内利润", "年內利潤"],
    "期间费用": ["销售费用", "銷售費用", "销售开支", "銷售開支", "管理费用", "管理費用", "行政开支", "行政開支", "研发费用", "研發費用", "研发开支", "研發開支", "财务费用", "財務費用", "财务成本", "財務成本"],
    "现金流": ["经营活动", "經營活動", "投资活动", "投資活動", "融资活动", "融資活動", "现金流量", "現金流量"],
    "财务预测": ["财务预测", "財務預測", "盈利预测", "盈利預測", "profit forecast", "financial forecast"],
}

CANONICAL_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("revenue", ("收入", "收益", "营业收入", "營業收入")),
    ("cost_of_sales", ("销售成本", "銷售成本", "营业成本", "營業成本", "服务成本", "服務成本")),
    ("gross_profit", ("毛利",)),
    ("net_profit", ("净利润", "淨利潤", "年内利润", "年內利潤", "本年利润", "本年利潤")),
    ("selling_expense", ("销售费用", "銷售費用", "销售开支", "銷售開支", "分销开支", "分銷開支")),
    ("administrative_expense", ("管理费用", "管理費用", "行政费用", "行政費用", "行政开支", "行政開支")),
    ("research_expense", ("研发费用", "研發費用", "研发开支", "研發開支", "研发成本", "研發成本")),
    ("finance_expense", ("财务费用", "財務費用", "财务成本", "財務成本", "融资成本", "融資成本")),
    ("cash", ("货币资金", "貨幣資金", "现金及现金等价物", "現金及現金等價物", "银行结余及现金", "銀行結餘及現金", "现金及银行结余")),
    ("inventory", ("存货", "存貨")),
    ("trade_receivable", ("应收账款", "應收賬款", "贸易应收款项", "貿易應收款項", "贸易及其他应收款项", "貿易及其他應收款項")),
    ("notes_receivable", ("应收票据", "應收票據")),
    ("other_receivable", ("其他应收款", "其他應收款", "其他应收款项", "其他應收款項")),
    ("fixed_assets", ("固定资产", "固定資產", "物业、厂房及设备", "物業、廠房及設備")),
    ("right_of_use_assets", ("使用权资产", "使用權資產")),
    ("current_assets", ("流动资产总额", "流動資產總額", "流动资产", "流動資產")),
    ("total_assets", ("资产总额", "資產總額", "资产总值", "資產總值", "总资产", "總資產")),
    ("trade_payable", ("应付账款", "應付賬款", "贸易应付款项", "貿易應付款項")),
    ("other_payable", ("其他应付款", "其他應付款", "其他应付款项", "其他應付款項")),
    ("contract_liability", ("合同负债", "合同負債", "合约负债", "合約負債")),
    ("short_term_borrowing", ("短期借款", "短期贷款", "短期貸款", "一年内到期的借款", "一年內到期的借款")),
    ("long_term_borrowing", ("长期借款", "長期借款", "长期贷款", "長期貸款", "非流动借款", "非流動借款")),
    ("current_liabilities", ("流动负债总额", "流動負債總額", "流动负债", "流動負債")),
    ("total_liabilities", ("负债总额", "負債總額", "总负债", "總負債")),
    ("net_assets", ("资产净值", "資產淨值", "权益总额", "權益總額", "总权益", "總權益")),
    ("operating_cash_flow", ("经营活动产生的现金流量净额", "經營活動產生的現金流量淨額", "经营活动所得现金净额", "經營活動所得現金淨額", "经营活动所用现金净额", "經營活動所用現金淨額")),
    ("investing_cash_flow", ("投资活动产生的现金流量净额", "投資活動產生的現金流量淨額", "投资活动所得现金净额", "投資活動所得現金淨額", "投资活动所用现金净额", "投資活動所用現金淨額")),
    ("financing_cash_flow", ("融资活动产生的现金流量净额", "融資活動產生的現金流量淨額", "融资活动所得现金净额", "融資活動所得現金淨額", "融资活动所用现金净额", "融資活動所用現金淨額")),
    ("deferred_income", ("递延收益", "遞延收益", "递延收入", "遞延收入")),
]


def canonical_tag_for_item(item_name: str) -> str:
    compact = "".join(item_name.split()).lower()
    candidates: list[tuple[int, str]] = []
    for tag, aliases in CANONICAL_PATTERNS:
        for alias in aliases:
            alias_compact = "".join(alias.split()).lower()
            if alias_compact in compact:
                candidates.append((len(alias_compact), tag))
    return max(candidates, default=(0, "other"))[1]
''', encoding="utf-8")

# -----------------------------------------------------------------------------
# 2. 每个主题只选最相关的两页
# -----------------------------------------------------------------------------
(root / "src/ipo_financial_agent/document/topic_page_selector.py").write_text(
r'''from __future__ import annotations

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
''', encoding="utf-8")

# -----------------------------------------------------------------------------
# 3. 主表由 Python 提取；LLM 只抽取附注
# -----------------------------------------------------------------------------
(root / "src/ipo_financial_agent/extraction/fast_financial_parser.py").write_text(
r'''from __future__ import annotations

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
''', encoding="utf-8")

# -----------------------------------------------------------------------------
# 4. 修改 pipeline：不再使用旧的96分块解析器
# -----------------------------------------------------------------------------
pipeline_path = root / "src/ipo_financial_agent/pipeline.py"
text = pipeline_path.read_text(encoding="utf-8")
text = text.replace(
    "from ipo_financial_agent.document.page_selector import FinancialPageSelector\n",
    "from ipo_financial_agent.document.topic_page_selector import TopicPageSelector\n",
)
text = re.sub(
    r"from ipo_financial_agent\.extraction\.financial_parser import \([\s\S]*?\)\n",
    "from ipo_financial_agent.extraction.fast_financial_parser import (\n"
    "    RawStatementFactExtractor,\n"
    "    TopicFinancialNoteParser,\n"
    ")\n",
    text,
    count=1,
)

old_detect = '''    def _detect_sections(self, state: dict[str, Any]) -> dict[str, Any]:
        hits = detect_sections(state["pages"])
        selector = FinancialPageSelector(self.settings.candidate_context_pages)
        candidates = selector.select(state["pages"], hits)
        return {"section_hits": hits, "candidate_pages": candidates}
'''
new_detect = '''    def _detect_sections(self, state: dict[str, Any]) -> dict[str, Any]:
        hits = detect_sections(state["pages"])
        selector = TopicPageSelector(pages_per_topic=2, context_pages=0)
        topic_groups = selector.select_groups(state["pages"], hits)
        candidates = selector.flatten(topic_groups)
        print(
            f"[page-selector] 主题组={len(topic_groups)}，"
            f"LLM候选页={len(candidates)}，"
            f"页码={[page.page for page in candidates]}",
            flush=True,
        )
        return {
            "section_hits": hits,
            "candidate_pages": candidates,
            "topic_page_groups": topic_groups,
        }
'''
if old_detect in text:
    text = text.replace(old_detect, new_detect, 1)
elif "TopicPageSelector(pages_per_topic=2" not in text:
    raise SystemExit("pipeline.py 中未找到 _detect_sections，请先恢复备份后重试。")

pattern = (
    r"    def _parse_financial_information\(self, state: dict\[str, Any\]\) "
    r"-> dict\[str, Any\]:[\s\S]*?\n    def _calculate_metrics"
)
new_parse = '''    def _parse_financial_information(self, state: dict[str, Any]) -> dict[str, Any]:
        statement_facts = RawStatementFactExtractor().extract(
            document_id=state["document_id"],
            company=state["company"],
            raw_statements=state["raw_statements"],
        )
        print(
            f"[statement-parser] 从原始三大报表提取关键事实 {len(statement_facts)} 条",
            flush=True,
        )

        notes_result = FinancialExtractionResult()
        if self._should_use_llm(state["llm_mode"]):
            client = OpenAICompatibleClient(self.settings)
            notes_result = TopicFinancialNoteParser(client, max_tokens=1400).parse(
                document_id=state["document_id"],
                company=state["company"],
                topic_page_groups=state.get("topic_page_groups", {}),
            )
        else:
            notes_result.warnings.append("未调用大模型：未抽取财务附注解释。")

        result = FinancialExtractionResult(
            statement_facts=statement_facts,
            financial_notes=notes_result.financial_notes,
            warnings=notes_result.warnings,
        )
        return {"extraction_result": result}

    def _calculate_metrics'''
text, count = re.subn(pattern, new_parse, text, count=1)
if count != 1 and "RawStatementFactExtractor().extract" not in text:
    raise SystemExit("pipeline.py 中未找到 _parse_financial_information。")
pipeline_path.write_text(text, encoding="utf-8")

# -----------------------------------------------------------------------------
# 5. 限制第二次报告生成的上下文
# -----------------------------------------------------------------------------
agent_path = root / "src/ipo_financial_agent/agents/financial_agent.py"
text = agent_path.read_text(encoding="utf-8")
text = re.sub(r"max_tokens=\d+,", "max_tokens=2500,", text, count=1)
text = re.sub(
    r"\)\[:\d+\]\n        selected_notes",
    ")[:120]\n        selected_notes",
    text,
    count=1,
)
text = re.sub(
    r"\)\[:\d+\]\n        return \{",
    ")[:40]\n        return {",
    text,
    count=1,
)
agent_path.write_text(text, encoding="utf-8")

# -----------------------------------------------------------------------------
# 6. LangGraph state 增加主题页组
# -----------------------------------------------------------------------------
graph_path = root / "src/ipo_financial_agent/workflow/graph.py"
text = graph_path.read_text(encoding="utf-8")
if "topic_page_groups:" not in text:
    text = text.replace(
        "    candidate_pages: list[Any]\n",
        "    candidate_pages: list[Any]\n"
        "    topic_page_groups: dict[str, list[Any]]\n",
    )
graph_path.write_text(text, encoding="utf-8")

print("\n快速模式补丁已完成。")
print("主表：Python确定性提取；附注：按主题调用LLM。")
