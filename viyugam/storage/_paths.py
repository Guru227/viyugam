"""
storage/_paths.py — All file path constants and low-level JSON helpers.

Every other storage submodule imports this via ``from . import _paths``
and accesses paths as ``_paths.HOME``, ``_paths.DATA``, etc. at *call time*
so that test fixtures can monkeypatch these attributes.
"""
from __future__ import annotations

import json
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

HOME      = Path.home() / ".viyugam"
DATA      = HOME / "data"
JOURNALS  = HOME / "journals"
JOURNAL   = HOME / "journal"    # per-dimension journal dir
RESEARCH  = HOME / "research"
PLANS     = HOME / "plans"
CONFIG_FILE   = HOME / "config.yaml"
CALENDAR_FILE = DATA / "calendar.json"
CALENDAR_ICS  = HOME / "calendar.ics"
SLOW_BURNS_FILE  = DATA / "slow_burns.json"
MILESTONES_FILE  = DATA / "milestones.json"
BUDGETS_FILE     = DATA / "budgets.json"
BUDGET_YAML      = HOME / "budget.yaml"
TRANSACTIONS_FILE= DATA / "transactions.json"
DECISIONS_FILE   = DATA / "decisions.json"
ACTUALS_FILE     = DATA / "actuals.json"
MEMORY_FILE      = HOME / "memory.json"
CONSTITUTION_FILE= HOME / "constitution.md"
VALUES_FILE      = HOME / "values.yaml"
ENERGY_CACHE_FILE= DATA / "energy_pattern.json"
OKRS_FILE        = DATA / "okrs.json"
PROJECT_PLANS_FILE = DATA / "project_plans.json"
RECURRING_FILE   = DATA / "recurring.json"
JOURNALS_DIR     = JOURNALS
TRIAGE_FILE      = HOME / "triage.json"
COUNTERS_FILE    = DATA / "counters.json"
NOTES_FILE       = DATA / "notes.json"
NUDGES_FILE      = DATA / "nudges.json"
PATTERNS_FILE    = DATA / "patterns.json"
SESSIONS_DIR     = HOME / "sessions"


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _load(name: str) -> list[dict] | dict:
    path = DATA / f"{name}.json"
    if not path.exists():
        return [] if name != "state" else {}
    text = path.read_text().strip()
    if not text:
        return [] if name != "state" else {}
    return json.loads(text)


def _save(name: str, data: list[dict] | dict) -> None:
    path = DATA / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _load_json(file_path: Path) -> list[dict]:
    """Load a JSON array from an arbitrary path. Returns [] if missing/empty."""
    if not file_path.exists():
        return []
    text = file_path.read_text().strip()
    return json.loads(text) if text else []


def _save_json(file_path: Path, data: list[dict]) -> None:
    """Write a JSON array to an arbitrary path."""
    file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _next_id(prefix: str) -> str:
    """Return next sequential ID like T-001, G-002, P-003, N-004."""
    counters = {}
    if COUNTERS_FILE.exists():
        text = COUNTERS_FILE.read_text().strip()
        if text:
            counters = json.loads(text)
    n = counters.get(prefix, 0) + 1
    counters[prefix] = n
    COUNTERS_FILE.write_text(json.dumps(counters, indent=2))
    return f"{prefix}-{n:03d}"
