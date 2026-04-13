"""storage/plans.py — Plan load/save by scope."""
from __future__ import annotations

import json
from pathlib import Path

from . import _paths


def load_plan(scope: str) -> dict:
    path = _paths.PLANS / f"{scope}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def save_plan(scope: str, plan: dict) -> Path:
    path = _paths.PLANS / f"{scope}.json"
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    return path
