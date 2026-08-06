"""Legal, compliance, governance, and adverse-matter prospectus review."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, ClassVar

from ipo_financial_agent.models_agent import Evidence, LegalGovernanceAnalysis
from ipo_financial_agent.tools.search_tool import search_legal_governance_info


class LegalGovernanceAgent:
    """Surface review leads with page evidence; never issue a legal opinion."""

    CATEGORY_KEYWORDS: ClassVar[dict[str, tuple[str, ...]]] = {
        "special_shareholder_rights": (
            "对赌", "贖回", "赎回", "反攤薄", "反摊薄", "優先權", "优先权",
            "special rights", "redemption",
        ),
        "related_party_matters": (
            "關聯交易", "关联交易", "關連交易", "关连交易", "關聯方", "关联方",
            "related party", "connected transaction",
        ),
        "controller_and_ownership_risks": (
            "實際控制人", "实际控制人", "控股股東", "控股股东", "股權質押",
            "股权质押", "代持", "controlling shareholder",
        ),
        "litigation_and_penalties": (
            "訴訟", "诉讼", "仲裁", "處罰", "处罚", "監管問詢", "监管问询",
            "litigation", "penalty",
        ),
        "licensing_ip_data_risks": (
            "知識產權", "知识产权", "專利", "专利", "牌照", "許可證", "许可证",
            "數據安全", "数据安全", "intellectual property", "licence",
        ),
    }
    MAX_EVIDENCE_PER_CATEGORY = 2
    WEB_TOPIC_CATEGORIES: ClassVar[dict[str, str]] = {
        "hkex_filings": "listing_filings",
        "regulatory": "litigation_and_penalties",
        "corporate_registry": "controller_and_ownership_risks",
        "litigation": "litigation_and_penalties",
        "controller_related_parties": "controller_and_ownership_risks",
        "accounting_auditor": "financial_reporting_integrity",
        "financing_debt": "financing_debt_guarantees",
        "adverse_media": "adverse_information",
    }

    def analyze(self, *, company: str, pages: list[Any]) -> LegalGovernanceAnalysis:
        grouped: dict[str, list[Evidence]] = defaultdict(list)
        for page in pages:
            text = str(getattr(page, "text", "") or "")
            page_number = int(getattr(page, "page", 0) or 0)
            if (
                len(text.strip()) < 120
                or page_number < 1
                or self._is_reference_page(text)
            ):
                continue
            lowered = text.lower()
            for category, keywords in self.CATEGORY_KEYWORDS.items():
                if len(grouped[category]) >= self.MAX_EVIDENCE_PER_CATEGORY:
                    continue
                matched = next(
                    (keyword for keyword in keywords if keyword.lower() in lowered), None
                )
                if not matched:
                    continue
                if category == "special_shareholder_rights" and not any(
                    token in text
                    for token in (
                        "股东",
                        "股東",
                        "投资者",
                        "投資者",
                        "股份",
                        "shareholder",
                        "investor",
                    )
                ):
                    continue
                grouped[category].append(
                    Evidence(
                        source_type="prospectus",
                        title=f"{category} - P{page_number}",
                        content=self._excerpt(text, matched),
                        source_file=str(getattr(page, "source_file", "") or ""),
                        page_number=page_number,
                        confidence=0.75,
                        metadata={
                            "topic": "legal_governance",
                            "category": category,
                            "matched_keyword": matched,
                            "review_status": "lead_not_legal_opinion",
                        },
                    )
                )

        prospectus_evidence = [item for items in grouped.values() for item in items]
        web_results = search_legal_governance_info(company)
        web_evidence: list[Evidence] = []
        for result in web_results:
            url = str(result.get("url", "")).strip()
            content = str(result.get("content", "")).strip()
            if not url or not content:
                continue
            topic = str(result.get("topic", "adverse_media"))
            category = self.WEB_TOPIC_CATEGORIES.get(topic, "adverse_information")
            web_evidence.append(
                Evidence(
                    source_type="web",
                    title=str(result.get("title", "公开信息核查线索")),
                    content=content[:900],
                    source=url,
                    source_url=url,
                    published_at=result.get("published_at"),
                    retrieved_at=result.get("retrieved_at"),
                    confidence=float(result.get("confidence", 0.5)),
                    metadata={
                        "topic": topic,
                        "category": category,
                        "source_scope": "external",
                        "source_tier": result.get("source_tier", "unknown"),
                        "publisher": result.get("publisher", ""),
                        "query": result.get("query", ""),
                        "review_status": "search_lead_requires_source_review",
                    },
                )
            )
        evidence = [*prospectus_evidence, *web_evidence]
        web_by_category: dict[str, list[Evidence]] = defaultdict(list)
        for item in web_evidence:
            web_by_category[str(item.metadata.get("category", "adverse_information"))].append(item)
        searched_topics = {str(item.metadata.get("topic", "")) for item in web_evidence}
        expected_topics = set(self.WEB_TOPIC_CATEGORIES)
        open_questions = [
            "逐条打开公开信息原始 URL，核对主体、日期、全文语境和当前状态；搜索摘要不能替代原文。"
        ]
        if not web_evidence:
            open_questions.append("外部诉讼、处罚、工商登记、审计及负面舆情检索尚未取得可追溯结果。")
        else:
            missing = sorted(expected_topics - searched_topics)
            if missing:
                open_questions.append(
                    "公开信息检索尚未覆盖或未命中：" + "、".join(missing)
                )
        return LegalGovernanceAnalysis(
            company=company,
            special_shareholder_rights=self._lead_lines(
                grouped["special_shareholder_rights"]
            ),
            related_party_matters=self._lead_lines(grouped["related_party_matters"]),
            controller_and_ownership_risks=self._lead_lines(
                grouped["controller_and_ownership_risks"]
            ),
            litigation_and_penalties=self._lead_lines(
                grouped["litigation_and_penalties"]
            ),
            licensing_ip_data_risks=self._lead_lines(
                grouped["licensing_ip_data_risks"]
            ),
            financial_reporting_integrity=self._web_lead_lines(
                web_by_category["financial_reporting_integrity"]
            ),
            financing_debt_guarantees=self._web_lead_lines(
                web_by_category["financing_debt_guarantees"]
            ),
            listing_filings=self._web_lead_lines(
                web_by_category["listing_filings"]
            ),
            adverse_information=self._web_lead_lines(
                web_by_category["adverse_information"]
            ),
            evidence=evidence,
            open_questions=open_questions,
        )

    @staticmethod
    def _excerpt(text: str, keyword: str, radius: int = 180) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        index = normalized.lower().find(keyword.lower())
        if index < 0:
            return normalized[: radius * 2]
        start = max(0, index - radius)
        end = min(len(normalized), index + len(keyword) + radius)
        return normalized[start:end]

    @staticmethod
    def _is_reference_page(text: str) -> bool:
        """Exclude table-of-contents and glossary-style keyword mentions."""
        compact = re.sub(r"\s+", "", text)
        if compact.count("...") >= 3 or compact.count("……") >= 3:
            return True
        return compact.count("指具有") >= 3 or compact.count("指根據") >= 3

    @staticmethod
    def _lead_lines(evidence: list[Evidence]) -> list[str]:
        return [
            f"招股书 P{item.page_number} 核查线索：{item.content}"
            for item in evidence
        ]

    @staticmethod
    def _web_lead_lines(evidence: list[Evidence]) -> list[str]:
        return [
            f"公开信息核查线索：{item.title}（{item.source_url}）"
            for item in evidence
        ]
