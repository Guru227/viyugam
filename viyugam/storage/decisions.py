"""storage/decisions.py — Decision storage."""
from __future__ import annotations

from datetime import date, timedelta

from viyugam.models import ActualRecord, Decision

from . import _paths


def get_decisions() -> list[Decision]:
    raw = _paths._load_json(_paths.DECISIONS_FILE)
    return [Decision(**d) for d in raw]


def save_decision(d: Decision) -> None:
    raw = _paths._load_json(_paths.DECISIONS_FILE)
    raw = [x for x in raw if x["id"] != d.id]
    raw.append(d.model_dump())
    _paths._save_json(_paths.DECISIONS_FILE, raw)


def get_decisions_for_review(days: int = 90) -> list[Decision]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return [
        d for d in get_decisions()
        if d.created_at[:10] >= cutoff and not d.actual_outcome
    ]


# ── Actuals ───────────────────────────────────────────────────────────────────

def save_actual(record: ActualRecord) -> None:
    raw = _paths._load_json(_paths.ACTUALS_FILE)
    raw = [x for x in raw if x["id"] != record.id]
    raw.append(record.model_dump())
    _paths._save_json(_paths.ACTUALS_FILE, raw)


def get_actuals(for_date: str | None = None, days: int | None = None) -> list[ActualRecord]:
    raw = _paths._load_json(_paths.ACTUALS_FILE)
    records = [ActualRecord(**r) for r in raw]
    if for_date:
        records = [r for r in records if r.date == for_date]
    if days:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        records = [r for r in records if r.date >= cutoff]
    return records


def get_plan_vs_actual(for_date: str) -> dict:
    records = get_actuals(for_date=for_date)
    if not records:
        return {}
    planned = sum(r.planned_minutes for r in records)
    actual  = sum(r.actual_minutes or 0 for r in records)
    return {
        "date": for_date,
        "tasks_completed": len(records),
        "planned_minutes": planned,
        "actual_minutes": actual,
        "delta_minutes": actual - planned,
    }
