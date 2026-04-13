"""storage/core.py — Cross-cutting functions: ensure_dirs, config, state, coherence, etc."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import yaml

from viyugam.models import (
    ResilienceState,
    SystemState,
    TaskStatus,
    ViyugamConfig,
)

from . import _paths

# ── Directory setup ───────────────────────────────────────────────────────────

def ensure_dirs() -> None:
    """Create ~/.viyugam/ directory structure if it doesn't exist."""
    _paths.HOME.mkdir(exist_ok=True)
    _paths.DATA.mkdir(exist_ok=True)
    _paths.JOURNALS.mkdir(exist_ok=True)
    _paths.JOURNAL.mkdir(exist_ok=True)
    _paths.RESEARCH.mkdir(exist_ok=True)
    _paths.PLANS.mkdir(exist_ok=True)
    _paths.SESSIONS_DIR.mkdir(exist_ok=True)
    for name in ("tasks", "projects", "goals", "inbox", "someday", "state"):
        path = _paths.DATA / f"{name}.json"
        if not path.exists():
            path.write_text("[]" if name != "state" else "{}")
    if not _paths.CALENDAR_FILE.exists():
        _paths.CALENDAR_FILE.write_text("[]")
    for fpath in (
        _paths.SLOW_BURNS_FILE, _paths.MILESTONES_FILE, _paths.BUDGETS_FILE,
        _paths.TRANSACTIONS_FILE, _paths.DECISIONS_FILE, _paths.ACTUALS_FILE,
        _paths.OKRS_FILE, _paths.RECURRING_FILE, _paths.NOTES_FILE,
        _paths.PROJECT_PLANS_FILE, _paths.NUDGES_FILE, _paths.PATTERNS_FILE,
    ):
        if not fpath.exists():
            fpath.write_text("[]")
    if not _paths.COUNTERS_FILE.exists():
        _paths.COUNTERS_FILE.write_text("{}")
    if not _paths.TRIAGE_FILE.exists():
        from .triage import _migrate_inbox_to_triage
        _migrate_inbox_to_triage()
    from .goals import _ensure_pseudo_goals
    _ensure_pseudo_goals()


# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> ViyugamConfig:
    if not _paths.CONFIG_FILE.exists():
        return ViyugamConfig()
    with open(_paths.CONFIG_FILE) as f:
        raw = yaml.safe_load(f) or {}
    return ViyugamConfig(**raw)


def save_config(config: ViyugamConfig) -> None:
    with open(_paths.CONFIG_FILE, "w") as f:
        yaml.dump(
            config.model_dump(mode="json", exclude_none=True),
            f, default_flow_style=False, allow_unicode=True,
        )


# ── System State ──────────────────────────────────────────────────────────────

def load_state() -> SystemState:
    raw = _paths._load("state")
    if not raw:
        return SystemState()
    if isinstance(raw, list):
        return SystemState()
    return SystemState(**raw)


def save_state(state: SystemState) -> None:
    _paths._save("state", state.model_dump())


def touch_active(state: SystemState) -> SystemState:
    now = datetime.now()
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


# ── Mark entity done by seq_id ────────────────────────────────────────────────

def mark_entity_done(seq_id: str) -> Optional[str]:
    """Mark a Task/Goal/Project/Note done by its sequential ID (T-NNN etc)."""
    from .goals import _recompute_goal_progress, get_goals, save_goal
    from .notes import get_notes
    from .projects import get_projects, project_stats, save_project
    from .tasks import _check_unblocked, get_tasks, save_task

    prefix = seq_id.split("-")[0].upper() if "-" in seq_id else ""

    if prefix == "T":
        tasks = get_tasks()
        for t in tasks:
            if t.seq_id == seq_id or t.seq_id == seq_id.upper():
                t.status = TaskStatus.DONE
                t.last_done = date.today().isoformat()
                save_task(t)
                result = f"Task {seq_id} marked done: {t.title}"
                if t.project_id:
                    project_stats(t.project_id, _tasks=tasks)
                for gid in t.aligns_to:
                    pct = _recompute_goal_progress(gid, _tasks=tasks)
                    if pct is not None:
                        result += f"\n  Goal progress updated: {pct:.0f}%"
                unblocked = _check_unblocked(t.id)
                if unblocked:
                    result += "\n  Unblocked: " + ", ".join(unblocked)
                return result
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


# ── Period boundaries ─────────────────────────────────────────────────────────

def period_start(scope: str, for_date: Optional[date] = None) -> date:
    d = for_date or date.today()
    if scope == "daily":
        return d
    if scope == "weekly":
        dow = d.weekday()
        days_since_sunday = (dow + 1) % 7
        return d - timedelta(days=days_since_sunday)
    if scope == "monthly":
        return d.replace(day=1)
    if scope == "quarterly":
        q_start_month = ((d.month - 1) // 3) * 3 + 1
        return d.replace(month=q_start_month, day=1)
    return d


def period_end(scope: str, for_date: Optional[date] = None) -> date:
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
    d = from_date or date.today()
    days_until_sunday = (6 - d.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    return d + timedelta(days=days_until_sunday)


# ── Resilience: Bankruptcy settlement ─────────────────────────────────────────

def settle_bankruptcy() -> dict:
    from .projects import get_projects, save_project
    from .tasks import get_tasks, save_tasks

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
    from .tasks import get_tasks

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
        key = t.dimension.value if t.dimension is not None else "unset"
        counts[key] = counts.get(key, 0) + 1

    return max(counts, key=lambda k: counts.get(k, 0))


def get_season_drift(config: ViyugamConfig) -> Optional[str]:
    if not config.season:
        return None
    intended = config.season.focus.value if hasattr(config.season.focus, "value") else str(config.season.focus)
    actual = calculate_actual_season()
    if actual and actual != intended:
        return (
            f"Intended focus: {intended} -- "
            f"Actual (last 30 days): {actual}. "
            "A gap worth noticing."
        )
    return None


def get_avg_dimension_scores(days: int = 14) -> list[dict]:
    from .journal import get_recent_summaries

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


# ── Coherence Score ───────────────────────────────────────────────────────────

def _coherence_breakdown(done_tasks: list) -> dict[str, float]:
    counts: dict[str, int] = {}
    for t in done_tasks:
        key = t.dimension.value if t.dimension is not None else "unset"
        counts[key] = counts.get(key, 0) + 1
    total = sum(counts.values())
    return {k: round(v / total * 100, 1) for k, v in counts.items()}


def _coherence_season_score(config: ViyugamConfig, breakdown: dict[str, float]) -> int:
    if not config.season:
        return 0
    focus = config.season.focus.value if hasattr(config.season.focus, "value") else str(config.season.focus)
    focus_pct = breakdown.get(focus, 0)
    return min(40, int(focus_pct * 0.4))


def _coherence_balance_score(config: ViyugamConfig, breakdown: dict[str, float]) -> int:
    balance_score = 40
    for dim, pct in breakdown.items():
        if config.season and dim == (config.season.focus.value if hasattr(config.season.focus, "value") else ""):
            continue
        if pct > 50:
            balance_score = max(0, balance_score - int((pct - 50)))
    return balance_score


def _coherence_narrative(config: ViyugamConfig, breakdown: dict[str, float], total_score: int) -> str:
    focus_name = config.season.focus.value if config.season else "unset"
    top_dim = max(breakdown, key=lambda k: breakdown.get(k, 0.0)) if breakdown else "none"
    if total_score >= 75:
        return f"Strong coherence. Top dimension: {top_dim} ({breakdown.get(top_dim, 0)}%). Season focus '{focus_name}' is reflected in your work."
    elif total_score >= 50:
        return f"Moderate coherence. You're partially aligned with '{focus_name}' season but {top_dim} is dominating at {breakdown.get(top_dim, 0)}%."
    else:
        return f"Low coherence. Most energy went to '{top_dim}' ({breakdown.get(top_dim, 0)}%) while your stated season is '{focus_name}'. Worth examining."


def compute_coherence_score(config: ViyugamConfig, days: int = 7) -> dict:
    from .tasks import get_tasks

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    done_tasks = [
        t for t in get_tasks(status="done")
        if t.scheduled_date and t.scheduled_date >= cutoff and t.dimension
    ]

    if not done_tasks:
        return {"score": None, "breakdown": {}, "narrative": "Not enough data yet."}

    breakdown = _coherence_breakdown(done_tasks)
    season_score = _coherence_season_score(config, breakdown)
    balance_score = _coherence_balance_score(config, breakdown)
    activity_score = min(20, len(done_tasks) * 2)
    total_score = season_score + balance_score + activity_score
    narrative = _coherence_narrative(config, breakdown, total_score)

    return {"score": total_score, "breakdown": breakdown, "narrative": narrative}


# ── Energy pattern ────────────────────────────────────────────────────────────

def get_energy_pattern() -> dict:
    from viyugam.agents.energy import get_energy_pattern as _get
    return _get(_paths.JOURNALS_DIR, _paths.ENERGY_CACHE_FILE)
