"""storage/calendar.py — Calendar entries, ICS parsing."""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from viyugam.models import CalendarEntry, ViyugamConfig

from . import _paths


def get_calendar_entries(date_str: str) -> list[CalendarEntry]:
    DOW = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    dow = DOW[date.fromisoformat(date_str).weekday()]
    raw = _paths._load_json(_paths.CALENDAR_FILE)
    results = [
        CalendarEntry(**e) for e in raw
        if (e.get("recurs_on") and dow in e["recurs_on"])
        or e.get("date") == date_str
    ]
    return sorted(results, key=lambda e: e.start_time or "99:99")


def save_calendar_entry(entry: CalendarEntry) -> None:
    raw = _paths._load_json(_paths.CALENDAR_FILE)
    raw = [e for e in raw if e["id"] != entry.id]
    raw.append(entry.model_dump())
    _paths._save_json(_paths.CALENDAR_FILE, raw)


def delete_calendar_entry(entry_id: str) -> None:
    raw = _paths._load_json(_paths.CALENDAR_FILE)
    _paths._save_json(_paths.CALENDAR_FILE, [e for e in raw if e["id"] != entry_id])


def get_day_type(date_str: str, config: ViyugamConfig) -> str:
    if not config.work_schedule:
        return "wfh"
    DOW = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    dow = DOW[date.fromisoformat(date_str).weekday()]
    ws = config.work_schedule
    if dow in ws.office_days:
        return "office"
    if dow in ws.wfh_days:
        return "wfh"
    return "off"


# ── ICS parsing ───────────────────────────────────────────────────────────────

def _parse_ics_datetime(val: str) -> Optional[datetime]:
    val = val.strip()
    if ":" in val:
        val = val.split(":")[-1]
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def parse_ics(path: Optional[Path] = None) -> list[dict]:
    ics_path = path or _paths.CALENDAR_ICS
    if not ics_path.exists():
        return []

    try:
        content = ics_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    events = []
    vevent_re = re.compile(r'BEGIN:VEVENT(.*?)END:VEVENT', re.DOTALL)
    for match in vevent_re.finditer(content):
        block = match.group(1)
        props: dict[str, str] = {}
        for line in block.splitlines():
            line = line.strip()
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.split(";")[0].strip().upper()
                props[key] = val.strip()

        summary = props.get("SUMMARY", "Untitled")
        dtstart_raw = props.get("DTSTART", "")
        dtend_raw = props.get("DTEND", "")

        if not dtstart_raw:
            continue

        all_day = len(dtstart_raw.replace(":", "").replace("T", "").replace("Z", "").replace("-", "")) == 8
        dt_start = _parse_ics_datetime(dtstart_raw)
        dt_end = _parse_ics_datetime(dtend_raw) if dtend_raw else None

        if not dt_start:
            continue

        events.append({
            "title": summary,
            "date": dt_start.date().isoformat(),
            "start_time": dt_start.strftime("%H:%M") if not all_day else None,
            "end_time": dt_end.strftime("%H:%M") if dt_end and not all_day else None,
            "all_day": all_day,
        })

    events.sort(key=lambda e: (e["date"], e["start_time"] or "00:00"))
    return events


def get_ics_events_for_period(start: date, end: date) -> list[dict]:
    events = parse_ics()
    start_str = start.isoformat()
    end_str = end.isoformat()
    return [e for e in events if start_str <= e["date"] <= end_str]
