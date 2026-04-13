"""engine/tools/_executors.py — Thin executor functions.

Each executor receives ``(args: dict, *, connector, **kw)`` and calls the connector.
If no connector is provided, falls back to the local storage connector.
"""
from __future__ import annotations

from typing import Any


def _get_connector(connector: Any = None):
    """Return the provided connector or the default LocalStorageConnector."""
    if connector is not None:
        return connector
    from viyugam.connectors.local_storage import LocalStorageConnector
    return LocalStorageConnector()


# ── Task executors ────────────────────────────────────────────────────────────

def exec_get_tasks(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_tasks(
        status=args.get("status"),
        scheduled_date=args.get("scheduled_date"),
    )


def exec_get_task_by_id(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_task_by_id(task_id=args["task_id"])


def exec_save_task(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.save_task(task_data=args)


def exec_mark_task_done(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.mark_task_done(task_id=args["task_id"])


# ── Project executors ─────────────────────────────────────────────────────────

def exec_get_projects(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_projects(status=args.get("status"))


def exec_save_project(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.save_project(project_data=args)


# ── Goal executors ────────────────────────────────────────────────────────────

def exec_get_goals(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_goals(active_only=args.get("active_only", True))


def exec_save_goal(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.save_goal(goal_data=args)


def exec_delete_goal(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.delete_goal(goal_id=args["goal_id"])


# ── Triage executors ──────────────────────────────────────────────────────────

def exec_get_triage(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_triage(unprocessed_only=args.get("unprocessed_only", True))


def exec_append_triage(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.append_triage(
        content=args["content"],
        source=args.get("source", "cli"),
    )


def exec_mark_triage_processed(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.mark_triage_processed(item_ids=args["item_ids"])


# ── Journal executors ─────────────────────────────────────────────────────────

def exec_get_recent_journals(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_recent_journals(days=args.get("days", 14))


def exec_load_journal_summary(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.load_journal_summary(for_date=args.get("for_date"))


def exec_save_journal(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.save_journal(
        content=args["content"],
        for_date=args.get("for_date"),
    )


# ── Finance executors ─────────────────────────────────────────────────────────

def exec_get_budget_summary(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_budget_summary()


def exec_get_monthly_cashflow(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_monthly_cashflow(month=args["month"])


def exec_get_recurring_items(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_recurring_items(active_only=args.get("active_only", True))


def exec_get_transactions(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_transactions(budget_id=args.get("budget_id"))


def exec_save_transaction(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.save_transaction(tx_data=args)


# ── Calendar executors ────────────────────────────────────────────────────────

def exec_get_calendar_events(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_calendar_events(date_str=args["date"])


# ── Values executors ──────────────────────────────────────────────────────────

def exec_load_values(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.load_values()


# ── GPS executors ─────────────────────────────────────────────────────────────

def exec_get_priority_context(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_priority_context()


# ── Notes executors ───────────────────────────────────────────────────────────

def exec_get_notes(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_notes()


def exec_save_note(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.save_note(note_data=args)


# ── Decision executors ────────────────────────────────────────────────────────

def exec_get_decisions(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_decisions()


def exec_save_decision(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.save_decision(decision_data=args)


# ── System executors ──────────────────────────────────────────────────────────

def exec_get_system_state(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_system_state()


def exec_save_system_state(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.save_system_state(state_data=args)


# ── Memory executors ──────────────────────────────────────────────────────────

def exec_get_memory_context(args: dict, *, connector=None, **_kw) -> dict:
    c = _get_connector(connector)
    return c.get_memory_context(max_entries=args.get("max_entries", 7))
