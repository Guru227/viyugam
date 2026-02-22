"""
agents/coach.py — The Coach.
Runs the conversational journaling session.
Dual voice: Observer + Encourager.
Human Living Guardian always active.
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


# ── Coach system prompt ────────────────────────────────────────────────────────

COACH_SYSTEM = """You are the Coach for Viyugam — a personal Life OS.

Your character is a blend of two voices that always work together:
- The Observer: honest, pattern-tracking, names things plainly without drama
- The Encourager: finds strength in hard days, anchors to wins, optimistic bias

Your core rules:
1. Never give generic praise. "Good job" is useless. "You finished that despite being exhausted — that's follow-through" is meaningful.
2. Always explain the why behind observations.
3. Read the room. If the user is exhausted, hold back on analysis. If they're spinning in circles, gently push toward clarity.
4. Bias toward action and forward momentum, not endless reflection.
5. Keep responses concise — this is a conversation, not an essay.
6. Ask one follow-up question at a time. Never pepper the user with multiple questions.

THE HUMAN LIVING GUARDIAN (critical rule):
If the user mentions something that involves the texture of human connection — what a friend likes, a gift idea for someone, a memory with a loved one, an experience they want to have WITH someone, anything where the effort and the doing IS the value — pause and reflect gently:

Say something like: "That's the kind of thing that might be better lived than logged. The effort of remembering, or getting it wrong and laughing about it, is part of what makes it meaningful. Worth keeping human?"

This is not a block. It's a moment of reflection. Then move on.

WRAPPING UP:
When the conversation has covered enough ground (usually 4-8 exchanges), naturally bring it to a close. End your final message with exactly this marker on its own line:
[READY_TO_SAVE]

DIMENSION SCORES:
After [READY_TO_SAVE], you will be asked separately to generate a structured summary. Do not generate it during the conversation — just have a natural, human conversation.

Dimensions to be aware of (for the summary later):
health, wealth, career, relationships, joy, learning"""


OPENER_SYSTEM = """You are opening a journaling session for {user_name}.

Context about their day/situation:
{context}

Write a warm, natural opening question. One sentence. Not "How was your day?" — that's generic.
Use the context if available (e.g. if they had tasks scheduled, reference something specific).
If no context, ask something open but specific like "What's the one thing from today that's still on your mind?"

Just the question. No preamble."""


SUMMARY_SYSTEM = """Based on the journaling conversation below, generate a structured summary.

Conversation:
{conversation}

Return ONLY a JSON object:
{{
  "date": "{date}",
  "energy_level": "low|medium|high",
  "mood": "one word",
  "dimension_scores": [
    {{"dimension": "health", "score": 1-10, "note": "brief reason or null"}},
    {{"dimension": "wealth", "score": 1-10, "note": "brief reason or null"}},
    {{"dimension": "career", "score": 1-10, "note": "brief reason or null"}},
    {{"dimension": "relationships", "score": 1-10, "note": "brief reason or null"}},
    {{"dimension": "joy", "score": 1-10, "note": "brief reason or null"}},
    {{"dimension": "learning", "score": 1-10, "note": "brief reason or null"}}
  ],
  "wins": ["list of genuine wins mentioned, even small ones"],
  "challenges": ["list of challenges or friction mentioned"],
  "patterns_noted": ["any recurring themes worth flagging for future sessions"],
  "coach_note": "One sentence synthesis — what matters most from this session"
}}

Rules:
- Scores must be grounded in what was actually said. Don't assume.
- If a dimension wasn't mentioned, score it 5 (neutral) with note null.
- wins should feel earned, not generic.
- coach_note should be the one thing worth remembering."""


def get_opener(user_name: str, context: str, today_tasks: list[dict]) -> str:
    """Generate a context-aware opening question."""
    task_context = ""
    if today_tasks:
        done = [t for t in today_tasks if t.get("status") == "done"]
        pending = [t for t in today_tasks if t.get("status") in ("todo", "in_progress")]
        if done:
            task_context += f"Completed today: {', '.join(t['title'] for t in done[:3])}. "
        if pending:
            task_context += f"Left undone: {', '.join(t['title'] for t in pending[:3])}."

    full_context = context
    if task_context:
        full_context = task_context + " " + context

    client = _client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        system=OPENER_SYSTEM.format(
            user_name=user_name,
            context=full_context.strip() or "No specific context available.",
        ),
        messages=[{"role": "user", "content": "Generate the opening question."}],
    )
    return response.content[0].text.strip().strip('"')


def chat_turn(
    history: list[dict],
    user_message: str,
    config: dict,
    season_context: str = "",
) -> tuple[str, bool]:
    """
    Send one turn of the journaling conversation.
    Returns (coach_response, is_ready_to_save).
    """
    client = _client()

    system = COACH_SYSTEM
    if season_context:
        system += f"\n\nUser context: {season_context}"

    messages = history + [{"role": "user", "content": redact(user_message)}]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=system,
        messages=messages,
    )

    text = response.content[0].text.strip()
    ready = "[READY_TO_SAVE]" in text
    clean_text = text.replace("[READY_TO_SAVE]", "").strip()

    return clean_text, ready


def generate_summary(conversation: list[dict], today: str) -> dict:
    """
    After the conversation, generate a structured JSON summary.
    """
    # Format conversation as readable text
    conv_text = ""
    for msg in conversation:
        role = "Coach" if msg["role"] == "assistant" else "You"
        conv_text += f"\n{role}: {msg['content']}\n"

    client = _client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system="You generate structured JSON summaries of journaling conversations. Return only valid JSON.",
        messages=[{
            "role": "user",
            "content": SUMMARY_SYSTEM.format(
                conversation=conv_text,
                date=today,
            )
        }],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(text)


def format_journal_markdown(
    conversation: list[dict],
    summary: dict,
    today: str,
) -> str:
    """Format the full journal entry as markdown."""
    lines = [f"# Journal · {today}\n"]

    # Conversation transcript
    lines.append("## Session\n")
    for msg in conversation:
        role = "**Coach**" if msg["role"] == "assistant" else "**You**"
        lines.append(f"{role}: {msg['content']}\n")

    # Structured summary (hidden in a JSON block for machine reading)
    lines.append("\n## Summary\n")
    if summary.get("coach_note"):
        lines.append(f"_{summary['coach_note']}_\n")
    if summary.get("wins"):
        lines.append("\n**Wins**")
        for win in summary["wins"]:
            lines.append(f"- {win}")
    if summary.get("challenges"):
        lines.append("\n**Challenges**")
        for c in summary["challenges"]:
            lines.append(f"- {c}")

    lines.append("\n```json")
    lines.append(json.dumps(summary, indent=2, ensure_ascii=False))
    lines.append("```\n")

    return "\n".join(lines)
