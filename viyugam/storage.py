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
    Task, Project, Goal, InboxItem, TriageItem, Note, SomedayItem,
    JournalSummary, SystemState, ViyugamConfig,
    TaskStatus, ResilienceState, CalendarEntry,
    SlowBurn, Milestone, Budget, Transaction, Decision, ActualRecord,
    OKR, KeyResult, RecurringItem, TxType, Dimension,
)


# ── Paths ──────────────────────────────────────────────────────────────────────

HOME      = Path.home() / ".viyugam"
DATA      = HOME / "data"
JOURNALS  = HOME / "journals"
JOURNAL   = HOME / "journal"    # new per-dimension journal dir
RESEARCH  = HOME / "research"
PLANS     = HOME / "plans"
CONFIG_FILE   = HOME / "config.yaml"
CALENDAR_FILE = DATA / "calendar.json"
CALENDAR_ICS  = HOME / "calendar.ics"
SLOW_BURNS_FILE  = DATA / "slow_burns.json"
MILESTONES_FILE  = DATA / "milestones.json"
BUDGETS_FILE     = DATA / "budgets.json"
BUDGET_YAML      = HOME / "budget.yaml"
TRANSACTIONS_FILE= DATA / "transactions.json"
DECISIONS_FILE   = DATA / "decisions.json"
ACTUALS_FILE     = DATA / "actuals.json"
MEMORY_FILE      = HOME / "memory.json"
CONSTITUTION_FILE= HOME / "constitution.md"
VALUES_FILE      = HOME / "values.yaml"
ENERGY_CACHE_FILE= DATA / "energy_pattern.json"
OKRS_FILE        = DATA / "okrs.json"
RECURRING_FILE   = DATA / "recurring.json"
JOURNALS_DIR     = JOURNALS
TRIAGE_FILE      = HOME / "triage.json"
COUNTERS_FILE    = DATA / "counters.json"
NOTES_FILE       = DATA / "notes.json"


def ensure_dirs() -> None:
    """Create ~/.viyugam/ directory structure if it doesn't exist."""
    HOME.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    JOURNALS.mkdir(exist_ok=True)
    JOURNAL.mkdir(exist_ok=True)
    RESEARCH.mkdir(exist_ok=True)
    PLANS.mkdir(exist_ok=True)
    for name in ("tasks", "projects", "goals", "inbox", "someday", "state"):
        path = DATA / f"{name}.json"
        if not path.exists():
            path.write_text("[]" if name != "state" else "{}")
    if not CALENDAR_FILE.exists():
        CALENDAR_FILE.write_text("[]")
    for fpath in (SLOW_BURNS_FILE, MILESTONES_FILE, BUDGETS_FILE,
                  TRANSACTIONS_FILE, DECISIONS_FILE, ACTUALS_FILE, OKRS_FILE,
                  RECURRING_FILE, NOTES_FILE):
        if not fpath.exists():
            fpath.write_text("[]")
    if not COUNTERS_FILE.exists():
        COUNTERS_FILE.write_text("{}")
    if not TRIAGE_FILE.exists():
        _migrate_inbox_to_triage()
    _ensure_pseudo_goals()


# ── Sequential IDs ─────────────────────────────────────────────────────────────

def _next_id(prefix: str) -> str:
    """Return next sequential ID like T-001, G-002, P-003, N-004."""
    counters = {}
    if COUNTERS_FILE.exists():
        text = COUNTERS_FILE.read_text().strip()
        if text:
            counters = json.loads(text)
    n = counters.get(prefix, 0) + 1
    counters[prefix] = n
    COUNTERS_FILE.write_text(json.dumps(counters, indent=2))
    return f"{prefix}-{n:03d}"


# ── Triage (replaces inbox as primary capture) ─────────────────────────────────

def _migrate_inbox_to_triage() -> None:
    """One-time migration: copy inbox.json → triage.json with new fields."""
    inbox_path = DATA / "inbox.json"
    if inbox_path.exists():
        try:
            raw = json.loads(inbox_path.read_text().strip() or "[]")
            migrated = []
            for item in raw:
                migrated.append({
                    "id": item.get("id", ""),
                    "content": item.get("content", ""),
                    "source": item.get("source", "cli"),
                    "processed": item.get("is_processed", False),
                    "snooze_until": None,
                    "boardroom_notes": None,
                    "created_at": item.get("created_at", datetime.now().isoformat()),
                })
            TRIAGE_FILE.write_text(json.dumps(migrated, indent=2, ensure_ascii=False))
            return
        except Exception:
            pass
    TRIAGE_FILE.write_text("[]")


def get_triage(unprocessed_only: bool = True) -> list[TriageItem]:
    """Load triage items. Optionally filter out already-processed ones."""
    if not TRIAGE_FILE.exists():
        return []
    raw = json.loads(TRIAGE_FILE.read_text().strip() or "[]")
    items = [TriageItem(**i) for i in raw]
    if unprocessed_only:
        today = date.today().isoformat()
        result = []
        for item in items:
            if item.processed:
                continue
            # Re-surface snoozed items if snooze_until has passed
            if item.snooze_until and item.snooze_until > today:
                continue
            result.append(item)
        return result
    return items


def append_triage(content: str, source: str = "cli") -> TriageItem:
    """Append a new triage capture. Fast — no AI."""
    item = TriageItem(content=content, source=source)
    raw = json.loads(TRIAGE_FILE.read_text().strip() or "[]") if TRIAGE_FILE.exists() else []
    raw.append(item.model_dump())
    TRIAGE_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))
    return item


def save_triage_item(item: TriageItem) -> None:
    raw = json.loads(TRIAGE_FILE.read_text().strip() or "[]") if TRIAGE_FILE.exists() else []
    raw = [i for i in raw if i["id"] != item.id]
    raw.append(item.model_dump())
    TRIAGE_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))


def mark_triage_processed(item_ids: list[str]) -> None:
    raw = json.loads(TRIAGE_FILE.read_text().strip() or "[]") if TRIAGE_FILE.exists() else []
    for item in raw:
        if item["id"] in item_ids:
            item["processed"] = True
    TRIAGE_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))


def get_recent_triage_logs(n: int = 5) -> list[TriageItem]:
    """Last N triage captures regardless of processed state, newest first."""
    if not TRIAGE_FILE.exists():
        return []
    raw = json.loads(TRIAGE_FILE.read_text().strip() or "[]")
    items = [TriageItem(**i) for i in raw]
    items.sort(key=lambda x: x.created_at, reverse=True)
    return items[:n]


# ── Pseudo-goals ───────────────────────────────────────────────────────────────

def _ensure_pseudo_goals() -> None:
    """Create ~maintenance and ~unplanned pseudo-goals if not present."""
    raw = json.loads((DATA / "goals.json").read_text().strip() or "[]") if (DATA / "goals.json").exists() else []
    titles = {g.get("title") for g in raw}
    changed = False
    for pseudo_title, dim in [("~maintenance", "health"), ("~unplanned", "career")]:
        if pseudo_title not in titles:
            goal = Goal(
                title=pseudo_title,
                dimension=Dimension(dim),
                is_pseudo=True,
            )
            raw.append(goal.model_dump())
            changed = True
    if changed:
        (DATA / "goals.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False))


# ── Values (values.yaml) ───────────────────────────────────────────────────────

def load_values() -> dict:
    """Load values.yaml. Returns {prayer: str, chapters: {dim: str}}."""
    if VALUES_FILE.exists():
        try:
            data = yaml.safe_load(VALUES_FILE.read_text()) or {}
            return data
        except Exception:
            pass
    # Migrate from constitution.md if it exists
    if CONSTITUTION_FILE.exists():
        content = CONSTITUTION_FILE.read_text()
        values = {
            "prayer": "",
            "chapters": {
                "career": content,
                "wealth": "",
                "health": "",
                "relationships": "",
                "joy": "",
                "learning": "",
            },
        }
        VALUES_FILE.write_text(yaml.dump(values, allow_unicode=True, default_flow_style=False))
        return values
    return {"prayer": "", "chapters": {d: "" for d in ["career", "wealth", "health", "relationships", "joy", "learning"]}}


def save_values(values: dict) -> None:
    VALUES_FILE.write_text(yaml.dump(values, allow_unicode=True, default_flow_style=False))


# ── Plans ──────────────────────────────────────────────────────────────────────

def load_plan(scope: str) -> dict:
    """Load plans/{scope}.json. scope = daily|weekly|monthly|quarterly."""
    path = PLANS / f"{scope}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def save_plan(scope: str, plan: dict) -> Path:
    path = PLANS / f"{scope}.json"
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    return path


# ── Notes ──────────────────────────────────────────────────────────────────────

def get_notes() -> list[Note]:
    raw = json.loads(NOTES_FILE.read_text().strip() or "[]") if NOTES_FILE.exists() else []
    return [Note(**n) for n in raw]


def save_note(note: Note) -> None:
    if not note.seq_id:
        note.seq_id = _next_id("N")
    raw = json.loads(NOTES_FILE.read_text().strip() or "[]") if NOTES_FILE.exists() else []
    raw = [n for n in raw if n["id"] != note.id]
    raw.append(note.model_dump())
    NOTES_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))


# ── Period boundaries ──────────────────────────────────────────────────────────

def period_start(scope: str, for_date: Optional[date] = None) -> date:
    """Return start of the period containing for_date. Weeks start Sunday."""
    d = for_date or date.today()
    if scope == "daily":
        return d
    if scope == "weekly":
        # Sunday = weekday 6, Monday = 0
        dow = d.weekday()  # Mon=0 … Sun=6
        days_since_sunday = (dow + 1) % 7
        return d - timedelta(days=days_since_sunday)
    if scope == "monthly":
        return d.replace(day=1)
    if scope == "quarterly":
        q_start_month = ((d.month - 1) // 3) * 3 + 1
        return d.replace(month=q_start_month, day=1)
    return d


def period_end(scope: str, for_date: Optional[date] = None) -> date:
    """Return end of the period containing for_date (inclusive). Weeks end Saturday."""
    import calendar as _cal
    d = for_date or date.today()
    if scope == "daily":
        return d
    if scope == "weekly":
        start = period_start("weekly", d)
        return start + timedelta(days=6)
    if scope == "monthly":
        last_day = _cal.monthrange(d.year, d.month)[1]
        return d.replace(day=last_day)
    if scope == "quarterly":
        q_end_month = ((d.month - 1) // 3) * 3 + 3
        last_day = _cal.monthrange(d.year, q_end_month)[1]
        return d.replace(month=q_end_month, day=last_day)
    return d


def next_sunday(from_date: Optional[date] = None) -> date:
    """Return the next Sunday (or today if today is Sunday)."""
    d = from_date or date.today()
    days_until_sunday = (6 - d.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    return d + timedelta(days=days_until_sunday)


# ── Mark entity done by seq_id ─────────────────────────────────────────────────

def mark_entity_done(seq_id: str) -> Optional[str]:
    """
    Mark a Task/Goal/Project/Note done by its sequential ID (T-NNN etc).
    Returns human-readable result string, or None if not found.
    """
    prefix = seq_id.split("-")[0].upper() if "-" in seq_id else ""

    if prefix == "T":
        tasks = get_tasks()
        for t in tasks:
            if t.seq_id == seq_id or t.seq_id == seq_id.upper():
                t.status = TaskStatus.DONE
                t.last_done = date.today().isoformat()
                save_task(t)
                return f"Task {seq_id} marked done: {t.title}"
    elif prefix == "G":
        goals = get_goals(active_only=False)
        for g in goals:
            if g.seq_id == seq_id or g.seq_id == seq_id.upper():
                g.is_active = False
                save_goal(g)
                return f"Goal {seq_id} marked done: {g.title}"
    elif prefix == "P":
        from viyugam.models import ProjectStatus
        projects = get_projects()
        for p in projects:
            if p.seq_id == seq_id or p.seq_id == seq_id.upper():
                p.status = ProjectStatus.COMPLETED
                save_project(p)
                return f"Project {seq_id} marked done: {p.title}"
    elif prefix == "N":
        notes = get_notes()
        for n in notes:
            if n.seq_id == seq_id or n.seq_id == seq_id.upper():
                return f"Note {seq_id} acknowledged: {n.title}"
    return None


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
        if t.seq_id and (t.seq_id == task_id or t.seq_id.upper() == task_id.upper()):
            return t
    return None


def save_task(task: Task) -> None:
    if not task.seq_id:
        task.seq_id = _next_id("T")
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
    if not project.seq_id:
        project.seq_id = _next_id("P")
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
    if not goal.seq_id and not goal.is_pseudo:
        goal.seq_id = _next_id("G")
    raw = _load("goals")
    existing = [g for g in raw if g["id"] != goal.id]
    existing.append(goal.model_dump())
    _save("goals", existing)


def delete_goal(goal_id: str) -> bool:
    """Remove a goal by id. Returns True if found and deleted."""
    raw = _load("goals")
    filtered = [g for g in raw if g["id"] != goal_id]
    if len(filtered) == len(raw):
        return False
    _save("goals", filtered)
    return True


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
        path = JOURNALS_DIR / f"{d}.md"
        if path.exists():
            try:
                entries.append((d, path.read_text()))
            except Exception:
                pass
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

def get_calendar_entries(date_str: str) -> list[CalendarEntry]:
    """Recurring entries matching day-of-week + one-off entries for this date."""
    DOW = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    dow = DOW[date.fromisoformat(date_str).weekday()]
    raw = json.loads(CALENDAR_FILE.read_text()) if CALENDAR_FILE.exists() else []
    results = [
        CalendarEntry(**e) for e in raw
        if (e.get("recurs_on") and dow in e["recurs_on"])
        or e.get("date") == date_str
    ]
    return sorted(results, key=lambda e: e.start_time or "99:99")


def save_calendar_entry(entry: CalendarEntry) -> None:
    raw = json.loads(CALENDAR_FILE.read_text()) if CALENDAR_FILE.exists() else []
    raw = [e for e in raw if e["id"] != entry.id]
    raw.append(entry.model_dump())
    CALENDAR_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))


def delete_calendar_entry(entry_id: str) -> None:
    raw = json.loads(CALENDAR_FILE.read_text()) if CALENDAR_FILE.exists() else []
    CALENDAR_FILE.write_text(json.dumps(
        [e for e in raw if e["id"] != entry_id], indent=2, ensure_ascii=False
    ))


def get_day_type(date_str: str, config: ViyugamConfig) -> str:
    """Returns 'office', 'wfh', or 'off'. Default 'wfh' if no schedule set."""
    if not config.work_schedule:
        return "wfh"
    DOW = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    dow = DOW[date.fromisoformat(date_str).weekday()]
    ws = config.work_schedule
    if dow in ws.office_days:
        return "office"
    if dow in ws.wfh_days:
        return "wfh"
    return "off"


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


# ── Slow Burns ─────────────────────────────────────────────────────────────────

def get_slow_burns() -> list[SlowBurn]:
    raw = json.loads(SLOW_BURNS_FILE.read_text()) if SLOW_BURNS_FILE.exists() else []
    return [SlowBurn(**s) for s in raw]

def save_slow_burn(item: SlowBurn) -> None:
    raw = json.loads(SLOW_BURNS_FILE.read_text()) if SLOW_BURNS_FILE.exists() else []
    raw = [s for s in raw if s["id"] != item.id]
    raw.append(item.model_dump())
    SLOW_BURNS_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))

def delete_slow_burn(item_id: str) -> None:
    raw = json.loads(SLOW_BURNS_FILE.read_text()) if SLOW_BURNS_FILE.exists() else []
    SLOW_BURNS_FILE.write_text(json.dumps(
        [s for s in raw if s["id"] != item_id], indent=2, ensure_ascii=False
    ))

# ── Milestones ────────────────────────────────────────────────────────────────

def get_milestones(goal_id: str | None = None, project_id: str | None = None) -> list[Milestone]:
    raw = json.loads(MILESTONES_FILE.read_text()) if MILESTONES_FILE.exists() else []
    items = [Milestone(**m) for m in raw]
    if goal_id:
        items = [m for m in items if m.goal_id == goal_id]
    if project_id:
        items = [m for m in items if m.project_id == project_id]
    return items

def save_milestone(m: Milestone) -> None:
    raw = json.loads(MILESTONES_FILE.read_text()) if MILESTONES_FILE.exists() else []
    raw = [x for x in raw if x["id"] != m.id]
    raw.append(m.model_dump())
    MILESTONES_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))

def delete_milestone(m_id: str) -> None:
    raw = json.loads(MILESTONES_FILE.read_text()) if MILESTONES_FILE.exists() else []
    MILESTONES_FILE.write_text(json.dumps(
        [m for m in raw if m["id"] != m_id], indent=2, ensure_ascii=False
    ))

# ── Finance ───────────────────────────────────────────────────────────────────

def get_budgets() -> list[Budget]:
    raw = json.loads(BUDGETS_FILE.read_text()) if BUDGETS_FILE.exists() else []
    return [Budget(**b) for b in raw]

def get_budget_by_id(budget_id: str) -> Optional[Budget]:
    for b in get_budgets():
        if b.id == budget_id or b.id.startswith(budget_id):
            return b
    return None

def save_budget(b: Budget) -> None:
    raw = json.loads(BUDGETS_FILE.read_text()) if BUDGETS_FILE.exists() else []
    raw = [x for x in raw if x["id"] != b.id]
    raw.append(b.model_dump())
    BUDGETS_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))

def get_transactions(budget_id: str | None = None) -> list[Transaction]:
    raw = json.loads(TRANSACTIONS_FILE.read_text()) if TRANSACTIONS_FILE.exists() else []
    txns = [Transaction(**t) for t in raw]
    if budget_id:
        txns = [t for t in txns if t.budget_id == budget_id]
    return txns

def save_transaction(t: Transaction) -> None:
    # Also update budget spent
    raw = json.loads(TRANSACTIONS_FILE.read_text()) if TRANSACTIONS_FILE.exists() else []
    raw = [x for x in raw if x["id"] != t.id]
    raw.append(t.model_dump())
    TRANSACTIONS_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))
    if t.budget_id:
        b = get_budget_by_id(t.budget_id)
        if b:
            all_txns = get_transactions(budget_id=t.budget_id)
            b.spent = round(sum(x.amount for x in all_txns), 2)
            save_budget(b)

def get_budget_summary() -> list[dict]:
    """Return list of {name, total_limit, spent, remaining, pct} for active budgets."""
    today = date.today().isoformat()
    budgets = [b for b in get_budgets() if b.period_end >= today]
    result = []
    for b in budgets:
        remaining = round(b.total_limit - b.spent, 2)
        pct = round((b.spent / b.total_limit) * 100, 1) if b.total_limit > 0 else 0
        result.append({
            "id": b.id, "name": b.name, "total_limit": b.total_limit,
            "spent": b.spent, "remaining": remaining, "pct": pct,
            "dimension": b.dimension.value if b.dimension else None,
        })
    return result


# ── Recurring items ───────────────────────────────────────────────────────────

def get_recurring_items(active_only: bool = True) -> list[RecurringItem]:
    raw = json.loads(RECURRING_FILE.read_text()) if RECURRING_FILE.exists() else []
    items = [RecurringItem(**r) for r in raw]
    if active_only:
        items = [i for i in items if i.is_active]
    return items


def save_recurring_item(item: RecurringItem) -> None:
    raw = json.loads(RECURRING_FILE.read_text()) if RECURRING_FILE.exists() else []
    raw = [r for r in raw if r["id"] != item.id]
    raw.append(item.model_dump())
    RECURRING_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))


def delete_recurring_item(item_id: str) -> None:
    raw = json.loads(RECURRING_FILE.read_text()) if RECURRING_FILE.exists() else []
    RECURRING_FILE.write_text(json.dumps(
        [r for r in raw if r["id"] != item_id], indent=2, ensure_ascii=False
    ))


def get_transactions_by_period(start: str, end: str) -> list[Transaction]:
    """Return transactions where occurred_at falls within [start, end] (YYYY-MM-DD)."""
    all_txns = get_transactions()
    return [t for t in all_txns if start <= t.occurred_at[:10] <= end]


def get_spending_by_category(start: str, end: str) -> dict[str, float]:
    """Return {category: total_amount} for EXPENSE transactions in the period."""
    txns = [t for t in get_transactions_by_period(start, end)
            if t.tx_type == TxType.EXPENSE]
    result: dict[str, float] = {}
    for t in txns:
        result[t.category] = round(result.get(t.category, 0.0) + t.amount, 2)
    return result


def get_monthly_cashflow(month: str) -> dict:
    """month='YYYY-MM' → {income, expenses, net, by_category, transactions}"""
    start = f"{month}-01"
    # Calculate end of month
    year, mon = int(month[:4]), int(month[5:7])
    import calendar as _cal
    last_day = _cal.monthrange(year, mon)[1]
    end = f"{month}-{last_day:02d}"

    txns = get_transactions_by_period(start, end)
    income = round(sum(t.amount for t in txns if t.tx_type == TxType.INCOME), 2)
    expenses = round(sum(t.amount for t in txns if t.tx_type == TxType.EXPENSE), 2)
    net = round(income - expenses, 2)
    by_category: dict[str, float] = {}
    for t in txns:
        if t.tx_type == TxType.EXPENSE:
            by_category[t.category] = round(by_category.get(t.category, 0.0) + t.amount, 2)
    return {
        "month": month,
        "income": income,
        "expenses": expenses,
        "net": net,
        "by_category": by_category,
        "transactions": [t.model_dump() for t in txns],
    }


def get_due_recurring_items(as_of: str | None = None) -> list[RecurringItem]:
    """Active items where day_of_month == today.day AND last_logged != this month."""
    today_date = date.fromisoformat(as_of) if as_of else date.today()
    this_month = today_date.strftime("%Y-%m")
    items = get_recurring_items(active_only=True)
    due = []
    for item in items:
        if item.day_of_month != today_date.day:
            continue
        # Check if already logged this month
        if item.last_logged and item.last_logged[:7] == this_month:
            continue
        due.append(item)
    return due


def get_finance_context(months: int = 3) -> str:
    """Comprehensive snapshot string for agents: budgets, cashflow, recurring, net."""
    today = date.today()
    lines = ["FINANCE CONTEXT:"]

    # Active budgets
    summaries = get_budget_summary()
    if summaries:
        lines.append(f"\nActive budgets ({len(summaries)}):")
        for b in summaries:
            lines.append(
                f"  {b['name']}: {b['spent']:,.0f}/{b['total_limit']:,.0f} spent ({b['pct']}% used)"
            )

    # Monthly cashflow for last N months
    cashflows = []
    for i in range(months):
        year = today.year
        mon = today.month - i
        while mon <= 0:
            mon += 12
            year -= 1
        month_str = f"{year}-{mon:02d}"
        cf = get_monthly_cashflow(month_str)
        cashflows.append(cf)

    if cashflows:
        lines.append(f"\nMonthly cashflow (last {months} months):")
        for cf in cashflows:
            lines.append(
                f"  {cf['month']}: income={cf['income']:,.0f}  "
                f"expenses={cf['expenses']:,.0f}  net={cf['net']:+,.0f}"
            )
        # Top categories from most recent month
        top_cats = sorted(
            cashflows[0]["by_category"].items(), key=lambda x: -x[1]
        )[:5]
        if top_cats:
            lines.append(f"\nTop expense categories ({cashflows[0]['month']}):")
            for cat, amt in top_cats:
                lines.append(f"  {cat}: {amt:,.0f}")

    # Recurring items
    all_recurring = get_recurring_items(active_only=True)
    if all_recurring:
        total_monthly_expense = sum(
            r.amount for r in all_recurring
            if r.tx_type == TxType.EXPENSE and r.frequency.value == "monthly"
        )
        total_monthly_income = sum(
            r.amount for r in all_recurring
            if r.tx_type == TxType.INCOME and r.frequency.value == "monthly"
        )
        lines.append(
            f"\nRecurring items ({len(all_recurring)} active): "
            f"monthly expenses={total_monthly_expense:,.0f}  "
            f"monthly income={total_monthly_income:,.0f}"
        )

    return "\n".join(lines)

# ── Decisions ─────────────────────────────────────────────────────────────────

def get_decisions() -> list[Decision]:
    raw = json.loads(DECISIONS_FILE.read_text()) if DECISIONS_FILE.exists() else []
    return [Decision(**d) for d in raw]

def save_decision(d: Decision) -> None:
    raw = json.loads(DECISIONS_FILE.read_text()) if DECISIONS_FILE.exists() else []
    raw = [x for x in raw if x["id"] != d.id]
    raw.append(d.model_dump())
    DECISIONS_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))

def get_decisions_for_review(days: int = 90) -> list[Decision]:
    """Decisions made in last N days without actual_outcome recorded."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return [
        d for d in get_decisions()
        if d.created_at[:10] >= cutoff and not d.actual_outcome
    ]

# ── Actuals ───────────────────────────────────────────────────────────────────

def save_actual(record: ActualRecord) -> None:
    raw = json.loads(ACTUALS_FILE.read_text()) if ACTUALS_FILE.exists() else []
    raw = [x for x in raw if x["id"] != record.id]
    raw.append(record.model_dump())
    ACTUALS_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))

def get_actuals(for_date: str | None = None, days: int | None = None) -> list[ActualRecord]:
    raw = json.loads(ACTUALS_FILE.read_text()) if ACTUALS_FILE.exists() else []
    records = [ActualRecord(**r) for r in raw]
    if for_date:
        records = [r for r in records if r.date == for_date]
    if days:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        records = [r for r in records if r.date >= cutoff]
    return records

def get_plan_vs_actual(for_date: str) -> dict:
    """Return planned vs actual summary for a date."""
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

# ── Session Memory ────────────────────────────────────────────────────────────

def load_memory() -> dict:
    """Load rolling session memory."""
    if not MEMORY_FILE.exists():
        return {"summaries": [], "energy_patterns": {}, "last_updated": None}
    try:
        return json.loads(MEMORY_FILE.read_text())
    except Exception:
        return {"summaries": [], "energy_patterns": {}, "last_updated": None}

def save_memory(memory: dict) -> None:
    MEMORY_FILE.write_text(json.dumps(memory, indent=2, ensure_ascii=False))

def update_memory_summary(new_summary: str, source: str = "plan") -> None:
    """Append a summary entry, keep last 30."""
    memory = load_memory()
    memory.setdefault("summaries", []).append({
        "date": date.today().isoformat(),
        "source": source,
        "summary": new_summary,
    })
    memory["summaries"] = memory["summaries"][-30:]
    memory["last_updated"] = datetime.now().isoformat()
    save_memory(memory)

def get_memory_context(max_entries: int = 7) -> str:
    """Return recent memory as context string for agents."""
    memory = load_memory()
    summaries = memory.get("summaries", [])[-max_entries:]
    if not summaries:
        return ""
    lines = ["RECENT CONTEXT (from memory):"]
    for s in summaries:
        lines.append(f"  [{s['date']} via {s['source']}] {s['summary']}")
    return "\n".join(lines)

# ── Constitution ──────────────────────────────────────────────────────────────

def load_constitution() -> str:
    """Load the user's constitution document."""
    if not CONSTITUTION_FILE.exists():
        return ""
    return CONSTITUTION_FILE.read_text()

def save_constitution(content: str) -> None:
    CONSTITUTION_FILE.write_text(content)

# ── Coherence Score ───────────────────────────────────────────────────────────

def get_okrs(active_only: bool = True) -> list[OKR]:
    raw = json.loads(OKRS_FILE.read_text()) if OKRS_FILE.exists() else []
    okrs = [OKR(**o) for o in raw]
    if active_only:
        return [o for o in okrs if o.is_active]
    return okrs

def save_okr(okr: OKR) -> None:
    raw = json.loads(OKRS_FILE.read_text()) if OKRS_FILE.exists() else []
    raw = [o for o in raw if o["id"] != okr.id]
    raw.append(okr.model_dump())
    OKRS_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))

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

def get_energy_pattern() -> dict:
    from viyugam.agents.energy import get_energy_pattern as _get
    return _get(JOURNALS_DIR, ENERGY_CACHE_FILE)


def compute_coherence_score(config: "ViyugamConfig", days: int = 7) -> dict:
    """
    Compute a coherence score 0-100 based on:
    - Season alignment: did task dimensions match the season focus?
    - Dimension balance: no single non-season dimension over 60%
    - Goal progress: were milestones/tasks linked to goals completed?
    Returns dict with score, breakdown, and narrative.
    """
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    done_tasks = [
        t for t in get_tasks(status="done")
        if t.scheduled_date and t.scheduled_date >= cutoff and t.dimension
    ]

    if not done_tasks:
        return {"score": None, "breakdown": {}, "narrative": "Not enough data yet."}

    # Dimension distribution
    counts: dict[str, int] = {}
    for t in done_tasks:
        key = t.dimension.value if hasattr(t.dimension, "value") else str(t.dimension)
        counts[key] = counts.get(key, 0) + 1
    total = sum(counts.values())
    breakdown = {k: round(v / total * 100, 1) for k, v in counts.items()}

    # Season alignment score (0-40 points)
    season_score = 0
    if config.season:
        focus = config.season.focus.value if hasattr(config.season.focus, "value") else str(config.season.focus)
        focus_pct = breakdown.get(focus, 0)
        season_score = min(40, int(focus_pct * 0.4))

    # Balance score (0-40 points) — penalise if one non-season dim > 50%
    balance_score = 40
    for dim, pct in breakdown.items():
        if config.season and dim == (config.season.focus.value if hasattr(config.season.focus, "value") else ""):
            continue
        if pct > 50:
            balance_score = max(0, balance_score - int((pct - 50)))

    # Activity score (0-20 points) — completing things
    activity_score = min(20, len(done_tasks) * 2)

    total_score = season_score + balance_score + activity_score

    # Narrative
    focus_name = config.season.focus.value if config.season else "unset"
    top_dim = max(breakdown, key=breakdown.get) if breakdown else "none"
    if total_score >= 75:
        narrative = f"Strong coherence. Top dimension: {top_dim} ({breakdown.get(top_dim, 0)}%). Season focus '{focus_name}' is reflected in your work."
    elif total_score >= 50:
        narrative = f"Moderate coherence. You're partially aligned with '{focus_name}' season but {top_dim} is dominating at {breakdown.get(top_dim, 0)}%."
    else:
        narrative = f"Low coherence. Most energy went to '{top_dim}' ({breakdown.get(top_dim, 0)}%) while your stated season is '{focus_name}'. Worth examining."

    return {"score": total_score, "breakdown": breakdown, "narrative": narrative}


# ── ICS Calendar Reader ────────────────────────────────────────────────────────

def _parse_ics_datetime(val: str) -> Optional[datetime]:
    """Parse iCalendar DTSTART/DTEND value to datetime."""
    val = val.strip()
    # Strip timezone id suffix like ;TZID=Asia/Kolkata
    if ":" in val:
        val = val.split(":")[-1]
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def parse_ics(path: Optional[Path] = None) -> list[dict]:
    """
    Parse ~/.viyugam/calendar.ics (or provided path) into list of event dicts.
    Each dict: {title, date, start_time, end_time, all_day}
    Only returns VEVENT components. Minimal parser — no external deps.
    """
    ics_path = path or CALENDAR_ICS
    if not ics_path.exists():
        return []

    events = []
    try:
        content = ics_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    # Split into VEVENT blocks
    vevent_re = re.compile(r'BEGIN:VEVENT(.*?)END:VEVENT', re.DOTALL)
    for match in vevent_re.finditer(content):
        block = match.group(1)
        props: dict[str, str] = {}
        for line in block.splitlines():
            line = line.strip()
            if ":" in line:
                key, _, val = line.partition(":")
                # Normalize key (strip TZID params etc)
                key = key.split(";")[0].strip().upper()
                props[key] = val.strip()

        summary = props.get("SUMMARY", "Untitled")
        dtstart_raw = props.get("DTSTART", "")
        dtend_raw = props.get("DTEND", "")

        if not dtstart_raw:
            continue

        all_day = len(dtstart_raw.replace(":", "").replace("T", "").replace("Z", "").replace("-", "")) == 8
        dt_start = _parse_ics_datetime(dtstart_raw)
        dt_end = _parse_ics_datetime(dtend_raw) if dtend_raw else None

        if not dt_start:
            continue

        events.append({
            "title": summary,
            "date": dt_start.date().isoformat(),
            "start_time": dt_start.strftime("%H:%M") if not all_day else None,
            "end_time": dt_end.strftime("%H:%M") if dt_end and not all_day else None,
            "all_day": all_day,
        })

    # Sort by date then start_time
    events.sort(key=lambda e: (e["date"], e["start_time"] or "00:00"))
    return events


def get_ics_events_for_period(start: date, end: date) -> list[dict]:
    """Return ICS events in [start, end] date range."""
    events = parse_ics()
    start_str = start.isoformat()
    end_str = end.isoformat()
    return [e for e in events if start_str <= e["date"] <= end_str]


# ── Budget YAML ────────────────────────────────────────────────────────────────

def load_budget_yaml() -> dict:
    """
    Load budget.yaml. Structure:
    {currency: str, envelopes: [{name, monthly_limit, category}]}
    Migrates from data/budgets.json on first load if budget.yaml doesn't exist.
    """
    if BUDGET_YAML.exists():
        try:
            data = yaml.safe_load(BUDGET_YAML.read_text()) or {}
            return data
        except Exception:
            pass

    # Migrate from budgets.json
    budget_data = {"currency": "₹", "envelopes": []}
    if BUDGETS_FILE.exists():
        try:
            raw = json.loads(BUDGETS_FILE.read_text().strip() or "[]")
            for b in raw:
                budget_data["envelopes"].append({
                    "name": b.get("name", ""),
                    "monthly_limit": b.get("total_limit", 0),
                    "category": b.get("dimension") or "general",
                })
        except Exception:
            pass

    BUDGET_YAML.write_text(yaml.dump(budget_data, allow_unicode=True, default_flow_style=False))
    return budget_data


def save_budget_yaml(data: dict) -> None:
    BUDGET_YAML.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False))


def get_budget_envelope_summary() -> list[dict]:
    """Return [{name, monthly_limit, category}] from budget.yaml."""
    data = load_budget_yaml()
    return data.get("envelopes", [])
