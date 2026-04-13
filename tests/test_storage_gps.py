"""
test_storage_gps.py — Tests for GPS-related storage functions:
mark_entity_done cascade, nudge persistence, pattern persistence,
project_stats, merge_pattern, and more.
Uses conftest.py to patch paths to tmp_path.
"""
from __future__ import annotations

import json
import pytest
from datetime import date, timedelta

import viyugam.storage as storage
from viyugam.models import (
    Task,
    TaskStatus,
    Goal,
    Dimension,
    Project,
    ProjectStatus,
    Nudge,
    NudgeType,
    PatternInsight,
    Note,
    Budget,
    Transaction,
    TxType,
    RecurringItem,
    RecurringFrequency,
    ViyugamConfig,
    SeasonConfig,
    SystemState,
    ResilienceState,
)


# ── mark_entity_done — Task ──────────────────────────────────────────────────

def test_mark_task_done_by_seq_id():
    t = Task(title="Test task", dimension=Dimension.CAREER)
    storage.save_task(t)
    result = storage.mark_entity_done(t.seq_id)
    assert result is not None
    assert "marked done" in result
    assert t.title in result
    # Verify status changed
    updated = storage.get_task_by_id(t.id)
    assert updated.status == TaskStatus.DONE


def test_mark_task_done_case_insensitive():
    t = Task(title="Case test")
    storage.save_task(t)
    # Use lowercase seq_id
    lower_id = t.seq_id.lower()
    result = storage.mark_entity_done(lower_id)
    assert result is not None


def test_mark_task_done_cascade_goal_progress():
    g = Goal(title="Ship it", dimension=Dimension.CAREER)
    storage.save_goal(g)
    t1 = Task(title="Step 1", aligns_to=[g.id], status=TaskStatus.TODO)
    t2 = Task(title="Step 2", aligns_to=[g.id], status=TaskStatus.DONE)
    storage.save_task(t1)
    storage.save_task(t2)
    result = storage.mark_entity_done(t1.seq_id)
    assert "Goal progress updated" in result
    # Goal should now be at 100% (2/2 aligned tasks done)
    updated_goal = next(g2 for g2 in storage.get_goals(active_only=False) if g2.id == g.id)
    assert updated_goal.progress_pct == 100.0


def test_mark_task_done_cascade_unblocked():
    blocker = Task(title="Blocker")
    blocked = Task(title="Blocked", status=TaskStatus.TODO)
    blocker.blocks = [blocked.id]
    storage.save_task(blocker)
    storage.save_task(blocked)
    result = storage.mark_entity_done(blocker.seq_id)
    assert "Unblocked" in result
    assert "Blocked" in result


def test_mark_task_done_cascade_project_stats():
    p = Project(title="Test project", dimension=Dimension.CAREER)
    storage.save_project(p)
    t = Task(title="Project task", project_id=p.id)
    storage.save_task(t)
    result = storage.mark_entity_done(t.seq_id)
    assert result is not None
    assert "marked done" in result


# ── mark_entity_done — Goal ──────────────────────────────────────────────────

def test_mark_goal_done_by_seq_id():
    g = Goal(title="Test goal", dimension=Dimension.HEALTH)
    storage.save_goal(g)
    result = storage.mark_entity_done(g.seq_id)
    assert result is not None
    assert "marked done" in result
    # Verify is_active is False
    updated = next(
        g2 for g2 in storage.get_goals(active_only=False) if g2.id == g.id
    )
    assert updated.is_active is False


# ── mark_entity_done — Project ───────────────────────────────────────────────

def test_mark_project_done_by_seq_id():
    p = Project(title="Test project")
    storage.save_project(p)
    result = storage.mark_entity_done(p.seq_id)
    assert result is not None
    assert "marked done" in result
    # Verify status is COMPLETED
    projects = storage.get_projects()
    updated = next((p2 for p2 in projects if p2.id == p.id), None)
    assert updated is not None
    assert updated.status == ProjectStatus.COMPLETED


# ── mark_entity_done — Note ──────────────────────────────────────────────────

def test_mark_note_acknowledged():
    n = Note(title="Test note", content="Some content")
    storage.save_note(n)
    result = storage.mark_entity_done(n.seq_id)
    assert result is not None
    assert "acknowledged" in result


# ── mark_entity_done — Not found ─────────────────────────────────────────────

def test_mark_entity_done_not_found():
    result = storage.mark_entity_done("T-999")
    assert result is None


def test_mark_entity_done_no_prefix():
    result = storage.mark_entity_done("noprefixhere")
    assert result is None


# ── project_stats ────────────────────────────────────────────────────────────

def test_project_stats_no_tasks():
    p = Project(title="Empty project")
    storage.save_project(p)
    pct, mins_done, mins_total, budget = storage.project_stats(p.id)
    assert pct == 0
    assert mins_done == 0
    assert mins_total == 0
    assert budget == 0.0


def test_project_stats_with_tasks():
    p = Project(title="Stats project", budget_cap=5000.0)
    storage.save_project(p)
    t1 = Task(title="Done", project_id=p.id, status=TaskStatus.DONE,
              energy_cost=5, estimated_minutes=60)
    t2 = Task(title="Todo", project_id=p.id, status=TaskStatus.TODO,
              energy_cost=5, estimated_minutes=30)
    storage.save_task(t1)
    storage.save_task(t2)
    pct, mins_done, mins_total, budget = storage.project_stats(p.id)
    assert pct == 50  # 5/10 energy done
    assert mins_done == 60
    assert mins_total == 90
    assert budget == 5000.0


def test_project_stats_all_done():
    p = Project(title="Finished project")
    storage.save_project(p)
    t1 = Task(title="T1", project_id=p.id, status=TaskStatus.DONE,
              energy_cost=3, estimated_minutes=20)
    t2 = Task(title="T2", project_id=p.id, status=TaskStatus.DONE,
              energy_cost=7, estimated_minutes=40)
    storage.save_task(t1)
    storage.save_task(t2)
    pct, mins_done, mins_total, budget = storage.project_stats(p.id)
    assert pct == 100
    assert mins_done == 60
    assert mins_total == 60


def test_project_stats_excludes_habits():
    p = Project(title="Habit project")
    storage.save_project(p)
    t1 = Task(title="Real task", project_id=p.id, status=TaskStatus.DONE,
              energy_cost=5, estimated_minutes=30)
    habit = Task(title="Habit", project_id=p.id, status=TaskStatus.TODO,
                 is_habit=True, energy_cost=3, estimated_minutes=15)
    storage.save_task(t1)
    storage.save_task(habit)
    pct, mins_done, mins_total, budget = storage.project_stats(p.id)
    assert pct == 100  # only real task counted
    assert mins_total == 30


# ── Nudge persistence ────────────────────────────────────────────────────────

def test_save_and_get_nudge():
    n = Nudge(
        nudge_type=NudgeType.DEADLINE,
        entity_id="t123",
        message="Task overdue",
        severity="critical",
    )
    storage.save_nudge(n)
    stored = storage.get_stored_nudges()
    assert any(s["id"] == n.id for s in stored)


def test_nudge_upsert():
    n = Nudge(
        nudge_type=NudgeType.STREAK,
        entity_id="h456",
        message="Streak broken",
    )
    storage.save_nudge(n)
    n.message = "Streak still broken"
    storage.save_nudge(n)
    stored = storage.get_stored_nudges()
    matching = [s for s in stored if s["id"] == n.id]
    assert len(matching) == 1
    assert matching[0]["message"] == "Streak still broken"


def test_dismiss_nudge_existing():
    n = Nudge(
        nudge_type=NudgeType.STALE_TASK,
        entity_id="t789",
        message="Task sitting",
    )
    storage.save_nudge(n)
    result = storage.dismiss_nudge("t789", "stale_task")
    assert result is True
    stored = storage.get_stored_nudges()
    dismissed = [s for s in stored if s["entity_id"] == "t789" and s["dismissed"]]
    assert len(dismissed) >= 1


def test_dismiss_nudge_nonexistent():
    result = storage.dismiss_nudge("nonexistent", "stale_task")
    assert result is True  # creates a marker even if not found
    stored = storage.get_stored_nudges()
    markers = [s for s in stored if s["entity_id"] == "nonexistent" and s["dismissed"]]
    assert len(markers) >= 1


def test_get_stored_nudges_empty():
    stored = storage.get_stored_nudges()
    assert stored == []


# ── Pattern persistence ──────────────────────────────────────────────────────

def test_save_and_get_pattern():
    p = PatternInsight(pattern="I am most productive in the morning")
    storage.save_pattern(p)
    patterns = storage.get_patterns()
    assert any(pat.id == p.id for pat in patterns)


def test_get_patterns_precipitated_filter():
    p1 = PatternInsight(pattern="Morning energy", precipitated=True)
    p2 = PatternInsight(pattern="Evening slump", precipitated=False)
    storage.save_pattern(p1)
    storage.save_pattern(p2)
    all_patterns = storage.get_patterns(precipitated_only=False)
    precipitated = storage.get_patterns(precipitated_only=True)
    assert len(all_patterns) >= 2
    assert len(precipitated) >= 1
    assert all(p.precipitated for p in precipitated)


def test_get_patterns_empty():
    patterns = storage.get_patterns()
    assert patterns == []


# ── merge_pattern ────────────────────────────────────────────────────────────

def test_merge_pattern_creates_new():
    result = storage.merge_pattern("I work best in quiet environments")
    assert result.pattern == "I work best in quiet environments"
    assert result.occurrences == 1
    assert result.precipitated is False


def test_merge_pattern_deduplicates_high_overlap():
    # First create a pattern
    storage.merge_pattern("I am most productive in the morning time")
    # Merge very similar text (>70% word overlap)
    result = storage.merge_pattern("I am most productive in the morning hours")
    assert result.occurrences == 2
    # Original text preserved
    assert "morning" in result.pattern.lower()


def test_merge_pattern_no_dedup_low_overlap():
    storage.merge_pattern("I love coding in Python")
    result = storage.merge_pattern("The weather is great today for a walk")
    assert result.occurrences == 1  # new pattern, no merge


def test_merge_pattern_precipitates_at_3():
    storage.merge_pattern("I get tired after lunch every day")
    storage.merge_pattern("I get tired after lunch every afternoon")
    result = storage.merge_pattern("I get tired after lunch every time")
    assert result.occurrences >= 3
    assert result.precipitated is True


def test_merge_pattern_with_tags():
    result = storage.merge_pattern("Exercise boosts my mood", tags=["health", "mood"])
    assert "health" in result.tags
    assert "mood" in result.tags


def test_merge_pattern_tags_merged_on_dedup():
    storage.merge_pattern("I focus better with music", tags=["productivity"])
    result = storage.merge_pattern("I focus better with music playing", tags=["music"])
    assert "productivity" in result.tags
    assert "music" in result.tags


# ── _recompute_goal_progress ─────────────────────────────────────────────────

def test_recompute_goal_progress():
    g = Goal(title="Test goal", dimension=Dimension.CAREER)
    storage.save_goal(g)
    t1 = Task(title="T1", aligns_to=[g.id], status=TaskStatus.DONE)
    t2 = Task(title="T2", aligns_to=[g.id], status=TaskStatus.TODO)
    storage.save_task(t1)
    storage.save_task(t2)
    pct = storage._recompute_goal_progress(g.id)
    assert pct == 50.0
    # Check it was persisted
    updated = next(
        g2 for g2 in storage.get_goals(active_only=False) if g2.id == g.id
    )
    assert updated.progress_pct == 50.0


def test_recompute_goal_progress_no_aligned():
    g = Goal(title="Lonely", dimension=Dimension.HEALTH)
    storage.save_goal(g)
    pct = storage._recompute_goal_progress(g.id)
    assert pct == 0.0


def test_recompute_goal_progress_goal_not_found():
    pct = storage._recompute_goal_progress("nonexistent")
    assert pct is None


# ── _check_unblocked ─────────────────────────────────────────────────────────

def test_check_unblocked_simple():
    blocker = Task(title="Blocker", status=TaskStatus.DONE)
    blocked = Task(title="Blocked", status=TaskStatus.TODO)
    blocker.blocks = [blocked.id]
    storage.save_task(blocker)
    storage.save_task(blocked)
    unblocked = storage._check_unblocked(blocker.id)
    assert "Blocked" in unblocked


def test_check_unblocked_still_blocked_by_another():
    blocker1 = Task(title="Blocker 1", status=TaskStatus.DONE)
    blocker2 = Task(title="Blocker 2", status=TaskStatus.TODO)
    blocked = Task(title="Blocked", status=TaskStatus.TODO)
    blocker1.blocks = [blocked.id]
    blocker2.blocks = [blocked.id]
    storage.save_task(blocker1)
    storage.save_task(blocker2)
    storage.save_task(blocked)
    unblocked = storage._check_unblocked(blocker1.id)
    # Still blocked by blocker2
    assert "Blocked" not in unblocked


def test_check_unblocked_no_blocks():
    t = Task(title="Unrelated", status=TaskStatus.DONE)
    storage.save_task(t)
    unblocked = storage._check_unblocked(t.id)
    assert unblocked == []


# ── get_finance_context ──────────────────────────────────────────────────────

def test_get_finance_context_empty():
    ctx = storage.get_finance_context(months=1)
    assert "FINANCE CONTEXT:" in ctx


def test_get_finance_context_with_budget_and_transactions():
    today = date.today()
    b = Budget(
        name="Monthly",
        total_limit=50000.0,
        period_start=today.isoformat(),
        period_end=(today + timedelta(days=30)).isoformat(),
    )
    storage.save_budget(b)
    t = Transaction(
        amount=10000.0, category="food", description="Groceries",
        tx_type=TxType.EXPENSE, budget_id=b.id,
    )
    storage.save_transaction(t)

    ctx = storage.get_finance_context(months=1)
    assert "FINANCE CONTEXT:" in ctx
    assert "Monthly" in ctx
    assert "Active budgets" in ctx


def test_get_finance_context_with_recurring():
    r = RecurringItem(
        name="Salary",
        amount=80000.0,
        tx_type=TxType.INCOME,
        frequency=RecurringFrequency.MONTHLY,
    )
    storage.save_recurring_item(r)
    ctx = storage.get_finance_context(months=1)
    assert "Recurring items" in ctx


# ── load_config / save_config ────────────────────────────────────────────────

def test_load_config_default():
    cfg = storage.load_config()
    assert cfg.user_name == "friend"
    assert cfg.currency == "\u20b9"


def test_save_and_load_config():
    cfg = ViyugamConfig(user_name="guru", currency="$")
    storage.save_config(cfg)
    loaded = storage.load_config()
    assert loaded.user_name == "guru"
    assert loaded.currency == "$"


def test_load_config_with_season():
    cfg = ViyugamConfig(
        season=SeasonConfig(name="Health Sprint", focus=Dimension.HEALTH)
    )
    storage.save_config(cfg)
    loaded = storage.load_config()
    assert loaded.season is not None
    assert loaded.season.focus == Dimension.HEALTH


# ── get_season_drift ─────────────────────────────────────────────────────────

def test_season_drift_no_season():
    cfg = ViyugamConfig()
    result = storage.get_season_drift(cfg)
    assert result is None


def test_season_drift_insufficient_data():
    cfg = ViyugamConfig(
        season=SeasonConfig(name="Career", focus=Dimension.CAREER)
    )
    # No done tasks => calculate_actual_season returns None
    result = storage.get_season_drift(cfg)
    assert result is None


def test_season_drift_aligned():
    cfg = ViyugamConfig(
        season=SeasonConfig(name="Career", focus=Dimension.CAREER)
    )
    today = date.today().isoformat()
    for i in range(6):
        t = Task(title=f"Career {i}", status=TaskStatus.DONE,
                 dimension=Dimension.CAREER, scheduled_date=today)
        storage.save_task(t)
    result = storage.get_season_drift(cfg)
    # All tasks match intended => no drift
    assert result is None


def test_season_drift_misaligned():
    cfg = ViyugamConfig(
        season=SeasonConfig(name="Career", focus=Dimension.CAREER)
    )
    today = date.today().isoformat()
    for i in range(6):
        t = Task(title=f"Health {i}", status=TaskStatus.DONE,
                 dimension=Dimension.HEALTH, scheduled_date=today)
        storage.save_task(t)
    result = storage.get_season_drift(cfg)
    assert result is not None
    assert "career" in result.lower()
    assert "health" in result.lower()


# ── System state ─────────────────────────────────────────────────────────────

def test_load_state_default():
    state = storage.load_state()
    assert state.resilience == ResilienceState.FLOW
    assert state.current_streak == 0


def test_save_and_load_state():
    state = SystemState(resilience=ResilienceState.DRIFT, current_streak=5)
    storage.save_state(state)
    loaded = storage.load_state()
    assert loaded.resilience == ResilienceState.DRIFT
    assert loaded.current_streak == 5


def test_touch_active_increments_streak():
    state = SystemState(
        last_active=(date.today() - timedelta(days=1)).isoformat() + "T10:00:00",
        current_streak=3,
    )
    updated = storage.touch_active(state)
    assert updated.current_streak == 4
    assert updated.resilience == ResilienceState.FLOW


def test_touch_active_first_time():
    state = SystemState()
    updated = storage.touch_active(state)
    assert updated.current_streak == 1


def test_check_resilience_flow():
    state = SystemState(last_active=date.today().isoformat() + "T10:00:00")
    assert storage.check_resilience(state) == ResilienceState.FLOW


def test_check_resilience_drift():
    three_days_ago = (date.today() - timedelta(days=3)).isoformat() + "T10:00:00"
    state = SystemState(last_active=three_days_ago)
    assert storage.check_resilience(state) == ResilienceState.DRIFT


def test_check_resilience_bankruptcy():
    ten_days_ago = (date.today() - timedelta(days=10)).isoformat() + "T10:00:00"
    state = SystemState(last_active=ten_days_ago)
    assert storage.check_resilience(state) == ResilienceState.BANKRUPTCY


def test_check_resilience_no_activity():
    state = SystemState()
    assert storage.check_resilience(state) == ResilienceState.FLOW


# ── Period boundaries ────────────────────────────────────────────────────────

def test_period_start_daily():
    today = date.today()
    assert storage.period_start("daily", today) == today


def test_period_start_monthly():
    d = date(2026, 3, 15)
    assert storage.period_start("monthly", d) == date(2026, 3, 1)


def test_period_start_quarterly():
    d = date(2026, 5, 15)
    assert storage.period_start("quarterly", d) == date(2026, 4, 1)


def test_period_end_daily():
    today = date.today()
    assert storage.period_end("daily", today) == today


def test_period_end_monthly():
    d = date(2026, 2, 15)
    assert storage.period_end("monthly", d) == date(2026, 2, 28)


def test_period_end_quarterly():
    d = date(2026, 5, 15)
    assert storage.period_end("quarterly", d) == date(2026, 6, 30)


def test_period_start_weekly():
    # 2026-03-10 is Tuesday, week starts Sunday => 2026-03-08
    d = date(2026, 3, 10)
    start = storage.period_start("weekly", d)
    assert start == date(2026, 3, 8)


def test_period_end_weekly():
    d = date(2026, 3, 10)  # Tuesday
    end = storage.period_end("weekly", d)
    assert end == date(2026, 3, 14)  # Saturday


# ── Goal CRUD ────────────────────────────────────────────────────────────────

def test_save_and_get_goal():
    g = Goal(title="Learn Rust", dimension=Dimension.LEARNING)
    storage.save_goal(g)
    goals = storage.get_goals(active_only=False)
    assert any(g2.id == g.id for g2 in goals)


def test_get_goals_active_only():
    g1 = Goal(title="Active", dimension=Dimension.CAREER, is_active=True)
    g2 = Goal(title="Inactive", dimension=Dimension.HEALTH, is_active=False)
    storage.save_goal(g1)
    storage.save_goal(g2)
    active = storage.get_goals(active_only=True)
    assert any(g.id == g1.id for g in active)
    assert not any(g.id == g2.id for g in active)


def test_delete_goal():
    g = Goal(title="Delete me", dimension=Dimension.JOY)
    storage.save_goal(g)
    assert storage.delete_goal(g.id) is True
    goals = storage.get_goals(active_only=False)
    assert not any(g2.id == g.id for g2 in goals)


def test_delete_goal_not_found():
    assert storage.delete_goal("nonexistent") is False


# ── Project CRUD ─────────────────────────────────────────────────────────────

def test_save_and_get_project():
    p = Project(title="Viyugam", dimension=Dimension.CAREER)
    storage.save_project(p)
    projects = storage.get_projects()
    assert any(p2.id == p.id for p2 in projects)


def test_get_projects_by_status():
    p1 = Project(title="Active", status=ProjectStatus.ACTIVE)
    p2 = Project(title="Paused", status=ProjectStatus.PAUSED)
    storage.save_project(p1)
    storage.save_project(p2)
    active = storage.get_projects(status="active")
    assert any(p.id == p1.id for p in active)
    assert not any(p.id == p2.id for p in active)


# ── Triage ───────────────────────────────────────────────────────────────────

def test_append_and_get_triage():
    item = storage.append_triage("Fix a bug in the login flow")
    items = storage.get_triage(unprocessed_only=True)
    assert any(i.id == item.id for i in items)


def test_mark_triage_processed():
    item = storage.append_triage("Write tests")
    storage.mark_triage_processed([item.id])
    items = storage.get_triage(unprocessed_only=True)
    assert not any(i.id == item.id for i in items)


def test_get_recent_triage_logs():
    for i in range(7):
        storage.append_triage(f"Item {i}")
    recent = storage.get_recent_triage_logs(n=5)
    assert len(recent) == 5


# ── Notes ────────────────────────────────────────────────────────────────────

def test_save_and_get_note():
    n = Note(title="API Design", content="Use REST with versioned endpoints")
    storage.save_note(n)
    notes = storage.get_notes()
    assert any(note.id == n.id for note in notes)
    assert n.seq_id is not None
    assert n.seq_id.startswith("N-")


# ── Values ───────────────────────────────────────────────────────────────────

def test_load_values_default():
    vals = storage.load_values()
    assert "prayer" in vals
    assert "chapters" in vals


def test_save_and_load_values():
    vals = {"prayer": "Be grateful", "chapters": {"career": "Build with purpose"}}
    storage.save_values(vals)
    loaded = storage.load_values()
    assert loaded["prayer"] == "Be grateful"


# ── Plans ────────────────────────────────────────────────────────────────────

def test_save_and_load_plan():
    plan = {"tasks": ["Write code", "Review PR"], "focus": "career"}
    storage.save_plan("daily", plan)
    loaded = storage.load_plan("daily")
    assert loaded["focus"] == "career"
    assert len(loaded["tasks"]) == 2


def test_load_plan_empty():
    loaded = storage.load_plan("weekly")
    assert loaded == {}


# ── Sequential IDs ───────────────────────────────────────────────────────────

def test_next_id_increments():
    id1 = storage._next_id("T")
    id2 = storage._next_id("T")
    # Extract numbers
    n1 = int(id1.split("-")[1])
    n2 = int(id2.split("-")[1])
    assert n2 == n1 + 1


def test_next_id_different_prefixes():
    t_id = storage._next_id("T")
    g_id = storage._next_id("G")
    assert t_id.startswith("T-")
    assert g_id.startswith("G-")


# ── get_nudges (legacy system state nudges) ──────────────────────────────────

def test_get_nudges_no_log():
    state = SystemState()
    nudges = storage.get_nudges(state)
    assert any("log" in n.lower() for n in nudges)


def test_get_nudges_no_think():
    state = SystemState()
    nudges = storage.get_nudges(state)
    assert any("think" in n.lower() for n in nudges)


def test_get_nudges_no_review():
    state = SystemState()
    nudges = storage.get_nudges(state)
    assert any("review" in n.lower() for n in nudges)


def test_get_nudges_stale_log():
    three_days_ago = (date.today() - timedelta(days=3)).isoformat()
    state = SystemState(last_log=three_days_ago)
    nudges = storage.get_nudges(state)
    assert any("log" in n.lower() for n in nudges)
