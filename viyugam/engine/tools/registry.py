"""engine/tools/registry.py — ToolSpec, TOOL_REGISTRY, and builder functions.

Each tool maps a name to its Anthropic declaration + executor path + metadata.
Executor resolution uses importlib lazy loading.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from . import declarations as decl


class ToolCategory(str, Enum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    declaration: dict               # Anthropic tool_use format
    executor_path: str              # dotted path for lazy import, e.g. "viyugam.engine.tools._executors.exec_get_tasks"
    domain: str                     # "task", "journal", "finance", etc.
    category: ToolCategory


def _resolve_executor(dotted_path: str) -> Callable:
    """Lazily import and return the callable at dotted_path."""
    module_path, _, func_name = dotted_path.rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


# ── Registry ──────────────────────────────────────────────────────────────────

_EXEC = "viyugam.engine.tools._executors"

TOOL_REGISTRY: dict[str, ToolSpec] = {
    # Task
    "get_tasks":        ToolSpec("get_tasks",        decl.GET_TASKS,        f"{_EXEC}.exec_get_tasks",        "task",    ToolCategory.READ),
    "get_task_by_id":   ToolSpec("get_task_by_id",   decl.GET_TASK_BY_ID,   f"{_EXEC}.exec_get_task_by_id",   "task",    ToolCategory.READ),
    "save_task":        ToolSpec("save_task",         decl.SAVE_TASK,        f"{_EXEC}.exec_save_task",        "task",    ToolCategory.WRITE),
    "mark_task_done":   ToolSpec("mark_task_done",    decl.MARK_TASK_DONE,   f"{_EXEC}.exec_mark_task_done",   "task",    ToolCategory.WRITE),
    # Project
    "get_projects":     ToolSpec("get_projects",      decl.GET_PROJECTS,     f"{_EXEC}.exec_get_projects",     "project", ToolCategory.READ),
    "save_project":     ToolSpec("save_project",      decl.SAVE_PROJECT,     f"{_EXEC}.exec_save_project",     "project", ToolCategory.WRITE),
    # Goal
    "get_goals":        ToolSpec("get_goals",         decl.GET_GOALS,        f"{_EXEC}.exec_get_goals",        "goal",    ToolCategory.READ),
    "save_goal":        ToolSpec("save_goal",         decl.SAVE_GOAL,        f"{_EXEC}.exec_save_goal",        "goal",    ToolCategory.WRITE),
    "delete_goal":      ToolSpec("delete_goal",       decl.DELETE_GOAL,      f"{_EXEC}.exec_delete_goal",      "goal",    ToolCategory.WRITE),
    # Triage
    "get_triage":       ToolSpec("get_triage",        decl.GET_TRIAGE,       f"{_EXEC}.exec_get_triage",       "triage",  ToolCategory.READ),
    "append_triage":    ToolSpec("append_triage",     decl.APPEND_TRIAGE,    f"{_EXEC}.exec_append_triage",    "triage",  ToolCategory.WRITE),
    "mark_triage_processed": ToolSpec("mark_triage_processed", decl.MARK_TRIAGE_PROCESSED, f"{_EXEC}.exec_mark_triage_processed", "triage", ToolCategory.WRITE),
    # Journal
    "get_recent_journals":  ToolSpec("get_recent_journals",  decl.GET_RECENT_JOURNALS,  f"{_EXEC}.exec_get_recent_journals",  "journal", ToolCategory.READ),
    "load_journal_summary": ToolSpec("load_journal_summary", decl.LOAD_JOURNAL_SUMMARY, f"{_EXEC}.exec_load_journal_summary", "journal", ToolCategory.READ),
    "save_journal":         ToolSpec("save_journal",         decl.SAVE_JOURNAL,         f"{_EXEC}.exec_save_journal",         "journal", ToolCategory.WRITE),
    # Finance
    "get_budget_summary":   ToolSpec("get_budget_summary",   decl.GET_BUDGET_SUMMARY,   f"{_EXEC}.exec_get_budget_summary",   "finance", ToolCategory.READ),
    "get_monthly_cashflow": ToolSpec("get_monthly_cashflow", decl.GET_MONTHLY_CASHFLOW, f"{_EXEC}.exec_get_monthly_cashflow", "finance", ToolCategory.READ),
    "get_recurring_items":  ToolSpec("get_recurring_items",  decl.GET_RECURRING_ITEMS,  f"{_EXEC}.exec_get_recurring_items",  "finance", ToolCategory.READ),
    "get_transactions":     ToolSpec("get_transactions",     decl.GET_TRANSACTIONS,     f"{_EXEC}.exec_get_transactions",     "finance", ToolCategory.READ),
    "save_transaction":     ToolSpec("save_transaction",     decl.SAVE_TRANSACTION,     f"{_EXEC}.exec_save_transaction",     "finance", ToolCategory.WRITE),
    # Calendar
    "get_calendar_events":  ToolSpec("get_calendar_events",  decl.GET_CALENDAR_EVENTS,  f"{_EXEC}.exec_get_calendar_events",  "calendar", ToolCategory.READ),
    # Values
    "load_values":          ToolSpec("load_values",          decl.LOAD_VALUES,          f"{_EXEC}.exec_load_values",          "values",   ToolCategory.READ),
    # GPS
    "get_priority_context": ToolSpec("get_priority_context", decl.GET_PRIORITY_CONTEXT, f"{_EXEC}.exec_get_priority_context", "gps",      ToolCategory.READ),
    # Notes
    "get_notes":            ToolSpec("get_notes",            decl.GET_NOTES,            f"{_EXEC}.exec_get_notes",            "notes",    ToolCategory.READ),
    "save_note":            ToolSpec("save_note",            decl.SAVE_NOTE,            f"{_EXEC}.exec_save_note",            "notes",    ToolCategory.WRITE),
    # Decision
    "get_decisions":        ToolSpec("get_decisions",        decl.GET_DECISIONS,        f"{_EXEC}.exec_get_decisions",        "decision", ToolCategory.READ),
    "save_decision":        ToolSpec("save_decision",        decl.SAVE_DECISION,        f"{_EXEC}.exec_save_decision",        "decision", ToolCategory.WRITE),
    # System
    "get_system_state":     ToolSpec("get_system_state",     decl.GET_SYSTEM_STATE,     f"{_EXEC}.exec_get_system_state",     "system",   ToolCategory.READ),
    "save_system_state":    ToolSpec("save_system_state",    decl.SAVE_SYSTEM_STATE,    f"{_EXEC}.exec_save_system_state",    "system",   ToolCategory.WRITE),
    # Memory
    "get_memory_context":   ToolSpec("get_memory_context",   decl.GET_MEMORY_CONTEXT,   f"{_EXEC}.exec_get_memory_context",   "memory",   ToolCategory.READ),
}


# ── Builder functions ─────────────────────────────────────────────────────────

def build_tools_for_agent(
    domains: list[str],
) -> tuple[list[dict], dict[str, Callable]]:
    """Return (tool_declarations, dispatch_dict) filtered by domains."""
    declarations: list[dict] = []
    dispatch: dict[str, Callable] = {}
    for spec in TOOL_REGISTRY.values():
        if spec.domain in domains:
            declarations.append(spec.declaration)
            dispatch[spec.name] = _resolve_executor(spec.executor_path)
    return declarations, dispatch


def build_all_read_tools() -> tuple[list[dict], dict[str, Callable]]:
    """All READ tools -- for the router agent that can answer queries directly."""
    declarations: list[dict] = []
    dispatch: dict[str, Callable] = {}
    for spec in TOOL_REGISTRY.values():
        if spec.category == ToolCategory.READ:
            declarations.append(spec.declaration)
            dispatch[spec.name] = _resolve_executor(spec.executor_path)
    return declarations, dispatch
