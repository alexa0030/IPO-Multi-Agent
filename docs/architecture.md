# Architecture

## Design goals

The system optimizes for traceability, deterministic financial calculations, bounded agent autonomy, and graceful offline operation. An Agent may interpret evidence, but it may not silently invent a source or replace a Python calculation.

## Layers

### 1. Document and evidence layer

- `pages.json` stores page number, full text, and raw tables.
- `raw_statements.json` preserves detected statement layouts and labels.
- `Evidence` represents either a PDF location, a calculation trace, or a real web URL.
- `EvidenceStore` deduplicates evidence and validates Finding references.
- SQLite and JSON outputs allow later review without rerunning the model.

### 2. Deterministic financial tool layer

The Financial DD Agent orchestrates raw-statement extraction, canonical fact mapping, metric calculation, six baseline risk rules, and twenty forensic rules. Every derived metric retains its source facts and pages. LLM reasoning is downstream of these tools.

### 3. Agent collaboration layer

```text
ResearchManager
  ├── FinancialDD ──┐
  ├── Prospectus ───┼──> InvestmentCommittee ──> Skeptic
  └── Industry ─────┘                              ├──> targeted follow-up (max 1 round)
                                                   └──> ReportWriter
```

- `ResearchManager` creates typed tasks.
- Specialist Agents return append-only `ResearchPatch` objects.
- `InvestmentCommittee` compares conclusions and records contradictions.
- `Skeptic` converts the most material gaps into at most three `Challenge` objects.
- Only externally verifiable market challenges can trigger web search.
- The graph permits at most one follow-up round, preventing open-ended loops.
- `ReportWriter` renders from state and does not create new facts.

LangGraph executes the specialist branches in parallel when installed. A deterministic sequential fallback uses the same node contracts.

## Search integrity

Search is provider-based. The current Tavily adapter returns an empty list when its API key is absent; it never emits mock results. Queries are planned by source need (filings, regulatory, registry, litigation, industry, adverse media), URLs are deduplicated, and known official domains receive a source-tier label. Search evidence still requires analyst review.

## State and routing

Parallel branches append `research_evidence`, `research_findings`, `open_questions`, and `agent_messages`. Challenges are produced after fan-in and therefore replace a plain list rather than use a reducer. The `followup_round` counter is a hard routing guard.

## Traceability invariants

1. A PDF Evidence item must reference an actual input page.
2. A web Evidence item must contain a real URL.
3. A Finding must cite at least one known Evidence ID.
4. A computed metric retains source fact IDs and pages.
5. Missing evidence remains an open question or unresolved challenge.
6. Report sections cite the Evidence Ledger instead of copying unsupported Agent prose.

## Known failure modes

- Scanned pages need OCR before the current text path can analyze them.
- Borderless and merged-cell tables can require manual correction.
- Canonical mapping can confuse similarly named line items or mixed periods.
- A search result is discoverability evidence, not proof that its claim is true.
- Filing amendments and post-listing events require document/version awareness.
