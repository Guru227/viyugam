"""
viyugam.storage — All file I/O for Viyugam.

This package re-exports every public symbol from its submodules so that
existing code using ``import viyugam.storage as storage; storage.get_tasks()``
continues to work unchanged.
"""
from __future__ import annotations

# ── Path constants (re-exported from _paths) ──────────────────────────────────
from ._paths import (  # noqa: F401
    ACTUALS_FILE,
    BUDGET_YAML,
    BUDGETS_FILE,
    CALENDAR_FILE,
    CALENDAR_ICS,
    CONFIG_FILE,
    CONSTITUTION_FILE,
    COUNTERS_FILE,
    DATA,
    DECISIONS_FILE,
    ENERGY_CACHE_FILE,
    HOME,
    JOURNAL,
    JOURNALS,
    JOURNALS_DIR,
    MEMORY_FILE,
    MILESTONES_FILE,
    NOTES_FILE,
    NUDGES_FILE,
    OKRS_FILE,
    PATTERNS_FILE,
    PLANS,
    PROJECT_PLANS_FILE,
    RECURRING_FILE,
    RESEARCH,
    SESSIONS_DIR,
    SLOW_BURNS_FILE,
    TRANSACTIONS_FILE,
    TRIAGE_FILE,
    VALUES_FILE,
    _next_id,
)

# ── Calendar ──────────────────────────────────────────────────────────────────
from .calendar import (  # noqa: F401
    delete_calendar_entry,
    get_calendar_entries,
    get_day_type,
    get_ics_events_for_period,
    parse_ics,
    save_calendar_entry,
)

# ── Core (config, state, ensure_dirs, coherence, etc.) ───────────────────────
from .core import (  # noqa: F401
    calculate_actual_season,
    check_resilience,
    compute_coherence_score,
    ensure_dirs,
    get_avg_dimension_scores,
    get_energy_pattern,
    get_season_drift,
    load_config,
    load_state,
    mark_entity_done,
    next_sunday,
    period_end,
    period_start,
    save_config,
    save_state,
    settle_bankruptcy,
    touch_active,
)

# ── Decisions / Actuals ──────────────────────────────────────────────────────
from .decisions import (  # noqa: F401
    get_actuals,
    get_decisions,
    get_decisions_for_review,
    get_plan_vs_actual,
    save_actual,
    save_decision,
)

# ── Finance ───────────────────────────────────────────────────────────────────
from .finance import (  # noqa: F401
    delete_recurring_item,
    get_budget_by_id,
    get_budget_envelope_summary,
    get_budget_summary,
    get_budgets,
    get_due_recurring_items,
    get_finance_context,
    get_monthly_cashflow,
    get_recurring_items,
    get_spending_by_category,
    get_transactions,
    get_transactions_by_period,
    load_budget_yaml,
    save_budget,
    save_budget_yaml,
    save_recurring_item,
    save_transaction,
)

# ── Goals ─────────────────────────────────────────────────────────────────────
from .goals import (  # noqa: F401
    _recompute_goal_progress,
    delete_goal,
    get_goals,
    save_goal,
)

# ── Journal ───────────────────────────────────────────────────────────────────
from .journal import (  # noqa: F401
    get_recent_journals,
    get_recent_summaries,
    journal_path,
    load_journal,
    load_journal_summary,
    save_journal,
    save_research,
)

# ── Memory ────────────────────────────────────────────────────────────────────
from .memory import (  # noqa: F401
    get_memory_context,
    load_memory,
    save_memory,
    update_memory_summary,
)

# ── Notes ─────────────────────────────────────────────────────────────────────
from .notes import (  # noqa: F401
    get_notes,
    save_note,
)

# ── Nudges / Patterns ────────────────────────────────────────────────────────
from .nudges import (  # noqa: F401
    dismiss_nudge,
    get_nudges,
    get_patterns,
    get_stored_nudges,
    merge_pattern,
    save_nudge,
    save_pattern,
)

# ── OKRs ──────────────────────────────────────────────────────────────────────
from .okrs import (  # noqa: F401
    get_current_quarter,
    get_next_quarter,
    get_okrs,
    save_okr,
)

# ── Plans ─────────────────────────────────────────────────────────────────────
from .plans import (  # noqa: F401
    load_plan,
    save_plan,
)

# ── Projects ──────────────────────────────────────────────────────────────────
from .projects import (  # noqa: F401
    get_all_project_plans,
    get_project_plan,
    get_projects,
    project_stats,
    save_project,
    save_project_plan,
)

# ── Sessions ──────────────────────────────────────────────────────────────────
from .sessions import (  # noqa: F401
    load_last_chat_session,
    save_chat_session,
)

# ── Slow Burns / Milestones ──────────────────────────────────────────────────
from .slow_burns import (  # noqa: F401
    delete_milestone,
    delete_slow_burn,
    get_milestones,
    get_slow_burns,
    save_milestone,
    save_slow_burn,
)

# ── Tasks ─────────────────────────────────────────────────────────────────────
from .tasks import (  # noqa: F401
    _check_unblocked,
    get_habits,
    get_task_by_id,
    get_tasks,
    save_task,
    save_tasks,
)

# ── Triage / Inbox / Someday ─────────────────────────────────────────────────
from .triage import (  # noqa: F401
    append_inbox,
    append_triage,
    delete_someday,
    get_inbox,
    get_recent_triage_logs,
    get_someday,
    get_triage,
    mark_inbox_processed,
    mark_triage_processed,
    save_someday,
    save_triage_item,
)

# ── Values / Constitution ────────────────────────────────────────────────────
from .values import (  # noqa: F401
    load_constitution,
    load_values,
    save_constitution,
    save_values,
)
