from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from ipo_financial_agent.models import (
    AnalysisResult,
    FinancialNote,
    MetricResult,
    PageData,
    RawStatementTable,
    RiskFinding,
    StatementFact,
)


class FinancialRepository:
    """SQLite事实库。原始报表、财务知识和证据页码分表保存。"""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                source_file TEXT NOT NULL,
                pdf_path TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS pages (
                document_id TEXT NOT NULL,
                page INTEGER NOT NULL,
                text TEXT NOT NULL,
                tables_json TEXT NOT NULL,
                PRIMARY KEY (document_id, page),
                FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS raw_statement_tables (
                table_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                statement_name TEXT NOT NULL,
                statement_type TEXT NOT NULL,
                company TEXT NOT NULL,
                entity_scope TEXT,
                unit TEXT,
                currency TEXT,
                pages_json TEXT NOT NULL,
                rows_json TEXT NOT NULL,
                row_pages_json TEXT NOT NULL,
                source_file TEXT NOT NULL,
                confidence REAL NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS statement_facts (
                fact_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                company TEXT NOT NULL,
                statement_name TEXT NOT NULL,
                item_name TEXT NOT NULL,
                canonical_tag TEXT NOT NULL,
                period TEXT NOT NULL,
                value REAL,
                raw_value TEXT NOT NULL,
                unit TEXT,
                currency TEXT,
                page INTEGER NOT NULL,
                note TEXT,
                entity_scope TEXT,
                row_order INTEGER,
                source_table_id TEXT,
                confidence REAL NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS financial_notes (
                note_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                company TEXT NOT NULL,
                topic TEXT NOT NULL,
                title TEXT NOT NULL,
                information_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                pages_json TEXT NOT NULL,
                explanations_json TEXT NOT NULL,
                tables_json TEXT NOT NULL,
                related_fact_ids_json TEXT NOT NULL,
                source_excerpt TEXT,
                confidence REAL NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS metrics (
                metric_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_code TEXT NOT NULL,
                period TEXT NOT NULL,
                value REAL,
                display_value TEXT NOT NULL,
                formula TEXT NOT NULL,
                source_fact_ids_json TEXT NOT NULL,
                source_pages_json TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS risk_findings (
                risk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT NOT NULL,
                evidence_metric_ids_json TEXT NOT NULL,
                evidence_fact_ids_json TEXT NOT NULL,
                source_pages_json TEXT NOT NULL,
                rule_code TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS analysis_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                company TEXT NOT NULL,
                markdown TEXT NOT NULL,
                cited_pages_json TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                model TEXT,
                FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
            );
            """
        )
        self.connection.commit()
        self._ensure_column("raw_statement_tables", "row_pages_json", "TEXT NOT NULL DEFAULT '[]'")

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {row[1] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            self.connection.commit()

    def replace_document(
        self,
        *,
        document_id: str,
        company: str,
        source_file: str,
        pdf_path: str,
    ) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
            self.connection.execute(
                "INSERT INTO documents(document_id, company, source_file, pdf_path) VALUES (?, ?, ?, ?)",
                (document_id, company, source_file, pdf_path),
            )

    def save_pages(self, document_id: str, pages: Iterable[PageData]) -> None:
        rows = [
            (
                document_id,
                page.page,
                page.text,
                json.dumps([table.model_dump() for table in page.tables], ensure_ascii=False),
            )
            for page in pages
        ]
        with self.connection:
            self.connection.executemany(
                "INSERT OR REPLACE INTO pages(document_id, page, text, tables_json) VALUES (?, ?, ?, ?)",
                rows,
            )

    def save_raw_statement_tables(
        self, document_id: str, tables: Iterable[RawStatementTable]
    ) -> None:
        rows = [
            (
                table.table_id,
                document_id,
                table.statement_name,
                table.statement_type,
                table.company,
                table.entity_scope,
                table.unit,
                table.currency,
                json.dumps(table.pages, ensure_ascii=False),
                json.dumps(table.rows, ensure_ascii=False),
                json.dumps(table.row_pages, ensure_ascii=False),
                table.source_file,
                table.confidence,
            )
            for table in tables
        ]
        with self.connection:
            self.connection.executemany(
                """
                INSERT OR REPLACE INTO raw_statement_tables(
                    table_id, document_id, statement_name, statement_type, company,
                    entity_scope, unit, currency, pages_json, rows_json, row_pages_json, source_file, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def save_statement_facts(self, facts: Iterable[StatementFact]) -> None:
        rows = [
            (
                fact.fact_id,
                fact.document_id,
                fact.company,
                fact.statement_name,
                fact.item_name,
                fact.canonical_tag,
                fact.period,
                fact.value,
                fact.raw_value,
                fact.unit,
                fact.currency,
                fact.page,
                fact.note,
                fact.entity_scope,
                fact.row_order,
                fact.source_table_id,
                fact.confidence,
            )
            for fact in facts
        ]
        with self.connection:
            self.connection.executemany(
                """
                INSERT OR REPLACE INTO statement_facts(
                    fact_id, document_id, company, statement_name, item_name, canonical_tag,
                    period, value, raw_value, unit, currency, page, note, entity_scope,
                    row_order, source_table_id, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def save_financial_notes(self, notes: Iterable[FinancialNote]) -> None:
        rows = [
            (
                note.note_id,
                note.document_id,
                note.company,
                note.topic,
                note.title,
                note.information_type,
                note.summary,
                json.dumps(note.pages, ensure_ascii=False),
                json.dumps([item.model_dump() for item in note.explanations], ensure_ascii=False),
                json.dumps([item.model_dump() for item in note.tables], ensure_ascii=False),
                json.dumps(note.related_fact_ids, ensure_ascii=False),
                note.source_excerpt,
                note.confidence,
            )
            for note in notes
        ]
        with self.connection:
            self.connection.executemany(
                """
                INSERT OR REPLACE INTO financial_notes(
                    note_id, document_id, company, topic, title, information_type,
                    summary, pages_json, explanations_json, tables_json,
                    related_fact_ids_json, source_excerpt, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def save_metrics(self, metrics: Iterable[MetricResult]) -> None:
        rows = [
            (
                metric.metric_id,
                metric.document_id,
                metric.metric_name,
                metric.metric_code,
                metric.period,
                metric.value,
                metric.display_value,
                metric.formula,
                json.dumps(metric.source_fact_ids, ensure_ascii=False),
                json.dumps(metric.source_pages, ensure_ascii=False),
                metric.status,
            )
            for metric in metrics
        ]
        with self.connection:
            self.connection.executemany(
                """
                INSERT OR REPLACE INTO metrics(
                    metric_id, document_id, metric_name, metric_code, period,
                    value, display_value, formula, source_fact_ids_json,
                    source_pages_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def save_risk_findings(self, findings: Iterable[RiskFinding]) -> None:
        rows = [
            (
                finding.risk_id,
                finding.document_id,
                finding.category,
                finding.title,
                finding.severity,
                finding.description,
                json.dumps(finding.evidence_metric_ids, ensure_ascii=False),
                json.dumps(finding.evidence_fact_ids, ensure_ascii=False),
                json.dumps(finding.source_pages, ensure_ascii=False),
                finding.rule_code,
            )
            for finding in findings
        ]
        with self.connection:
            self.connection.executemany(
                """
                INSERT OR REPLACE INTO risk_findings(
                    risk_id, document_id, category, title, severity, description,
                    evidence_metric_ids_json, evidence_fact_ids_json,
                    source_pages_json, rule_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def save_analysis(self, analysis: AnalysisResult) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO analysis_runs(
                    document_id, company, markdown, cited_pages_json, generated_at, model
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis.document_id,
                    analysis.company,
                    analysis.markdown,
                    json.dumps(analysis.cited_pages, ensure_ascii=False),
                    analysis.generated_at,
                    analysis.model,
                ),
            )
