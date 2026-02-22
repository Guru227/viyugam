"""
agents/chairman.py — The Chairman.
Handles inbox triage and daily schedule generation.
Fast, tactical, grounded in context.
"""
from __future__ import annotations
import json
import os
from typing import Optional

import anthropic

from viyugam.pii import redact


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to your environment or ~/.viyugam/config.yaml"
        )
    return anthropic.Anthropic(api_key=api_key)


# ── Inbox Triage ───────────────────────────────────────────────────────────────

TRIAGE_SYSTEM = """You are the Chairman — a tactical planning agent for Viyugam, a personal Life OS.

Your job right now: triage raw inbox captures. Classify each one and extract metadata.

Rules:
- Be practical and grounded. Don't over-engineer classifications.
- Energy cost is cognitive load 1-10 (1 = mindless, 10 = deep focus required).
- Dimensions: health, wealth, career, relationships, joy, learning.
- If something sounds like it involves a person the user loves (gift ideas, personal details
  about friends/family, emotional memories), flag it as human_territory: true.
  These deserve a gentle check before being turned into tasks.

Return ONLY a JSON array, no other text:
[
  {
    "original": "...",
    "type": "task" | "project" | "note" | "human_territory",
    "human_territory": false,
    "title": "...",
    "dimension": "career" | "health" | "wealth" | "relationships" | "joy" | "learning" | null,
    "energy_cost": 1-10,
    "estimated_minutes": 15-240,
    "context": "at-desk" | "errand" | "calls" | "anywhere" | null,
    "notes": "any extra context worth keeping"
  }
]"""


def triage_inbox(items: list[str], config_context: str = "") -> list[dict]:
    """
    Process raw inbox strings into structured classifications.
    Returns list of dicts ready to be turned into Tasks/Projects.
    """
    if not items:
        return []

    redacted_items = [redact(item) for item in items]
    user_content = f"{config_context}\n\nInbox items to triage:\n" + "\n".join(
        f"- {item}" for item in redacted_items
    )

    client = _client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=TRIAGE_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(text)


# ── Daily Schedule ─────────────────────────────────────────────────────────────

PLAN_SYSTEM = """You are the Chairman — a tactical planning agent for Viyugam, a personal Life OS.

Your job right now: build a realistic, humane daily schedule.

Rules:
1. Use the user's actual energy patterns from their journal entries. Do NOT assume fixed
   circadian rhythms. If you see patterns (e.g. "always sharp at 11pm"), use them.
   If there's no journal data yet, default to: morning = deep work, afternoon = shallow,
   evening = light/admin.
2. High energy tasks (cost 7-10) go in peak energy windows.
3. Low energy tasks (cost 1-4) go in low energy windows.
4. Insert a 15-minute break after every 90 minutes of focused work.
5. If tasks exceed available work hours, move the lowest priority / least urgent to backlog.
6. Always schedule habits that are due today.
7. Be realistic — don't schedule 10 hours of deep work. People need breathing room.
8. The schedule should feel good to look at, not anxiety-inducing.

Return ONLY a JSON object, no other text:
{
  "schedule": [
    {
      "time": "09:00",
      "duration_mins": 90,
      "type": "task" | "habit" | "break",
      "task_id": "...",
      "title": "...",
      "energy_cost": 7,
      "time_period": "morning" | "afternoon" | "evening" | "night"
    }
  ],
  "moved_to_backlog": ["task_id_1"],
  "energy_read": "Short note on what you read from journal entries about their energy patterns",
  "season_note": null
}

If moved_to_backlog is empty, return [].
season_note: only include if there's meaningful tension between scheduled tasks and current season."""


def plan_day(
    tasks: list[dict],
    habits: list[dict],
    projects: list[dict],
    goals: list[dict],
    recent_journals: list[tuple[str, str]],
    config: dict,
    today: str,
    nudges: list[str],
) -> dict:
    """
    Generate a time-blocked daily schedule.
    Returns structured plan dict.
    """
    journal_context = ""
    if recent_journals:
        journal_context = "RECENT JOURNAL ENTRIES (use these to understand energy patterns):\n"
        for d, content in recent_journals[:7]:  # last 7 days max
            journal_context += f"\n--- {d} ---\n{content[:800]}\n"  # cap per entry
    else:
        journal_context = "No journal entries yet. Use default energy pattern assumptions."

    season_info = ""
    if config.get("season"):
        s = config["season"]
        season_info = f"Current season: {s.get('name', '')} | Focus: {s.get('focus', '')} | Secondary: {s.get('secondary', '')}"

    user_content = f"""TODAY: {today}
USER: {config.get('user_name', 'friend')}
Work hours cap: {config.get('work_hours_cap', 8)}h
{season_info}

TASKS DUE TODAY OR OVERDUE:
{json.dumps(tasks, indent=2) if tasks else "None scheduled yet."}

HABITS:
{json.dumps(habits, indent=2) if habits else "No habits configured yet."}

ACTIVE PROJECTS (for context):
{json.dumps([{"id": p.get("id"), "title": p.get("title"), "dimension": p.get("dimension")} for p in projects[:5]], indent=2) if projects else "None."}

GOALS (for context):
{json.dumps([{"title": g.get("title"), "dimension": g.get("dimension")} for g in goals], indent=2) if goals else "None set yet."}

{journal_context}"""

    client = _client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=PLAN_SYSTEM,
        messages=[{"role": "user", "content": redact(user_content)}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    result = json.loads(text)
    result["nudges"] = nudges
    return result
