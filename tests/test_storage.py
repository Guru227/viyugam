"""
test_storage.py — Tests for all storage CRUD functions.
Uses conftest.py to patch paths to tmp_path.
"""
from __future__ import annotations
import json
import pytest
from datetime import date, timedelta

import viyugam.storage as storage
from viyugam.models import (
    Task, TaskStatus, Goal, Dimension, SlowBurn, Milestone,
    Budget, Transaction, Decision, ActualRecord, CalendarEntry,
    CalendarEntryType, ViyugamConfig, SeasonConfig, WorkSchedule,
)


# ── ensure_dirs ───────────────────────────────────────────────────────────────

def test_ensure_dirs_creates_files():
    # conftest already called ensure_dirs; check files exist
    assert storage.DATA.exists()
    assert storage.JOURNALS.exists()
    assert storage.SLOW_BURNS_FILE.exists()
    assert storage.MILESTONES_FILE.exists()
    assert storage.BUDGETS_FILE.exists()
    assert storage.TRANSACTIONS_FILE.exists()
    assert storage.DECISIONS_FILE.exists()
    assert storage.ACTUALS_FILE.exists()


def test_ensure_dirs_initialises_json():
    raw = json.loads(storage.SLOW_BURNS_FILE.read_text())
    assert raw == []


# ── Tasks ─────────────────────────────────────────────────────────────────────

def test_save_and_get_task():
    task = Task(title="Write tests", dimension=Dimension.CAREER)
    storage.save_task(task)
    tasks = storage.get_tasks()
    assert any(t.id == task.id for t in tasks)


def test_get_task_by_id():
    task = Task(title="Buy groceries", dimension=Dimension.HEALTH)
    storage.save_task(task)
    found = storage.get_task_by_id(task.id)
    assert found is not None
    assert found.title == "Buy groceries"


def test_get_task_by_partial_id():
    task = Task(title="Partial ID test")
    storage.save_task(task)
    # Use first 4 chars
    found = storage.get_task_by_id(task.id[:4])
    assert found is not None


def test_get_tasks_by_status():
    done_task = Task(title="Already done", status=TaskStatus.DONE)
    storage.save_task(done_task)
    todo_task = Task(title="Still todo", status=TaskStatus.TODO)
    storage.save_task(todo_task)
    done_tasks = storage.get_tasks(status="done")
    assert any(t.id == done_task.id for t in done_tasks)
    assert not any(t.id == todo_task.id for t in done_tasks)


def test_get_tasks_by_scheduled_date():
    today = date.today().isoformat()
    task = Task(title="Today task", scheduled_date=today)
    storage.save_task(task)
    tasks = storage.get_tasks(scheduled_date=today)
    assert any(t.id == task.id for t in tasks)


# ── Slow Burns ─────────────────────────────────────────────────────────────────

def test_save_and_get_slow_burn():
    sb = SlowBurn(title="Learn Spanish", dimension=Dimension.LEARNING)
    storage.save_slow_burn(sb)
    items = storage.get_slow_burns()
    assert any(s.id == sb.id for s in items)


def test_slow_burn_idempotent_save():
    sb = SlowBurn(title="Get fit")
    storage.save_slow_burn(sb)
    sb.notes = "Updated notes"
    storage.save_slow_burn(sb)
    items = storage.get_slow_burns()
    matching = [s for s in items if s.id == sb.id]
    assert len(matching) == 1
    assert matching[0].notes == "Updated notes"


def test_delete_slow_burn():
    sb = SlowBurn(title="To be deleted")
    storage.save_slow_burn(sb)
    storage.delete_slow_burn(sb.id)
    items = storage.get_slow_burns()
    assert not any(s.id == sb.id for s in items)


# ── Milestones ─────────────────────────────────────────────────────────────────

def test_save_and_get_milestone():
    m = Milestone(title="Ship v1")
    storage.save_milestone(m)
    items = storage.get_milestones()
    assert any(x.id == m.id for x in items)


def test_get_milestones_by_goal():
    m1 = Milestone(title="Phase 1", goal_id="goal001")
    m2 = Milestone(title="Phase 2", goal_id="goal002")
    storage.save_milestone(m1)
    storage.save_milestone(m2)
    filtered = storage.get_milestones(goal_id="goal001")
    assert any(x.id == m1.id for x in filtered)
    assert not any(x.id == m2.id for x in filtered)


def test_delete_milestone():
    m = Milestone(title="Delete me")
    storage.save_milestone(m)
    storage.delete_milestone(m.id)
    items = storage.get_milestones()
    assert not any(x.id == m.id for x in items)


# ── Budgets ───────────────────────────────────────────────────────────────────

def test_save_and_get_budget():
    b = Budget(name="Monthly", total_limit=30000.0,
               period_start="2026-02-01", period_end="2026-02-28")
    storage.save_budget(b)
    budgets = storage.get_budgets()
    assert any(x.id == b.id for x in budgets)


def test_get_budget_by_id():
    b = Budget(name="Travel", total_limit=10000.0,
               period_start="2026-02-01", period_end="2026-02-28")
    storage.save_budget(b)
    found = storage.get_budget_by_id(b.id)
    assert found is not None
    assert found.name == "Travel"


def test_budget_summary_active_only():
    today = date.today()
    active = Budget(name="Active", total_limit=5000.0,
                    period_start=today.isoformat(),
                    period_end=(today + timedelta(days=30)).isoformat())
    expired = Budget(name="Expired", total_limit=5000.0,
                     period_start="2025-01-01", period_end="2025-01-31")
    storage.save_budget(active)
    storage.save_budget(expired)
    summary = storage.get_budget_summary()
    names = [s["name"] for s in summary]
    assert "Active" in names
    assert "Expired" not in names


# ── Transactions ──────────────────────────────────────────────────────────────

def test_save_transaction_updates_budget_spent():
    today = date.today()
    b = Budget(name="Test Budget", total_limit=10000.0,
               period_start=today.isoformat(),
               period_end=(today + timedelta(days=30)).isoformat())
    storage.save_budget(b)

    t = Transaction(amount=1500.0, category="food",
                    description="Groceries", budget_id=b.id)
    storage.save_transaction(t)

    updated_budget = storage.get_budget_by_id(b.id)
    assert updated_budget.spent == 1500.0


def test_multiple_transactions_accumulate():
    today = date.today()
    b = Budget(name="Multi txn", total_limit=20000.0,
               period_start=today.isoformat(),
               period_end=(today + timedelta(days=30)).isoformat())
    storage.save_budget(b)

    storage.save_transaction(Transaction(amount=500.0, category="food",
                                         description="Lunch", budget_id=b.id))
    storage.save_transaction(Transaction(amount=300.0, category="transport",
                                         description="Cab", budget_id=b.id))

    updated = storage.get_budget_by_id(b.id)
    assert updated.spent == 800.0


def test_transaction_without_budget():
    t = Transaction(amount=200.0, category="misc", description="Random spend")
    storage.save_transaction(t)  # Should not raise
    txns = storage.get_transactions()
    assert any(x.id == t.id for x in txns)


# ── Decisions ─────────────────────────────────────────────────────────────────

def test_save_and_get_decision():
    d = Decision(proposal="Launch podcast", outcome="approved",
                 reasoning="Good fit for learning season")
    storage.save_decision(d)
    decisions = storage.get_decisions()
    assert any(x.id == d.id for x in decisions)


def test_get_decisions_for_review():
    # Recent decision without actual_outcome — should show up
    d = Decision(proposal="Hire VA", outcome="approved",
                 reasoning="Time savings")
    storage.save_decision(d)

    for_review = storage.get_decisions_for_review(days=90)
    assert any(x.id == d.id for x in for_review)


def test_decisions_with_actual_outcome_excluded():
    d = Decision(proposal="Buy standing desk", outcome="approved",
                 reasoning="Ergonomics", actual_outcome="Great decision")
    storage.save_decision(d)

    for_review = storage.get_decisions_for_review(days=90)
    assert not any(x.id == d.id for x in for_review)


# ── Actuals ───────────────────────────────────────────────────────────────────

def test_save_and_get_actual():
    r = ActualRecord(task_id="t1", task_title="Test task",
                     planned_minutes=30, date=date.today().isoformat())
    storage.save_actual(r)
    records = storage.get_actuals()
    assert any(x.id == r.id for x in records)


def test_get_actuals_by_date():
    today = date.today().isoformat()
    r = ActualRecord(task_id="t2", task_title="Daily task",
                     planned_minutes=20, date=today)
    storage.save_actual(r)
    records = storage.get_actuals(for_date=today)
    assert any(x.id == r.id for x in records)


def test_get_plan_vs_actual():
    today = date.today().isoformat()
    r1 = ActualRecord(task_id="t3", task_title="Task A",
                      planned_minutes=60, actual_minutes=75, date=today)
    r2 = ActualRecord(task_id="t4", task_title="Task B",
                      planned_minutes=30, actual_minutes=20, date=today)
    storage.save_actual(r1)
    storage.save_actual(r2)

    summary = storage.get_plan_vs_actual(today)
    assert summary["planned_minutes"] == 90
    assert summary["actual_minutes"] == 95
    assert summary["delta_minutes"] == 5


def test_get_plan_vs_actual_empty():
    result = storage.get_plan_vs_actual("2020-01-01")
    assert result == {}


# ── Memory ────────────────────────────────────────────────────────────────────

def test_load_memory_empty():
    mem = storage.load_memory()
    assert mem["summaries"] == []
    assert mem["energy_patterns"] == {}


def test_update_memory_summary():
    storage.update_memory_summary("Planned 5 tasks, mode=full", source="plan")
    mem = storage.load_memory()
    assert len(mem["summaries"]) == 1
    assert mem["summaries"][0]["source"] == "plan"


def test_memory_keeps_last_30():
    for i in range(35):
        storage.update_memory_summary(f"Entry {i}", source="plan")
    mem = storage.load_memory()
    assert len(mem["summaries"]) == 30


def test_get_memory_context_empty():
    ctx = storage.get_memory_context()
    assert ctx == ""


def test_get_memory_context_with_entries():
    storage.update_memory_summary("Day was productive", source="log")
    ctx = storage.get_memory_context()
    assert "RECENT CONTEXT" in ctx
    assert "Day was productive" in ctx


# ── Constitution ──────────────────────────────────────────────────────────────

def test_save_and_load_constitution():
    content = "Family first. No work after 9pm. Exercise daily."
    storage.save_constitution(content)
    loaded = storage.load_constitution()
    assert loaded == content


def test_load_constitution_empty():
    loaded = storage.load_constitution()
    assert loaded == ""


# ── Coherence Score ───────────────────────────────────────────────────────────

def test_coherence_no_data():
    cfg = ViyugamConfig()
    result = storage.compute_coherence_score(cfg)
    assert result["score"] is None
    assert "Not enough data" in result["narrative"]


def test_coherence_with_tasks():
    today = date.today().isoformat()
    cfg = ViyugamConfig(season=SeasonConfig(name="Career Focus", focus=Dimension.CAREER))

    # Add some done tasks
    for i in range(3):
        t = Task(title=f"Career task {i}", status=TaskStatus.DONE,
                 dimension=Dimension.CAREER, scheduled_date=today)
        storage.save_task(t)

    result = storage.compute_coherence_score(cfg)
    assert result["score"] is not None
    assert 0 <= result["score"] <= 100
    assert isinstance(result["narrative"], str)
    assert len(result["narrative"]) > 0


# ── Calendar ──────────────────────────────────────────────────────────────────

def test_save_and_get_calendar_recurring():
    entry = CalendarEntry(title="Weekly standup", recurs_on=["mon"])
    storage.save_calendar_entry(entry)

    # Find a Monday
    d = date.today()
    while d.weekday() != 0:  # 0 = Monday
        d = d + __import__("datetime").timedelta(days=1)

    entries = storage.get_calendar_entries(d.isoformat())
    assert any(e.id == entry.id for e in entries)


def test_save_and_get_calendar_one_off():
    target_date = "2026-12-25"
    entry = CalendarEntry(title="Christmas", date=target_date)
    storage.save_calendar_entry(entry)

    entries = storage.get_calendar_entries(target_date)
    assert any(e.id == entry.id for e in entries)


# ── Day type ──────────────────────────────────────────────────────────────────

def test_get_day_type_no_schedule():
    cfg = ViyugamConfig()
    result = storage.get_day_type("2026-02-24", cfg)  # Tuesday — no schedule → wfh default
    assert result == "wfh"


def test_get_day_type_office():
    cfg = ViyugamConfig(
        work_schedule=WorkSchedule(
            office_days=["mon", "tue", "wed"],
            wfh_days=["thu", "fri"]
        )
    )
    # Monday = weekday 0
    result = storage.get_day_type("2026-02-23", cfg)  # Monday
    assert result == "office"


def test_get_day_type_off():
    cfg = ViyugamConfig(
        work_schedule=WorkSchedule(
            office_days=["mon", "tue"],
            wfh_days=["wed"]
        )
    )
    # Saturday
    result = storage.get_day_type("2026-02-28", cfg)  # Saturday
    assert result == "off"
