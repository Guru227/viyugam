"""storage/nudges.py — Nudge + pattern storage."""
from __future__ import annotations

from datetime import date, timedelta

from viyugam.models import Nudge, NudgeType, PatternInsight, SystemState

from . import _paths

# ── Context nudges (computed) ─────────────────────────────────────────────────

def get_nudges(state: SystemState) -> list[str]:
    nudges = []
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    if state.last_log and state.last_log < yesterday:
        nudges.append(f"No log since {state.last_log} -- quick catch-up after planning?")
    elif not state.last_log:
        nudges.append("You haven't logged yet -- try 'viyugam log' this evening.")

    if state.last_think:
        days_since = (date.today() - date.fromisoformat(state.last_think)).days
        if days_since >= 5:
            nudges.append(f"No think session in {days_since} days -- worth scheduling one.")
    else:
        nudges.append("You haven't used 'think' yet -- it's great for big decisions.")

    if state.last_review:
        days_since = (date.today() - date.fromisoformat(state.last_review)).days
        if days_since >= 7:
            nudges.append(f"Weekly review is {days_since} days overdue -- run 'viyugam review'.")
    else:
        nudges.append("No reviews yet -- 'viyugam review' helps clear cognitive overhead weekly.")

    return nudges


# ── Nudge persistence (GPS engine) ───────────────────────────────────────────

def get_stored_nudges() -> list[dict]:
    return _paths._load_json(_paths.NUDGES_FILE)


def save_nudge(nudge: Nudge) -> None:
    raw = get_stored_nudges()
    raw = [n for n in raw if n["id"] != nudge.id]
    raw.append(nudge.model_dump())
    _paths._save_json(_paths.NUDGES_FILE, raw)


def dismiss_nudge(entity_id: str, nudge_type: str) -> bool:
    raw = get_stored_nudges()
    found = False
    for n in raw:
        if n.get("entity_id") == entity_id and n.get("nudge_type") == nudge_type:
            n["dismissed"] = True
            found = True
    if found:
        _paths._save_json(_paths.NUDGES_FILE, raw)
    else:
        marker = Nudge(
            nudge_type=NudgeType(nudge_type) if nudge_type in NudgeType.__members__.values() else NudgeType.STALE_TASK,
            entity_id=entity_id,
            message="dismissed",
            dismissed=True,
        )
        raw.append(marker.model_dump())
        _paths._save_json(_paths.NUDGES_FILE, raw)
        found = True
    return found


# ── Pattern persistence (GPS engine) ─────────────────────────────────────────

def get_patterns(precipitated_only: bool = False) -> list[PatternInsight]:
    raw = _paths._load_json(_paths.PATTERNS_FILE)
    patterns = [PatternInsight(**p) for p in raw]
    if precipitated_only:
        patterns = [p for p in patterns if p.precipitated]
    return patterns


def save_pattern(pattern: PatternInsight) -> None:
    raw = _paths._load_json(_paths.PATTERNS_FILE)
    raw = [p for p in raw if p["id"] != pattern.id]
    raw.append(pattern.model_dump())
    _paths._save_json(_paths.PATTERNS_FILE, raw)


def merge_pattern(text: str, source: str = "system", tags: list[str] | None = None) -> PatternInsight:
    from datetime import datetime

    existing = get_patterns()
    text_words = set(text.lower().split())

    best_match = None
    best_overlap = 0.0
    for p in existing:
        p_words = set(p.pattern.lower().split())
        if not text_words or not p_words:
            continue
        overlap = len(text_words & p_words) / max(len(text_words | p_words), 1)
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = p

    now = datetime.now().isoformat()

    if best_match and best_overlap >= 0.7:
        best_match.occurrences += 1
        best_match.last_seen = now
        if best_match.occurrences >= 3:
            best_match.precipitated = True
        if tags:
            best_match.tags = list(set(best_match.tags + tags))
        save_pattern(best_match)
        return best_match
    else:
        new = PatternInsight(
            pattern=text, source=source, tags=tags or [],
            first_seen=now, last_seen=now,
        )
        save_pattern(new)
        return new
