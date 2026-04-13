"""test_engine_executors.py — Tests for executor functions via mock connector."""
from __future__ import annotations

from unittest.mock import MagicMock

from viyugam.engine.tools._executors import (
    exec_append_triage,
    exec_get_budget_summary,
    exec_get_calendar_events,
    exec_get_decisions,
    exec_get_goals,
    exec_get_memory_context,
    exec_get_notes,
    exec_get_projects,
    exec_get_system_state,
    exec_get_tasks,
    exec_get_triage,
    exec_load_values,
    exec_mark_task_done,
    exec_save_decision,
    exec_save_task,
)


def _mock_connector(**overrides) -> MagicMock:
    c = MagicMock()
    for key, val in overrides.items():
        setattr(c, key, MagicMock(return_value=val))
    return c


def test_exec_get_tasks_delegates():
    c = _mock_connector(get_tasks={"tasks": [], "count": 0})
    result = exec_get_tasks({"status": "todo"}, connector=c)
    c.get_tasks.assert_called_once_with(status="todo", scheduled_date=None)
    assert result == {"tasks": [], "count": 0}


def test_exec_get_tasks_no_filters():
    c = _mock_connector(get_tasks={"tasks": [], "count": 0})
    exec_get_tasks({}, connector=c)
    c.get_tasks.assert_called_once_with(status=None, scheduled_date=None)


def test_exec_save_task_delegates():
    c = _mock_connector(save_task={"status": "saved"})
    result = exec_save_task({"title": "Test"}, connector=c)
    c.save_task.assert_called_once_with(task_data={"title": "Test"})
    assert result["status"] == "saved"


def test_exec_mark_task_done_delegates():
    c = _mock_connector(mark_task_done={"status": "done"})
    result = exec_mark_task_done({"task_id": "T-001"}, connector=c)
    c.mark_task_done.assert_called_once_with(task_id="T-001")


def test_exec_get_projects_delegates():
    c = _mock_connector(get_projects={"projects": [], "count": 0})
    exec_get_projects({"status": "active"}, connector=c)
    c.get_projects.assert_called_once_with(status="active")


def test_exec_get_goals_delegates():
    c = _mock_connector(get_goals={"goals": [], "count": 0})
    exec_get_goals({"active_only": False}, connector=c)
    c.get_goals.assert_called_once_with(active_only=False)


def test_exec_get_triage_delegates():
    c = _mock_connector(get_triage={"items": [], "count": 0})
    exec_get_triage({}, connector=c)
    c.get_triage.assert_called_once_with(unprocessed_only=True)


def test_exec_append_triage_delegates():
    c = _mock_connector(append_triage={"status": "captured"})
    exec_append_triage({"content": "buy milk"}, connector=c)
    c.append_triage.assert_called_once_with(content="buy milk", source="cli")


def test_exec_get_budget_summary_delegates():
    c = _mock_connector(get_budget_summary={"budgets": []})
    exec_get_budget_summary({}, connector=c)
    c.get_budget_summary.assert_called_once()


def test_exec_get_calendar_events_delegates():
    c = _mock_connector(get_calendar_events={"events": []})
    exec_get_calendar_events({"date": "2026-03-16"}, connector=c)
    c.get_calendar_events.assert_called_once_with(date_str="2026-03-16")


def test_exec_load_values_delegates():
    c = _mock_connector(load_values={"prayer": "", "chapters": {}})
    exec_load_values({}, connector=c)
    c.load_values.assert_called_once()


def test_exec_get_notes_delegates():
    c = _mock_connector(get_notes={"notes": [], "count": 0})
    exec_get_notes({}, connector=c)
    c.get_notes.assert_called_once()


def test_exec_get_decisions_delegates():
    c = _mock_connector(get_decisions={"decisions": [], "count": 0})
    exec_get_decisions({}, connector=c)
    c.get_decisions.assert_called_once()


def test_exec_save_decision_delegates():
    c = _mock_connector(save_decision={"status": "saved"})
    data = {"proposal": "Buy desk", "outcome": "yes", "reasoning": "ergonomics"}
    exec_save_decision(data, connector=c)
    c.save_decision.assert_called_once_with(decision_data=data)


def test_exec_get_system_state_delegates():
    c = _mock_connector(get_system_state={"last_plan": "2026-03-16"})
    exec_get_system_state({}, connector=c)
    c.get_system_state.assert_called_once()


def test_exec_get_memory_context_delegates():
    c = _mock_connector(get_memory_context={"context": ""})
    exec_get_memory_context({"max_entries": 5}, connector=c)
    c.get_memory_context.assert_called_once_with(max_entries=5)
