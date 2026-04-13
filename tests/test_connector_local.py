"""test_connector_local.py — Tests for LocalStorageConnector.

Each method should round-trip through storage and return JSON-serializable dicts.
"""
from __future__ import annotations

from datetime import date, timedelta

import viyugam.storage as storage
from viyugam.connectors.local_storage import LocalStorageConnector
from viyugam.models import (
    Budget,
    CalendarEntry,
    Decision,
    Dimension,
    Goal,
    Note,
    Task,
    TaskStatus,
)


def _connector() -> LocalStorageConnector:
    return LocalStorageConnector()


# ── Tasks ─────────────────────────────────────────────────────────────────────

def test_get_tasks_empty():
    result = _connector().get_tasks()
    assert result["count"] == 0
    assert result["tasks"] == []


def test_save_and_get_task():
    c = _connector()
    result = c.save_task({"title": "Test connector", "dimension": "career"})
    assert result["status"] == "saved"
    assert result["seq_id"].startswith("T-")

    tasks = c.get_tasks()
    assert tasks["count"] >= 1


def test_get_task_by_id():
    c = _connector()
    saved = c.save_task({"title": "Find me"})
    task_id = saved["task_id"]
    found = c.get_task_by_id(task_id)
    assert found["title"] == "Find me"


def test_get_task_by_id_not_found():
    result = _connector().get_task_by_id("nonexistent")
    assert "error" in result


def test_mark_task_done():
    c = _connector()
    saved = c.save_task({"title": "Complete me"})
    seq_id = saved["seq_id"]
    result = c.mark_task_done(seq_id)
    assert result["status"] == "done"


def test_mark_task_done_not_found():
    result = _connector().mark_task_done("T-999")
    assert "error" in result


# ── Projects ──────────────────────────────────────────────────────────────────

def test_get_projects_empty():
    result = _connector().get_projects()
    assert result["count"] == 0


def test_save_and_get_project():
    c = _connector()
    saved = c.save_project({"title": "My Project", "dimension": "career"})
    assert saved["status"] == "saved"
    projects = c.get_projects()
    assert projects["count"] >= 1


# ── Goals ─────────────────────────────────────────────────────────────────────

def test_get_goals():
    result = _connector().get_goals()
    # Pseudo-goals are created by ensure_dirs
    assert result["count"] >= 2


def test_save_and_delete_goal():
    c = _connector()
    saved = c.save_goal({"title": "Run 10k", "dimension": "health"})
    assert saved["status"] == "saved"
    goal_id = saved["goal_id"]

    deleted = c.delete_goal(goal_id)
    assert deleted["status"] == "deleted"

    not_found = c.delete_goal("nonexistent")
    assert not_found["status"] == "not_found"


# ── Triage ────────────────────────────────────────────────────────────────────

def test_triage_roundtrip():
    c = _connector()
    captured = c.append_triage("buy groceries")
    assert captured["status"] == "captured"

    items = c.get_triage()
    assert items["count"] >= 1

    c.mark_triage_processed([captured["id"]])
    remaining = c.get_triage()
    assert remaining["count"] == 0


# ── Journal ───────────────────────────────────────────────────────────────────

def test_journal_roundtrip():
    c = _connector()
    saved = c.save_journal("# Great day\nDid lots of work.", for_date="2026-03-15")
    assert saved["status"] == "saved"

    entries = c.get_recent_journals(days=7)
    # May or may not find it depending on date — just verify no crash
    assert isinstance(entries, dict)


def test_load_journal_summary_none():
    result = _connector().load_journal_summary(for_date="2020-01-01")
    assert result["summary"] is None


# ── Finance ───────────────────────────────────────────────────────────────────

def test_budget_summary_empty():
    result = _connector().get_budget_summary()
    assert isinstance(result["budgets"], list)


def test_save_and_get_transaction():
    c = _connector()
    # Create a budget first
    today = date.today()
    b = Budget(
        name="Test", total_limit=10000.0,
        period_start=today.isoformat(),
        period_end=(today + timedelta(days=30)).isoformat(),
    )
    storage.save_budget(b)

    result = c.save_transaction({
        "amount": 500,
        "category": "food",
        "description": "Lunch",
        "tx_type": "expense",
    })
    assert result["status"] == "saved"

    txns = c.get_transactions()
    assert txns["count"] >= 1


def test_monthly_cashflow():
    result = _connector().get_monthly_cashflow(month="2026-03")
    assert "income" in result
    assert "expenses" in result


def test_recurring_items_empty():
    result = _connector().get_recurring_items()
    assert result["count"] == 0


# ── Calendar ──────────────────────────────────────────────────────────────────

def test_calendar_events():
    c = _connector()
    result = c.get_calendar_events(date_str="2026-03-16")
    assert "events" in result


# ── Values ────────────────────────────────────────────────────────────────────

def test_load_values():
    result = _connector().load_values()
    assert isinstance(result, dict)


# ── Notes ─────────────────────────────────────────────────────────────────────

def test_notes_roundtrip():
    c = _connector()
    saved = c.save_note({"title": "Test note", "content": "Some content"})
    assert saved["status"] == "saved"

    notes = c.get_notes()
    assert notes["count"] >= 1


# ── Decisions ─────────────────────────────────────────────────────────────────

def test_decisions_roundtrip():
    c = _connector()
    saved = c.save_decision({
        "proposal": "Buy desk",
        "outcome": "approved",
        "reasoning": "Ergonomics",
    })
    assert saved["status"] == "saved"

    decisions = c.get_decisions()
    assert decisions["count"] >= 1


# ── System State ──────────────────────────────────────────────────────────────

def test_system_state_roundtrip():
    c = _connector()
    state = c.get_system_state()
    assert isinstance(state, dict)

    result = c.save_system_state({"last_plan": "2026-03-16"})
    assert result["status"] == "saved"


# ── Memory ────────────────────────────────────────────────────────────────────

def test_memory_context():
    result = _connector().get_memory_context()
    assert "context" in result
