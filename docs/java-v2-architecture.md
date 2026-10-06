# Java V2 Architecture Decision

## Decision

Java V2 is an incremental control-plane and service-layer evolution of the existing Python IPO Research Agent.
It is not a full rewrite and not a thin controller that merely shells out to Python.

## Responsibility split

| Layer | Owner | Responsibility |
|---|---|---|
| Document intelligence | Python | PDF parsing, statement extraction, note extraction and mature research pipeline |
| Shared contracts | JSON Schema | Financial facts, reporting entity, evidence lineage and stable identifiers |
| Deterministic finance | Java + Python parity | Metrics and explainable screening rules |
| Control plane | Java | Job lifecycle, API, retries, persistence, trace and orchestration |
| Agent reasoning | Java workflow | Planning, bounded parallel execution, review and one bounded repair round |
| Evaluation | Shared fixtures | Cross-language parity and end-to-end regression |

## Borrowed architectural patterns

- TradingAgents: parallel specialist research followed by centralized risk review.
- Spring AI Alibaba: stateful graph execution and explicit sequential/parallel/routing patterns.
- DataAgent: long-running task state, retry, report generation and human feedback boundaries.
- Azure Java Banking Assistant: supervisor and domain tool separation.
- FinRobot: deterministic software owns numbers; models explain; agents coordinate.

No source file from these projects is copied into this repository. Their patterns are adapted to the project's
existing Evidence/Finding contracts and IPO due-diligence constraints.

## Reliability rules

1. An LLM must not calculate or overwrite financial numbers.
2. A rule hit is an `observation`, not a final risk conclusion.
3. Every metric retains source fact IDs and pages.
4. Parser responses must match the requested `documentId` and contain verified facts.
5. Parser exports only fact IDs approved by a document-level `verified_fact_manifest.json`.
6. Python and Java consume the same fixtures and must stay within declared numeric tolerance.
7. Agent repair is bounded; failure remains visible in job status and trace.

## Delivery sequence

1. Deterministic vertical slice and REST job API.
2. Shared contract and Python/Java parity tests.
3. Python parser service integration.
4. Framework-independent task DAG, reviewer challenge and bounded replan.
5. Persistent asynchronous jobs and idempotency.
6. Spring AI Alibaba runtime adapter for planner/executors/reviewer.
7. Web console, SSE trace, Docker Compose and cloud deployment.
