"""
storage.py — all file I/O for Viyugam.
Everything lives under ~/.viyugam/
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Optional

import yaml

from viyugam.models import (
    Task, Project, Goal, InboxItem, SomedayItem,
    JournalSummary, SystemState, ViyugamConfig,
    TaskStatus, ResilienceState
)


# ── Paths ──────────────────────────────────────────────────────────────────────

HOME      = Path.home() / ".viyugam"
DATA      = HOME / "data"
JOURNALS  = HOME / "journals"
RESEARCH  = HOME / "research"
CONFIG_FILE = HOME / "config.yaml"


def ensure_dirs() -> None:
    """Create ~/.viyugam/ directory structure if it doesn't exist."""
    HOME.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    JOURNALS.mkdir(exist_ok=True)
    RESEARCH.mkdir(exist_ok=True)
    for name in ("tasks", "projects", "goals", "inbox", "someday", "state"):
        path = DATA / f"{name}.json"
        if not path.exists():
            path.write_text("[]" if name != "state" else "{}")


# ── Config ─────────────────────────────────────────────────────────────────────

def load_config() -> ViyugamConfig:
    if not CONFIG_FILE.exists():
        return ViyugamConfig()
    with open(CONFIG_FILE) as f:
        raw = yaml.safe_load(f) or {}
    return ViyugamConfig(**raw)


def save_config(config: ViyugamConfig) -> None:
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config.model_dump(exclude_none=True), f, default_flow_style=False, allow_unicode=True)


# ── Generic JSON helpers ───────────────────────────────────────────────────────

def _load(name: str) -> list[dict] | dict:
    path = DATA / f"{name}.json"
    if not path.exists():
        return [] if name != "state" else {}
    text = path.read_text().strip()
    if not text:
        return [] if name != "state" else {}
    return json.loads(text)


def _save(name: str, data: list[dict] | dict) -> None:
    path = DATA / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ── System State ───────────────────────────────────────────────────────────────

def load_state() -> SystemState:
    raw = _load("state")
    if not raw:
        return SystemState()
    return SystemState(**raw)


def save_state(state: SystemState) -> None:
    _save("state", state.model_dump())


def touch_active(state: SystemState) -> SystemState:
    """Update last_active to now and increment streak if new day."""
    now = datetime.now()
    today = now.date().isoformat()
    if state.last_active:
        last = datetime.fromisoformat(state.last_active).date()
        if last < now.date():
            state.current_streak += 1
    else:
        state.current_streak = 1
    state.last_active = now.isoformat()
    state.resilience = ResilienceState.FLOW
    return state


def check_resilience(state: SystemState) -> ResilienceState:
    """Determine current resilience state from last_active timestamp."""
    if not state.last_active:
        return ResilienceState.FLOW
    last = datetime.fromisoformat(state.last_active)
    delta = datetime.now() - last
    if delta < timedelta(hours=48):
        return ResilienceState.FLOW
    elif delta < timedelta(days=5):
        return ResilienceState.DRIFT
    else:
        return ResilienceState.BANKRUPTCY


# ── Tasks ──────────────────────────────────────────────────────────────────────

def get_tasks(
    status: Optional[str] = None,
    scheduled_date: Optional[str] = None,
    include_habits: bool = True
) -> list[Task]:
    raw = _load("tasks")
    tasks = [Task(**t) for t in raw]
    if status:
        tasks = [t for t in tasks if t.status.value == status]
    if scheduled_date:
        tasks = [t for t in tasks if t.scheduled_date == scheduled_date]
    if not include_habits:
        tasks = [t for t in tasks if not t.is_habit]
    return tasks


def get_task_by_id(task_id: str) -> Optional[Task]:
    for t in get_tasks():
        if t.id == task_id or t.id.startswith(task_id):
            return t
    return None


def save_task(task: Task) -> None:
    raw = _load("tasks")
    existing = [t for t in raw if t["id"] != task.id]
    existing.append(task.model_dump())
    _save("tasks", existing)


def save_tasks(tasks: list[Task]) -> None:
    raw = _load("tasks")
    updated_ids = {t.id for t in tasks}
    kept = [t for t in raw if t["id"] not in updated_ids]
    kept.extend([t.model_dump() for t in tasks])
    _save("tasks", kept)


def get_habits() -> list[Task]:
    return [t for t in get_tasks() if t.is_habit]


# ── Projects ───────────────────────────────────────────────────────────────────

def get_projects(status: Optional[str] = None) -> list[Project]:
    raw = _load("projects")
    projects = [Project(**p) for p in raw]
    if status:
        projects = [p for p in projects if p.status.value == status]
    return projects


def save_project(project: Project) -> None:
    raw = _load("projects")
    existing = [p for p in raw if p["id"] != project.id]
    existing.append(project.model_dump())
    _save("projects", existing)


# ── Goals ──────────────────────────────────────────────────────────────────────

def get_goals(active_only: bool = True) -> list[Goal]:
    raw = _load("goals")
    goals = [Goal(**g) for g in raw]
    if active_only:
        goals = [g for g in goals if g.is_active]
    return goals


def save_goal(goal: Goal) -> None:
    raw = _load("goals")
    existing = [g for g in raw if g["id"] != goal.id]
    existing.append(goal.model_dump())
    _save("goals", existing)


# ── Inbox ──────────────────────────────────────────────────────────────────────

def get_inbox(unprocessed_only: bool = True) -> list[InboxItem]:
    raw = _load("inbox")
    items = [InboxItem(**i) for i in raw]
    if unprocessed_only:
        items = [i for i in items if not i.is_processed]
    return items


def append_inbox(content: str, source: str = "cli") -> InboxItem:
    item = InboxItem(content=content, source=source)
    raw = _load("inbox")
    raw.append(item.model_dump())
    _save("inbox", raw)
    return item


def mark_inbox_processed(item_ids: list[str]) -> None:
    raw = _load("inbox")
    for item in raw:
        if item["id"] in item_ids:
            item["is_processed"] = True
    _save("inbox", raw)


# ── Someday ────────────────────────────────────────────────────────────────────

def get_someday() -> list[SomedayItem]:
    raw = _load("someday")
    return [SomedayItem(**s) for s in raw]


def save_someday(item: SomedayItem) -> None:
    raw = _load("someday")
    existing = [s for s in raw if s["id"] != item.id]
    existing.append(item.model_dump())
    _save("someday", existing)


def delete_someday(item_id: str) -> None:
    raw = _load("someday")
    _save("someday", [s for s in raw if s["id"] != item_id])


# ── Journals ───────────────────────────────────────────────────────────────────

def journal_path(for_date: Optional[str] = None) -> Path:
    d = for_date or date.today().isoformat()
    return JOURNALS / f"{d}.md"


def load_journal(for_date: Optional[str] = None) -> Optional[str]:
    path = journal_path(for_date)
    if not path.exists():
        return None
    return path.read_text()


def save_journal(content: str, for_date: Optional[str] = None) -> Path:
    path = journal_path(for_date)
    path.write_text(content)
    return path


def get_recent_journals(days: int = 14) -> list[tuple[str, str]]:
    """Return list of (date_str, content) for the last N days that have entries."""
    entries = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        content = load_journal(d)
        if content:
            entries.append((d, content))
    return entries


def load_journal_summary(for_date: Optional[str] = None) -> Optional[JournalSummary]:
    """Extract the structured JSON summary block from a journal markdown file."""
    content = load_journal(for_date)
    if not content:
        return None
    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        return JournalSummary(**data)
    except Exception:
        return None


def get_recent_summaries(days: int = 14) -> list[JournalSummary]:
    summaries = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        s = load_journal_summary(d)
        if s:
            summaries.append(s)
    return summaries


# ── Resilience: Bankruptcy settlement ─────────────────────────────────────────

def settle_bankruptcy() -> dict:
    """Archive overdue tasks to backlog, pause active projects."""
    today = date.today().isoformat()
    tasks = get_tasks()
    cleared = 0
    for task in tasks:
        if (
            task.status not in (TaskStatus.DONE, TaskStatus.BACKLOG)
            and task.scheduled_date
            and task.scheduled_date < today
        ):
            task.status = TaskStatus.BACKLOG
            task.scheduled_date = None
            task.is_overdue = False
            cleared += 1
    save_tasks(tasks)

    projects = get_projects(status="active")
    for project in projects:
        project.status.value  # access to avoid lint
        from viyugam.models import ProjectStatus
        project.status = ProjectStatus.PAUSED
        save_project(project)

    state = load_state()
    state.current_streak = 0
    state.resilience = ResilienceState.FLOW
    state.last_active = datetime.now().isoformat()
    save_state(state)

    return {"cleared_tasks": cleared, "paused_projects": len(projects)}


# ── Season drift detection ────────────────────────────────────────────────────

def calculate_actual_season(days: int = 30) -> Optional[str]:
    """
    Derive the actual season from completed task dimension distribution.
    Returns the dominant dimension as a string, or None if insufficient data.
    """
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    tasks = get_tasks(status="done")
    recent = [
        t for t in tasks
        if t.dimension and t.scheduled_date and t.scheduled_date >= cutoff
    ]
    if len(recent) < 5:
        return None

    counts: dict[str, int] = {}
    for t in recent:
        key = t.dimension.value if hasattr(t.dimension, "value") else str(t.dimension)
        counts[key] = counts.get(key, 0) + 1

    return max(counts, key=counts.get)


def get_season_drift(config: "ViyugamConfig") -> Optional[str]:
    """
    Returns a drift message if actual season diverges from intended.
    Returns None if aligned or insufficient data.
    """
    if not config.season:
        return None
    intended = config.season.focus.value if hasattr(config.season.focus, "value") else str(config.season.focus)
    actual = calculate_actual_season()
    if actual and actual != intended:
        return (
            f"Intended focus: {intended} — "
            f"Actual (last 30 days): {actual}. "
            "A gap worth noticing."
        )
    return None


def get_avg_dimension_scores(days: int = 14) -> list[dict]:
    """
    Average dimension scores across recent journal summaries.
    Returns list of {dimension, score, note} dicts.
    """
    summaries = get_recent_summaries(days)
    if not summaries:
        return []

    scores_by_dim: dict[str, list[int]] = {}
    for summary in summaries:
        for ds in summary.dimension_scores:
            key = ds.dimension.value if hasattr(ds.dimension, "value") else str(ds.dimension)
            scores_by_dim.setdefault(key, []).append(ds.score)

    result = []
    for dim, scores in scores_by_dim.items():
        avg = round(sum(scores) / len(scores), 1)
        result.append({"dimension": dim, "score": avg, "note": None})
    return result


# ── Nudge detection ────────────────────────────────────────────────────────────

# ── Research ───────────────────────────────────────────────────────────────────

def save_research(topic: str, content: str) -> Path:
    """Save a research report to ~/.viyugam/research/{slug}-{date}.md."""
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:60]
    today = date.today().isoformat()
    path = RESEARCH / f"{slug}-{today}.md"
    path.write_text(content, encoding="utf-8")
    return path


# ── Nudge detection ────────────────────────────────────────────────────────────

def get_nudges(state: SystemState) -> list[str]:
    """Return contextual nudges based on system state."""
    nudges = []
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    if state.last_log and state.last_log < yesterday:
        nudges.append(f"No log since {state.last_log} — quick catch-up after planning?")
    elif not state.last_log:
        nudges.append("You haven't logged yet — try 'viyugam log' this evening.")

    if state.last_think:
        days_since = (date.today() - date.fromisoformat(state.last_think)).days
        if days_since >= 5:
            nudges.append(f"No think session in {days_since} days — worth scheduling one.")
    else:
        nudges.append("You haven't used 'think' yet — it's great for big decisions.")

    if state.last_review:
        days_since = (date.today() - date.fromisoformat(state.last_review)).days
        if days_since >= 7:
            nudges.append(f"Weekly review is {days_since} days overdue — run 'viyugam review'.")
    else:
        nudges.append("No reviews yet — 'viyugam review' helps clear cognitive overhead weekly.")

    return nudges
