from __future__ import annotations

from ipo_financial_agent.schemas.legal import LegalEntity, LegalResearchTopic


def build_entity_search_queries(entities: list[LegalEntity], *, max_entities: int = 10) -> list[dict]:
    terms = {
        LegalResearchTopic.LITIGATION_PENALTY: ("诉讼 仲裁 行政处罚 执行 失信", ["wenshu.court.gov.cn", "creditchina.gov.cn"]),
        LegalResearchTopic.OWNERSHIP_CONTROL: ("股权 冻结 监管 实际控制人", ["cninfo.com.cn", "creditchina.gov.cn"]),
        LegalResearchTopic.RELATED_PARTY: ("关联交易 同业竞争 监管问询", ["cninfo.com.cn", "hkexnews.hk"]),
        LegalResearchTopic.LICENSE_IP: ("专利 商标 知识产权 侵权", ["cnipa.gov.cn", "wipo.int"]),
        LegalResearchTopic.GOVERNANCE_INTERNAL_CONTROL: ("内控 审计 担保 资金占用 处罚", ["cninfo.com.cn", "hkexnews.hk"]),
    }
    queries = []
    for entity in [item for item in entities if item.search_enabled][:max_entities]:
        for topic, (suffix, domains) in terms.items():
            queries.append({"entity_id": entity.entity_id, "entity_name": entity.name_cn, "research_topic": topic, "query": f'"{entity.name_cn}" {suffix}', "domains": domains, "priority": "P0" if topic == LegalResearchTopic.LITIGATION_PENALTY else "P1"})
    return queries
