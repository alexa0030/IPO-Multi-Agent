from __future__ import annotations

import re
from functools import lru_cache

from opencc import OpenCC


@lru_cache(maxsize=1)
def _converter() -> OpenCC:
    return OpenCC("t2s")


def to_simplified(text: str | None) -> str:
    """Normalize matching text without modifying auditable source evidence."""
    if not text:
        return ""
    return _converter().convert(str(text))


def normalize_search_text(text: str | None, *, compact: bool = False) -> str:
    value = to_simplified(text).replace("\u3000", " ").replace("\xa0", " ")
    if compact:
        return re.sub(r"\s+", "", value).lower()
    return re.sub(r"\s+", " ", value).strip().lower()
