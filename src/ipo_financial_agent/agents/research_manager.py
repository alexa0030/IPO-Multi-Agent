"""Research Manager Agent - 研究经理，规划研究任务并分配给专业 Agent。"""
from __future__ import annotations

import json
from typing import Any

from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.llm.prompts_agents import RESEARCH_MANAGER_SYSTEM_PROMPT
from ipo_financial_agent.models_agent import ResearchPlan, ResearchTask


class ResearchManagerAgent:
    """
    研究经理 Agent

    职责：
    - 接收文档概况（页数、章节数、公司名）
    - 规划研究任务，为每个专业 Agent 设定目标和优先级
    - 输出 ResearchPlan，驱动后续 Agent 并行执行

    这不是数据加载节点，而是真正的 Agent 决策节点。
    """

    def __init__(self, client: OpenAICompatibleClient | None = None) -> None:
        self.client = client

    def plan(
        self,
        *,
        company: str,
        document_summary: dict[str, Any],
    ) -> ResearchPlan:
        if self.client is None:
            return self._default_plan(company, document_summary)
        return self._plan_with_llm(company, document_summary)

    def _default_plan(
        self,
        company: str,
        document_summary: dict[str, Any],
    ) -> ResearchPlan:
        page_count = document_summary.get("page_count", 0)
        section_count = document_summary.get("section_count", 0)
        section_names = document_summary.get("section_names", [])

        tasks = [
            ResearchTask(
                agent="prospectus",
                objective=(
                    f"分析{company}的商业模式、核心产品、客户结构、"
                    f"供应商体系和竞争优势"
                ),
                priority="high",
            ),
            ResearchTask(
                agent="financial",
                objective=(
                    f"评估{company}的财务质量，重点关注盈利能力、"
                    f"现金流健康度、资产负债结构和收入质量"
                ),
                priority="high",
            ),
            ResearchTask(
                agent="industry",
                objective=(
                    f"研究{company}所处行业的市场规模、竞争格局、"
                    f"增长趋势和行业风险"
                ),
                priority="normal",
            ),
        ]

        focus_areas = ["商业模式", "财务质量", "行业竞争"]
        if section_names:
            risk_sections = [
                s for s in section_names if "risk" in s.lower() or "风险" in s
            ]
            if risk_sections:
                focus_areas.append("风险因素")
                tasks[0].priority = "high"

        notes = (
            f"文档概况：{page_count}页，检测到{section_count}个章节"
        )
        if section_names:
            notes += f"（{', '.join(section_names[:5])}）"
        notes += (
            f"。启动三个专业 Agent 并行研究，"
            f"重点关注：{', '.join(focus_areas)}。"
        )

        return ResearchPlan(
            company=company,
            tasks=tasks,
            manager_notes=notes,
            focus_areas=focus_areas,
        )

    def _plan_with_llm(
        self,
        company: str,
        document_summary: dict[str, Any],
    ) -> ResearchPlan:
        context = json.dumps(
            {
                "company": company,
                "page_count": document_summary.get("page_count", 0),
                "section_count": document_summary.get("section_count", 0),
                "section_names": document_summary.get("section_names", []),
            },
            ensure_ascii=False,
        )

        prompt = (
            f"请为{company}制定港股 IPO 研究计划。\n"
            "根据文档概况，决定需要哪些 Agent 参与分析，"
            "并为每个 Agent 设定研究目标和优先级。\n"
            "可用 Agent：prospectus（招股书分析）、"
            "financial（财务分析）、industry（行业研究）。\n\n"
            f"文档概况：\n{context}"
        )

        markdown = self.client.complete_text(
            system_prompt=RESEARCH_MANAGER_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=800,
        )

        return self._parse_llm_plan(company, markdown, document_summary)

    @staticmethod
    def _parse_llm_plan(
        company: str,
        markdown: str,
        document_summary: dict[str, Any],
    ) -> ResearchPlan:
        import re

        tasks: list[ResearchTask] = []
        agent_pattern = re.compile(
            r'"agent"\s*:\s*"(prospectus|financial|industry)"'
        )
        objective_pattern = re.compile(
            r'"objective"\s*:\s*"([^"]*)"'
        )
        priority_pattern = re.compile(
            r'"priority"\s*:\s*"(high|normal|low)"'
        )

        agents = agent_pattern.findall(markdown)
        objectives = objective_pattern.findall(markdown)
        priorities = priority_pattern.findall(markdown)

        for i, agent in enumerate(agents):
            objective = objectives[i] if i < len(objectives) else ""
            priority = priorities[i] if i < len(priorities) else "normal"
            tasks.append(
                ResearchTask(
                    agent=agent,
                    objective=objective,
                    priority=priority,
                )
            )

        if not tasks:
            return ResearchManagerAgent._default_plan(company, document_summary)

        return ResearchPlan(
            company=company,
            tasks=tasks,
            manager_notes=markdown[:500],
            focus_areas=[t.agent for t in tasks],
        )
