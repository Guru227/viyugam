"""
agents/energy.py — Energy pattern analyser.
Reads recent journal entries and extracts the user's personal energy model.
Cached for 3 days to avoid repeated API calls.
"""
from __future__ import annotations
import json
import os
from datetime import date, timedelta
from pathlib import Path

import anthropic


ENERGY_SYSTEM = """You are an analyst reading someone's journal entries to understand their personal energy patterns.

Extract a concise personal energy model. Be specific to what the journals actually say — do NOT assume standard circadian rhythms if the journals contradict them.

Return ONLY a JSON object:
{
  "peak_hours": "e.g. 9–11am and 4–6pm",
  "low_energy": "e.g. 2–3pm after lunch",
  "best_for_deep_work": "morning or evening or ...",
  "energy_triggers": ["coffee", "exercise", "..."],
  "energy_drains": ["meetings", "..."],
  "pattern_summary": "2-3 sentence plain-English summary of this person's energy pattern"
}

If there is insufficient data to determine something, use null for that field."""


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    return anthropic.Anthropic(api_key=api_key)


def analyze_energy_patterns(journal_entries: list[tuple[str, str]]) -> dict:
    """
    journal_entries: list of (date_str, markdown_content) tuples, newest first.
    Returns energy pattern dict.
    """
    if not journal_entries:
        return {}

    content = ""
    for d, text in journal_entries[:14]:
        content += f"\n--- {d} ---\n{text[:600]}\n"

    client = _client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=ENERGY_SYSTEM,
        messages=[{"role": "user", "content": f"Journal entries:\n{content}"}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def get_energy_pattern(journal_dir: Path, cache_file: Path) -> dict:
    """
    Load cached energy pattern or reanalyse if stale (>3 days old).
    Returns empty dict if no data or API unavailable.
    """
    # Check cache freshness
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            analyzed_on = cached.get("_analyzed_on", "")
            if analyzed_on:
                age = (date.today() - date.fromisoformat(analyzed_on)).days
                if age < 3:
                    return {k: v for k, v in cached.items() if not k.startswith("_")}
        except Exception:
            pass

    # Load journal entries
    if not journal_dir.exists():
        return {}
    entries = []
    for f in sorted(journal_dir.glob("*.md"), reverse=True)[:14]:
        try:
            entries.append((f.stem, f.read_text()))
        except Exception:
            continue

    if not entries:
        return {}

    try:
        pattern = analyze_energy_patterns(entries)
        pattern["_analyzed_on"] = date.today().isoformat()
        cache_file.write_text(json.dumps(pattern, indent=2, ensure_ascii=False))
        return {k: v for k, v in pattern.items() if not k.startswith("_")}
    except Exception:
        return {}
