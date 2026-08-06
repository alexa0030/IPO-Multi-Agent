"""Deterministic Financial-only stage; no Manager, Reviewer, web, or report generation."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ipo_financial_agent.agents.financial_agent import FinancialAnalysisAgent
from ipo_financial_agent.config import Settings, get_settings
from ipo_financial_agent.document.pdf_loader import PDFLoader
from ipo_financial_agent.document.section_detector import detect_sections
from ipo_financial_agent.document.topic_page_selector import TopicPageSelector
from ipo_financial_agent.llm.client import LLMConfigurationError, OpenAICompatibleClient
from ipo_financial_agent.research.financial_contract_adapter import (
    build_financial_agent_result,
    register_financial_evidence,
)
from ipo_financial_agent.research.fixed_financial_task import build_fixed_financial_task
from ipo_financial_agent.schemas import FinancialAgentResult
from ipo_financial_agent.storage.json_store import write_json


class FinancialStage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(
        self, *, pdf_path: str | Path, company_name: str, llm_mode: str = "off"
    ) -> dict[str, Any]:
        path = Path(pdf_path).resolve()
        job_id = self._job_id(path)
        pages = PDFLoader(path).load()
        section_hits = detect_sections(pages)
        topic_groups = TopicPageSelector(pages_per_topic=2, context_pages=0).select_groups(
            pages, section_hits
        )
        task = build_fixed_financial_task()
        analysis = FinancialAnalysisAgent(self._client(llm_mode)).analyze(
            document_id=job_id,
            company=company_name,
            pages=pages,
            section_hits=section_hits,
            topic_page_groups=topic_groups,
            llm_mode=llm_mode,
            task=task,
        )
        evidence = register_financial_evidence(
            facts=analysis["extraction_result"].statement_facts,
            metrics=analysis["metrics"],
        )
        result = build_financial_agent_result(
            task=task, rules=analysis["findings"], evidence=evidence,
            metrics=analysis["metrics"],
        )
        # Revalidate before export so persisted output is the public contract, not an internal dict.
        result = FinancialAgentResult.model_validate(result.model_dump(mode="json"))
        output_dir = self.settings.output_dir / job_id / "stage_financial"
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "financial_task": write_json(output_dir / "financial_task.json", task),
            "financial_evidences": write_json(
                output_dir / "financial_evidences.json", result.evidences
            ),
            "financial_findings": write_json(
                output_dir / "financial_findings.json", result.findings
            ),
            "financial_agent_result": write_json(
                output_dir / "financial_agent_result.json", result
            ),
        }
        return {
            "job_id": job_id,
            "completion_status": result.completion_status,
            "answered_question_ids": result.answered_question_ids,
            "evidence_count": len(result.evidences),
            "finding_count": len(result.findings),
            "paths": {key: str(value) for key, value in paths.items()},
        }

    def _client(self, llm_mode: str) -> OpenAICompatibleClient | None:
        if llm_mode not in {"off", "auto", "on"}:
            raise ValueError("llm_mode must be off, auto, or on")
        if llm_mode == "off":
            return None
        if not self.settings.llm_configured:
            if llm_mode == "on":
                raise LLMConfigurationError("llm_mode=on but model settings are missing")
            return None
        return OpenAICompatibleClient(self.settings)

    @staticmethod
    def _job_id(path: Path) -> str:
        digest = hashlib.sha1(path.read_bytes()).hexdigest()[:8]
        stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", path.stem).strip("_")
        return f"{stem[:48]}_{digest}"
