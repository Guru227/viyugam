"""storage/values.py — Values/constitution load."""
from __future__ import annotations

import yaml

from . import _paths


def load_values() -> dict:
    if _paths.VALUES_FILE.exists():
        try:
            data = yaml.safe_load(_paths.VALUES_FILE.read_text()) or {}
            return data
        except Exception:
            pass
    # Migrate from constitution.md if it exists
    if _paths.CONSTITUTION_FILE.exists():
        content = _paths.CONSTITUTION_FILE.read_text()
        values = {
            "prayer": "",
            "chapters": {
                "career": content,
                "wealth": "",
                "health": "",
                "relationships": "",
                "joy": "",
                "learning": "",
            },
        }
        _paths.VALUES_FILE.write_text(
            yaml.dump(values, allow_unicode=True, default_flow_style=False)
        )
        return values
    return {
        "prayer": "",
        "chapters": {d: "" for d in ["career", "wealth", "health", "relationships", "joy", "learning"]},
    }


def save_values(values: dict) -> None:
    _paths.VALUES_FILE.write_text(
        yaml.dump(values, allow_unicode=True, default_flow_style=False)
    )


def load_constitution() -> str:
    if not _paths.CONSTITUTION_FILE.exists():
        return ""
    return _paths.CONSTITUTION_FILE.read_text()


def save_constitution(content: str) -> None:
    _paths.CONSTITUTION_FILE.write_text(content)
