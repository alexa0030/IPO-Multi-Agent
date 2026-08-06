from __future__ import annotations

import re
from ipo_financial_agent.schemas.legal import LegalEntity


def normalize_entity_name(name: str) -> str:
    value = re.sub(r"[（）()]", "", name or "")
    value = re.sub(r"\s+", "", value).strip("，,。；;:：")
    return value


def enable_entity_search(entity: LegalEntity) -> bool:
    return entity.entity_type in {"issuer", "controller", "controlling_shareholder"} or entity.importance in {"core", "major"}


def build_entity_registry(company: str, pages: list[object]) -> list[LegalEntity]:
    names: list[tuple[str, str, str]] = [(normalize_entity_name(company), "issuer", "core")]
    for page in pages:
        text = str(getattr(page, "text", "") or "")
        for match in re.findall(r"[\u4e00-\u9fffA-Za-z0-9（）()·]{2,40}(?:有限公司|有限责任公司|集团|公司)", text):
            name = normalize_entity_name(match)
            if name and name not in {item[0] for item in names}:
                kind = "subsidiary" if any(token in text[max(0, text.find(match)-80):text.find(match)+80] for token in ("子公司", "附属")) else "related_party"
                names.append((name, kind, "major" if kind == "subsidiary" else "ordinary"))
            if len(names) >= 25:
                break
        if len(names) >= 25:
            break
    entities = []
    for index, (name, kind, importance) in enumerate(names, start=1):
        entity = LegalEntity(entity_id=f"LE{index:03d}", name_cn=name, entity_type=kind, importance=importance)
        entity.search_enabled = enable_entity_search(entity)
        entities.append(entity)
    return entities
