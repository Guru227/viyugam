"""storage/goals.py — Goal CRUD."""
from __future__ import annotations

import json
from typing import Optional

from viyugam.models import Dimension, Goal, TaskStatus

from . import _paths


def _ensure_pseudo_goals() -> None:
    """Create ~maintenance and ~unplanned pseudo-goals if not present."""
    goals_path = _paths.DATA / "goals.json"
    raw = json.loads(goals_path.read_text().strip() or "[]") if goals_path.exists() else []
    titles = {g.get("title") for g in raw}
    changed = False
    for pseudo_title, dim in [("~maintenance", "health"), ("~unplanned", "career")]:
        if pseudo_title not in titles:
            goal = Goal(title=pseudo_title, dimension=Dimension(dim), is_pseudo=True)
            raw.append(goal.model_dump())
            changed = True
    if changed:
        goals_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False))


def get_goals(active_only: bool = True) -> list[Goal]:
    raw = _paths._load("goals")
    goals = [Goal(**g) for g in raw]
    if active_only:
        goals = [g for g in goals if g.is_active]
    return goals


def save_goal(goal: Goal) -> None:
    if not goal.seq_id and not goal.is_pseudo:
        goal.seq_id = _paths._next_id("G")
    raw = _paths._load("goals")
    existing = [g for g in raw if g["id"] != goal.id]
    existing.append(goal.model_dump())
    _paths._save("goals", existing)


def delete_goal(goal_id: str) -> bool:
    raw = _paths._load("goals")
    filtered = [g for g in raw if g["id"] != goal_id]
    if len(filtered) == len(raw):
        return False
    _paths._save("goals", filtered)
    return True


def _recompute_goal_progress(goal_id: str, _tasks: list | None = None) -> Optional[float]:
    """Recompute and save goal progress_pct from aligned tasks."""
    goals = get_goals(active_only=False)
    goal = next((g for g in goals if g.id == goal_id), None)
    if not goal:
        return None
    if _tasks is None:
        from .tasks import get_tasks
        _tasks = get_tasks(include_habits=False)
    tasks = _tasks
    aligned = [t for t in tasks if goal_id in t.aligns_to]
    if not aligned:
        return 0.0
    done = [t for t in aligned if t.status == TaskStatus.DONE]
    pct = len(done) / len(aligned) * 100.0
    goal.progress_pct = round(pct, 1)
    save_goal(goal)
    return pct
