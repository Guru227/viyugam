"""storage/okrs.py — OKR storage."""
from __future__ import annotations

from datetime import date

from viyugam.models import OKR

from . import _paths


def get_okrs(active_only: bool = True) -> list[OKR]:
    raw = _paths._load_json(_paths.OKRS_FILE)
    okrs = [OKR(**o) for o in raw]
    if active_only:
        return [o for o in okrs if o.is_active]
    return okrs


def save_okr(okr: OKR) -> None:
    raw = _paths._load_json(_paths.OKRS_FILE)
    raw = [o for o in raw if o["id"] != okr.id]
    raw.append(okr.model_dump())
    _paths._save_json(_paths.OKRS_FILE, raw)


def get_current_quarter() -> str:
    today = date.today()
    q = (today.month - 1) // 3 + 1
    return f"{today.year}-Q{q}"


def get_next_quarter() -> str:
    today = date.today()
    q = (today.month - 1) // 3 + 1
    if q == 4:
        return f"{today.year + 1}-Q1"
    return f"{today.year}-Q{q + 1}"
