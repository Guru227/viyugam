"""storage/journal.py — Journal read/write, summaries, rolling context."""
from __future__ import annotations

import json
import re
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from viyugam.models import JournalSummary

from . import _paths


def journal_path(for_date: Optional[str] = None) -> Path:
    d = for_date or date.today().isoformat()
    return _paths.JOURNALS / f"{d}.md"


def load_journal(for_date: Optional[str] = None) -> Optional[str]:
    path = journal_path(for_date)
    if not path.exists():
        return None
    return path.read_text()


def save_journal(content: str, for_date: Optional[str] = None) -> Path:
    path = journal_path(for_date)
    path.write_text(content)
    # Trigger energy pattern re-analysis in the background.
    threading.Thread(target=_trigger_energy_reanalysis, daemon=True).start()
    return path


def _trigger_energy_reanalysis() -> None:
    """Lazy-import to avoid circular dependency with core."""
    from .core import get_energy_pattern
    get_energy_pattern()


def get_recent_journals(days: int = 14) -> list[tuple[str, str]]:
    entries = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        path = _paths.JOURNALS_DIR / f"{d}.md"
        if path.exists():
            try:
                entries.append((d, path.read_text()))
            except Exception:
                pass
    return entries


def load_journal_summary(for_date: Optional[str] = None) -> Optional[JournalSummary]:
    content = load_journal(for_date)
    if not content:
        return None
    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        return JournalSummary(**data)
    except Exception:
        return None


def get_recent_summaries(days: int = 14) -> list[JournalSummary]:
    summaries = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        s = load_journal_summary(d)
        if s:
            summaries.append(s)
    return summaries


# ── Research ──────────────────────────────────────────────────────────────────

def save_research(topic: str, content: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:60]
    today = date.today().isoformat()
    path = _paths.RESEARCH / f"{slug}-{today}.md"
    path.write_text(content, encoding="utf-8")
    return path
