"""storage/sessions.py — Chat session persistence."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from . import _paths


def save_chat_session(chat: list) -> None:
    from .core import ensure_dirs
    ensure_dirs()
    today = date.today().isoformat()
    path = _paths.SESSIONS_DIR / f"{today}.json"
    entries = [e for e in chat if not (e.get("role") == "assistant" and "Ctrl" in e.get("ansi", ""))]
    if entries:
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
    # Prune files older than 30 days
    cutoff = date.today() - timedelta(days=30)
    for f in _paths.SESSIONS_DIR.glob("*.json"):
        try:
            if date.fromisoformat(f.stem) < cutoff:
                f.unlink()
        except ValueError:
            pass


def load_last_chat_session() -> list:
    from .core import ensure_dirs
    ensure_dirs()
    today = date.today().isoformat()
    today_file = _paths.SESSIONS_DIR / f"{today}.json"
    if today_file.exists():
        try:
            return json.loads(today_file.read_text())
        except Exception:
            pass
    if datetime.now().hour < 12:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        yfile = _paths.SESSIONS_DIR / f"{yesterday}.json"
        if yfile.exists():
            try:
                return json.loads(yfile.read_text())
            except Exception:
                pass
    return []
