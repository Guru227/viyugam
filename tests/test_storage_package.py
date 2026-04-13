"""test_storage_package.py — Verify the storage/ package split preserves all exports."""
from __future__ import annotations

import viyugam.storage as storage
from viyugam.storage import _paths


# ── All path constants accessible via storage.* ──────────────────────────────

def test_path_constants_exist():
    path_attrs = [
        "HOME", "DATA", "JOURNALS", "JOURNAL", "RESEARCH", "PLANS",
        "CONFIG_FILE", "CALENDAR_FILE", "CALENDAR_ICS",
        "SLOW_BURNS_FILE", "MILESTONES_FILE", "BUDGETS_FILE", "BUDGET_YAML",
        "TRANSACTIONS_FILE", "DECISIONS_FILE", "ACTUALS_FILE",
        "MEMORY_FILE", "CONSTITUTION_FILE", "VALUES_FILE",
        "ENERGY_CACHE_FILE", "OKRS_FILE", "PROJECT_PLANS_FILE",
        "RECURRING_FILE", "JOURNALS_DIR", "TRIAGE_FILE",
        "COUNTERS_FILE", "NOTES_FILE", "NUDGES_FILE", "PATTERNS_FILE",
        "SESSIONS_DIR",
    ]
    for attr in path_attrs:
        assert hasattr(storage, attr), f"storage.{attr} missing"
        assert hasattr(_paths, attr), f"_paths.{attr} missing"


# ── All public functions re-exported ─────────────────────────────────────────

def test_core_functions():
    fns = [
        "ensure_dirs", "load_config", "save_config",
        "load_state", "save_state", "touch_active", "check_resilience",
        "mark_entity_done", "period_start", "period_end", "next_sunday",
        "settle_bankruptcy", "calculate_actual_season", "get_season_drift",
        "get_avg_dimension_scores", "compute_coherence_score",
        "get_energy_pattern",
    ]
    for fn in fns:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_task_functions():
    for fn in ["get_tasks", "get_task_by_id", "save_task", "save_tasks", "get_habits"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_project_functions():
    for fn in ["get_projects", "save_project", "project_stats",
               "get_all_project_plans", "get_project_plan", "save_project_plan"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_goal_functions():
    for fn in ["get_goals", "save_goal", "delete_goal"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_triage_functions():
    for fn in ["get_triage", "append_triage", "save_triage_item",
               "mark_triage_processed", "get_recent_triage_logs",
               "get_inbox", "append_inbox", "mark_inbox_processed",
               "get_someday", "save_someday", "delete_someday"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_journal_functions():
    for fn in ["journal_path", "load_journal", "save_journal",
               "get_recent_journals", "load_journal_summary",
               "get_recent_summaries", "save_research"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_finance_functions():
    for fn in ["get_budgets", "get_budget_by_id", "save_budget",
               "get_transactions", "save_transaction", "get_budget_summary",
               "get_recurring_items", "save_recurring_item", "delete_recurring_item",
               "get_transactions_by_period", "get_spending_by_category",
               "get_monthly_cashflow", "get_due_recurring_items",
               "get_finance_context", "load_budget_yaml", "save_budget_yaml",
               "get_budget_envelope_summary"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_calendar_functions():
    for fn in ["get_calendar_entries", "save_calendar_entry",
               "delete_calendar_entry", "get_day_type", "parse_ics",
               "get_ics_events_for_period"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_notes_functions():
    for fn in ["get_notes", "save_note"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_values_functions():
    for fn in ["load_values", "save_values", "load_constitution", "save_constitution"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_plans_functions():
    for fn in ["load_plan", "save_plan"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_nudge_functions():
    for fn in ["get_nudges", "get_stored_nudges", "save_nudge",
               "dismiss_nudge", "get_patterns", "save_pattern", "merge_pattern"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_decision_functions():
    for fn in ["get_decisions", "save_decision", "get_decisions_for_review",
               "save_actual", "get_actuals", "get_plan_vs_actual"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_okr_functions():
    for fn in ["get_okrs", "save_okr", "get_current_quarter", "get_next_quarter"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_memory_functions():
    for fn in ["load_memory", "save_memory", "update_memory_summary", "get_memory_context"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_slow_burn_functions():
    for fn in ["get_slow_burns", "save_slow_burn", "delete_slow_burn",
               "get_milestones", "save_milestone", "delete_milestone"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


def test_session_functions():
    for fn in ["save_chat_session", "load_last_chat_session"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


# ── Private helpers re-exported for GPS tests ────────────────────────────────

def test_private_helpers_exported():
    for fn in ["_next_id", "_check_unblocked", "_recompute_goal_progress"]:
        assert callable(getattr(storage, fn, None)), f"storage.{fn} not callable"


# ── Submodule imports work ───────────────────────────────────────────────────

def test_submodule_direct_import():
    from viyugam.storage.tasks import get_tasks
    from viyugam.storage.goals import get_goals
    from viyugam.storage.finance import get_budgets
    from viyugam.storage.journal import load_journal
    from viyugam.storage.core import load_config
    # Just verify they're callable
    assert callable(get_tasks)
    assert callable(get_goals)
    assert callable(get_budgets)
    assert callable(load_journal)
    assert callable(load_config)
