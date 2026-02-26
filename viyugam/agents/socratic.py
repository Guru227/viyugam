"""
agents/socratic.py — Socratic values session for Viyugam.
Used in quarterly review (L4) to update values.yaml.
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
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    return anthropic.Anthropic(api_key=api_key)


SYNTHESIZE_SYSTEM = """You are analysing journal entries from a quarterly review to find cross-dimension patterns.
Be direct and specific. Reference actual language from the journals.
Return a concise paragraph (≤200 words) describing the key patterns: what's flourishing, what's stagnant, what's unexamined."""


def synthesize_patterns(journal_entries: list[dict], current_values: dict) -> str:
    """
    Synthesise cross-dimension patterns from quarterly journal entries.
    Returns a pattern summary string.
    """
    if not journal_entries:
        return "Insufficient journal data for pattern synthesis."

    client = _client()
    entries_text = "\n\n".join(
        f"[{e.get('dimension', '?')} — {e.get('date', '')}]\n{e.get('content', '')}"
        for e in journal_entries[:12]
    )
    prayer = current_values.get("prayer", "")
    context = f"User prayer/values:\n{prayer}\n\nJournal entries:\n{entries_text}" if prayer else f"Journal entries:\n{entries_text}"

    response = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SYNTHESIZE_SYSTEM,
        messages=[{"role": "user", "content": redact(context)}],
    )
    return response.content[0].text.strip()


SOCRATIC_QUESTION_SYSTEM = """You are running a Socratic values session for Viyugam.
Your role: ask one sharp question that challenges assumptions or surfaces something unexamined.
- Questions should arise from the patterns, not from a fixed list.
- Ask about ONE thing at a time.
- Don't ask about what they're already aware of.
- When the conversation is complete (user says 'next' or 'skip'), include [SESSION_COMPLETE] on its own line.
Return ONLY the question text."""


def next_question(patterns: str, conversation_so_far: list[dict]) -> tuple[str, bool]:
    """
    Generate next Socratic question from patterns.
    Returns (question, is_complete).
    """
    client = _client()
    messages = list(conversation_so_far)
    context = f"Patterns:\n{patterns}"
    if messages:
        messages.append({"role": "user", "content": "What should we explore next?"})
    else:
        messages = [{"role": "user", "content": context}]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=SOCRATIC_QUESTION_SYSTEM,
        messages=messages,
    )
    text = response.content[0].text.strip()
    complete = "[SESSION_COMPLETE]" in text
    text = text.replace("[SESSION_COMPLETE]", "").strip()
    return text, complete


VALUES_DIFF_SYSTEM = """You are proposing updates to a values.yaml based on a Socratic conversation.
Return ONLY a JSON object with proposed changes:
{
  "prayer": "updated prayer text (or null to keep unchanged)",
  "chapters": {
    "career": "updated chapter text (or null to keep)",
    "wealth": null,
    "health": null,
    "relationships": null,
    "joy": null,
    "learning": null
  },
  "rationale": "1-2 sentences explaining the key change"
}
Only include chapters that genuinely need updating based on the conversation."""


def draft_values_diff(current_values: dict, conversation: list[dict]) -> dict:
    """
    Propose changes to values.yaml based on Socratic conversation.
    Returns proposed diff dict.
    """
    client = _client()
    current_text = f"Current values:\n{json.dumps(current_values, ensure_ascii=False, indent=2)[:1000]}"
    conversation_text = "\n".join(
        f"{'Viyugam' if m['role']=='assistant' else 'User'}: {m['content']}"
        for m in conversation[-10:]
    )
    msg = f"{current_text}\n\nConversation:\n{conversation_text}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=VALUES_DIFF_SYSTEM,
        messages=[{"role": "user", "content": redact(msg)}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except Exception:
        return {"prayer": None, "chapters": {}, "rationale": "Could not parse diff."}
