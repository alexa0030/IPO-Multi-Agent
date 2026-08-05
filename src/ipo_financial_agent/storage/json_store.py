from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def write_json(path: str | Path, value: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(to_jsonable(value), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
