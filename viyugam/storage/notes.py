"""storage/notes.py — Notes CRUD."""
from __future__ import annotations

from viyugam.models import Note

from . import _paths


def get_notes() -> list[Note]:
    raw = _paths._load_json(_paths.NOTES_FILE)
    return [Note(**n) for n in raw]


def save_note(note: Note) -> None:
    if not note.seq_id:
        note.seq_id = _paths._next_id("N")
    raw = _paths._load_json(_paths.NOTES_FILE)
    raw = [n for n in raw if n["id"] != note.id]
    raw.append(note.model_dump())
    _paths._save_json(_paths.NOTES_FILE, raw)
