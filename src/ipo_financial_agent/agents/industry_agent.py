"""Industry and competition research with prospectus-grounded evidence."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.llm.prompts_agents import INDUSTRY_ANALYSIS_SYSTEM_PROMPT
from ipo_financial_agent.models_agent import Evidence, IndustryAnalysis
from ipo_financial_agent.tools.search_tool import search_industry_info

_MARKET_KEYWORDS = (
    "市场规模",
    "复合年增长率",
    "增长率",
    "市场份额",
    "排名第",
    "竞争格局",
    "市场参与者",
    "竞争对手",
)
_GROWTH_KEYWORDS = ("市场规模", "复合年增长率", "增长率", "CAGR")
_POSITION_KEYWORDS = ("市场份额", "排名第", "排名第一", "领先")
_COMPETITION_KEYWORDS = ("竞争格局", "竞争对手", "市场参与者", "价格竞争")


class IndustryAgent:
    """Separate issuer-disclosed market claims from independent web evidence."""

    def __init__(self, client: OpenAICompatibleClient | None = None) -> None:
        self.client = client

    def analyze(
        self,
        *,
        company: str,
        business_description: str = "",
        pages: list[Any] | None = None,
    ) -> IndustryAnalysis:
        prospectus_claims, prospectus_evidence = self._extract_prospectus_claims(
            pages or []
        )
        search_results = search_industry_info(company, business_description)
        web_evidence = self._web_evidence(search_results)

        if self.client is None:
            return self._offline_analysis(
                company=company,
                claims=prospectus_claims,
                prospectus_evidence=prospectus_evidence,
                web_evidence=web_evidence,
            )

        web_text = "\n\n".join(
            f"【{item.title}】{item.content}" for item in web_evidence
        )
        claim_text = "\n".join(f"- {claim}" for claim in prospectus_claims)
        prompt = (
            f"请分析{company}所处行业。必须区分发行人招股书披露与外部独立验证，"
            "不得把招股书引用的咨询机构数据表述为已经独立确认。\n\n"
            f"业务描述：{business_description or '未知'}\n\n"
            f"招股书行业声明：\n{claim_text or '未提取到'}\n\n"
            f"外部搜索证据：\n{web_text or '未取得'}\n\n"
            "按 Markdown 输出：行业概述、市场增长、竞争对手、行业趋势、行业风险。"
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
            evidence=[*prospectus_evidence, *web_evidence],
            raw_markdown=markdown,
        )

    @staticmethod
    def _sentences(text: str) -> list[str]:
        normalized = re.sub(r"\s+", "", text)
        return [
            sentence.strip("；;。")
            for sentence in re.split(r"[。；;]", normalized)
            if 20 <= len(sentence) <= 420
        ]

    @classmethod
    def _extract_prospectus_claims(
        cls, pages: list[Any]
    ) -> tuple[list[str], list[Evidence]]:
        """Retrieve issuer-disclosed market claims and retain page citations."""
        claims: list[str] = []
        evidence: list[Evidence] = []
        seen: set[str] = set()
        ranked_pages: list[tuple[int, int, Any]] = []
        for page in pages:
            page_number = int(getattr(page, "page", 0) or 0)
            if page_number <= 12:
                continue
            text = getattr(page, "text", "") or ""
            if not any(keyword in text for keyword in _MARKET_KEYWORDS):
                continue
            head = re.sub(r"\s+", "", text[:500])
            score = sum(text.count(keyword) for keyword in _MARKET_KEYWORDS)
            if "行业概览" in head:
                score += 30
            if "资料来源" in text and ("沙利文" in text or "咨询" in text):
                score += 10
            if "风险因素" in head:
                score -= 15
            if "释义" in head or "财务资料" in head:
                score -= 20
            ranked_pages.append((-score, page_number, page))

        category_counts = {"growth": 0, "position": 0, "competition": 0}
        category_limits = {"growth": 6, "position": 10, "competition": 5}
        for _, page_number, page in sorted(ranked_pages):
            text = getattr(page, "text", "") or ""
            for sentence in cls._sentences(text):
                categories: list[str] = []
                if "市场" in sentence and any(
                    keyword in sentence for keyword in _GROWTH_KEYWORDS
                ):
                    categories.append("growth")
                if any(keyword in sentence for keyword in _POSITION_KEYWORDS):
                    categories.append("position")
                if any(keyword in sentence for keyword in _COMPETITION_KEYWORDS):
                    categories.append("competition")
                available = [
                    category
                    for category in categories
                    if category_counts[category] < category_limits[category]
                ]
                if not available:
                    continue
                sentence = sentence[:360]
                key = re.sub(r"\d", "#", sentence[:120])
                if key in seen:
                    continue
                seen.add(key)
                for category in available:
                    category_counts[category] += 1
                claims.append(sentence)
                evidence.append(
                    Evidence(
                        source_type="prospectus",
                        page=page_number,
                        source=f"P{page_number}",
                        title="招股书行业声明",
                        content=sentence,
                        confidence=0.8,
                        metadata={
                            "topic": "industry_competition",
                            "claim_categories": available,
                            "source_scope": "issuer_disclosed",
                            "independently_verified": False,
                        },
                    )
                )
                if all(
                    category_counts[name] >= limit
                    for name, limit in category_limits.items()
                ):
                    return claims, evidence
        return claims, evidence

    @staticmethod
    def _web_evidence(results: list[dict[str, Any]]) -> list[Evidence]:
        topic_domains: dict[str, set[str]] = {}
        topic_has_authoritative: dict[str, bool] = {}
        for result in results:
            topic = result.get("topic", "industry")
            host = (urlparse(result.get("url", "")).hostname or "").lower()
            if host:
                topic_domains.setdefault(topic, set()).add(host)
            if result.get("source_tier") in {"official", "primary"}:
                topic_has_authoritative[topic] = True
        return [
            Evidence(
                source_type="web",
                title=result.get("title", ""),
                content=result.get("content", ""),
                source=result.get("url", ""),
                source_url=result.get("url") or None,
                published_at=result.get("published_at"),
                retrieved_at=result.get("retrieved_at"),
                confidence=float(result.get("confidence", 0.5)),
                metadata={
                    "topic": result.get("topic", "industry"),
                    "source_tier": result.get("source_tier", "unknown"),
                    "publisher": result.get("publisher", ""),
                    "query": result.get("query", ""),
                    "source_scope": "external",
                    # External does not automatically mean corroborated.  This is
                    # topic-level coverage only; the Reviewer still verifies claims.
                    "independently_verified": (
                        len(topic_domains.get(result.get("topic", "industry"), set())) >= 2
                        and topic_has_authoritative.get(
                            result.get("topic", "industry"), False
                        )
                    ),
                    "topic_source_count": len(
                        topic_domains.get(result.get("topic", "industry"), set())
                    ),
                    "search_provider": result.get("search_provider", result.get("provider", "")),
                    "search_cost_mode": result.get("search_cost_mode", ""),
                },
            )
            for result in results
            if result.get("url") and result.get("content")
        ]

    @classmethod
    def _offline_analysis(
        cls,
        *,
        company: str,
        claims: list[str],
        prospectus_evidence: list[Evidence],
        web_evidence: list[Evidence],
    ) -> IndustryAnalysis:
        growth = [c for c in claims if any(k in c for k in _GROWTH_KEYWORDS)]
        position = [c for c in claims if any(k in c for k in _POSITION_KEYWORDS)]
        position.sort(
            key=lambda claim: (
                not (
                    "排名" in claim
                    and ("我们" in claim or "公司" in claim)
                    and "市场份额" in claim
                ),
                len(claim),
            )
        )
        competition = [c for c in claims if any(k in c for k in _COMPETITION_KEYWORDS)]
        overview = (
            "招股书披露的市场定位：" + "；".join(position[:2])
            if position
            else "未从招股书提取到明确的市场定位声明。"
        )
        if not prospectus_evidence and not web_evidence:
            overview = "未配置或未成功访问外部搜索源，本次未生成行业事实。"
        market_growth = "；".join(growth[:3])
        trends = [f"招股书披露：{item}" for item in competition[:4]]
        risks: list[str] = []
        if prospectus_evidence and not web_evidence:
            risks.append("行业数据目前仅来自招股书，尚未取得外部独立来源验证。")
        if not growth:
            risks.append("尚未取得可追溯的市场规模或增速数据。")
        evidence = [*prospectus_evidence, *web_evidence]
        lines = [
            f"# {company} 行业与竞争分析",
            "",
            "> 招股书声明与外部证据分开记录；未外部验证的声明不视为独立事实。",
            "",
            "## 行业概述",
            overview,
            "",
            "## 市场增长",
            market_growth or "待核查",
            "",
            "## 行业风险",
            *[f"- {item}" for item in risks],
        ]
        return IndustryAnalysis(
            company=company,
            industry_overview=overview,
            market_growth=market_growth,
            industry_trends=trends,
            industry_risks=risks,
            evidence=evidence,
            raw_markdown="\n".join(lines),
        )

    @staticmethod
    def _extract_section(markdown: str, keyword: str) -> str:
        pattern = rf"##\s*.*{keyword}.*\n(.*?)(?=\n##\s|$)"
        match = re.search(pattern, markdown, re.DOTALL)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_list(markdown: str, keyword: str) -> list[str]:
        pattern = rf"##\s*.*{keyword}.*\n(.*?)(?=\n##\s|$)"
        match = re.search(pattern, markdown, re.DOTALL)
        if not match:
            return []
        return [
            item.strip()
            for item in re.findall(r"^\s*[-*]\s*(.+)", match.group(1), re.MULTILINE)
            if item.strip()
        ]
