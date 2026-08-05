"""Prospectus Analyst Agent — Tool-Augmented.

Tools:
1. Section Retriever — uses section_detector results to find relevant pages
2. Entity Extractor — regex-based extraction of customers, suppliers, products, management
3. Risk Factor Extractor — structured extraction from risk factors section
4. Claim Extractor — identifies key claims for cross-validation by Investment Committee

Every finding carries Evidence (page number) so downstream agents can trace
claims back to the prospectus source.
"""
from __future__ import annotations

import re
from typing import Any

from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.llm.prompts_agents import PROSPECTUS_ANALYSIS_SYSTEM_PROMPT
from ipo_financial_agent.models_agent import Evidence, ProspectusAnalysis, ProspectusEntity


# ==================== Page Selection ====================

_BUSINESS_KEYWORDS = [
    "业务", "商业模式", "经营", "产品", "服务",
    "客户", "供应商", "董事", "高管", "管理层",
    "竞争优势", "风险因素", "历史", "发展",
    "BUSINESS", "OVERVIEW", "RISK", "PRODUCTS",
    "CUSTOMERS", "SUPPLIERS", "MANAGEMENT",
]

_MAX_CONTEXT_CHARS = 12000


# ==================== Entity Extraction Patterns ====================

# Customer patterns: "前五大客户" / "主要客户" / "客户一" etc.
_CUSTOMER_PATTERN = re.compile(
    r"(?:前五大|主要|核心|前\d+大)?客户[一二三四五六七八九十\d]?\s*[:：]?\s*(.+?)(?:\n|$)",
    re.MULTILINE,
)

# Supplier patterns
_SUPPLIER_PATTERN = re.compile(
    r"(?:前五大|主要|核心|前\d+大)?供应商[一二三四五六七八九十\d]?\s*[:：]?\s*(.+?)(?:\n|$)",
    re.MULTILINE,
)

# Product patterns: "主要产品" / "产品包括" etc.
_PRODUCT_PATTERN = re.compile(
    r"(?:主要|核心)?产品[/／]?服务?\s*(?:包括|包含|有|为|：|:)\s*(.+?)(?:\n|$)",
    re.MULTILINE,
)

# Management patterns: "董事长" / "总经理" / "CEO" etc.
_MGMT_PATTERN = re.compile(
    r"(董事长|执行董事|非执行董事|独立董事|总经理|首席执行官|CEO|CFO|财务总监|副总经理|监事会主席|监事)\s*[:：]?\s*([\u4e00-\u9fff·]{2,8})",
    re.MULTILINE,
)

# Revenue ratio: "占比35%" / "收入占比35.2%" etc.
_RATIO_PATTERN = re.compile(r"占比[约]?(\d+\.?\d*)\s*%")

# Claim keywords for cross-validation
_CLAIM_PATTERNS = {
    "growth": re.compile(r"(?:收入|营收|利润|业绩|规模)(?:连续|持续)?(?:高速|快速|大幅)?增长(?:\d+\.?\d*\s*%|倍)?", re.MULTILINE),
    "leadership": re.compile(r"(?:行业|市场|细分)?(?:领先|龙头|第一|最大|首位|排名(?:第一|前列)|市占率(?:第一|最高))", re.MULTILINE),
    "pricing_power": re.compile(r"(?:议价能力|定价权|品牌优势|技术壁垒|核心竞争力|竞争优势)", re.MULTILINE),
    "cash_strong": re.compile(r"(?:资金充裕|现金流充足|现金充裕|财务稳健|流动性良好)", re.MULTILINE),
    "customer_diverse": re.compile(r"(?:客户多元|客户分散|客户结构优化|不存在重大依赖)", re.MULTILINE),
}


class ProspectusAgent:
    """Prospectus Analyst Agent — Tool-Augmented with evidence tracking."""

    def __init__(self, client: OpenAICompatibleClient | None = None) -> None:
        self.client = client

    def analyze(
        self,
        *,
        company: str,
        pages: list[Any],
        section_hits: list[Any] | None = None,
    ) -> ProspectusAnalysis:
        # Tool 1: Section Retriever — select relevant pages
        relevant_pages = self._select_relevant_pages(pages, section_hits)
        combined_text = "\n".join(p["text"] for p in relevant_pages)

        if not combined_text.strip():
            return ProspectusAnalysis(
                company=company,
                raw_markdown="> Prospectus text is empty, unable to analyze.",
            )

        if self.client is None:
            return self._offline_analysis(company, relevant_pages, combined_text)

        # LLM mode: send context, parse, attach evidence
        return self._llm_analysis(company, relevant_pages, combined_text)

    # ==================== Tool 1: Section Retriever ====================

    def _select_relevant_pages(
        self,
        pages: list[Any],
        section_hits: list[Any] | None,
    ) -> list[dict[str, Any]]:
        """Select pages relevant to business analysis using section hits + keywords.

        Returns list of {"page": int, "text": str, "title": str}.
        """
        # Build page lookup
        page_map: dict[int, str] = {}
        for p in pages:
            page_num = getattr(p, "page", 0)
            text = (getattr(p, "text", "") or "").strip()
            if text:
                page_map[page_num] = text

        # Find relevant section hits
        relevant_sections: list[tuple[int, str]] = []
        if section_hits:
            for hit in section_hits:
                title = getattr(hit, "title", "") or ""
                title_upper = title.upper()
                page_num = getattr(hit, "page", 0)
                if any(kw in title or kw in title_upper for kw in _BUSINESS_KEYWORDS):
                    relevant_sections.append((page_num, title))

        # Collect text with page tracking
        selected: list[dict[str, Any]] = []
        total_chars = 0
        seen_pages: set[int] = set()

        # Priority 1: section hit pages
        for page_num, title in relevant_sections:
            if page_num in page_map and page_num not in seen_pages and total_chars < _MAX_CONTEXT_CHARS:
                text = page_map[page_num]
                selected.append({"page": page_num, "text": text, "title": title})
                seen_pages.add(page_num)
                total_chars += len(text)

        # Priority 2: keyword-matched pages
        if total_chars < _MAX_CONTEXT_CHARS // 2:
            for page_num, text in sorted(page_map.items()):
                if page_num in seen_pages:
                    continue
                if total_chars >= _MAX_CONTEXT_CHARS:
                    break
                if any(kw in text for kw in _BUSINESS_KEYWORDS[:10]):
                    chunk = text[:1500]
                    selected.append({"page": page_num, "text": chunk, "title": "keyword_match"})
                    seen_pages.add(page_num)
                    total_chars += len(chunk)

        # Priority 3: first 30 pages (usually business overview)
        if total_chars < _MAX_CONTEXT_CHARS // 3:
            for page_num in sorted(page_map.keys())[:30]:
                if page_num in seen_pages:
                    continue
                if total_chars >= _MAX_CONTEXT_CHARS:
                    break
                chunk = page_map[page_num][:800]
                selected.append({"page": page_num, "text": chunk, "title": "early_pages"})
                seen_pages.add(page_num)
                total_chars += len(chunk)

        return selected

    # ==================== Tool 2: Entity Extractor ====================

    @staticmethod
    def _extract_entities(
        text: str,
        pattern: re.Pattern,
        page_num: int,
        section_name: str,
    ) -> list[ProspectusEntity]:
        """Extract entities matching a pattern, with evidence."""
        entities: list[ProspectusEntity] = []
        for match in pattern.finditer(text):
            name = match.group(1).strip() if match.groups() else match.group(0).strip()
            # Clean up name — remove trailing punctuation, limit length
            name = re.sub(r"[,，。；;。]$", "", name).strip()[:100]
            if not name or len(name) < 2:
                continue

            # Try to find revenue ratio near the match
            ratio_match = _RATIO_PATTERN.search(text[match.end():match.end() + 200])
            detail = ""
            if ratio_match:
                detail = f"revenue_ratio: {ratio_match.group(1)}%"

            entities.append(ProspectusEntity(
                name=name,
                detail=detail,
                evidence=[Evidence(
                    source_type="prospectus",
                    page=page_num,
                    source=f"P{page_num}",
                    detail=f"{section_name}: {name[:60]}",
                )],
            ))
        return entities[:20]  # Cap at 20

    @staticmethod
    def _extract_management(
        text: str,
        page_num: int,
    ) -> list[ProspectusEntity]:
        """Extract management team members with roles."""
        entities: list[ProspectusEntity] = []
        seen_names: set[str] = set()

        for match in _MGMT_PATTERN.finditer(text):
            role = match.group(1).strip()
            name = match.group(2).strip()
            if name in seen_names:
                continue
            seen_names.add(name)

            entities.append(ProspectusEntity(
                name=name,
                detail=f"role: {role}",
                evidence=[Evidence(
                    source_type="prospectus",
                    page=page_num,
                    source=f"P{page_num}",
                    detail=f"{role}: {name}",
                )],
            ))
        return entities[:15]

    # ==================== Tool 3: Risk Factor Extractor ====================

    @staticmethod
    def _extract_risk_factors(
        pages: list[dict[str, Any]],
    ) -> list[str]:
        """Extract risk factors from the risk factors section."""
        risks: list[str] = []
        in_risk_section = False

        for page_info in pages:
            title = page_info.get("title", "")
            text = page_info["text"]
            page_num = page_info["page"]

            # Detect risk section start
            if "风险因素" in title or "RISK FACTORS" in title.upper():
                in_risk_section = True

            if not in_risk_section:
                continue

            # Extract bullet points or numbered items
            # Pattern: "1." / "（1）" / "一、" / "- " at start of line
            for line in text.split("\n"):
                line = line.strip()
                if re.match(r"^(?:\d+[.、]|（\d+）|[一二三四五六七八九十]+[、)]|-\s)", line):
                    risk_text = re.sub(r"^(?:\d+[.、]|（\d+）|[一二三四五六七八九十]+[、)]|-\s)", "", line).strip()
                    if len(risk_text) > 10 and risk_text not in risks:
                        risks.append(risk_text[:200])

            # Stop after risk section (next major section)
            if in_risk_section and re.search(r"^#\s*(?:业务|财务|管理层|董事)", text, re.MULTILINE):
                break

        return risks[:15]

    # ==================== Tool 4: Claim Extractor ====================

    @staticmethod
    def _extract_key_claims(text: str) -> list[str]:
        """Extract key claims for cross-validation by Investment Committee."""
        claims: list[str] = []
        for claim_type, pattern in _CLAIM_PATTERNS.items():
            for match in pattern.finditer(text):
                claim = match.group(0).strip()
                if len(claim) > 5 and claim not in claims:
                    claims.append(claim[:150])
        return claims[:10]

    # ==================== Offline Analysis ====================

    def _offline_analysis(
        self,
        company: str,
        pages: list[dict[str, Any]],
        combined_text: str,
    ) -> ProspectusAnalysis:
        """Offline mode: extract real information using regex tools."""
        customers: list[ProspectusEntity] = []
        suppliers: list[ProspectusEntity] = []
        products: list[ProspectusEntity] = []
        management: list[ProspectusEntity] = []
        advantages: list[str] = []
        all_claims: list[str] = []

        for page_info in pages:
            text = page_info["text"]
            page_num = page_info["page"]

            # Extract entities with evidence
            customers.extend(self._extract_entities(text, _CUSTOMER_PATTERN, page_num, "customer"))
            suppliers.extend(self._extract_entities(text, _SUPPLIER_PATTERN, page_num, "supplier"))
            products.extend(self._extract_entities(text, _PRODUCT_PATTERN, page_num, "product"))
            management.extend(self._extract_management(text, page_num))

            # Extract claims
            all_claims.extend(self._extract_key_claims(text))

            # Extract competitive advantages (look for bullet points near "竞争优势")
            if "竞争优势" in text or "核心优势" in text:
                adv_section = re.search(
                    r"(?:竞争优势|核心优势)[\s\S]{0,500}",
                    text,
                )
                if adv_section:
                    for line in adv_section.group(0).split("\n"):
                        line = line.strip()
                        if re.match(r"^[-*]\s", line):
                            adv = line.lstrip("-* ").strip()
                            if len(adv) > 5:
                                advantages.append(adv[:150])

        # Extract risk factors
        risks = self._extract_risk_factors(pages)

        # Build business model summary from first few pages
        business_text = combined_text[:800].replace("\n", " ").strip()

        # Build evidence for business model
        bm_evidence = [
            Evidence(
                source_type="prospectus",
                page=pages[0]["page"] if pages else 0,
                source=f"P{pages[0]['page']}" if pages else "",
                detail="business_overview",
            )
        ] if pages else []

        # Deduplicate
        all_claims = list(dict.fromkeys(all_claims))[:10]
        advantages = list(dict.fromkeys(advantages))[:10]

        markdown = self._build_offline_markdown(
            company, business_text, products, customers,
            suppliers, management, advantages, risks, all_claims, pages,
        )

        return ProspectusAnalysis(
            company=company,
            business_model=f"（离线模式-工具提取）{business_text[:400]}...",
            business_model_evidence=bm_evidence,
            main_products=products[:10],
            customers=customers[:10],
            suppliers=suppliers[:10],
            management_team=management[:10],
            competitive_advantages=advantages,
            prospectus_risks=risks,
            key_claims=all_claims,
            raw_markdown=markdown,
        )

    @staticmethod
    def _build_offline_markdown(
        company: str,
        business_text: str,
        products: list[ProspectusEntity],
        customers: list[ProspectusEntity],
        suppliers: list[ProspectusEntity],
        management: list[ProspectusEntity],
        advantages: list[str],
        risks: list[str],
        claims: list[str],
        pages: list[dict[str, Any]],
    ) -> str:
        sections: list[str] = [
            f"# {company} Prospectus Analysis (Offline Tool-Augmented Mode)",
            "",
            f"> Extracted using regex-based entity extraction tools.",
            f"> Pages analyzed: {len(pages)} (P{pages[0]['page']}" if pages else "",
            f"-P{pages[-1]['page']})" if pages else "",
            "",
        ]

        sections.append("## Business Model")
        sections.append(f"\n{business_text[:500]}...")
        sections.append("")

        sections.append("## Main Products/Services")
        if products:
            for p in products[:10]:
                ev = p.evidence[0] if p.evidence else None
                ref = f" [{ev.source}]" if ev else ""
                detail = f" ({p.detail})" if p.detail else ""
                sections.append(f"- {p.name}{detail}{ref}")
        else:
            sections.append("- (Not extracted)")
        sections.append("")

        sections.append("## Key Customers")
        if customers:
            for c in customers[:10]:
                ev = c.evidence[0] if c.evidence else None
                ref = f" [{ev.source}]" if ev else ""
                detail = f" ({c.detail})" if c.detail else ""
                sections.append(f"- {c.name}{detail}{ref}")
        else:
            sections.append("- (Not extracted)")
        sections.append("")

        sections.append("## Key Suppliers")
        if suppliers:
            for s in suppliers[:10]:
                ev = s.evidence[0] if s.evidence else None
                ref = f" [{ev.source}]" if ev else ""
                sections.append(f"- {s.name}{ref}")
        else:
            sections.append("- (Not extracted)")
        sections.append("")

        sections.append("## Management Team")
        if management:
            for m in management[:10]:
                ev = m.evidence[0] if m.evidence else None
                ref = f" [{ev.source}]" if ev else ""
                sections.append(f"- {m.detail}: {m.name}{ref}")
        else:
            sections.append("- (Not extracted)")
        sections.append("")

        sections.append("## Competitive Advantages")
        if advantages:
            for a in advantages:
                sections.append(f"- {a}")
        else:
            sections.append("- (Not extracted)")
        sections.append("")

        sections.append("## Prospectus Risk Factors")
        if risks:
            for r in risks[:10]:
                sections.append(f"- {r}")
        else:
            sections.append("- (Not extracted)")
        sections.append("")

        sections.append("## Key Claims (for Cross-Validation)")
        if claims:
            for c in claims:
                sections.append(f"- {c}")
        else:
            sections.append("- (No specific claims detected)")
        sections.append("")

        return "\n".join(sections)

    # ==================== LLM Analysis ====================

    def _llm_analysis(
        self,
        company: str,
        pages: list[dict[str, Any]],
        combined_text: str,
    ) -> ProspectusAnalysis:
        """LLM mode: send context, parse response, attach evidence."""
        # First run offline extraction for evidence
        offline = self._offline_analysis(company, pages, combined_text)

        # Build LLM prompt with page references
        context_text = ""
        for p in pages:
            context_text += f"--- P{p['page']} ---\n{p['text'][:2000]}\n\n"

        prompt = (
            f"Please analyze the prospectus for {company}.\n\n"
            f"Prospectus text (with page markers):\n{context_text[:10000]}\n\n"
            f"Output (Markdown with page references like [P123]):\n"
            f"## Business Model\n## Main Products/Services\n## Key Customers\n"
            f"## Key Suppliers\n## Management Team\n## Competitive Advantages\n"
            f"## Risk Factors\n## Key Claims"
        )

        markdown = self.client.complete_text(
            system_prompt=PROSPECTUS_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=2000,
        )

        # Merge: use LLM text but keep offline evidence
        return ProspectusAnalysis(
            company=company,
            business_model=self._extract_section(markdown, "Business Model|商业模式"),
            business_model_evidence=offline.business_model_evidence,
            main_products=offline.main_products,
            customers=offline.customers,
            suppliers=offline.suppliers,
            management_team=offline.management_team,
            competitive_advantages=self._extract_list(markdown, "Competitive|竞争优势"),
            prospectus_risks=self._extract_list(markdown, "Risk Factor|风险因素"),
            key_claims=offline.key_claims,
            raw_markdown=markdown,
        )

    # ==================== Parsing Helpers ====================

    @staticmethod
    def _extract_section(markdown: str, keyword: str) -> str:
        pattern = rf"##\s*.*(?:{keyword}).*\n(.*?)(?=\n##\s|$)"
        match = re.search(pattern, markdown, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def _extract_list(markdown: str, keyword: str) -> list[str]:
        pattern = rf"##\s*.*(?:{keyword}).*\n(.*?)(?=\n##\s|$)"
        match = re.search(pattern, markdown, re.DOTALL)
        if not match:
            return []
        section = match.group(1)
        items = re.findall(r"^\s*[-*]\s*(.+)", section, re.MULTILINE)
        return [item.strip() for item in items if item.strip()]
