"""
conftest.py — Patch all storage path constants to use tmp_path so tests
never touch ~/.viyugam/.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def patch_storage_paths(tmp_path, monkeypatch):
    """Redirect all storage file paths to a temporary directory."""
    import viyugam.storage as storage

    home     = tmp_path / ".viyugam"
    data     = home / "data"
    journals = home / "journals"
    research = home / "research"

    home.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    journals.mkdir(parents=True, exist_ok=True)
    research.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(storage, "HOME",               home)
    monkeypatch.setattr(storage, "DATA",               data)
    monkeypatch.setattr(storage, "JOURNALS",           journals)
    monkeypatch.setattr(storage, "RESEARCH",           research)
    monkeypatch.setattr(storage, "CONFIG_FILE",        home / "config.yaml")
    monkeypatch.setattr(storage, "CALENDAR_FILE",      data / "calendar.json")
    monkeypatch.setattr(storage, "SLOW_BURNS_FILE",    data / "slow_burns.json")
    monkeypatch.setattr(storage, "MILESTONES_FILE",    data / "milestones.json")
    monkeypatch.setattr(storage, "BUDGETS_FILE",       data / "budgets.json")
    monkeypatch.setattr(storage, "TRANSACTIONS_FILE",  data / "transactions.json")
    monkeypatch.setattr(storage, "DECISIONS_FILE",     data / "decisions.json")
    monkeypatch.setattr(storage, "ACTUALS_FILE",       data / "actuals.json")
    monkeypatch.setattr(storage, "MEMORY_FILE",        home / "memory.json")
    monkeypatch.setattr(storage, "CONSTITUTION_FILE",  home / "constitution.md")

    # Initialise all json files
    storage.ensure_dirs()

    yield
