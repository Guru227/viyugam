"""
agents/goal_planner.py — Goal Planning Boardroom.
Conversational session to clarify OKRs, refine success criteria, and
align a goal to the current season and dimension focus.
"""
from __future__ import annotations
import json
import os

import anthropic


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    return anthropic.Anthropic(api_key=api_key)


GOAL_PLAN_SYSTEM = """\
You are a goal clarity collaborator helping someone sharpen a goal and its OKRs.

Your role:
- Help define what "done" actually looks like for this goal (concrete, measurable)
- Challenge vague or wishful key results — make them specific and time-bound
- Surface how this goal connects to the person's values and current season
- Identify which projects are serving this goal and which gaps exist
- Keep key results grounded: 2-4 KRs max, each measurable, each worth tracking

You work iteratively. Ask one focused question at a time.
Never give generic advice — make everything specific to this goal and context.

When the person says "save", "done", "that's it", or "looks good" — summarise
what you've captured and confirm you're ready to save.

The session ends when the person explicitly approves ("save" / "done" / "that's it").

After each response, if you are proposing or refining the goal plan, append a PLAN_STATE block:

PLAN_STATE:
+ KR: Ship MVP to 100 users by Apr 15
+ KR: 3 paying customers by Apr 30
- KR: < 2% monthly churn (too early to measure, removing)
= Objective: Launch a sustainable product (confirmed)

Use + for additions or revisions, - for removals, = for items carried forward unchanged.
Only include items that represent the goal's structure (objective, key results, success criteria).
Omit the PLAN_STATE block if nothing meaningful changed."""


def _goal_context(goal: dict, existing_okrs: list[dict],
                  projects: list[dict], values: dict) -> str:
    """Build the opening context string."""
    lines = [
        f"Goal: {goal.get('title', 'Untitled')} ({goal.get('seq_id', goal.get('id', ''))})",
        f"Dimension: {goal.get('dimension', '—')}",
    ]
    if goal.get("description"):
        lines.append(f"Description: {goal['description']}")

    if existing_okrs:
        lines.append("\nExisting OKRs for this goal's dimension:")
        for o in existing_okrs[:4]:
            obj = o.get("objective", "")
            krs = o.get("key_results", [])
            kr_text = "; ".join(
                kr.get("text", "") for kr in krs if not kr.get("is_done")
            )
            lines.append(f"  [{o.get('quarter', '—')}] {obj}" +
                         (f" → {kr_text}" if kr_text else ""))

    goal_id = goal.get("id")
    linked_projects = [p for p in projects if p.get("goal_id") == goal_id]
    if linked_projects:
        lines.append("\nLinked projects:")
        for p in linked_projects[:5]:
            lines.append(f"  {p.get('seq_id', '·')}  {p.get('title', '')}"
                         f"  [{p.get('status', 'active')}]")

    if values.get("prayer"):
        lines.append(f"\nValues/prayer: {values['prayer'][:200]}")

    return "\n".join(lines)


def start_goal_plan_session(goal: dict, existing_okrs: list[dict] | None = None,
                            projects: list[dict] | None = None,
                            values: dict | None = None) -> str:
    """Generate the opening message for a goal planning session."""
    ctx = _goal_context(
        goal,
        existing_okrs or [],
        projects or [],
        values or {},
    )
    client = _client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=GOAL_PLAN_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Let's clarify this goal and its OKRs.\n\n{ctx}",
        }],
    )
    return response.content[0].text.strip()


def goal_plan_turn(history: list[dict], user_message: str,
                   goal: dict) -> tuple[str, bool]:
    """
    Continue the goal planning conversation.
    Returns (assistant_message, is_done).
    """
    done_kw = {"save", "done", "that's it", "thats it", "looks good",
               "confirm", "approve", "finish"}
    tl = user_message.strip().lower()
    is_done = any(kw in tl for kw in done_kw)

    messages = list(history) + [{"role": "user", "content": user_message}]
    client = _client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=GOAL_PLAN_SYSTEM,
        messages=messages,
    )
    reply = response.content[0].text.strip()
    return reply, is_done


def extract_goal_plan(history: list[dict], goal: dict) -> dict:
    """
    After the session ends, extract a structured goal plan.
    Returns a dict with keys: objective, key_results, success_criteria, notes.
    """
    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in history
    )
    extraction_prompt = f"""\
Extract a structured goal plan from this goal planning conversation.

Goal: {goal.get('title', 'Untitled')} — dimension: {goal.get('dimension', '—')}

Conversation:
{conversation[:3000]}

Return ONLY valid JSON with this structure:
{{
  "objective": "Refined objective statement (1 clear sentence)",
  "key_results": [
    {{"text": "KR description", "due_date": "YYYY-MM-DD or null", "target": "measurable target"}}
  ],
  "success_criteria": ["done when X", "done when Y"],
  "notes": "key context, risks, or connections to season/values in 1-2 sentences"
}}

If information wasn't discussed, use empty string / empty list as defaults.
Key results: 2-4 max, each concrete and measurable."""

    client = _client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": extraction_prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except Exception:
        return {
            "objective": "",
            "key_results": [],
            "success_criteria": [],
            "notes": "",
        }
