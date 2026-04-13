"""storage/slow_burns.py — Slow burns, milestones."""
from __future__ import annotations

from viyugam.models import Milestone, SlowBurn

from . import _paths

# ── Slow Burns ────────────────────────────────────────────────────────────────

def get_slow_burns() -> list[SlowBurn]:
    raw = _paths._load_json(_paths.SLOW_BURNS_FILE)
    return [SlowBurn(**s) for s in raw]


def save_slow_burn(item: SlowBurn) -> None:
    raw = _paths._load_json(_paths.SLOW_BURNS_FILE)
    raw = [s for s in raw if s["id"] != item.id]
    raw.append(item.model_dump())
    _paths._save_json(_paths.SLOW_BURNS_FILE, raw)


def delete_slow_burn(item_id: str) -> None:
    raw = _paths._load_json(_paths.SLOW_BURNS_FILE)
    _paths._save_json(_paths.SLOW_BURNS_FILE, [s for s in raw if s["id"] != item_id])


# ── Milestones ────────────────────────────────────────────────────────────────

def get_milestones(goal_id: str | None = None, project_id: str | None = None) -> list[Milestone]:
    raw = _paths._load_json(_paths.MILESTONES_FILE)
    items = [Milestone(**m) for m in raw]
    if goal_id:
        items = [m for m in items if m.goal_id == goal_id]
    if project_id:
        items = [m for m in items if m.project_id == project_id]
    return items


def save_milestone(m: Milestone) -> None:
    raw = _paths._load_json(_paths.MILESTONES_FILE)
    raw = [x for x in raw if x["id"] != m.id]
    raw.append(m.model_dump())
    _paths._save_json(_paths.MILESTONES_FILE, raw)


def delete_milestone(m_id: str) -> None:
    raw = _paths._load_json(_paths.MILESTONES_FILE)
    _paths._save_json(_paths.MILESTONES_FILE, [m for m in raw if m["id"] != m_id])
