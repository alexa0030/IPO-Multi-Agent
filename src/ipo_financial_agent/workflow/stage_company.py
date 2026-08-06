"""Deterministic Company & Business stage backed by ProspectusAgent."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ipo_financial_agent.agents.prospectus_agent import ProspectusAgent
from ipo_financial_agent.config import Settings, get_settings
from ipo_financial_agent.llm.client import LLMConfigurationError, OpenAICompatibleClient
from ipo_financial_agent.models_agent import ProspectusAnalysis
from ipo_financial_agent.research import prospectus_research_patch
from ipo_financial_agent.storage.json_store import write_json

PDFLoader = None
detect_sections = None
TopicPageSelector = None


class CompanyBusinessStage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(
        self, *, pdf_path: str | Path, company_name: str, llm_mode: str = "off"
    ) -> dict[str, Any]:
        global PDFLoader, detect_sections, TopicPageSelector
        if PDFLoader is None or detect_sections is None or TopicPageSelector is None:
            from ipo_financial_agent.document.pdf_loader import PDFLoader as _PDFLoader
            from ipo_financial_agent.document.section_detector import (
                detect_sections as _detect_sections,
            )
            from ipo_financial_agent.document.topic_page_selector import (
                TopicPageSelector as _TopicPageSelector,
            )

            PDFLoader = _PDFLoader
            detect_sections = _detect_sections
            TopicPageSelector = _TopicPageSelector

        path = Path(pdf_path).resolve()
        job_id = self._job_id(path)
        pages = PDFLoader(path).load()
        section_hits = detect_sections(pages)
        topic_groups = TopicPageSelector(pages_per_topic=2, context_pages=0).select_groups(
            pages, section_hits
        )
        client = self._client(llm_mode)
        try:
            analysis = ProspectusAgent(client).analyze(
                company=company_name,
                pages=pages,
                section_hits=section_hits,
            )
        except Exception:
            if llm_mode != "auto" or client is None:
                raise
            # ``auto`` promises availability: if the configured model endpoint
            # is temporarily unreachable, rerun the deterministic analyser.
            analysis = ProspectusAgent(None).analyze(
                company=company_name,
                pages=pages,
                section_hits=section_hits,
            )
        analysis = ProspectusAnalysis.model_validate(analysis.model_dump(mode="json"))
        patch = prospectus_research_patch(analysis)
        output_dir = self.settings.output_dir / job_id / "stage_company"
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "company_task": write_json(
                output_dir / "company_task.json",
                {
                    "job_id": job_id,
                    "company": company_name,
                    "pdf_path": str(path),
                    "section_count": len(section_hits),
                    "candidate_pages": len(topic_groups),
                },
            ),
            "company_analysis": write_json(output_dir / "company_analysis.json", analysis),
            "company_evidences": write_json(output_dir / "company_evidences.json", patch.evidence),
            "company_findings": write_json(output_dir / "company_findings.json", patch.findings),
            "company_open_questions": write_json(
                output_dir / "company_open_questions.json", patch.open_questions
            ),
        }
        return {
            "job_id": job_id,
            "output_status": "completed",
            "company_name": company_name,
            "finding_count": len(patch.findings),
            "evidence_count": len(patch.evidence),
            "open_question_count": len(patch.open_questions),
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
