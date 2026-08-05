"""Industry Agent —— 行业研究。

模拟行业研究员，回答"这个行业有没有未来？"
基于公司名称、业务描述和外部搜索结果进行行业分析。
"""
from __future__ import annotations

from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.llm.prompts_agents import INDUSTRY_ANALYSIS_SYSTEM_PROMPT
from ipo_financial_agent.models_agent import Evidence, IndustryAnalysis
from ipo_financial_agent.tools.search_tool import search_industry_info


class IndustryAgent:
    """行业研究 Agent。"""

    def __init__(self, client: OpenAICompatibleClient | None = None) -> None:
        self.client = client

    def analyze(
        self,
        *,
        company: str,
        business_description: str = "",
    ) -> IndustryAnalysis:
        # 1. 搜索行业信息
        search_results = search_industry_info(company, business_description)
        if not search_results:
            return self._unavailable_analysis(company)
        search_text = "\n\n".join(
            f"【{r.get('title', '')}】\n{r.get('content', '')}"
            for r in search_results
        )
        evidence = [
            Evidence(
                source_type="web",
                title=result.get("title", ""),
                content=result.get("content", ""),
                source=result.get("url", ""),
                source_url=result.get("url") or None,
                confidence=0.6,
            )
            for result in search_results
            if result.get("url") and result.get("content")
        ]

        # 2. 无 LLM 时返回搜索结果摘要
        if self.client is None:
            return self._offline_analysis(company, search_text, evidence)

        # 3. LLM 分析
        prompt = (
            f"请基于以下搜索结果，分析{company}所处行业的情况。\n\n"
            f"公司：{company}\n"
            f"业务描述：{business_description or '（未知）'}\n\n"
            f"搜索结果：\n{search_text}\n\n"
            f"请输出以下内容（Markdown 格式）：\n"
            f"## 行业概述\n（行业定义、产业链位置）\n\n"
            f"## 市场增长\n（市场规模和增速，无数据则说明）\n\n"
            f"## 竞争对手\n- 竞争对手1\n\n"
            f"## 行业趋势\n- 趋势1\n\n"
            f"## 行业风险\n- 风险1"
        )

        markdown = self.client.complete_text(
            system_prompt=INDUSTRY_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=1800,
        )

        return IndustryAnalysis(
            company=company,
            industry_overview=self._extract_section(markdown, "行业概述"),
            market_growth=self._extract_section(markdown, "市场增长"),
            competitors=self._extract_list(markdown, "竞争对手"),
            industry_trends=self._extract_list(markdown, "行业趋势"),
            industry_risks=self._extract_list(markdown, "行业风险"),
            evidence=evidence,
            raw_markdown=markdown,
        )

    @staticmethod
    def _extract_section(markdown: str, keyword: str) -> str:
        import re
        pattern = rf"##\s*.*{keyword}.*\n(.*?)(?=\n##\s|$)"
        match = re.search(pattern, markdown, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def _extract_list(markdown: str, keyword: str) -> list[str]:
        import re
        pattern = rf"##\s*.*{keyword}.*\n(.*?)(?=\n##\s|$)"
        match = re.search(pattern, markdown, re.DOTALL)
        if not match:
            return []
        section = match.group(1)
        items = re.findall(r"^\s*[-*]\s*(.+)", section, re.MULTILINE)
        return [item.strip() for item in items if item.strip()]

    @staticmethod
    def _offline_analysis(
        company: str,
        search_text: str,
        evidence: list[Evidence],
    ) -> IndustryAnalysis:
        return IndustryAnalysis(
            company=company,
            industry_overview=f"（离线模式）{search_text[:300]}...",
            evidence=evidence,
            raw_markdown=(
                f"# {company} 行业分析（离线模式）\n\n"
                f"> 未调用大模型，以下为搜索结果摘要。\n\n"
                f"{search_text}\n"
            ),
        )

    @staticmethod
    def _unavailable_analysis(company: str) -> IndustryAnalysis:
        message = "未配置或未成功访问外部搜索源，本次未生成行业事实。"
        return IndustryAnalysis(
            company=company,
            industry_overview=message,
            raw_markdown=f"# {company} 行业分析\n\n> {message}\n",
        )
