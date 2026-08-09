from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ipo_financial_agent.tools.registry import DomainToolRegistry


class RuntimeBudgetExceeded(RuntimeError):
    """Raised when an agent exceeds its bounded rounds or tool calls."""


class ToolExecutionTimeout(TimeoutError):
    """Raised when one tool call exceeds its configured wall-clock timeout."""


class RuntimeBudget(BaseModel):
    max_rounds: int = Field(default=3, ge=1, le=10)
    max_tool_calls: int = Field(default=5, ge=1, le=20)
    max_retries: int = Field(default=1, ge=0, le=3)
    timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    used_rounds: int = Field(default=0, ge=0)
    used_tool_calls: int = Field(default=0, ge=0)


class ToolCallTrace(BaseModel):
    call_id: str
    role: str
    tool_name: str
    round_number: int
    attempt: int
    started_at: str
    duration_ms: int = Field(ge=0)
    status: Literal["success", "error", "timeout", "budget_exhausted"]
    arguments: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class AgentRuntime:
    """Execute structured tools with bounded cost and an append-only trace."""

    def __init__(
        self,
        *,
        registry: DomainToolRegistry,
        role: str,
        budget: RuntimeBudget | None = None,
    ) -> None:
        self.registry = registry
        self.role = role
        self.budget = budget or RuntimeBudget()
        self.trace: list[ToolCallTrace] = []

    def begin_round(self) -> int:
        if self.budget.used_rounds >= self.budget.max_rounds:
            raise RuntimeBudgetExceeded(
                f"agent {self.role!r} exceeded {self.budget.max_rounds} rounds"
            )
        self.budget.used_rounds += 1
        return self.budget.used_rounds

    def execute_tool(self, tool_name: str, **arguments: Any) -> BaseModel:
        if self.budget.used_rounds == 0:
            self.begin_round()
        if self.budget.used_tool_calls >= self.budget.max_tool_calls:
            self._append_budget_trace(tool_name, arguments)
            raise RuntimeBudgetExceeded(
                f"agent {self.role!r} exceeded {self.budget.max_tool_calls} tool calls"
            )
        self.budget.used_tool_calls += 1

        last_error: Exception | None = None
        for attempt in range(1, self.budget.max_retries + 2):
            started_at = datetime.now(timezone.utc).isoformat()
            started = time.perf_counter()
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(
                self.registry.execute,
                self.role,
                tool_name,
                **arguments,
            )
            try:
                output = future.result(timeout=self.budget.timeout_seconds)
            except FutureTimeoutError as exc:
                future.cancel()
                duration = self._duration_ms(started)
                self.trace.append(
                    ToolCallTrace(
                        call_id=self._call_id(),
                        role=self.role,
                        tool_name=tool_name,
                        round_number=self.budget.used_rounds,
                        attempt=attempt,
                        started_at=started_at,
                        duration_ms=duration,
                        status="timeout",
                        arguments=arguments,
                        error=f"timeout after {self.budget.timeout_seconds}s",
                    )
                )
                executor.shutdown(wait=False, cancel_futures=True)
                raise ToolExecutionTimeout(
                    f"tool {tool_name!r} timed out after {self.budget.timeout_seconds}s"
                ) from exc
            except Exception as exc:
                last_error = exc
                self.trace.append(
                    ToolCallTrace(
                        call_id=self._call_id(),
                        role=self.role,
                        tool_name=tool_name,
                        round_number=self.budget.used_rounds,
                        attempt=attempt,
                        started_at=started_at,
                        duration_ms=self._duration_ms(started),
                        status="error",
                        arguments=arguments,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                executor.shutdown(wait=False, cancel_futures=True)
                if attempt > self.budget.max_retries:
                    raise
                continue
            else:
                executor.shutdown(wait=True)
                self.trace.append(
                    ToolCallTrace(
                        call_id=self._call_id(),
                        role=self.role,
                        tool_name=tool_name,
                        round_number=self.budget.used_rounds,
                        attempt=attempt,
                        started_at=started_at,
                        duration_ms=self._duration_ms(started),
                        status="success",
                        arguments=arguments,
                        output_summary=self._summarize(output),
                    )
                )
                return output
        assert last_error is not None
        raise last_error

    def _append_budget_trace(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> None:
        self.trace.append(
            ToolCallTrace(
                call_id=self._call_id(),
                role=self.role,
                tool_name=tool_name,
                round_number=self.budget.used_rounds,
                attempt=0,
                started_at=datetime.now(timezone.utc).isoformat(),
                duration_ms=0,
                status="budget_exhausted",
                arguments=arguments,
                error="tool-call budget exhausted",
            )
        )

    @staticmethod
    def _summarize(output: BaseModel) -> dict[str, Any]:
        payload = output.model_dump()
        return {
            "output_type": type(output).__name__,
            "fields": sorted(payload),
            "item_counts": {
                key: len(value)
                for key, value in payload.items()
                if isinstance(value, list)
            },
        }

    @staticmethod
    def _duration_ms(started: float) -> int:
        return max(0, round((time.perf_counter() - started) * 1000))

    @staticmethod
    def _call_id() -> str:
        return f"tool_{uuid.uuid4().hex[:16]}"
