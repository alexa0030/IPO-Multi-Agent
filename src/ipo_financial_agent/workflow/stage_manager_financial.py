"""Research Manager -> Financial Agent stage with explicit fallback and audit output."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ipo_financial_agent.agents.financial_agent import FinancialAnalysisAgent
from ipo_financial_agent.agents.financial_research_manager import (
    FinancialResearchManager,
    ManagerPlanAttempt,
)
from ipo_financial_agent.config import Settings, get_settings
from ipo_financial_agent.document.pdf_loader import PDFLoader
from ipo_financial_agent.document.section_detector import detect_sections
from ipo_financial_agent.document.topic_page_selector import TopicPageSelector
from ipo_financial_agent.llm.client import LLMConfigurationError, OpenAICompatibleClient
from ipo_financial_agent.research.financial_contract_adapter import (
    build_financial_agent_result,
    register_financial_evidence,
)
from ipo_financial_agent.research.manager_context import build_manager_context
from ipo_financial_agent.research.manager_validator import select_financial_task
from ipo_financial_agent.schemas import (
    FinancialAgentResult,
    ManagerFinancialRunResult,
    ManagerPlanArtifact,
)
from ipo_financial_agent.storage.json_store import write_json
from ipo_financial_agent.workflow.stage_financial import FinancialStage


class ManagerFinancialStage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(
        self, *, pdf_path: str | Path, company_name: str, llm_mode: str = "on",
        manager_client: OpenAICompatibleClient | None = None,
    ) -> ManagerFinancialRunResult:
        path = Path(pdf_path).resolve()
        job_id = FinancialStage._job_id(path)
        pages = PDFLoader(path).load()
        section_hits = detect_sections(pages)
        topic_groups = TopicPageSelector(pages_per_topic=2, context_pages=0).select_groups(
            pages, section_hits
        )
        # Financial numbers are always produced by deterministic tools in this stage.
        analysis = FinancialAnalysisAgent(None).analyze(
            document_id=job_id, company=company_name, pages=pages,
            section_hits=section_hits, topic_page_groups=topic_groups,
            llm_mode="off", task=None,
        )
        extraction = analysis["extraction_result"]
        context = build_manager_context(
            company_name=company_name,
            pages=pages,
            section_hits=section_hits,
            facts=extraction.statement_facts,
            metrics=analysis["metrics"],
            forensic_results=analysis["findings"],
        )
        runtime_error: str | None = None
        try:
            client = manager_client or self._client(llm_mode)
            attempt = FinancialResearchManager(client).plan(context)
        except Exception as exc:
            runtime_error = str(exc)
            attempt = ManagerPlanAttempt(plan=None, raw_response="", parse_error=None)
        selected_task, validation, manager_status = select_financial_task(
            plan=attempt.plan,
            context=context,
            raw_response=attempt.raw_response,
            parse_error=attempt.parse_error,
        )
        if runtime_error:
            validation.validation_errors = [f"Research Manager运行失败: {runtime_error}"]
            manager_status = "failed_runtime"
        evidence = register_financial_evidence(
            facts=extraction.statement_facts, metrics=analysis["metrics"]
        )
        financial_result = build_financial_agent_result(
            task=selected_task,
            rules=analysis["findings"],
            evidence=evidence,
            metrics=analysis["metrics"],
        )
        financial_result = FinancialAgentResult.model_validate(
            financial_result.model_dump(mode="json")
        )
        manager_dir = self.settings.output_dir / job_id / "stage_manager"
        financial_dir = self.settings.output_dir / job_id / "stage_financial"
        manager_dir.mkdir(parents=True, exist_ok=True)
        financial_dir.mkdir(parents=True, exist_ok=True)
        write_json(manager_dir / "manager_input.json", context)
        write_json(manager_dir / "research_plan.json", ManagerPlanArtifact(
            plan=attempt.plan, raw_response=attempt.raw_response,
            parse_error=attempt.parse_error or runtime_error,
        ))
        write_json(manager_dir / "selected_financial_task.json", selected_task)
        write_json(manager_dir / "manager_validation.json", validation)
        write_json(financial_dir / "financial_task.json", selected_task)
        write_json(financial_dir / "financial_evidences.json", financial_result.evidences)
        write_json(financial_dir / "financial_findings.json", financial_result.findings)
        write_json(financial_dir / "financial_agent_result.json", financial_result)
        if financial_result.completion_status == "completed":
            pipeline_status = "completed_with_fallback" if validation.fallback_used else "completed"
        else:
            pipeline_status = "failed"
        run_result = ManagerFinancialRunResult(
            job_id=job_id,
            pipeline_status=pipeline_status,
            manager_status=manager_status,
            financial_status=financial_result.completion_status,
            task_source=validation.task_source,
            manager_validation=validation,
        )
        write_json(self.settings.output_dir / job_id / "manager_financial_run_result.json", run_result)
        return run_result

    def _client(self, llm_mode: str) -> OpenAICompatibleClient:
        if llm_mode != "on":
            raise LLMConfigurationError("Research Manager stage requires llm_mode=on")
        if not self.settings.llm_configured:
            raise LLMConfigurationError("model settings are missing")
        return OpenAICompatibleClient(self.settings)
