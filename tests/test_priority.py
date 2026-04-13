"""
test_priority.py — Tests for the GPS Priority Engine (priority.py).
Pure computation, no API calls.
"""
from __future__ import annotations

import pytest
from datetime import date, timedelta, datetime
from unittest.mock import patch

from viyugam.models import (
    Goal,
    Nudge,
    NudgeType,
    PriorityContext,
    Task,
    TaskStatus,
    Trajectory,
    Dimension,
    Budget,
)
from viyugam.priority import (
    _score_tasks,
    _count_downstream,
    _compute_urgency,
    _compute_energy_fit,
    _trace_bottleneck_and_unblocks,
    _current_energy_window,
    _classify_trajectory,
    _quarter_start,
    _quarter_end,
    compute_goal_trajectories,
    compute_nudges,
    format_context_for_prompt,
)


# ── _score_tasks ─────────────────────────────────────────────────────────────

def test_score_tasks_empty():
    assert _score_tasks([], []) == []


def test_score_tasks_single_task_no_goals():
    t = Task(title="Simple task")
    result = _score_tasks([t], [])
    assert len(result) == 1
    assert result[0].ai_priority_score is not None
    assert result[0].ai_priority_score >= 0


def test_score_tasks_higher_priority_higher_score():
    high = Task(title="High priority", priority="high")
    low = Task(title="Low priority", priority="low")
    result = _score_tasks([low, high], [])
    assert result[0].ai_priority_score >= result[1].ai_priority_score


def test_score_tasks_goal_alignment_boosts_score():
    g = Goal(title="Ship product", dimension=Dimension.CAREER)
    aligned = Task(title="Aligned", aligns_to=[g.id])
    unaligned = Task(title="Unaligned", aligns_to=[])
    # Give same priority/due so only goal_impact differs
    aligned.priority = "medium"
    unaligned.priority = "medium"
    result = _score_tasks([unaligned, aligned], [g])
    # Aligned task should score higher
    aligned_result = next(t for t in result if t.title == "Aligned")
    unaligned_result = next(t for t in result if t.title == "Unaligned")
    assert aligned_result.ai_priority_score > unaligned_result.ai_priority_score


def test_score_tasks_blocking_chain_boosts_constraint():
    t1 = Task(title="Blocker", blocks=["child1"])
    t2 = Task(id="child1", title="Child")
    result = _score_tasks([t1, t2], [])
    blocker = next(t for t in result if t.title == "Blocker")
    child = next(t for t in result if t.title == "Child")
    assert blocker.constraint_score > child.constraint_score


def test_score_tasks_overdue_gets_high_urgency():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    overdue = Task(title="Overdue", due=yesterday)
    future = Task(title="Future", due=(date.today() + timedelta(days=30)).isoformat())
    result = _score_tasks([future, overdue], [])
    overdue_t = next(t for t in result if t.title == "Overdue")
    future_t = next(t for t in result if t.title == "Future")
    assert overdue_t.ai_priority_score > future_t.ai_priority_score


def test_score_tasks_sets_constraint_score():
    t = Task(title="Solo task")
    result = _score_tasks([t], [])
    assert result[0].constraint_score is not None
    assert result[0].constraint_score == 0.0  # no downstream


def test_score_tasks_sorted_descending():
    tasks = [
        Task(title="Low", priority="low"),
        Task(title="High", priority="high"),
        Task(title="Medium", priority="medium"),
    ]
    result = _score_tasks(tasks, [])
    scores = [t.ai_priority_score for t in result]
    assert scores == sorted(scores, reverse=True)


# ── _count_downstream ────────────────────────────────────────────────────────

def test_count_downstream_empty():
    assert _count_downstream("t1", {}, set()) == 0


def test_count_downstream_direct():
    adj = {"t1": {"t2", "t3"}}
    assert _count_downstream("t1", adj, set()) == 2


def test_count_downstream_transitive():
    adj = {"t1": {"t2"}, "t2": {"t3"}}
    assert _count_downstream("t1", adj, set()) == 2


def test_count_downstream_cycle_safe():
    adj = {"t1": {"t2"}, "t2": {"t1"}}
    # Should not infinite loop; counts t2 (direct) + t1-via-t2 (back-edge counted before visited check)
    assert _count_downstream("t1", adj, set()) == 2


# ── _compute_urgency ────────────────────────────────────────────────────────

def test_urgency_no_due_date():
    t = Task(title="No due")
    assert _compute_urgency(t, date.today()) == 0.0


def test_urgency_overdue():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    t = Task(title="Overdue", due=yesterday)
    assert _compute_urgency(t, date.today()) == 1.0


def test_urgency_due_today():
    t = Task(title="Due today", due=date.today().isoformat())
    assert _compute_urgency(t, date.today()) == 0.95


def test_urgency_due_tomorrow():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    t = Task(title="Due tomorrow", due=tomorrow)
    assert _compute_urgency(t, date.today()) == 0.8


def test_urgency_due_in_5_days():
    future = (date.today() + timedelta(days=5)).isoformat()
    t = Task(title="Due soon", due=future)
    assert _compute_urgency(t, date.today()) == 0.5


def test_urgency_due_in_10_days():
    future = (date.today() + timedelta(days=10)).isoformat()
    t = Task(title="Due later", due=future)
    assert _compute_urgency(t, date.today()) == 0.3


def test_urgency_due_far_future():
    future = (date.today() + timedelta(days=30)).isoformat()
    t = Task(title="Far future", due=future)
    assert _compute_urgency(t, date.today()) == 0.1


def test_urgency_invalid_date():
    t = Task(title="Bad date", due="not-a-date")
    assert _compute_urgency(t, date.today()) == 0.0


def test_urgency_scheduled_date_fallback():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    t = Task(title="Scheduled", scheduled_date=tomorrow)
    assert _compute_urgency(t, date.today()) == 0.8


# ── _compute_energy_fit ──────────────────────────────────────────────────────

def test_energy_fit_morning_high_energy():
    t = Task(title="Heavy work", energy_cost=8)
    with patch("viyugam.priority.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 10, 9, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = _compute_energy_fit(t)
    assert result > 0.5


def test_energy_fit_evening_low_energy():
    t = Task(title="Light reading", energy_cost=3)
    with patch("viyugam.priority.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 10, 20, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = _compute_energy_fit(t)
    assert result > 0.5


def test_energy_fit_mismatch():
    t = Task(title="Heavy at night", energy_cost=10)
    with patch("viyugam.priority.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 10, 20, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = _compute_energy_fit(t)
    # window_energy=3, diff=7, max(0, 1 - 7/10) = 0.3
    assert result == pytest.approx(0.3, abs=0.01)


# ── _current_energy_window ───────────────────────────────────────────────────

def test_energy_window_morning():
    with patch("viyugam.priority.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 10, 9, 0)
        result = _current_energy_window()
    assert "morning" in result


def test_energy_window_afternoon():
    with patch("viyugam.priority.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 10, 14, 0)
        result = _current_energy_window()
    assert "afternoon" in result


def test_energy_window_evening():
    with patch("viyugam.priority.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 10, 20, 0)
        result = _current_energy_window()
    assert "evening" in result


# ── _trace_bottleneck_and_unblocks ───────────────────────────────────────────

def test_trace_no_blocks_no_goals():
    t = Task(title="Simple task")
    why, unblocks = _trace_bottleneck_and_unblocks(t, [])
    assert why == "highest composite score"
    assert unblocks == []


def test_trace_with_blocks():
    child = Task(title="Blocked task")
    blocker = Task(title="Blocker", blocks=[child.id])
    why, unblocks = _trace_bottleneck_and_unblocks(blocker, [blocker, child])
    assert "blocks 1 task(s)" in why
    assert "Blocked task" in unblocks


def test_trace_with_goals():
    t = Task(title="Goal task", aligns_to=["goal1"])
    why, unblocks = _trace_bottleneck_and_unblocks(t, [t])
    assert "serves 1 goal(s)" in why


def test_trace_overdue():
    yesterday = (date.today() - timedelta(days=3)).isoformat()
    t = Task(title="Overdue task", due=yesterday)
    why, unblocks = _trace_bottleneck_and_unblocks(t, [t])
    assert "overdue by 3d" in why


def test_trace_due_soon():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    t = Task(title="Due soon", due=tomorrow)
    why, unblocks = _trace_bottleneck_and_unblocks(t, [t])
    assert "due in 1d" in why


def test_trace_high_priority():
    t = Task(title="High prio", priority="high")
    why, unblocks = _trace_bottleneck_and_unblocks(t, [t])
    assert "high priority" in why


def test_trace_combined():
    child = Task(title="Child")
    t = Task(title="Critical", blocks=[child.id], aligns_to=["g1"], priority="high")
    why, unblocks = _trace_bottleneck_and_unblocks(t, [t, child])
    assert "blocks 1 task(s)" in why
    assert "serves 1 goal(s)" in why
    assert "high priority" in why


# ── Quarter helpers ──────────────────────────────────────────────────────────

def test_quarter_start_q1():
    assert _quarter_start(date(2026, 2, 15)) == date(2026, 1, 1)


def test_quarter_start_q2():
    assert _quarter_start(date(2026, 5, 10)) == date(2026, 4, 1)


def test_quarter_start_q3():
    assert _quarter_start(date(2026, 8, 1)) == date(2026, 7, 1)


def test_quarter_start_q4():
    assert _quarter_start(date(2026, 12, 31)) == date(2026, 10, 1)


def test_quarter_end_q1():
    assert _quarter_end(date(2026, 2, 15)) == date(2026, 3, 31)


def test_quarter_end_q4():
    assert _quarter_end(date(2026, 11, 15)) == date(2026, 12, 31)


def test_quarter_end_q2():
    assert _quarter_end(date(2026, 5, 10)) == date(2026, 6, 30)


# ── _classify_trajectory ─────────────────────────────────────────────────────

def test_classify_on_track():
    g = Goal(title="On track", dimension=Dimension.CAREER)
    today = date.today()
    qs = _quarter_start(today)
    qe = _quarter_end(today)
    total = (qe - qs).days or 1
    elapsed = (today - qs).days
    expected = (elapsed / total) * 100
    # 80% of expected = on_track
    result = _classify_trajectory(expected, g, today)
    assert result == Trajectory.ON_TRACK


def test_classify_at_risk():
    g = Goal(title="At risk", dimension=Dimension.CAREER)
    today = date.today()
    qs = _quarter_start(today)
    qe = _quarter_end(today)
    total = (qe - qs).days or 1
    elapsed = (today - qs).days
    expected = (elapsed / total) * 100
    # Between 50% and 80% of expected = at_risk
    mid = expected * 0.6  # 60% of expected
    result = _classify_trajectory(mid, g, today)
    assert result == Trajectory.AT_RISK


def test_classify_off_track():
    g = Goal(title="Off track", dimension=Dimension.CAREER)
    today = date.today()
    # 0% progress
    result = _classify_trajectory(0.0, g, today)
    assert result == Trajectory.OFF_TRACK


# ── compute_goal_trajectories ────────────────────────────────────────────────

def test_goal_trajectories_no_goals():
    result = compute_goal_trajectories([], [])
    assert result == []


def test_goal_trajectories_no_aligned_tasks():
    g = Goal(title="Lonely goal", dimension=Dimension.HEALTH)
    result = compute_goal_trajectories([g], [])
    assert len(result) == 1
    assert result[0]["progress_pct"] == 0.0
    assert result[0]["trajectory"] == Trajectory.OFF_TRACK
    assert result[0]["bottleneck_task"] is None
    assert result[0]["aligned_count"] == 0


def test_goal_trajectories_all_done():
    g = Goal(title="Done goal", dimension=Dimension.CAREER)
    t1 = Task(title="T1", status=TaskStatus.DONE, aligns_to=[g.id])
    t2 = Task(title="T2", status=TaskStatus.DONE, aligns_to=[g.id])
    result = compute_goal_trajectories([g], [t1, t2])
    assert len(result) == 1
    assert result[0]["progress_pct"] == 100.0
    assert result[0]["trajectory"] == Trajectory.ON_TRACK
    assert result[0]["aligned_count"] == 2


def test_goal_trajectories_partial_progress():
    g = Goal(title="Partial", dimension=Dimension.LEARNING)
    t1 = Task(title="T1", status=TaskStatus.DONE, aligns_to=[g.id])
    t2 = Task(title="T2", status=TaskStatus.TODO, aligns_to=[g.id])
    result = compute_goal_trajectories([g], [t1, t2])
    assert result[0]["progress_pct"] == 50.0
    assert result[0]["bottleneck_task"] is not None
    assert result[0]["aligned_count"] == 2


def test_goal_trajectories_bottleneck_is_highest_constraint():
    g = Goal(title="Goal", dimension=Dimension.CAREER)
    t1 = Task(title="T1", status=TaskStatus.TODO, aligns_to=[g.id], constraint_score=0.5)
    t2 = Task(title="T2", status=TaskStatus.TODO, aligns_to=[g.id], constraint_score=0.9)
    result = compute_goal_trajectories([g], [t1, t2])
    # t2 has higher constraint_score, so it's the bottleneck
    assert result[0]["bottleneck_task"] == (t2.seq_id or t2.id)


def test_goal_trajectories_multiple_goals():
    g1 = Goal(title="G1", dimension=Dimension.HEALTH)
    g2 = Goal(title="G2", dimension=Dimension.CAREER)
    t1 = Task(title="T1", status=TaskStatus.DONE, aligns_to=[g1.id])
    t2 = Task(title="T2", status=TaskStatus.TODO, aligns_to=[g2.id])
    result = compute_goal_trajectories([g1, g2], [t1, t2])
    assert len(result) == 2


def test_goal_trajectories_updates_goal_model():
    g = Goal(title="Test", dimension=Dimension.JOY)
    t = Task(title="T", status=TaskStatus.DONE, aligns_to=[g.id])
    compute_goal_trajectories([g], [t])
    assert g.progress_pct == 100.0
    assert g.trajectory == Trajectory.ON_TRACK


# ── compute_nudges ───────────────────────────────────────────────────────────

def test_nudges_deadline_overdue():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    t = Task(title="Overdue task", due=yesterday, status=TaskStatus.TODO)
    nudges = compute_nudges(tasks=[t], habits=[], goals=[])
    deadline_nudges = [n for n in nudges if n.nudge_type == NudgeType.DEADLINE]
    assert len(deadline_nudges) >= 1
    assert deadline_nudges[0].severity == "critical"
    assert "overdue" in deadline_nudges[0].message.lower()


def test_nudges_deadline_due_today():
    today = date.today().isoformat()
    t = Task(title="Due today", due=today, status=TaskStatus.TODO)
    nudges = compute_nudges(tasks=[t], habits=[], goals=[])
    deadline_nudges = [n for n in nudges if n.nudge_type == NudgeType.DEADLINE]
    assert len(deadline_nudges) >= 1
    assert deadline_nudges[0].severity == "warn"
    assert "due today" in deadline_nudges[0].message


def test_nudges_deadline_due_tomorrow():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    t = Task(title="Due tomorrow", due=tomorrow, status=TaskStatus.TODO)
    nudges = compute_nudges(tasks=[t], habits=[], goals=[])
    deadline_nudges = [n for n in nudges if n.nudge_type == NudgeType.DEADLINE]
    assert len(deadline_nudges) >= 1
    assert deadline_nudges[0].severity == "warn"


def test_nudges_deadline_due_in_2_days():
    future = (date.today() + timedelta(days=2)).isoformat()
    t = Task(title="Due in 2 days", due=future, status=TaskStatus.TODO)
    nudges = compute_nudges(tasks=[t], habits=[], goals=[])
    deadline_nudges = [n for n in nudges if n.nudge_type == NudgeType.DEADLINE]
    assert len(deadline_nudges) >= 1
    assert deadline_nudges[0].severity == "info"


def test_nudges_no_deadline_for_far_future():
    future = (date.today() + timedelta(days=10)).isoformat()
    t = Task(title="Far future", due=future, status=TaskStatus.TODO)
    nudges = compute_nudges(tasks=[t], habits=[], goals=[])
    deadline_nudges = [n for n in nudges if n.nudge_type == NudgeType.DEADLINE]
    assert len(deadline_nudges) == 0


def test_nudges_no_deadline_for_done_task():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    t = Task(title="Done overdue", due=yesterday, status=TaskStatus.DONE)
    nudges = compute_nudges(tasks=[t], habits=[], goals=[])
    deadline_nudges = [n for n in nudges if n.nudge_type == NudgeType.DEADLINE]
    assert len(deadline_nudges) == 0


def test_nudges_streak_broken():
    three_days_ago = (date.today() - timedelta(days=3)).isoformat()
    h = Task(title="Exercise", is_habit=True, last_done=three_days_ago)
    nudges = compute_nudges(tasks=[], habits=[h], goals=[])
    streak_nudges = [n for n in nudges if n.nudge_type == NudgeType.STREAK]
    assert len(streak_nudges) >= 1
    assert "streak broken" in streak_nudges[0].message


def test_nudges_streak_not_broken_if_recent():
    today = date.today().isoformat()
    h = Task(title="Exercise", is_habit=True, last_done=today)
    nudges = compute_nudges(tasks=[], habits=[h], goals=[])
    streak_nudges = [n for n in nudges if n.nudge_type == NudgeType.STREAK]
    assert len(streak_nudges) == 0


def test_nudges_snooze():
    t = Task(title="Snoozed task", snooze_count=4, status=TaskStatus.TODO)
    nudges = compute_nudges(tasks=[t], habits=[], goals=[])
    snooze_nudges = [n for n in nudges if n.nudge_type == NudgeType.SNOOZE]
    assert len(snooze_nudges) >= 1
    assert "snoozed 4 times" in snooze_nudges[0].message


def test_nudges_snooze_below_threshold():
    t = Task(title="Barely snoozed", snooze_count=2, status=TaskStatus.TODO)
    nudges = compute_nudges(tasks=[t], habits=[], goals=[])
    snooze_nudges = [n for n in nudges if n.nudge_type == NudgeType.SNOOZE]
    assert len(snooze_nudges) == 0


def test_nudges_goal_risk():
    g = Goal(title="Off track goal", dimension=Dimension.CAREER)
    # No aligned tasks => off_track trajectory
    nudges = compute_nudges(tasks=[], habits=[], goals=[g])
    goal_nudges = [n for n in nudges if n.nudge_type == NudgeType.GOAL_RISK]
    assert len(goal_nudges) >= 1
    assert goal_nudges[0].severity == "critical"


def test_nudges_goal_risk_not_for_pseudo():
    g = Goal(title="~maintenance", dimension=Dimension.HEALTH, is_pseudo=True)
    nudges = compute_nudges(tasks=[], habits=[], goals=[g])
    goal_nudges = [n for n in nudges if n.nudge_type == NudgeType.GOAL_RISK]
    assert len(goal_nudges) == 0


def test_nudges_stale_task():
    old_date = (datetime.now() - timedelta(days=20)).isoformat()
    t = Task(title="Stale task", status=TaskStatus.TODO, created_at=old_date)
    nudges = compute_nudges(tasks=[t], habits=[], goals=[])
    stale_nudges = [n for n in nudges if n.nudge_type == NudgeType.STALE_TASK]
    assert len(stale_nudges) >= 1
    assert "sitting for" in stale_nudges[0].message


def test_nudges_not_stale_if_recent():
    t = Task(title="New task", status=TaskStatus.TODO)
    nudges = compute_nudges(tasks=[t], habits=[], goals=[])
    stale_nudges = [n for n in nudges if n.nudge_type == NudgeType.STALE_TASK]
    assert len(stale_nudges) == 0


def test_nudges_budget_drift():
    """Budget over 80% triggers budget_drift nudge."""
    b = Budget(
        name="Overbudget",
        total_limit=10000.0,
        spent=9000.0,
        period_start=date.today().isoformat(),
        period_end=(date.today() + timedelta(days=30)).isoformat(),
    )
    import viyugam.storage as storage
    storage.save_budget(b)
    nudges = compute_nudges(tasks=[], habits=[], goals=[])
    budget_nudges = [n for n in nudges if n.nudge_type == NudgeType.BUDGET_DRIFT]
    assert len(budget_nudges) >= 1
    assert "90%" in budget_nudges[0].message


# ── format_context_for_prompt ────────────────────────────────────────────────

def test_format_empty_context():
    ctx = PriorityContext()
    result = format_context_for_prompt(ctx)
    assert result == ""


def test_format_with_directive():
    ctx = PriorityContext(
        directive_task={"title": "Fix bug", "_composite": 0.85},
        why_bottleneck="blocks 2 task(s)",
        unblocks=["Deploy", "Test"],
    )
    result = format_context_for_prompt(ctx)
    assert "GPS DIRECTIVE: Fix bug" in result
    assert "0.85" in result
    assert "blocks 2 task(s)" in result
    assert "Deploy" in result


def test_format_with_trajectories():
    ctx = PriorityContext(
        goal_trajectories=[{
            "seq_id": "G-001",
            "title": "Ship product",
            "trajectory": Trajectory.ON_TRACK,
            "progress_pct": 75.0,
        }],
    )
    result = format_context_for_prompt(ctx)
    assert "GOAL TRAJECTORIES:" in result
    assert "G-001" in result
    assert "on_track" in result
    assert "75%" in result


def test_format_with_nudges():
    ctx = PriorityContext(
        nudges=[
            Nudge(
                nudge_type=NudgeType.DEADLINE,
                entity_id="t1",
                message="'Task X' overdue by 2d",
                severity="critical",
            ),
        ],
    )
    result = format_context_for_prompt(ctx)
    assert "ACTIVE NUDGES:" in result
    assert "[critical]" in result
    assert "'Task X' overdue by 2d" in result


def test_format_with_all_sections():
    ctx = PriorityContext(
        directive_task={"title": "Top task", "_composite": 0.9},
        why_bottleneck="overdue by 1d",
        unblocks=["Next task"],
        goal_trajectories=[{
            "seq_id": "G-002",
            "title": "Learn Rust",
            "trajectory": Trajectory.AT_RISK,
            "progress_pct": 30.0,
        }],
        nudges=[
            Nudge(
                nudge_type=NudgeType.STALE_TASK,
                entity_id="t2",
                message="'Old task' sitting for 20 days",
                severity="info",
            ),
        ],
    )
    result = format_context_for_prompt(ctx)
    assert "GPS DIRECTIVE:" in result
    assert "GOAL TRAJECTORIES:" in result
    assert "ACTIVE NUDGES:" in result
    # Should have all the key info
    lines = result.split("\n")
    assert len(lines) >= 5


def test_format_truncates_nudges_to_5():
    nudges = [
        Nudge(nudge_type=NudgeType.STALE_TASK, entity_id=f"t{i}",
              message=f"Nudge {i}", severity="info")
        for i in range(10)
    ]
    ctx = PriorityContext(nudges=nudges)
    result = format_context_for_prompt(ctx)
    # Should show max 5
    nudge_lines = [l for l in result.split("\n") if l.strip().startswith("[")]
    assert len(nudge_lines) == 5


def test_format_truncates_trajectories_to_5():
    trajs = [{
        "seq_id": f"G-{i:03d}",
        "title": f"Goal {i}",
        "trajectory": Trajectory.ON_TRACK,
        "progress_pct": 50.0,
    } for i in range(10)]
    ctx = PriorityContext(goal_trajectories=trajs)
    result = format_context_for_prompt(ctx)
    traj_lines = [l for l in result.split("\n") if l.strip().startswith("G-")]
    assert len(traj_lines) == 5
