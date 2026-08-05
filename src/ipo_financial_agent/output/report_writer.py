from __future__ import annotations

from pathlib import Path


def write_markdown_report(path: str | Path, markdown: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown.strip() + "\n", encoding="utf-8")
    return target
