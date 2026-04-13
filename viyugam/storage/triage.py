"""storage/triage.py — Triage/inbox item storage."""
from __future__ import annotations

import json
from datetime import date, datetime

from viyugam.models import InboxItem, SomedayItem, TriageItem

from . import _paths

# ── Migration ─────────────────────────────────────────────────────────────────

def _migrate_inbox_to_triage() -> None:
    """One-time migration: copy inbox.json -> triage.json with new fields."""
    inbox_path = _paths.DATA / "inbox.json"
    if inbox_path.exists():
        try:
            raw = json.loads(inbox_path.read_text().strip() or "[]")
            migrated = []
            for item in raw:
                migrated.append({
                    "id": item.get("id", ""),
                    "content": item.get("content", ""),
                    "source": item.get("source", "cli"),
                    "processed": item.get("is_processed", False),
                    "snooze_until": None,
                    "boardroom_notes": None,
                    "created_at": item.get("created_at", datetime.now().isoformat()),
                })
            _paths.TRIAGE_FILE.write_text(
                json.dumps(migrated, indent=2, ensure_ascii=False)
            )
            return
        except Exception:
            pass
    _paths.TRIAGE_FILE.write_text("[]")


# ── Triage CRUD ───────────────────────────────────────────────────────────────

def get_triage(unprocessed_only: bool = True) -> list[TriageItem]:
    if not _paths.TRIAGE_FILE.exists():
        return []
    raw = json.loads(_paths.TRIAGE_FILE.read_text().strip() or "[]")
    items = [TriageItem(**i) for i in raw]
    if unprocessed_only:
        today = date.today().isoformat()
        result = []
        for item in items:
            if item.processed:
                continue
            if item.snooze_until and item.snooze_until > today:
                continue
            result.append(item)
        return result
    return items


def append_triage(content: str, source: str = "cli") -> TriageItem:
    item = TriageItem(content=content, source=source)
    raw = (
        json.loads(_paths.TRIAGE_FILE.read_text().strip() or "[]")
        if _paths.TRIAGE_FILE.exists()
        else []
    )
    raw.append(item.model_dump())
    _paths.TRIAGE_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))
    return item


def save_triage_item(item: TriageItem) -> None:
    raw = (
        json.loads(_paths.TRIAGE_FILE.read_text().strip() or "[]")
        if _paths.TRIAGE_FILE.exists()
        else []
    )
    raw = [i for i in raw if i["id"] != item.id]
    raw.append(item.model_dump())
    _paths.TRIAGE_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))


def mark_triage_processed(item_ids: list[str]) -> None:
    raw = (
        json.loads(_paths.TRIAGE_FILE.read_text().strip() or "[]")
        if _paths.TRIAGE_FILE.exists()
        else []
    )
    for item in raw:
        if item["id"] in item_ids:
            item["processed"] = True
    _paths.TRIAGE_FILE.write_text(json.dumps(raw, indent=2, ensure_ascii=False))


def get_recent_triage_logs(n: int = 5) -> list[TriageItem]:
    if not _paths.TRIAGE_FILE.exists():
        return []
    raw = json.loads(_paths.TRIAGE_FILE.read_text().strip() or "[]")
    items = [TriageItem(**i) for i in raw]
    items.sort(key=lambda x: x.created_at, reverse=True)
    return items[:n]


# ── Inbox (legacy) ────────────────────────────────────────────────────────────

def get_inbox(unprocessed_only: bool = True) -> list[InboxItem]:
    raw = _paths._load("inbox")
    items = [InboxItem(**i) for i in raw]
    if unprocessed_only:
        items = [i for i in items if not i.is_processed]
    return items


def append_inbox(content: str, source: str = "cli") -> InboxItem:
    item = InboxItem(content=content, source=source)
    raw = _paths._load("inbox")
    if not isinstance(raw, list):
        raw = []
    raw.append(item.model_dump())
    _paths._save("inbox", raw)
    return item


def mark_inbox_processed(item_ids: list[str]) -> None:
    raw = _paths._load("inbox")
    for item in raw:
        if item["id"] in item_ids:
            item["is_processed"] = True
    _paths._save("inbox", raw)


# ── Someday ───────────────────────────────────────────────────────────────────

def get_someday() -> list[SomedayItem]:
    raw = _paths._load("someday")
    return [SomedayItem(**s) for s in raw]


def save_someday(item: SomedayItem) -> None:
    raw = _paths._load("someday")
    existing = [s for s in raw if s["id"] != item.id]
    existing.append(item.model_dump())
    _paths._save("someday", existing)


def delete_someday(item_id: str) -> None:
    raw = _paths._load("someday")
    _paths._save("someday", [s for s in raw if s["id"] != item_id])
