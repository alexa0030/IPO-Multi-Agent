from __future__ import annotations

from fastapi import FastAPI, HTTPException

from ipo_financial_agent.config import get_settings
from ipo_financial_agent.interop.parser_contract import (
    AnalysisContract,
    ParserAnalysisRequest,
    ParserContractError,
    VerifiedFactContractService,
)


def create_app() -> FastAPI:
    settings = get_settings()
    service = VerifiedFactContractService(settings.extracted_dir)
    app = FastAPI(title="IPO Prospectus Parser Service", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/api/v1/parser/facts",
        response_model=AnalysisContract,
        response_model_by_alias=True,
    )
    def verified_facts(request: ParserAnalysisRequest) -> AnalysisContract:
        try:
            return service.load(request)
        except ParserContractError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


app = create_app()
