# Hosonsoft reproducibility sample

This directory contains sanitized, reviewable metadata from the real 2026-08-27 run. The 504-page prospectus, page-level extracted text, API credentials, database, and full internal report are excluded.

- Input: Shenzhen Hosonsoft application proof, 504 pages
- Deterministic run: `llm_mode=off`
- Model run: Qwen3.5-4B served by vLLM with a 32,768-token context window
- Model calls: 24 successful Chat Completions requests, no HTTP 4xx/5xx
- Deliverables: Markdown report, two Excel workbooks, evidence ledger, Agent trace, delivery manifest
- Development-case evaluation: 8/8 verified metrics, 6/6 verified findings, 100% evidence-page accuracy, 0 unsupported-finding rate

This is a single development case, not a claim of cross-company generalization.
