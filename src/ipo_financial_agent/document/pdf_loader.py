from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz
import pdfplumber

from ipo_financial_agent.models import PageData, RawTable


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class PDFLoader:
    """提取逐页文本与该页原始表格，页码从1开始。"""

    def __init__(self, pdf_path: str | Path) -> None:
        self.pdf_path = Path(pdf_path).resolve()
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在：{self.pdf_path}")
        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"输入文件不是PDF：{self.pdf_path}")

    def load(self) -> list[PageData]:
        page_texts = self._extract_texts()
        page_tables = self._extract_tables()
        pages: list[PageData] = []
        for page_number, text in page_texts.items():
            pages.append(
                PageData(
                    source_file=self.pdf_path.name,
                    page=page_number,
                    text=text,
                    tables=page_tables.get(page_number, []),
                )
            )
        return pages

    def _extract_texts(self) -> dict[int, str]:
        result: dict[int, str] = {}
        with fitz.open(self.pdf_path) as document:
            for page_index, page in enumerate(document):
                result[page_index + 1] = clean_text(page.get_text("text", sort=True))
        return result

    def _extract_tables(self) -> dict[int, list[RawTable]]:
        result: dict[int, list[RawTable]] = {}
        with pdfplumber.open(self.pdf_path) as document:
            for page_index, page in enumerate(document.pages):
                page_number = page_index + 1
                tables: list[RawTable] = []
                try:
                    extracted = page.extract_tables() or []
                except Exception:
                    extracted = []
                for table_index, table in enumerate(extracted, start=1):
                    rows: list[list[str]] = []
                    for row in table or []:
                        cleaned = [clean_text(cell) for cell in (row or [])]
                        if any(cleaned):
                            rows.append(cleaned)
                    if rows:
                        tables.append(RawTable(table_index=table_index, rows=rows))
                result[page_number] = tables
        return result
