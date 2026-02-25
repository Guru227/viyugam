"""
test_models.py — Tests for all new and existing models.
"""
from __future__ import annotations
import pytest
from datetime import datetime

from viyugam.models import (
    SlowBurn, Milestone, Budget, Transaction, Decision, ActualRecord,
    CalendarEntry, CalendarEntryType, WorkSchedule, ViyugamConfig,
    TaskStatus, Dimension, Recurrence, Task, Goal, SeasonConfig,
)


# ── SlowBurn ──────────────────────────────────────────────────────────────────

def test_slow_burn_basic():
    sb = SlowBurn(title="Learn Portuguese")
    assert sb.title == "Learn Portuguese"
    assert sb.id is not None
    assert len(sb.id) == 8
    assert sb.dimension is None
    assert sb.notes is None
    assert sb.last_chipped is None
    assert sb.created_at is not None


def test_slow_burn_with_dimension():
    sb = SlowBurn(title="Get fit eventually", dimension=Dimension.HEALTH)
    assert sb.dimension == Dimension.HEALTH


def test_slow_burn_with_notes():
    sb = SlowBurn(title="Learn guitar", notes="Been meaning to for years", last_chipped="2026-01-01")
    assert sb.notes == "Been meaning to for years"
    assert sb.last_chipped == "2026-01-01"


# ── Milestone ─────────────────────────────────────────────────────────────────

def test_milestone_basic():
    m = Milestone(title="Ship MVP")
    assert m.title == "Ship MVP"
    assert m.goal_id is None
    assert m.project_id is None
    assert m.is_done is False
    assert m.due_date is None


def test_milestone_with_goal():
    m = Milestone(title="Reach 10k users", goal_id="abc12345")
    assert m.goal_id == "abc12345"


def test_milestone_with_due_date():
    m = Milestone(title="Finish prototype", due_date="2026-03-31")
    assert m.due_date == "2026-03-31"


def test_milestone_done():
    m = Milestone(title="Launch beta", is_done=True)
    assert m.is_done is True


# ── Budget ────────────────────────────────────────────────────────────────────

def test_budget_creation():
    b = Budget(name="Monthly Expenses", total_limit=50000.0,
               period_start="2026-02-01", period_end="2026-02-28")
    assert b.name == "Monthly Expenses"
    assert b.total_limit == 50000.0
    assert b.spent == 0.0
    assert b.period_start == "2026-02-01"
    assert b.period_end == "2026-02-28"


def test_budget_with_dimension():
    b = Budget(name="Health Budget", total_limit=10000.0,
               period_start="2026-02-01", period_end="2026-02-28",
               dimension=Dimension.HEALTH)
    assert b.dimension == Dimension.HEALTH


# ── Transaction ───────────────────────────────────────────────────────────────

def test_transaction_basic():
    t = Transaction(amount=500.0, category="food", description="Dinner at restaurant")
    assert t.amount == 500.0
    assert t.category == "food"
    assert t.description == "Dinner at restaurant"
    assert t.budget_id is None
    assert t.occurred_at is not None


def test_transaction_with_budget():
    t = Transaction(amount=1200.0, category="transport",
                    description="Ola ride", budget_id="bud12345")
    assert t.budget_id == "bud12345"


# ── Decision ─────────────────────────────────────────────────────────────────

def test_decision_basic():
    d = Decision(proposal="Start a podcast", outcome="approved",
                 reasoning="Aligns with learning season")
    assert d.proposal == "Start a podcast"
    assert d.outcome == "approved"
    assert d.reasoning == "Aligns with learning season"
    assert d.voices == []
    assert d.condition is None
    assert d.actual_outcome is None


def test_decision_with_voices():
    voices = [{"voice": "Vision", "text": "Great idea", "vote": "yes"}]
    d = Decision(proposal="Build a SaaS", outcome="conditional",
                 reasoning="Resource concern", voices=voices,
                 condition="Only if runway > 6 months")
    assert len(d.voices) == 1
    assert d.condition == "Only if runway > 6 months"


def test_decision_with_actual_outcome():
    d = Decision(proposal="Hire a VA", outcome="approved",
                 reasoning="Time savings justify cost",
                 actual_outcome="worked well", revisited_at="2026-04-01")
    assert d.actual_outcome == "worked well"
    assert d.revisited_at == "2026-04-01"


# ── ActualRecord ──────────────────────────────────────────────────────────────

def test_actual_record_basic():
    r = ActualRecord(task_id="task1234", task_title="Write report",
                     planned_minutes=60, date="2026-02-25")
    assert r.task_id == "task1234"
    assert r.planned_minutes == 60
    assert r.actual_minutes is None
    assert r.completed is True


def test_actual_record_with_actuals():
    r = ActualRecord(task_id="task5678", task_title="Code review",
                     planned_minutes=30, actual_minutes=45,
                     date="2026-02-25")
    assert r.actual_minutes == 45


# ── CalendarEntry ─────────────────────────────────────────────────────────────

def test_calendar_entry_one_off():
    e = CalendarEntry(title="Doctor appointment", date="2026-03-05")
    assert e.date == "2026-03-05"
    assert e.recurs_on == []


def test_calendar_entry_recurring():
    e = CalendarEntry(title="Weekly standup", recurs_on=["mon", "wed", "fri"])
    assert "mon" in e.recurs_on
    assert e.date is None


def test_calendar_entry_no_date_or_recurrence_fails():
    with pytest.raises(Exception):
        CalendarEntry(title="No date no recurrence")


# ── WorkSchedule ──────────────────────────────────────────────────────────────

def test_work_schedule_defaults():
    ws = WorkSchedule()
    assert ws.start == "09:00"
    assert ws.end == "17:30"
    assert "mon" in ws.office_days
    assert ws.wfh_days == []


def test_work_schedule_custom():
    ws = WorkSchedule(start="10:00", end="19:00",
                      office_days=["mon", "tue"], wfh_days=["wed", "thu", "fri"])
    assert ws.start == "10:00"
    assert "wed" in ws.wfh_days


# ── ViyugamConfig ─────────────────────────────────────────────────────────────

def test_viyugam_config_defaults():
    cfg = ViyugamConfig()
    assert cfg.user_name == "friend"
    assert cfg.work_hours_cap == 8
    assert cfg.currency == "₹"
    assert cfg.constitution_exists is False


def test_viyugam_config_with_season():
    cfg = ViyugamConfig(season=SeasonConfig(name="Q1 Focus", focus=Dimension.CAREER))
    assert cfg.season is not None
    assert cfg.season.focus == Dimension.CAREER


# ── Enums ─────────────────────────────────────────────────────────────────────

def test_dimension_values():
    assert Dimension.HEALTH.value == "health"
    assert Dimension.WEALTH.value == "wealth"
    assert Dimension.CAREER.value == "career"
    assert Dimension.JOY.value == "joy"
    assert Dimension.LEARNING.value == "learning"
    assert Dimension.RELATIONSHIPS.value == "relationships"


def test_task_status_values():
    assert TaskStatus.TODO.value == "todo"
    assert TaskStatus.DONE.value == "done"
    assert TaskStatus.BACKLOG.value == "backlog"
    assert TaskStatus.IN_PROGRESS.value == "in_progress"


def test_calendar_entry_type():
    assert CalendarEntryType.EVENT.value == "event"
    assert CalendarEntryType.MEETING.value == "meeting"
    assert CalendarEntryType.WORKOUT.value == "workout"
    assert CalendarEntryType.BLOCK.value == "block"
