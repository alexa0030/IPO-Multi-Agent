from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile, status

from ipo_financial_agent.api.job_service import (
    DocumentNotFoundError,
    InMemoryJobService,
    JobNotFoundError,
    JobRecord,
    ReportNotReadyError,
)
from ipo_financial_agent.api.schemas import (
    DocumentResponse,
    JobCreateRequest,
    JobResponse,
    ReportResponse,
)
from ipo_financial_agent.config import get_settings

MAX_PDF_BYTES = 50 * 1024 * 1024


def _response(job: JobRecord) -> JobResponse:
    return JobResponse(**{field: getattr(job, field) for field in JobResponse.model_fields})


def create_app(service: InMemoryJobService | None = None) -> FastAPI:
    settings = get_settings()
    jobs = service or InMemoryJobService(settings.upload_dir)
    app = FastAPI(title="HK IPO Research API", version="1.0.0")
    app.state.jobs = jobs

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
    async def upload_document(file: Annotated[UploadFile, File()]) -> DocumentResponse:
        filename = Path(file.filename or "").name
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=415, detail="only PDF files are accepted")
        content = await file.read(MAX_PDF_BYTES + 1)
        if len(content) > MAX_PDF_BYTES:
            raise HTTPException(status_code=413, detail="PDF exceeds the 50 MB limit")
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=422, detail="file content is not a valid PDF")
        document_id = hashlib.sha256(content).hexdigest()
        path = jobs.upload_dir / f"{document_id}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(content)
        return DocumentResponse(document_id=document_id, filename=filename, size_bytes=len(content))

    @app.post("/api/v1/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
    def create_job(request: JobCreateRequest, background: BackgroundTasks) -> JobResponse:
        try:
            job = jobs.create(**request.model_dump())
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail="document not found") from exc
        background.add_task(jobs.run, job.job_id)
        return _response(job)

    @app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
    def get_job(job_id: str) -> JobResponse:
        try:
            return _response(jobs.get(job_id))
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.get("/api/v1/jobs/{job_id}/report", response_model=ReportResponse)
    def get_report(job_id: str) -> ReportResponse:
        try:
            return ReportResponse(job_id=job_id, markdown=jobs.report(job_id))
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        except ReportNotReadyError as exc:
            raise HTTPException(status_code=409, detail="report is not ready") from exc

    return app


app = create_app()
