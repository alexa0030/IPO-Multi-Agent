from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Protocol
from uuid import uuid4

from ipo_financial_agent.models import PipelineArtifacts
from ipo_financial_agent.pipeline import IPOFinancialPipeline


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PipelineRunner(Protocol):
    def run(self, *, pdf_path: str | Path, company: str, llm_mode: str) -> PipelineArtifacts: ...


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    document_id: str
    company: str
    llm_mode: str
    status: str
    created_at: datetime
    updated_at: datetime
    report_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class JobNotFoundError(KeyError):
    pass


class DocumentNotFoundError(FileNotFoundError):
    pass


class ReportNotReadyError(RuntimeError):
    pass


class InMemoryJobService:
    """Small process-local job service; storage can be replaced without touching routes."""

    def __init__(self, upload_dir: Path, runner: PipelineRunner | None = None) -> None:
        self.upload_dir = upload_dir
        self.runner = runner or IPOFinancialPipeline()
        self._jobs: dict[str, JobRecord] = {}
        self._lock = RLock()

    def create(self, *, document_id: str, company: str, llm_mode: str) -> JobRecord:
        if not self.document_path(document_id).is_file():
            raise DocumentNotFoundError(document_id)
        now = _now()
        job = JobRecord(
            job_id=uuid4().hex,
            document_id=document_id,
            company=company.strip(),
            llm_mode=llm_mode,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def run(self, job_id: str) -> None:
        job = self.get(job_id)
        self._save(replace(job, status="running", updated_at=_now()))
        try:
            artifacts = self.runner.run(
                pdf_path=self.document_path(job.document_id),
                company=job.company,
                llm_mode=job.llm_mode,
            )
            report_path = artifacts.final_report_path or artifacts.report_path
            if not report_path or not Path(report_path).is_file():
                raise ReportNotReadyError("pipeline completed without a readable report")
            self._save(replace(job, status="completed", updated_at=_now(), report_path=report_path))
        except Exception as exc:  # noqa: BLE001 - process boundary must persist arbitrary worker failures
            self._save(
                replace(
                    job,
                    status="failed",
                    updated_at=_now(),
                    error_code=type(exc).__name__,
                    error_message=str(exc)[:1000] or "pipeline execution failed",
                )
            )

    def get(self, job_id: str) -> JobRecord:
        with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError as exc:
                raise JobNotFoundError(job_id) from exc

    def report(self, job_id: str) -> str:
        job = self.get(job_id)
        if job.status != "completed" or not job.report_path:
            raise ReportNotReadyError(job.status)
        path = Path(job.report_path)
        if not path.is_file():
            raise ReportNotReadyError("report file is missing")
        return path.read_text(encoding="utf-8")

    def document_path(self, document_id: str) -> Path:
        if not document_id or any(char not in "0123456789abcdef" for char in document_id):
            raise DocumentNotFoundError(document_id)
        return self.upload_dir / f"{document_id}.pdf"

    def _save(self, job: JobRecord) -> None:
        with self._lock:
            self._jobs[job.job_id] = job
