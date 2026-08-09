from __future__ import annotations

import time

import pytest
from pydantic import BaseModel, Field

from ipo_financial_agent.runtime import (
    AgentRuntime,
    RuntimeBudget,
    RuntimeBudgetExceeded,
    ToolExecutionTimeout,
)
from ipo_financial_agent.tools.registry import DomainTool, DomainToolRegistry


class EchoInput(BaseModel):
    value: str = Field(min_length=1)


class EchoOutput(BaseModel):
    values: list[str]


def _registry(handler) -> DomainToolRegistry:
    return DomainToolRegistry(
        [
            DomainTool(
                name="echo",
                description="Test tool",
                handler=handler,
                allowed_roles=frozenset({"tester"}),
                input_model=EchoInput,
                output_model=EchoOutput,
            )
        ]
    )


def test_runtime_records_successful_structured_tool_call():
    runtime = AgentRuntime(
        registry=_registry(lambda value: {"values": [value]}),
        role="tester",
        budget=RuntimeBudget(max_tool_calls=1),
    )

    output = runtime.execute_tool("echo", value="ok")

    assert output.values == ["ok"]
    assert runtime.budget.used_rounds == 1
    assert runtime.budget.used_tool_calls == 1
    assert runtime.trace[0].status == "success"
    assert runtime.trace[0].output_summary["item_counts"] == {"values": 1}


def test_runtime_enforces_tool_call_and_round_budgets():
    runtime = AgentRuntime(
        registry=_registry(lambda value: {"values": [value]}),
        role="tester",
        budget=RuntimeBudget(max_rounds=1, max_tool_calls=1),
    )
    runtime.execute_tool("echo", value="first")

    with pytest.raises(RuntimeBudgetExceeded):
        runtime.execute_tool("echo", value="second")
    with pytest.raises(RuntimeBudgetExceeded):
        runtime.begin_round()

    assert runtime.trace[-1].status == "budget_exhausted"
    assert runtime.budget.used_tool_calls == 1


def test_runtime_retries_transient_error_within_one_logical_call():
    attempts = 0

    def flaky(value: str):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary")
        return {"values": [value]}

    runtime = AgentRuntime(
        registry=_registry(flaky),
        role="tester",
        budget=RuntimeBudget(max_tool_calls=1, max_retries=1),
    )

    assert runtime.execute_tool("echo", value="recovered").values == ["recovered"]
    assert [item.status for item in runtime.trace] == ["error", "success"]
    assert runtime.budget.used_tool_calls == 1


def test_runtime_stops_immediately_on_timeout():
    def slow(value: str):
        time.sleep(0.05)
        return {"values": [value]}

    runtime = AgentRuntime(
        registry=_registry(slow),
        role="tester",
        budget=RuntimeBudget(timeout_seconds=0.01, max_retries=1),
    )

    with pytest.raises(ToolExecutionTimeout):
        runtime.execute_tool("echo", value="late")

    assert [item.status for item in runtime.trace] == ["timeout"]
