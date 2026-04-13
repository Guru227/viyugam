"""
test_models_extra.py — Additional model validation tests.
Covers enums, GPS engine models, default values, validators, and edge cases
not covered by existing test_models.py.
"""
from __future__ import annotations

import pytest
from datetime import datetime

from viyugam.models import (
    CalendarEntry,
    CalendarEntryType,
    Decision,
    Dimension,
    Goal,
    InboxItem,
    JournalSummary,
    DimensionScore,
    KeyResult,
    Milestone,
    Note,
    Nudge,
    NudgeType,
    OKR,
    PatternInsight,
    PriorityContext,
    Project,
    ProjectPlan,
    ProjectStatus,
    Recurrence,
    RecurringFrequency,
    RecurringItem,
    ResilienceState,
    SeasonConfig,
    SlowBurn,
    SomedayItem,
    SystemState,
    Task,
    TaskStatus,
    Trajectory,
    Transaction,
    TriageItem,
    TxType,
    ViyugamConfig,
    WorkSchedule,
    new_id,
)


# ── new_id ───────────────────────────────────────────────────────────────────

def test_new_id_length():
    assert len(new_id()) == 8


def test_new_id_unique():
    ids = {new_id() for _ in range(100)}
    assert len(ids) == 100


# ── Enum completeness ────────────────────────────────────────────────────────

def test_project_status_values():
    assert ProjectStatus.ACTIVE.value == "active"
    assert ProjectStatus.PAUSED.value == "paused"
    assert ProjectStatus.COMPLETED.value == "completed"
    assert ProjectStatus.ICEBOX.value == "icebox"


def test_recurrence_values():
    assert Recurrence.DAILY.value == "daily"
    assert Recurrence.WEEKLY.value == "weekly"
    assert Recurrence.MONTHLY.value == "monthly"


def test_resilience_state_values():
    assert ResilienceState.FLOW.value == "flow"
    assert ResilienceState.DRIFT.value == "drift"
    assert ResilienceState.BANKRUPTCY.value == "bankruptcy"


def test_trajectory_values():
    assert Trajectory.ON_TRACK.value == "on_track"
    assert Trajectory.AT_RISK.value == "at_risk"
    assert Trajectory.OFF_TRACK.value == "off_track"


def test_nudge_type_values():
    assert NudgeType.DEADLINE.value == "deadline"
    assert NudgeType.STREAK.value == "streak"
    assert NudgeType.SNOOZE.value == "snooze"
    assert NudgeType.GOAL_RISK.value == "goal_risk"
    assert NudgeType.BUDGET_DRIFT.value == "budget_drift"
    assert NudgeType.STALE_TASK.value == "stale_task"
    assert NudgeType.SEASON_DRIFT.value == "season_drift"
    assert len(NudgeType) == 7


def test_tx_type_values():
    assert TxType.EXPENSE.value == "expense"
    assert TxType.INCOME.value == "income"
    assert TxType.TRANSFER.value == "transfer"


def test_recurring_frequency_values():
    assert RecurringFrequency.DAILY.value == "daily"
    assert RecurringFrequency.WEEKLY.value == "weekly"
    assert RecurringFrequency.MONTHLY.value == "monthly"
    assert RecurringFrequency.YEARLY.value == "yearly"


# ── Task model ───────────────────────────────────────────────────────────────

def test_task_defaults():
    t = Task(title="Test")
    assert t.status == TaskStatus.TODO
    assert t.estimated_minutes == 30
    assert t.energy_cost == 5
    assert t.financial_cost == 0.0
    assert t.is_habit is False
    assert t.streak == 0
    assert t.overdue_count == 0
    assert t.priority == "medium"
    assert t.blocks == []
    assert t.aligns_to == []
    assert t.snooze_count == 0
    assert t.constraint_score is None
    assert t.ai_priority_score is None
    assert t.id is not None
    assert t.created_at is not None


def test_task_all_priority_values():
    for p in ("high", "medium", "low"):
        t = Task(title="T", priority=p)
        assert t.priority == p


def test_task_habit_fields():
    t = Task(
        title="Exercise",
        is_habit=True,
        recurrence=Recurrence.DAILY,
        streak=10,
        last_done="2026-03-09",
    )
    assert t.is_habit is True
    assert t.recurrence == Recurrence.DAILY
    assert t.streak == 10
    assert t.last_done == "2026-03-09"


def test_task_gps_fields():
    t = Task(
        title="Blocker",
        blocks=["t2", "t3"],
        aligns_to=["g1"],
        snooze_count=2,
        constraint_score=0.8,
        ai_priority_score=0.75,
    )
    assert t.blocks == ["t2", "t3"]
    assert t.aligns_to == ["g1"]
    assert t.snooze_count == 2
    assert t.constraint_score == 0.8
    assert t.ai_priority_score == 0.75


def test_task_seq_id():
    t = Task(title="Sequenced", seq_id="T-042")
    assert t.seq_id == "T-042"


# ── Goal model ───────────────────────────────────────────────────────────────

def test_goal_defaults():
    g = Goal(title="Ship product", dimension=Dimension.CAREER)
    assert g.is_active is True
    assert g.is_pseudo is False
    assert g.trajectory is None
    assert g.bottleneck_task is None
    assert g.progress_pct == 0.0


def test_goal_pseudo():
    g = Goal(title="~maintenance", dimension=Dimension.HEALTH, is_pseudo=True)
    assert g.is_pseudo is True


def test_goal_gps_fields():
    g = Goal(
        title="Test",
        dimension=Dimension.JOY,
        trajectory=Trajectory.AT_RISK,
        bottleneck_task="T-001",
        progress_pct=45.5,
    )
    assert g.trajectory == Trajectory.AT_RISK
    assert g.bottleneck_task == "T-001"
    assert g.progress_pct == 45.5


# ── Project model ────────────────────────────────────────────────────────────

def test_project_defaults():
    p = Project(title="Viyugam")
    assert p.status == ProjectStatus.ACTIVE
    assert p.budget_cap == 0.0
    assert p.energy_cap == 0
    assert p.dimension is None
    assert p.seq_id is None


# ── Nudge model ──────────────────────────────────────────────────────────────

def test_nudge_defaults():
    n = Nudge(nudge_type=NudgeType.DEADLINE, entity_id="t1", message="Overdue")
    assert n.severity == "info"
    assert n.dismissed is False
    assert n.id is not None
    assert n.surfaced_at is not None
    assert n.created_at is not None


def test_nudge_all_severities():
    for sev in ("info", "warn", "critical"):
        n = Nudge(nudge_type=NudgeType.STALE_TASK, entity_id="t1",
                  message="Test", severity=sev)
        assert n.severity == sev


# ── PatternInsight model ─────────────────────────────────────────────────────

def test_pattern_insight_defaults():
    p = PatternInsight(pattern="Morning energy peak")
    assert p.occurrences == 1
    assert p.source == "system"
    assert p.precipitated is False
    assert p.tags == []
    assert p.first_seen is not None
    assert p.last_seen is not None


def test_pattern_insight_precipitated():
    p = PatternInsight(pattern="Consistent", occurrences=5, precipitated=True)
    assert p.precipitated is True
    assert p.occurrences == 5


# ── PriorityContext model ────────────────────────────────────────────────────

def test_priority_context_defaults():
    ctx = PriorityContext()
    assert ctx.directive_task is None
    assert ctx.why_bottleneck == ""
    assert ctx.unblocks == []
    assert ctx.nudges == []
    assert ctx.goal_trajectories == []
    assert ctx.energy_fit == ""
    assert ctx.computed_at is not None


def test_priority_context_with_data():
    n = Nudge(nudge_type=NudgeType.DEADLINE, entity_id="t1", message="Due")
    ctx = PriorityContext(
        directive_task={"title": "Fix bug"},
        why_bottleneck="blocks 2 tasks",
        unblocks=["Deploy"],
        nudges=[n],
        goal_trajectories=[{"goal_id": "g1", "progress": 50}],
        energy_fit="morning (peak energy)",
    )
    assert ctx.directive_task["title"] == "Fix bug"
    assert len(ctx.nudges) == 1
    assert len(ctx.goal_trajectories) == 1


# ── SystemState model ────────────────────────────────────────────────────────

def test_system_state_defaults():
    s = SystemState()
    assert s.resilience == ResilienceState.FLOW
    assert s.last_active is None
    assert s.current_streak == 0
    assert s.actual_season is None


# ── CalendarEntry validator ──────────────────────────────────────────────────

def test_calendar_entry_both_recurs_and_date():
    e = CalendarEntry(title="Both", recurs_on=["mon"], date="2026-03-10")
    assert e.recurs_on == ["mon"]
    assert e.date == "2026-03-10"


def test_calendar_entry_validates_recurs_or_date():
    with pytest.raises(ValueError, match="Must set recurs_on"):
        CalendarEntry(title="Neither")


def test_calendar_entry_type_defaults():
    e = CalendarEntry(title="Meeting", date="2026-03-10")
    assert e.entry_type == CalendarEntryType.EVENT


def test_calendar_entry_all_types():
    for t in CalendarEntryType:
        e = CalendarEntry(title=f"Type {t}", date="2026-03-10", entry_type=t)
        assert e.entry_type == t


def test_calendar_entry_with_time():
    e = CalendarEntry(
        title="Standup",
        recurs_on=["mon", "wed", "fri"],
        start_time="09:30",
        end_time="09:45",
    )
    assert e.start_time == "09:30"
    assert e.end_time == "09:45"


# ── InboxItem model ──────────────────────────────────────────────────────────

def test_inbox_item_defaults():
    i = InboxItem(content="Quick thought")
    assert i.source == "cli"
    assert i.is_processed is False
    assert i.id is not None


# ── TriageItem model ─────────────────────────────────────────────────────────

def test_triage_item_defaults():
    t = TriageItem(content="Need to fix auth bug")
    assert t.source == "cli"
    assert t.processed is False
    assert t.snooze_until is None
    assert t.entity_type is None
    assert t.parent_id is None


def test_triage_item_full():
    t = TriageItem(
        content="Scope the ML pipeline",
        source="voice",
        entity_type="project",
        parent_id="p123",
    )
    assert t.source == "voice"
    assert t.entity_type == "project"
    assert t.parent_id == "p123"


# ── Note model ───────────────────────────────────────────────────────────────

def test_note_defaults():
    n = Note(title="API Notes")
    assert n.content == ""
    assert n.tags == []
    assert n.dimension is None
    assert n.seq_id is None


def test_note_full():
    n = Note(
        title="Design Decision",
        content="Use event sourcing",
        dimension=Dimension.CAREER,
        tags=["architecture", "backend"],
        seq_id="N-001",
    )
    assert n.dimension == Dimension.CAREER
    assert len(n.tags) == 2


# ── SomedayItem model ───────────────────────────────────────────────────────

def test_someday_item_defaults():
    s = SomedayItem(proposal="Start a podcast")
    assert s.debate_transcript == []
    assert s.consensus is None
    assert s.deferred_reason is None
    assert s.revisit_after is None


# ── DimensionScore / JournalSummary ──────────────────────────────────────────

def test_dimension_score():
    ds = DimensionScore(dimension=Dimension.HEALTH, score=8, note="Felt great")
    assert ds.score == 8
    assert ds.note == "Felt great"


def test_journal_summary_defaults():
    js = JournalSummary(date="2026-03-10")
    assert js.dimension_scores == []
    assert js.wins == []
    assert js.challenges == []
    assert js.mood is None


def test_journal_summary_full():
    ds = DimensionScore(dimension=Dimension.JOY, score=9)
    js = JournalSummary(
        date="2026-03-10",
        dimension_scores=[ds],
        energy_level="high",
        mood="great",
        wins=["Shipped feature"],
        challenges=["Long meeting"],
        patterns_noted=["More productive after exercise"],
    )
    assert len(js.dimension_scores) == 1
    assert js.energy_level == "high"
    assert len(js.wins) == 1
    assert len(js.patterns_noted) == 1


# ── ProjectPlan model ────────────────────────────────────────────────────────

def test_project_plan_defaults():
    pp = ProjectPlan(project_id="p123")
    assert pp.scope_md == ""
    assert pp.success_criteria == []
    assert pp.out_of_scope == []
    assert pp.total_budget == 0.0
    assert pp.notes == ""


def test_project_plan_full():
    pp = ProjectPlan(
        project_id="p123",
        scope_md="# Scope\nBuild the MVP",
        success_criteria=["All tests pass", "Users can login"],
        out_of_scope=["Mobile app"],
        total_budget=10000.0,
        notes="Deadline: end of Q1",
    )
    assert len(pp.success_criteria) == 2
    assert pp.total_budget == 10000.0


# ── OKR / KeyResult ─────────────────────────────────────────────────────────

def test_key_result_defaults():
    kr = KeyResult(text="Ship 3 features")
    assert kr.target is None
    assert kr.is_done is False


def test_okr_defaults():
    okr = OKR(quarter="2026-Q1", objective="Deliver the product")
    assert okr.is_active is True
    assert okr.key_results == []
    assert okr.dimension is None


# ── SeasonConfig ─────────────────────────────────────────────────────────────

def test_season_config_basic():
    sc = SeasonConfig(name="Health Sprint", focus=Dimension.HEALTH)
    assert sc.secondary is None
    assert sc.until is None


def test_season_config_full():
    sc = SeasonConfig(
        name="Career + Learning",
        focus=Dimension.CAREER,
        secondary=Dimension.LEARNING,
        until="2026-06-30",
    )
    assert sc.secondary == Dimension.LEARNING
    assert sc.until == "2026-06-30"


# ── RecurringItem ────────────────────────────────────────────────────────────

def test_recurring_item_defaults():
    r = RecurringItem(name="Netflix", amount=500.0)
    assert r.tx_type == TxType.EXPENSE
    assert r.category == "general"
    assert r.frequency == RecurringFrequency.MONTHLY
    assert r.day_of_month == 1
    assert r.is_active is True
    assert r.last_logged is None


# ── Model serialization roundtrip ────────────────────────────────────────────

def test_task_model_dump_and_reconstruct():
    t = Task(
        title="Roundtrip",
        priority="high",
        blocks=["t2"],
        aligns_to=["g1"],
        dimension=Dimension.CAREER,
    )
    data = t.model_dump()
    t2 = Task(**data)
    assert t2.title == t.title
    assert t2.blocks == t.blocks
    assert t2.dimension == Dimension.CAREER


def test_goal_model_dump_and_reconstruct():
    g = Goal(
        title="Test",
        dimension=Dimension.HEALTH,
        trajectory=Trajectory.ON_TRACK,
        progress_pct=80.5,
    )
    data = g.model_dump()
    g2 = Goal(**data)
    assert g2.trajectory == Trajectory.ON_TRACK
    assert g2.progress_pct == 80.5


def test_nudge_model_dump_and_reconstruct():
    n = Nudge(
        nudge_type=NudgeType.BUDGET_DRIFT,
        entity_id="b1",
        message="Budget at 90%",
        severity="critical",
        dismissed=True,
    )
    data = n.model_dump()
    n2 = Nudge(**data)
    assert n2.nudge_type == NudgeType.BUDGET_DRIFT
    assert n2.dismissed is True
    assert n2.severity == "critical"
