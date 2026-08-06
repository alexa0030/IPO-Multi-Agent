"""Runnable Financial-only vertical slice required by PRD v2 phase one."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ipo_financial_agent.config import Settings, get_settings
from ipo_financial_agent.document.pdf_loader import PDFLoader
from ipo_financial_agent.document.section_detector import detect_sections
from ipo_financial_agent.document.topic_page_selector import TopicPageSelector
from ipo_financial_agent.llm.client import LLMConfigurationError, OpenAICompatibleClient
from ipo_financial_agent.nodes import (
    build_run_financial_node,
    generate_financial_report,
    plan_financial_research,
    review_financial_research,
)
from ipo_financial_agent.schemas import IPOResearchState
from ipo_financial_agent.storage.json_store import write_json
from ipo_financial_agent.output.report_writer import write_markdown_report


class _SequentialGraph:
    def __init__(self, nodes: list[Any]) -> None:
        self.nodes = nodes

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        current = dict(state)
        for node in self.nodes:
            update = node(current)
            for key in ("evidences", "financial_findings", "agent_messages", "errors"):
                if key in update:
                    current.setdefault(key, []).extend(update.pop(key))
            current.update(update)
        return current


def _build_graph(nodes: list[Any]) -> Any:
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return _SequentialGraph(nodes)
    graph = StateGraph(IPOResearchState)
    names = ("document_prepare", "plan_research", "run_financial", "review_research", "generate_report")
    for name, node in zip(names, nodes, strict=True):
        graph.add_node(name, node)
    graph.add_edge(START, names[0])
    for left, right in zip(names, names[1:], strict=False):
        graph.add_edge(left, right)
    graph.add_edge(names[-1], END)
    return graph.compile()


class FinancialMinimalClosure:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(
        self,
        *,
        pdf_path: str | Path,
        company_name: str,
        llm_mode: str = "off",
    ) -> dict[str, Any]:
        path = Path(pdf_path).resolve()
        job_id = self._job_id(path)
        client = self._client(llm_mode)

        def document_prepare(state: dict[str, Any]) -> dict[str, Any]:
            pages = PDFLoader(state["pdf_path"]).load()
            section_hits = detect_sections(pages)
            topic_groups = TopicPageSelector(pages_per_topic=2, context_pages=0).select_groups(
                pages, section_hits
            )
            return {
                "pages": pages,
                "section_hits": section_hits,
                "topic_page_groups": topic_groups,
                "document_manifest": {
                    "document_id": job_id,
                    "file_name": path.name,
                    "page_count": len(pages),
                    "language": "zh-CN",
                    "document_type": "hk_ipo_prospectus",
                    "parse_status": "success",
                },
                "document_index": {
                    topic: [item.page for item in items]
                    for topic, items in topic_groups.items()
                },
            }

        graph = _build_graph(
            [
                document_prepare,
                plan_financial_research,
                build_run_financial_node(client),
                review_financial_research,
                generate_financial_report,
            ]
        )
        result = graph.invoke(
            {
                "job_id": job_id,
                "company_name": company_name,
                "pdf_path": str(path),
                "llm_mode": llm_mode,
                "evidences": [],
                "company_findings": [],
                "financial_findings": [],
                "industry_findings": [],
                "legal_findings": [],
                "agent_messages": [],
                "errors": [],
                "follow_up_requests": [],
                "review_round": 0,
            }
        )
        output_dir = self.settings.output_dir / job_id / "financial_minimal"
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "research_task": write_json(output_dir / "research_task.json", result["research_tasks"]),
            "evidence": write_json(output_dir / "evidence.json", result["evidences"]),
            "findings": write_json(output_dir / "findings.json", result["financial_findings"]),
            "review": write_json(output_dir / "review_result.json", result["review_result"]),
            "agent_trace": write_json(output_dir / "agent_trace.json", result["agent_messages"]),
        }
        report_path = write_markdown_report(
            output_dir / "financial_report.md", result["final_report"]
        )
        return {
            "job_id": job_id,
            "document_manifest": result["document_manifest"],
            "research_task_count": len(result["research_tasks"]),
            "evidence_count": len(result["evidences"]),
            "calculation_evidence_count": len(
                [item for item in result["evidences"] if item.source_type == "calculation"]
            ),
            "financial_finding_count": len(result["financial_findings"]),
            "review_result": result["review_result"],
            "report_path": str(report_path),
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
