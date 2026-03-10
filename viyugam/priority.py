"""
priority.py — GPS Priority Engine for Viyugam.

Pure computation, no Claude calls, sub-second.
Computes: constraint scores, goal trajectories, nudges, and the single directive task.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from viyugam.models import (
    Task, Goal, Nudge, NudgeType, PriorityContext,
    TaskStatus, Dimension, Trajectory,
)
import viyugam.storage as storage


# ── Scoring weights ───────────────────────────────────────────────────────────

W_GOAL_IMPACT  = 0.30
W_CONSTRAINT   = 0.30
W_URGENCY      = 0.20
W_CRITICALITY  = 0.15
W_ENERGY_FIT   = 0.05


# ── Core: get_context() ──────────────────────────────────────────────────────

def get_context() -> PriorityContext:
    """Compute full priority context. Sub-second, no API calls.
    Loads all data once and passes to sub-functions."""
    # Single load of all data
    all_tasks = storage.get_tasks(include_habits=True)
    all_non_habit = [t for t in all_tasks if not t.is_habit]
    habits = [t for t in all_tasks if t.is_habit]
    active_tasks = [t for t in all_non_habit
                    if t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS)]
    goals = [g for g in storage.get_goals(active_only=True) if not g.is_pseudo]

    # Score all tasks
    scored = _score_tasks(active_tasks, goals)

    # Pick directive (highest composite score)
    directive = None
    why = ""
    unblocks: list[str] = []
    if scored:
        top = scored[0]
        directive = top.model_dump()
        directive["_composite"] = top.ai_priority_score
        why, unblocks = _trace_bottleneck_and_unblocks(top, active_tasks)

    # Goal trajectories (needs all tasks including done for progress calc)
    trajectories = compute_goal_trajectories(goals, all_non_habit)

    # Nudges (pass pre-loaded data to avoid re-reads)
    nudges = compute_nudges(all_non_habit, habits, goals)

    # Energy fit
    energy_str = _current_energy_window()

    return PriorityContext(
        directive_task=directive,
        why_bottleneck=why,
        unblocks=unblocks,
        nudges=nudges,
        goal_trajectories=trajectories,
        energy_fit=energy_str,
    )


# ── Task scoring ─────────────────────────────────────────────────────────────

def _score_tasks(tasks: list[Task], goals: list[Goal]) -> list[Task]:
    """Score and sort tasks by composite priority. Returns sorted list (highest first)."""
    if not tasks:
        return []

    # Build adjacency: task_id -> set of downstream task IDs
    downstream: dict[str, set[str]] = {}
    for t in tasks:
        for blocked_id in t.blocks:
            downstream.setdefault(t.id, set()).add(blocked_id)

    # Count downstream (transitive)
    downstream_counts: dict[str, int] = {}
    for t in tasks:
        downstream_counts[t.id] = _count_downstream(t.id, downstream, set())
    max_downstream = max(downstream_counts.values()) if downstream_counts else 1

    # Goal index
    active_goal_ids = {g.id for g in goals}
    total_active_goals = len(active_goal_ids) or 1

    today = date.today()

    for t in tasks:
        # Constraint score: how many things does this unblock?
        dc = downstream_counts.get(t.id, 0)
        constraint = dc / max_downstream if max_downstream > 0 else 0.0

        # Goal impact: how many active goals does this serve?
        aligned = len([gid for gid in t.aligns_to if gid in active_goal_ids])
        goal_impact = aligned / total_active_goals

        # Urgency from due date
        urgency = _compute_urgency(t, today)

        # Criticality from priority field
        crit_map = {"high": 1.0, "medium": 0.5, "low": 0.2}
        criticality = crit_map.get(t.priority, 0.5)

        # Energy fit (simplified — time-of-day matching)
        energy_fit = _compute_energy_fit(t)

        # Composite score
        composite = (
            W_GOAL_IMPACT * goal_impact
            + W_CONSTRAINT * constraint
            + W_URGENCY * urgency
            + W_CRITICALITY * criticality
            + W_ENERGY_FIT * energy_fit
        )

        t.constraint_score = round(constraint, 3)
        t.ai_priority_score = round(composite, 3)

    # Sort descending by composite
    tasks.sort(key=lambda t: t.ai_priority_score or 0, reverse=True)
    return tasks


def _count_downstream(task_id: str, adj: dict[str, set[str]], visited: set[str]) -> int:
    """Count transitive downstream tasks (BFS/DFS)."""
    if task_id in visited:
        return 0
    visited.add(task_id)
    direct = adj.get(task_id, set())
    count = len(direct)
    for child in direct:
        count += _count_downstream(child, adj, visited)
    return count


def _compute_urgency(task: Task, today: date) -> float:
    """0-1 urgency score based on due date proximity."""
    due_str = task.due or task.scheduled_date
    if not due_str:
        return 0.0
    try:
        due = date.fromisoformat(due_str)
    except (ValueError, TypeError):
        return 0.0
    days_until = (due - today).days
    if days_until < 0:
        return 1.0  # overdue
    if days_until == 0:
        return 0.95
    if days_until <= 2:
        return 0.8
    if days_until <= 7:
        return 0.5
    if days_until <= 14:
        return 0.3
    return 0.1


def _compute_energy_fit(task: Task) -> float:
    """Simple energy fit based on time of day vs task energy cost."""
    hour = datetime.now().hour
    # Morning (6-12): good for high energy. Afternoon (12-17): medium. Evening: low.
    if hour < 12:
        window_energy = 8
    elif hour < 17:
        window_energy = 5
    else:
        window_energy = 3
    # Perfect fit = 1.0, mismatch = lower
    diff = abs(task.energy_cost - window_energy)
    return max(0.0, 1.0 - diff / 10.0)


def _current_energy_window() -> str:
    """Human-readable current energy window."""
    hour = datetime.now().hour
    if hour < 12:
        return "morning (peak energy)"
    elif hour < 17:
        return "afternoon (moderate)"
    else:
        return "evening (wind-down)"


def _trace_bottleneck_and_unblocks(task: Task, all_tasks: list[Task]) -> tuple[str, list[str]]:
    """Explain why this task is the bottleneck and what it unblocks.
    Returns (why_string, unblocked_titles)."""
    parts = []
    blocked_titles = []
    for bid in task.blocks:
        for t in all_tasks:
            if t.id == bid or t.seq_id == bid:
                blocked_titles.append(t.title)
                break
    if blocked_titles:
        parts.append(f"blocks {len(blocked_titles)} task(s)")

    if task.aligns_to:
        parts.append(f"serves {len(task.aligns_to)} goal(s)")

    if task.due:
        try:
            days = (date.fromisoformat(task.due) - date.today()).days
            if days < 0:
                parts.append(f"overdue by {abs(days)}d")
            elif days <= 2:
                parts.append(f"due in {days}d")
        except (ValueError, TypeError):
            pass

    if task.priority == "high":
        parts.append("high priority")

    why = ", ".join(parts) if parts else "highest composite score"
    return why, blocked_titles


# ── Goal trajectories ────────────────────────────────────────────────────────

def compute_goal_trajectories(
    goals: list[Goal],
    all_tasks: list[Task],
) -> list[dict]:
    """Compute trajectory for each active goal based on aligned task progress."""
    today = date.today()
    results = []

    for g in goals:
        aligned = [t for t in all_tasks if g.id in t.aligns_to]
        if not aligned:
            # No aligned tasks — can't compute trajectory
            results.append({
                "goal_id": g.id,
                "seq_id": g.seq_id,
                "title": g.title,
                "dimension": g.dimension.value if g.dimension else None,
                "progress_pct": 0.0,
                "trajectory": Trajectory.OFF_TRACK,
                "bottleneck_task": None,
                "aligned_count": 0,
            })
            continue

        done = [t for t in aligned if t.status == TaskStatus.DONE]
        progress = len(done) / len(aligned) * 100.0

        # Classify trajectory (simple heuristic: compare to linear expected)
        trajectory = _classify_trajectory(progress, g, today)

        # Find bottleneck: highest constraint_score among undone aligned tasks
        undone = [t for t in aligned if t.status != TaskStatus.DONE]
        bottleneck = None
        if undone:
            # Sort by constraint_score descending
            undone_scored = sorted(undone, key=lambda t: t.constraint_score or 0, reverse=True)
            bottleneck = undone_scored[0].seq_id or undone_scored[0].id

        # Update goal model fields
        g.progress_pct = round(progress, 1)
        g.trajectory = trajectory
        g.bottleneck_task = bottleneck

        results.append({
            "goal_id": g.id,
            "seq_id": g.seq_id,
            "title": g.title,
            "dimension": g.dimension.value if g.dimension else None,
            "progress_pct": round(progress, 1),
            "trajectory": trajectory,
            "bottleneck_task": bottleneck,
            "aligned_count": len(aligned),
        })

    return results


def _classify_trajectory(progress: float, goal: Goal, today: date) -> Trajectory:
    """Classify goal as on_track, at_risk, or off_track."""
    # Use quarter end as default horizon
    q_end = _quarter_end(today)
    total_days = (q_end - _quarter_start(today)).days or 1
    elapsed_days = (today - _quarter_start(today)).days
    expected_pct = (elapsed_days / total_days) * 100.0

    if progress >= expected_pct * 0.8:
        return Trajectory.ON_TRACK
    elif progress >= expected_pct * 0.5:
        return Trajectory.AT_RISK
    else:
        return Trajectory.OFF_TRACK


def _quarter_start(d: date) -> date:
    q = (d.month - 1) // 3
    return date(d.year, q * 3 + 1, 1)


def _quarter_end(d: date) -> date:
    q = (d.month - 1) // 3
    end_month = (q + 1) * 3
    if end_month == 12:
        return date(d.year, 12, 31)
    return date(d.year, end_month + 1, 1) - timedelta(days=1)


# ── Nudge system ─────────────────────────────────────────────────────────────

def compute_nudges(
    tasks: list[Task] | None = None,
    habits: list[Task] | None = None,
    goals: list[Goal] | None = None,
) -> list[Nudge]:
    """Compute all nudges based on current system state. Deduplicates against dismissed.
    Accepts pre-loaded data to avoid redundant disk reads."""
    nudges: list[Nudge] = []
    today = date.today()

    # Load dismissed nudges for dedup
    dismissed = _get_dismissed_keys()

    # Use pre-loaded data or fall back to loading
    if tasks is None:
        tasks = storage.get_tasks(include_habits=False)
    if habits is None:
        habits = [t for t in storage.get_tasks(include_habits=True) if t.is_habit]
    if goals is None:
        goals = storage.get_goals(active_only=True)

    # DEADLINE: tasks due within 2 days
    for t in tasks:
        if t.status == TaskStatus.DONE:
            continue
        due_str = t.due or t.scheduled_date
        if not due_str:
            continue
        try:
            due = date.fromisoformat(due_str)
        except (ValueError, TypeError):
            continue
        days_until = (due - today).days
        if days_until <= 2:
            key = f"{t.id}:{NudgeType.DEADLINE}"
            if key not in dismissed:
                severity = "critical" if days_until < 0 else ("warn" if days_until <= 1 else "info")
                label = f"overdue by {abs(days_until)}d" if days_until < 0 else (
                    "due today" if days_until == 0 else f"due in {days_until}d")
                nudges.append(Nudge(
                    nudge_type=NudgeType.DEADLINE,
                    entity_id=t.id,
                    message=f"'{t.title}' {label}",
                    severity=severity,
                ))

    # STREAK: habits with broken streaks
    for h in habits:
        if h.last_done and h.last_done < (today - timedelta(days=1)).isoformat():
            key = f"{h.id}:{NudgeType.STREAK}"
            if key not in dismissed:
                nudges.append(Nudge(
                    nudge_type=NudgeType.STREAK,
                    entity_id=h.id,
                    message=f"'{h.title}' streak broken (last: {h.last_done})",
                    severity="warn",
                ))

    # SNOOZE: tasks snoozed 3+ times
    for t in tasks:
        if t.snooze_count >= 3 and t.status != TaskStatus.DONE:
            key = f"{t.id}:{NudgeType.SNOOZE}"
            if key not in dismissed:
                nudges.append(Nudge(
                    nudge_type=NudgeType.SNOOZE,
                    entity_id=t.id,
                    message=f"'{t.title}' snoozed {t.snooze_count} times -- decide or delete",
                    severity="warn",
                ))

    # GOAL_RISK: goals with at_risk or off_track trajectory
    non_pseudo_goals = [g for g in goals if not g.is_pseudo]
    trajectories = compute_goal_trajectories(non_pseudo_goals, tasks)
    for gt in trajectories:
        traj = gt["trajectory"]
        if traj in (Trajectory.AT_RISK, Trajectory.OFF_TRACK):
            key = f"{gt['goal_id']}:{NudgeType.GOAL_RISK}"
            if key not in dismissed:
                severity = "critical" if traj == Trajectory.OFF_TRACK else "warn"
                nudges.append(Nudge(
                    nudge_type=NudgeType.GOAL_RISK,
                    entity_id=gt["goal_id"],
                    message=f"Goal '{gt['title']}' {traj.value.replace('_', ' ')} ({gt['progress_pct']:.0f}%)",
                    severity=severity,
                ))

    # BUDGET_DRIFT: budget >80% spent
    try:
        budgets = storage.get_budgets()
        for b in budgets:
            if b.total_limit > 0 and b.spent / b.total_limit > 0.8:
                key = f"{b.id}:{NudgeType.BUDGET_DRIFT}"
                if key not in dismissed:
                    pct = int(b.spent / b.total_limit * 100)
                    nudges.append(Nudge(
                        nudge_type=NudgeType.BUDGET_DRIFT,
                        entity_id=b.id,
                        message=f"Budget '{b.name}' at {pct}% spent",
                        severity="warn" if pct < 95 else "critical",
                    ))
    except Exception:
        pass

    # STALE_TASK: todo tasks older than 14 days with no activity
    for t in tasks:
        if t.status == TaskStatus.TODO:
            try:
                created = datetime.fromisoformat(t.created_at).date()
                age = (today - created).days
                if age >= 14:
                    key = f"{t.id}:{NudgeType.STALE_TASK}"
                    if key not in dismissed:
                        nudges.append(Nudge(
                            nudge_type=NudgeType.STALE_TASK,
                            entity_id=t.id,
                            message=f"'{t.title}' has been sitting for {age} days",
                            severity="info",
                        ))
            except (ValueError, TypeError):
                pass

    # SEASON_DRIFT: actual vs intended season misalignment
    try:
        config = storage.load_config()
        drift = storage.get_season_drift(config)
        if drift:
            key = f"season:{NudgeType.SEASON_DRIFT}"
            if key not in dismissed:
                nudges.append(Nudge(
                    nudge_type=NudgeType.SEASON_DRIFT,
                    entity_id="season",
                    message=drift,
                    severity="warn",
                ))
    except Exception:
        pass

    return nudges


def _get_dismissed_keys() -> set[str]:
    """Load dismissed nudge keys (entity_id:nudge_type) from storage."""
    try:
        stored = storage.get_stored_nudges()
        return {f"{n['entity_id']}:{n['nudge_type']}" for n in stored if n.get("dismissed")}
    except Exception:
        return set()


# ── Prompt formatting ────────────────────────────────────────────────────────

def format_context_for_prompt(ctx: PriorityContext | None = None) -> str:
    """Format PriorityContext as a text block for injection into agent prompts.
    Shared by chairman and reviewer to avoid duplication."""
    if ctx is None:
        ctx = get_context()
    lines = []
    if ctx.directive_task:
        dt = ctx.directive_task
        lines.append(f"GPS DIRECTIVE: {dt.get('title', '')} (score: {dt.get('_composite', 'N/A')})")
        if ctx.why_bottleneck:
            lines.append(f"  Why: {ctx.why_bottleneck}")
        if ctx.unblocks:
            lines.append(f"  Unblocks: {', '.join(ctx.unblocks[:3])}")
    if ctx.goal_trajectories:
        lines.append("GOAL TRAJECTORIES:")
        for gt in ctx.goal_trajectories[:5]:
            traj = gt.get("trajectory", "")
            traj_str = traj.value if hasattr(traj, "value") else str(traj)
            lines.append(f"  {gt.get('seq_id', '')} {gt.get('title', '')}: {traj_str} ({gt.get('progress_pct', 0):.0f}%)")
    if ctx.nudges:
        lines.append("ACTIVE NUDGES:")
        for n in ctx.nudges[:5]:
            lines.append(f"  [{n.severity}] {n.message}")
    return "\n".join(lines)
