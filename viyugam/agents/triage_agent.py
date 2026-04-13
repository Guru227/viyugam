"""
agents/triage_agent.py — Triage Dig-Deeper Boardroom.
A focused 3-5 exchange conversation to understand a captured triage item
before classifying it. Output: a summary used as the entity's description.
"""
from __future__ import annotations

import json

from viyugam.engine.client import get_client, text_of

TRIAGE_DEBATE_SYSTEM = """\
You are helping the user understand and clarify a captured idea, thought, or task.

Your job:
- Ask focused questions to understand what this really is
- Help clarify why it matters and what action it implies
- Connect it to existing goals or projects if relevant
- Keep it tight: 3-5 exchanges max before offering a summary

Do NOT ask multiple questions at once. One sharp question per turn.
Do NOT give unsolicited advice about whether to do it — your job is to clarify, not evaluate.

When the user indicates they've got enough clarity (e.g. "got it", "that's clear",
"done", "save"), summarise what was discussed in 2-3 sentences.
The summary should read as a description of the item, not a recap of the conversation."""


DONE_KW = {"done", "save", "got it", "that's clear", "thats clear",
           "that's enough", "thats enough", "clear", "finish", "ok"}


def start_debate(item: dict, context: str,
                 goals: list[dict], projects: list[dict]) -> str:
    """Opening message for a triage dig-deeper session."""
    goal_titles    = ", ".join(g.get("title", "") for g in goals[:5]) or "none yet"
    proj_titles    = ", ".join(p.get("title", "") for p in projects[:5]) or "none yet"
    content        = item.get("content", "")
    captured       = item.get("created_at", "")[:10]

    user_msg = (
        f"Captured: {content}\n"
        f"Date: {captured}\n"
        f"Active goals: {goal_titles}\n"
        f"Active projects: {proj_titles}\n"
    )
    if context:
        user_msg += f"\nExtra context: {context}"

    client   = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=TRIAGE_DEBATE_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],  # type: ignore[arg-type]
    )
    return text_of(response).strip()


def debate_turn(history: list[dict], user_message: str,
                item: dict) -> tuple[str, bool]:
    """
    Continue the dig-deeper conversation.
    Returns (reply, is_done).
    is_done is True when the user signals they have enough clarity.
    """
    tl      = user_message.strip().lower()
    is_done = any(kw in tl for kw in DONE_KW)

    messages = list(history) + [{"role": "user", "content": user_message}]
    client   = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=TRIAGE_DEBATE_SYSTEM,
        messages=messages,  # type: ignore[arg-type]
    )
    reply = text_of(response).strip()
    return reply, is_done


def extract_debate_summary(history: list[dict], item: dict) -> str:
    """
    Summarise the debate into 2-3 sentences for use as the entity's description/notes.
    """
    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in history
    )
    extraction_prompt = (
        f"Original capture: {item.get('content', '')}\n\n"
        f"Conversation:\n{conversation[:2000]}\n\n"
        "Write a 2-3 sentence description of this item based on the conversation above. "
        "Write it as if describing the item itself — not as a summary of the conversation. "
        "Be concrete. Mention what it is, why it matters, and what action it implies if clear."
    )
    client   = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": extraction_prompt}],  # type: ignore[arg-type]
    )
    return text_of(response).strip()


def decompose_capture(item: dict, history: list[dict] | None = None) -> list[str]:
    """
    Break a large capture into a list of distinct, atomic items.
    Returns a list of strings — each becomes a separate triage item.
    Uses debate history for context if available.
    """
    content = item.get("content", "")
    history_text = ""
    if history:
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in history
        )

    prompt = (
        f"The following capture contains multiple distinct tasks, ideas, or notes "
        f"bundled together into one block of text.\n\n"
        f"Capture:\n{content}\n"
    )
    if history_text:
        prompt += f"\nContext from discussion:\n{history_text[:1500]}\n"
    prompt += (
        "\nBreak this into individual atomic items. Each item should be a single "
        "actionable task, idea, goal, or note — nothing compound.\n\n"
        "Return ONLY a JSON array of strings, one per item. "
        "No preamble, no explanation, just the JSON array.\n"
        "Example: [\"Buy running shoes\", \"Research trail routes\", \"Schedule long run\"]"
    )

    client   = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],  # type: ignore[arg-type]
    )
    text = text_of(response).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        items = json.loads(text)
        if isinstance(items, list):
            return [str(i).strip() for i in items if str(i).strip()]
    except Exception:
        pass
    # Fallback: split on newlines
    return [ln.strip() for ln in content.splitlines() if ln.strip()]
