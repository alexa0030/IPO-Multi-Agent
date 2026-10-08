FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    IPO_PROJECT_ROOT=/app

WORKDIR /app

RUN useradd --create-home --uid 10001 ipo

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --upgrade pip && python -m pip install ".[api]"

RUN mkdir -p data/uploads data/extracted data/output data/db && chown -R ipo:ipo /app
USER ipo

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"

CMD ["uvicorn", "ipo_financial_agent.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
