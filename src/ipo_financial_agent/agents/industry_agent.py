"""Industry and competition research with prospectus-grounded evidence."""

from __future__ import annotations

import json
import re
from typing import Any

from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.llm.prompts_agents import INDUSTRY_ANALYSIS_SYSTEM_PROMPT
from ipo_financial_agent.models_agent import Evidence, Finding, IndustryAnalysis
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

        all_evidence = [*prospectus_evidence, *web_evidence]
        evidence_catalog = "\n\n".join(
            (
                f"[{index}] scope={item.metadata.get('source_scope', 'issuer_disclosed')}; "
                f"topic={item.metadata.get('topic', 'industry_competition')}; "
                f"source={item.source_url or ('P' + str(item.page_number or '?'))}; "
                f"text={item.content[:700]}"
            )
            for index, item in enumerate(all_evidence, start=1)
        )
        prompt = f"""请为{company}完成港股 IPO 的行业与竞争尽调。
必须回答：行业边界与需求、产业链上下游、下游客户行业、市场规模与生命周期、
主要竞争者、竞争维度、进入壁垒、公司市场位置、未来增长驱动、海外或新行业拓展、
行业风险。重点解释公司为什么能生存、竞争者为什么暂时抢不走其份额；答案可能是技术、
质量、交付、服务、内容、认证、客户切换成本或时间积累，不得默认是价格。

规则：
1. 只能使用证据目录。外部搜索摘要只是待复核线索，不得写成已独立确认的事实。
2. 招股书披露必须标注为发行人披露；不得把发行人引用的咨询数据当独立验证。
3. 每条 finding 必须引用一个或多个真实证据编号；证据不足就写 open_questions。
4. 不得凭公司名称猜行业、竞争对手、市场规模或增长率。
5. 输出中文 JSON，不要 Markdown 或代码围栏。

JSON 格式：
{{
  "industry_overview":"...", "market_growth":"...",
  "competitors":["..."], "industry_trends":["..."], "industry_risks":["..."],
  "value_chain":["..."], "customer_industries":["..."],
  "competitive_dimensions":["..."], "barriers_to_entry":["..."],
  "growth_drivers":["..."], "expansion_paths":["..."],
  "findings":[{{"question":"...","conclusion":"...","evidence_refs":[1],
    "risks":["..."],"open_questions":["..."]}}]
}}

业务描述：{business_description or '未知'}

证据目录：
{evidence_catalog or '无可用证据'}
"""
        raw = self.client.complete_text(
            system_prompt=INDUSTRY_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=2800,
        )
        payload = self._parse_json_object(raw)
        if not payload:
            return self._offline_analysis(
                company=company,
                claims=prospectus_claims,
                prospectus_evidence=prospectus_evidence,
                web_evidence=web_evidence,
            )
        structured_findings = self._parse_structured_findings(
            payload.get("findings", []), all_evidence
        )
        return IndustryAnalysis(
            company=company,
            industry_overview=str(payload.get("industry_overview", "")).strip(),
            market_growth=str(payload.get("market_growth", "")).strip(),
            competitors=self._string_list(payload.get("competitors")),
            industry_trends=self._string_list(payload.get("industry_trends")),
            industry_risks=self._string_list(payload.get("industry_risks")),
            value_chain=self._string_list(payload.get("value_chain")),
            customer_industries=self._string_list(payload.get("customer_industries")),
            competitive_dimensions=self._string_list(payload.get("competitive_dimensions")),
            barriers_to_entry=self._string_list(payload.get("barriers_to_entry")),
            growth_drivers=self._string_list(payload.get("growth_drivers")),
            expansion_paths=self._string_list(payload.get("expansion_paths")),
            structured_findings=structured_findings,
            evidence=all_evidence,
            raw_markdown=raw,
        )

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        try:
            payload = json.loads(text)
        except (TypeError, ValueError):
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                return {}
            try:
                payload = json.loads(text[start : end + 1])
            except (TypeError, ValueError):
                return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()][:20]

    @classmethod
    def _parse_structured_findings(
        cls,
        items: Any,
        evidence: list[Evidence],
    ) -> list[Finding]:
        if not isinstance(items, list):
            return []
        output: list[Finding] = []
        for item in items[:20]:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question", "")).strip()
            conclusion = str(item.get("conclusion", "")).strip()
            references: list[int] = []
            for value in item.get("evidence_refs", []):
                match = re.search(r"\d+", str(value))
                if match:
                    references.append(int(match.group(0)))
            selected = [
                evidence[index - 1]
                for index in dict.fromkeys(references)
                if 1 <= index <= len(evidence)
            ]
            if not question or not conclusion or not selected:
                continue
            external_tiers = {
                str(entry.metadata.get("source_tier", "unknown"))
                for entry in selected
                if entry.metadata.get("source_scope") == "external"
            }
            strength = (
                "medium"
                if external_tiers.intersection({"official", "primary"})
                else "weak"
            )
            output.append(
                Finding(
                    agent_name="industry_competition",
                    question=question,
                    conclusion=conclusion,
                    evidence_ids=[entry.evidence_id for entry in selected],
                    evidence_strength=strength,
                    risks=cls._string_list(item.get("risks")),
                    open_questions=cls._string_list(item.get("open_questions")),
                )
            )
        return output

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
                    "independently_verified": False,
                    "verification_status": "search_lead_requires_source_review",
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
