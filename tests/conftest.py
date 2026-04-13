"""
conftest.py — Patch all storage path constants to use tmp_path so tests
never touch ~/.viyugam/.

After the storage/ package split, the *canonical* path constants live in
``viyugam.storage._paths``.  Submodules reference them via the ``_paths``
module at call time, so patching ``_paths.HOME`` etc. is sufficient.
We also patch the re-exported names on ``storage`` itself for any code
that reads ``storage.HOME`` directly.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path


# Name -> (parent_attr, value_builder) pairs.
# parent_attr is "home" or "data" — the tmp sub-dir they derive from.
_PATH_ATTRS = {
    "HOME":               ("home", None),
    "DATA":               ("data", None),
    "JOURNALS":           ("journals", None),
    "JOURNAL":            ("home", "journal"),
    "RESEARCH":           ("research", None),
    "PLANS":              ("home", "plans"),
    "CONFIG_FILE":        ("home", "config.yaml"),
    "CALENDAR_FILE":      ("data", "calendar.json"),
    "CALENDAR_ICS":       ("home", "calendar.ics"),
    "SLOW_BURNS_FILE":    ("data", "slow_burns.json"),
    "MILESTONES_FILE":    ("data", "milestones.json"),
    "BUDGETS_FILE":       ("data", "budgets.json"),
    "BUDGET_YAML":        ("home", "budget.yaml"),
    "TRANSACTIONS_FILE":  ("data", "transactions.json"),
    "DECISIONS_FILE":     ("data", "decisions.json"),
    "ACTUALS_FILE":       ("data", "actuals.json"),
    "MEMORY_FILE":        ("home", "memory.json"),
    "CONSTITUTION_FILE":  ("home", "constitution.md"),
    "VALUES_FILE":        ("home", "values.yaml"),
    "ENERGY_CACHE_FILE":  ("data", "energy_pattern.json"),
    "OKRS_FILE":          ("data", "okrs.json"),
    "PROJECT_PLANS_FILE": ("data", "project_plans.json"),
    "RECURRING_FILE":     ("data", "recurring.json"),
    "JOURNALS_DIR":       ("journals", None),
    "TRIAGE_FILE":        ("home", "triage.json"),
    "COUNTERS_FILE":      ("data", "counters.json"),
    "NOTES_FILE":         ("data", "notes.json"),
    "NUDGES_FILE":        ("data", "nudges.json"),
    "PATTERNS_FILE":      ("data", "patterns.json"),
    "SESSIONS_DIR":       ("home", "sessions"),
}


@pytest.fixture(autouse=True)
def patch_storage_paths(tmp_path, monkeypatch):
    """Redirect all storage file paths to a temporary directory."""
    import viyugam.storage as storage
    from viyugam.storage import _paths

    home     = tmp_path / ".viyugam"
    data     = home / "data"
    journals = home / "journals"
    research = home / "research"

    roots = {
        "home": home,
        "data": data,
        "journals": journals,
        "research": research,
    }

    for d in roots.values():
        d.mkdir(parents=True, exist_ok=True)

    for attr, (root_key, child) in _PATH_ATTRS.items():
        val = roots[root_key] / child if child else roots[root_key]
        # Patch the canonical _paths module (submodules read from here)
        monkeypatch.setattr(_paths, attr, val)
        # Patch the re-exported name on the storage package
        monkeypatch.setattr(storage, attr, val)

    # Initialise all json files
    storage.ensure_dirs()

    yield


@pytest.fixture
def mock_journal_thread(monkeypatch):
    """Suppress the energy-reanalysis background thread in journal.save_journal()."""
    monkeypatch.setattr(
        "viyugam.storage.journal.threading.Thread",
        lambda **kw: type("T", (), {"start": lambda self: None})(),
    )
