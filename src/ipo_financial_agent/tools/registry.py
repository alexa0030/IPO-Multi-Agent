"""Domain tool registry with least-privilege views for research agents.

The registry is deliberately separate from the deterministic pipeline. A tool
is exposed only when an agent needs runtime discretion over whether and how to
invoke it; mandatory parsing, calculation and report assembly remain services.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from pydantic import BaseModel


@dataclass(frozen=True)
class DomainTool:
    name: str
    description: str
    handler: Callable[..., Any]
    allowed_roles: frozenset[str]
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    mutates_evidence: bool = False

    def invoke(self, **arguments: Any) -> BaseModel:
        validated_input = self.input_model.model_validate(arguments)
        raw_output = self.handler(**validated_input.model_dump())
        return self.output_model.model_validate(raw_output)


class DomainToolRegistry:
    """Single registration point plus role-scoped tool views."""

    def __init__(self, tools: Iterable[DomainTool] = ()) -> None:
        self._tools: dict[str, DomainTool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: DomainTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate domain tool: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> DomainTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown domain tool: {name}") from exc

    def for_role(self, role: str) -> dict[str, DomainTool]:
        return {
            name: tool
            for name, tool in self._tools.items()
            if role in tool.allowed_roles
        }

    def describe(self, role: str | None = None) -> list[dict[str, Any]]:
        tools = self.for_role(role) if role else self._tools
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_model.model_json_schema(),
                "output_schema": tool.output_model.model_json_schema(),
                "mutates_evidence": tool.mutates_evidence,
            }
            for tool in tools.values()
        ]

    def execute(self, role: str, name: str, **arguments: Any) -> BaseModel:
        tool = self.get(name)
        if role not in tool.allowed_roles:
            raise PermissionError(f"role {role!r} cannot invoke tool {name!r}")
        return tool.invoke(**arguments)
