"""storage/memory.py — Memory context."""
from __future__ import annotations

import json
from datetime import date, datetime

from . import _paths


def load_memory() -> dict:
    if not _paths.MEMORY_FILE.exists():
        return {"summaries": [], "energy_patterns": {}, "last_updated": None}
    try:
        return json.loads(_paths.MEMORY_FILE.read_text())
    except Exception:
        return {"summaries": [], "energy_patterns": {}, "last_updated": None}


def save_memory(memory: dict) -> None:
    _paths.MEMORY_FILE.write_text(json.dumps(memory, indent=2, ensure_ascii=False))


def update_memory_summary(new_summary: str, source: str = "plan") -> None:
    memory = load_memory()
    memory.setdefault("summaries", []).append({
        "date": date.today().isoformat(),
        "source": source,
        "summary": new_summary,
    })
    memory["summaries"] = memory["summaries"][-30:]
    memory["last_updated"] = datetime.now().isoformat()
    save_memory(memory)


def get_memory_context(max_entries: int = 7) -> str:
    memory = load_memory()
    summaries = memory.get("summaries", [])[-max_entries:]
    if not summaries:
        return ""
    lines = ["RECENT CONTEXT (from memory):"]
    for s in summaries:
        lines.append(f"  [{s['date']} via {s['source']}] {s['summary']}")
    return "\n".join(lines)
