"""Legal, compliance, governance, and adverse-matter prospectus review."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, ClassVar

from ipo_financial_agent.models_agent import Evidence, LegalGovernanceAnalysis


class LegalGovernanceAgent:
    """Surface review leads with page evidence; never issue a legal opinion."""

    CATEGORY_KEYWORDS: ClassVar[dict[str, tuple[str, ...]]] = {
        "special_shareholder_rights": (
            "对赌",
            "贖回",
            "赎回",
            "反攤薄",
            "反摊薄",
            "優先權",
            "优先权",
            "special rights",
            "redemption",
        ),
        "related_party_matters": (
            "關聯交易",
            "关联交易",
            "關連交易",
            "关连交易",
            "關聯方",
            "关联方",
            "related party",
            "connected transaction",
        ),
        "controller_and_ownership_risks": (
            "實際控制人",
            "实际控制人",
            "控股股東",
            "控股股东",
            "股權質押",
            "股权质押",
            "代持",
            "controlling shareholder",
        ),
        "litigation_and_penalties": (
            "訴訟",
            "诉讼",
            "仲裁",
            "處罰",
            "处罚",
            "監管問詢",
            "监管问询",
            "litigation",
            "penalty",
        ),
        "licensing_ip_data_risks": (
            "知識產權",
            "知识产权",
            "專利",
            "专利",
            "牌照",
            "許可證",
            "许可证",
            "數據安全",
            "数据安全",
            "intellectual property",
            "licence",
        ),
    }
    MAX_EVIDENCE_PER_CATEGORY = 2

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
                    (keyword for keyword in keywords if keyword.lower() in lowered),
                    None,
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

        evidence = [item for items in grouped.values() for item in items]
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
            evidence=evidence,
            open_questions=[
                "External litigation, penalty, registry, and adverse-media checks remain pending."
            ],
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
            f"Prospectus review lead on P{item.page_number}: {item.content}"
            for item in evidence
        ]
