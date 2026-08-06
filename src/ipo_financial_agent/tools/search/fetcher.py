"""Small, bounded web fetcher for evidence registration.

Search snippets are leads only.  This module opens selected URLs and returns
clean text plus an audit record; it intentionally does not crawl recursively.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from html import unescape
from urllib.request import Request, urlopen


def fetch_source(url: str, *, timeout_seconds: int = 15, max_chars: int = 30_000) -> dict:
    retrieved_at = datetime.now(timezone.utc).isoformat()
    request = Request(
        url,
        headers={"User-Agent": "IPOResearchBot/0.1 (+evidence retrieval)"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        raw = response.read(2_000_000)
        final_url = response.geturl()
        content_type = response.headers.get_content_type()
        status = getattr(response, "status", 200)
    decoded = raw.decode("utf-8", errors="replace")
    text = _extract_text(decoded, content_type)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()[:max_chars]
    if len(text) < 80:
        raise ValueError("fetched source has insufficient正文")
    return {
        "url": url,
        "final_url": final_url,
        "http_status": status,
        "content_type": content_type,
        "retrieved_at": retrieved_at,
        "content": text,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "extraction_method": "trafilatura" if _has_trafilatura() else "html_text",
    }


def _has_trafilatura() -> bool:
    try:
        import trafilatura  # noqa: F401
    except ImportError:
        return False
    return True


def _extract_text(raw: str, content_type: str) -> str:
    if "html" not in content_type:
        return raw
    try:
        import trafilatura

        extracted = trafilatura.extract(raw, include_tables=True, include_links=True)
        if extracted:
            return extracted
    except Exception:
        pass
    raw = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", raw, flags=re.I | re.S)
    return unescape(re.sub(r"<[^>]+>", " ", raw))
