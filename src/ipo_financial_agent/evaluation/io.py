from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import EvalCase


def load_case(path: str | Path) -> EvalCase:
    return EvalCase.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
