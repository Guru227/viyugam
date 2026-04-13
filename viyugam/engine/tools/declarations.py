"""engine/tools/declarations.py — Tool specs in Anthropic tool_use format.

Pure data. Zero imports from agents or storage. Each tool is a dict matching
the Anthropic ``tools`` parameter schema.
"""
from __future__ import annotations

# ── Task tools ────────────────────────────────────────────────────────────────

GET_TASKS = {
    "name": "get_tasks",
    "description": "Retrieve tasks, optionally filtered by status and/or scheduled date.",
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["todo", "in_progress", "done", "backlog"],
                "description": "Filter by task status.",
            },
            "scheduled_date": {
                "type": "string",
                "description": "Filter by scheduled date (YYYY-MM-DD).",
            },
        },
        "required": [],
    },
}

GET_TASK_BY_ID = {
    "name": "get_task_by_id",
    "description": "Look up a single task by its ID or sequential ID (e.g. T-001).",
    "input_schema": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Task ID or seq_id."},
        },
        "required": ["task_id"],
    },
}

SAVE_TASK = {
    "name": "save_task",
    "description": "Create or update a task.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "dimension": {
                "type": "string",
                "enum": ["health", "wealth", "career", "relationships", "joy", "learning"],
            },
            "scheduled_date": {"type": "string", "description": "YYYY-MM-DD"},
            "estimated_minutes": {"type": "integer", "default": 30},
            "project_id": {"type": "string"},
            "aligns_to": {
                "type": "array", "items": {"type": "string"},
                "description": "Goal IDs this task aligns to.",
            },
        },
        "required": ["title"],
    },
}

MARK_TASK_DONE = {
    "name": "mark_task_done",
    "description": "Mark a task as done by its sequential ID (e.g. T-001).",
    "input_schema": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Sequential ID like T-001."},
        },
        "required": ["task_id"],
    },
}

# ── Project tools ─────────────────────────────────────────────────────────────

GET_PROJECTS = {
    "name": "get_projects",
    "description": "Retrieve all projects, optionally filtered by status.",
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["active", "paused", "completed", "icebox"],
            },
        },
        "required": [],
    },
}

SAVE_PROJECT = {
    "name": "save_project",
    "description": "Create or update a project.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "dimension": {
                "type": "string",
                "enum": ["health", "wealth", "career", "relationships", "joy", "learning"],
            },
            "budget_cap": {"type": "number"},
        },
        "required": ["title"],
    },
}

# ── Goal tools ────────────────────────────────────────────────────────────────

GET_GOALS = {
    "name": "get_goals",
    "description": "Retrieve goals. By default only active goals.",
    "input_schema": {
        "type": "object",
        "properties": {
            "active_only": {"type": "boolean", "default": True},
        },
        "required": [],
    },
}

SAVE_GOAL = {
    "name": "save_goal",
    "description": "Create or update a goal.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "dimension": {
                "type": "string",
                "enum": ["health", "wealth", "career", "relationships", "joy", "learning"],
            },
        },
        "required": ["title", "dimension"],
    },
}

DELETE_GOAL = {
    "name": "delete_goal",
    "description": "Permanently delete a goal by ID.",
    "input_schema": {
        "type": "object",
        "properties": {
            "goal_id": {"type": "string"},
        },
        "required": ["goal_id"],
    },
}

# ── Triage tools ──────────────────────────────────────────────────────────────

GET_TRIAGE = {
    "name": "get_triage",
    "description": "Get unprocessed triage items (quick captures awaiting processing).",
    "input_schema": {
        "type": "object",
        "properties": {
            "unprocessed_only": {"type": "boolean", "default": True},
        },
        "required": [],
    },
}

APPEND_TRIAGE = {
    "name": "append_triage",
    "description": "Capture a new item to the triage inbox.",
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The captured text."},
            "source": {"type": "string", "default": "cli"},
        },
        "required": ["content"],
    },
}

MARK_TRIAGE_PROCESSED = {
    "name": "mark_triage_processed",
    "description": "Mark triage items as processed.",
    "input_schema": {
        "type": "object",
        "properties": {
            "item_ids": {
                "type": "array", "items": {"type": "string"},
                "description": "IDs of triage items to mark as processed.",
            },
        },
        "required": ["item_ids"],
    },
}

# ── Journal tools ─────────────────────────────────────────────────────────────

GET_RECENT_JOURNALS = {
    "name": "get_recent_journals",
    "description": "Get recent journal entries as (date, content) pairs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "days": {"type": "integer", "default": 14},
        },
        "required": [],
    },
}

LOAD_JOURNAL_SUMMARY = {
    "name": "load_journal_summary",
    "description": "Load the structured summary from a journal entry.",
    "input_schema": {
        "type": "object",
        "properties": {
            "for_date": {"type": "string", "description": "YYYY-MM-DD, defaults to today."},
        },
        "required": [],
    },
}

SAVE_JOURNAL = {
    "name": "save_journal",
    "description": "Save journal content for a given date.",
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "for_date": {"type": "string", "description": "YYYY-MM-DD, defaults to today."},
        },
        "required": ["content"],
    },
}

# ── Finance tools ─────────────────────────────────────────────────────────────

GET_BUDGET_SUMMARY = {
    "name": "get_budget_summary",
    "description": "Get active budget envelopes with spent/remaining amounts.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

GET_MONTHLY_CASHFLOW = {
    "name": "get_monthly_cashflow",
    "description": "Get income/expense/net for a given month.",
    "input_schema": {
        "type": "object",
        "properties": {
            "month": {"type": "string", "description": "YYYY-MM format."},
        },
        "required": ["month"],
    },
}

GET_RECURRING_ITEMS = {
    "name": "get_recurring_items",
    "description": "Get recurring financial items (salary, EMIs, subscriptions).",
    "input_schema": {
        "type": "object",
        "properties": {
            "active_only": {"type": "boolean", "default": True},
        },
        "required": [],
    },
}

GET_TRANSACTIONS = {
    "name": "get_transactions",
    "description": "Get all transactions, optionally filtered by budget.",
    "input_schema": {
        "type": "object",
        "properties": {
            "budget_id": {"type": "string"},
        },
        "required": [],
    },
}

SAVE_TRANSACTION = {
    "name": "save_transaction",
    "description": "Record a financial transaction.",
    "input_schema": {
        "type": "object",
        "properties": {
            "amount": {"type": "number"},
            "category": {"type": "string"},
            "description": {"type": "string"},
            "tx_type": {"type": "string", "enum": ["expense", "income"]},
            "budget_id": {"type": "string"},
        },
        "required": ["amount", "category", "description"],
    },
}

# ── Calendar tools ────────────────────────────────────────────────────────────

GET_CALENDAR_EVENTS = {
    "name": "get_calendar_events",
    "description": "Get calendar events for a specific date.",
    "input_schema": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        "required": ["date"],
    },
}

# ── Values tools ──────────────────────────────────────────────────────────────

LOAD_VALUES = {
    "name": "load_values",
    "description": "Load the user's values document (prayer + dimension chapters).",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

# ── GPS tools ─────────────────────────────────────────────────────────────────

GET_PRIORITY_CONTEXT = {
    "name": "get_priority_context",
    "description": "Get GPS priority engine context: scored tasks, nudges, goal trajectories.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

# ── Notes tools ───────────────────────────────────────────────────────────────

GET_NOTES = {
    "name": "get_notes",
    "description": "Get all notes.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

SAVE_NOTE = {
    "name": "save_note",
    "description": "Create or update a note.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["title"],
    },
}

# ── Decision tools ────────────────────────────────────────────────────────────

GET_DECISIONS = {
    "name": "get_decisions",
    "description": "Get past boardroom decisions.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

SAVE_DECISION = {
    "name": "save_decision",
    "description": "Record a decision from the boardroom.",
    "input_schema": {
        "type": "object",
        "properties": {
            "proposal": {"type": "string"},
            "outcome": {"type": "string"},
            "reasoning": {"type": "string"},
        },
        "required": ["proposal", "outcome", "reasoning"],
    },
}

# ── System tools ──────────────────────────────────────────────────────────────

GET_SYSTEM_STATE = {
    "name": "get_system_state",
    "description": "Get system state: last plan/review/log dates, streak, resilience.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

SAVE_SYSTEM_STATE = {
    "name": "save_system_state",
    "description": "Update system state fields.",
    "input_schema": {
        "type": "object",
        "properties": {
            "last_plan": {"type": "string"},
            "last_review": {"type": "string"},
            "last_log": {"type": "string"},
        },
        "required": [],
    },
}

# ── Memory tools ──────────────────────────────────────────────────────────────

GET_MEMORY_CONTEXT = {
    "name": "get_memory_context",
    "description": "Get recent rolling memory context for continuity across sessions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "max_entries": {"type": "integer", "default": 7},
        },
        "required": [],
    },
}


# ── All declarations as a flat list ──────────────────────────────────────────

ALL_DECLARATIONS: list[dict] = [
    GET_TASKS, GET_TASK_BY_ID, SAVE_TASK, MARK_TASK_DONE,
    GET_PROJECTS, SAVE_PROJECT,
    GET_GOALS, SAVE_GOAL, DELETE_GOAL,
    GET_TRIAGE, APPEND_TRIAGE, MARK_TRIAGE_PROCESSED,
    GET_RECENT_JOURNALS, LOAD_JOURNAL_SUMMARY, SAVE_JOURNAL,
    GET_BUDGET_SUMMARY, GET_MONTHLY_CASHFLOW, GET_RECURRING_ITEMS,
    GET_TRANSACTIONS, SAVE_TRANSACTION,
    GET_CALENDAR_EVENTS,
    LOAD_VALUES,
    GET_PRIORITY_CONTEXT,
    GET_NOTES, SAVE_NOTE,
    GET_DECISIONS, SAVE_DECISION,
    GET_SYSTEM_STATE, SAVE_SYSTEM_STATE,
    GET_MEMORY_CONTEXT,
]
