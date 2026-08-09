"""Query planning, source grading and deduplication for IPO research."""

from __future__ import annotations

from urllib.parse import urlparse

from ipo_financial_agent.tools.search.models import SearchQuery, SearchResult, SearchRun
from ipo_financial_agent.tools.search.provider import SearchProvider

OFFICIAL_DOMAINS = {
    "hkexnews.hk",
    "hkex.com.hk",
    "sfc.hk",
    "cr.gov.hk",
    "judiciary.hk",
    "csrc.gov.cn",
    "samr.gov.cn",
    "creditchina.gov.cn",
    "wenshu.court.gov.cn",
    "sse.com.cn",
    "szse.cn",
    "bse.cn",
    "gov.cn",
    "miit.gov.cn",
    "stats.gov.cn",
    "cnipa.gov.cn",
    "court.gov.cn",
    "zxgk.court.gov.cn",
    "gsxt.gov.cn",
    "customs.gov.cn",
}

PRIMARY_DOMAINS = {"cninfo.com.cn"}


def classify_source_tier(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if any(host == domain or host.endswith(f".{domain}") for domain in OFFICIAL_DOMAINS):
        return "official"
    if any(host == domain or host.endswith(f".{domain}") for domain in PRIMARY_DOMAINS):
        return "primary"
    return "secondary"


def build_due_diligence_queries(
    company: str,
    business_description: str = "",
) -> list[SearchQuery]:
    context = business_description[:80].strip()
    industry_query = f"{company} {context} 行业 市场规模 增速 竞争格局".strip()
    return [
        SearchQuery(
            query=f"{company} 申请版本 招股书 上市文件",
            topic="hkex_filings",
            domains=["hkexnews.hk", "hkex.com.hk"],
            priority="P0",
            purpose="核对港交所申请版本、聆讯资料及后续更新",
        ),
        SearchQuery(
            query=f"{company} 监管 处罚 纪律 执法 通报",
            topic="regulatory",
            domains=["sfc.hk", "csrc.gov.cn", "samr.gov.cn", "creditchina.gov.cn"],
            priority="P0",
            purpose="排查发行人、实控人及主要子公司的监管记录",
        ),
        SearchQuery(
            query=f"{company} 公司登记 股东 董事 实际控制人",
            topic="corporate_registry",
            domains=["cr.gov.hk", "cninfo.com.cn"],
            priority="P0",
            purpose="交叉核对股权、董事和控制关系",
        ),
        SearchQuery(
            query=f"{company} 诉讼 仲裁 判决 被执行人",
            topic="litigation",
            domains=["judiciary.hk", "wenshu.court.gov.cn", "creditchina.gov.cn"],
            priority="P0",
            purpose="排查重大诉讼、仲裁与执行风险",
        ),
        SearchQuery(
            query=f"{company} 实际控制人 股权质押 关联交易 资金占用",
            topic="controller_related_parties",
            priority="P0",
            purpose="核实实控人、关联方和利益输送风险",
        ),
        SearchQuery(
            query=f"{company} 客户 供应商 集中度 返利 经销商",
            topic="customers_suppliers",
            priority="P0",
            purpose="寻找收入真实性及客户供应商关系的外部线索",
        ),
        SearchQuery(
            query=f"{company} 审计师 会计差错 财务造假 问询",
            topic="accounting_auditor",
            priority="P0",
            purpose="排查审计变更、会计差错和财务真实性风险",
        ),
        SearchQuery(
            query=f"{company} 融资 借款 担保 违约 股权质押",
            topic="financing_debt",
            priority="P1",
            purpose="交叉核对融资、负债和或有义务",
        ),
        SearchQuery(
            query=industry_query,
            topic="industry",
            domains=["stats.gov.cn", "miit.gov.cn", "gov.cn"],
            priority="P1",
            purpose="独立验证行业规模、增速和竞争特征",
        ),
        SearchQuery(
            query=f"{company} {context} 竞争对手 市场份额 产品价格".strip(),
            topic="competitors",
            priority="P1",
            purpose="识别可比公司并核对竞争格局",
        ),
        SearchQuery(
            query=f"{context or company} 下游需求 应用领域 景气度 采购周期",
            topic="downstream_demand",
            domains=["stats.gov.cn", "miit.gov.cn", "gov.cn"],
            priority="P1",
            purpose="验证下游行业需求、周期与客户采购驱动",
        ),
        SearchQuery(
            query=f"{context or company} 产业链 上游原材料 核心零部件 供应格局",
            topic="value_chain",
            priority="P1",
            purpose="识别上游约束、关键供应商和价值链议价关系",
        ),
        SearchQuery(
            query=f"{context or company} 技术路线 行业标准 国家标准 认证",
            topic="technology_standards",
            domains=["miit.gov.cn", "samr.gov.cn", "gov.cn"],
            priority="P1",
            purpose="核对技术演进、标准、认证与替代风险",
        ),
        SearchQuery(
            query=f"{context or company} 上市公司 年报 毛利率 研发投入 市场份额",
            topic="comparable_companies",
            domains=["hkexnews.hk", "cninfo.com.cn", "sse.com.cn", "szse.cn"],
            priority="P1",
            purpose="从可比公司公告建立独立经营与财务参照",
        ),
        SearchQuery(
            query=f"{context or company} 出口 海外市场 贸易数据 关税",
            topic="export_market",
            domains=["customs.gov.cn", "gov.cn"],
            priority="P2",
            purpose="核查海外需求、出口趋势、关税及地域风险",
        ),
        SearchQuery(
            query=f"{company} {context} 产业政策 行业监管 政策风险".strip(),
            topic="policy",
            domains=["gov.cn", "miit.gov.cn", "samr.gov.cn"],
            priority="P2",
            purpose="识别可能影响未来盈利能力的政策变化",
        ),
        SearchQuery(
            query=f"{company} 负面新闻 举报 处罚 诉讼 质量事故",
            topic="adverse_media",
            priority="P0",
            purpose="发现尚未进入正式监管文件的负面线索",
        ),
        SearchQuery(
            query=f"{company} 社会保险 住房公积金 劳动用工 行政处罚",
            topic="employment_compliance",
            domains=["creditchina.gov.cn", "gov.cn"],
            priority="P0",
            purpose="核查劳动用工、社保与住房公积金合规",
        ),
        SearchQuery(
            query=f"{company} 专利 商标 无效 侵权 行政裁决",
            topic="intellectual_property",
            domains=["cnipa.gov.cn", "court.gov.cn"],
            priority="P1",
            purpose="核查核心知识产权权属、有效性与争议",
        ),
    ]


class SearchService:
    def __init__(self, provider: SearchProvider) -> None:
        self.provider = provider

    def run(self, queries: list[SearchQuery]) -> list[SearchResult]:
        return self.run_report(queries).results

    def run_report(
        self,
        queries: list[SearchQuery],
        *,
        provider_name: str = "configured",
        cost_mode: str = "unavailable",
        max_queries: int | None = None,
    ) -> SearchRun:
        ordered = sorted(queries, key=lambda item: item.priority)
        selected = ordered[:max_queries] if max_queries else ordered
        results: dict[str, SearchResult] = {}
        errors: list[str] = []
        for query in selected:
            try:
                found = self.provider.search(query)
            except Exception as error:
                errors.append(f"{query.topic}: {type(error).__name__}")
                continue
            for item in found:
                item.source_tier = classify_source_tier(item.url)
                item.confidence = {
                    "official": 0.95,
                    "primary": 0.8,
                    "secondary": 0.55,
                    "unknown": 0.4,
                }[item.source_tier]
                previous = results.get(item.url)
                if previous is None or len(item.content) > len(previous.content):
                    results[item.url] = item
        output = list(results.values())
        covered = sorted({item.topic for item in output})
        required = {item.topic for item in selected if item.required}
        return SearchRun(
            provider=provider_name,
            cost_mode=cost_mode,
            queries=selected,
            results=output,
            covered_topics=covered,
            missing_topics=sorted(required - set(covered)),
            errors=errors,
        )
