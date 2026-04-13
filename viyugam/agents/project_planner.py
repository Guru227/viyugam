"""
agents/project_planner.py — Project Planning Boardroom.
Conversational session to define scope, milestones, budget, and success criteria
for a project. The output is a structured ProjectPlan stored to disk.
"""
from __future__ import annotations

import json

from viyugam.engine.client import get_client, text_of

PROJECT_PLAN_SYSTEM = """\
You are a project planning collaborator helping someone think through a project clearly.

Your role:
- Ask sharp questions to surface what's actually important, not what sounds good
- Help define real scope: what's in, what's explicitly out, what "done" looks like
- Surface risks and constraints the person may not have thought about
- Extract milestones that are concrete checkpoints, not vague phases
- Keep budget and cost grounded in reality

You work iteratively. Ask one focused question at a time. Build on what the person says.
Never give generic advice. Make everything specific to this project.

When the person says "save", "done", "that's it", or "looks good" — summarise what you've
captured and confirm you're ready to save.

The session ends when the person explicitly approves ("save" / "done" / "that's it").

After each response, if you are proposing or refining the project plan, append a PLAN_STATE block:

PLAN_STATE:
+ Milestone: Alpha shipped by Apr 1
+ Success: 100 users onboarded
- Success: 50% NPS score (removed — too early to measure)
= Scope: Auth, dashboard, payments (unchanged)

Use + for additions or revisions, - for removals, = for items carried forward unchanged.
Only include items that represent concrete plan elements (milestones, scope, success criteria, risks).
Omit the PLAN_STATE block if nothing meaningful changed."""


def _project_context(project: dict, existing_plan: "dict | None",
                     goals: list[dict]) -> str:
    """Build the opening context string for the boardroom."""
    lines = [
        f"Project: {project.get('title', 'Untitled')} ({project.get('seq_id', project.get('id', ''))})",
        f"Status:  {project.get('status', 'active')}",
    ]
    if project.get("dimension"):
        lines.append(f"Dimension: {project['dimension']}")
    if project.get("deadline"):
        lines.append(f"Deadline: {project['deadline']}")
    if project.get("budget_cap"):
        lines.append(f"Budget cap: ₹{project['budget_cap']:,.0f}")
    if project.get("description"):
        lines.append(f"Description: {project['description']}")

    linked_goal = next(
        (g for g in goals if g.get("id") == project.get("goal_id")), None
    )
    if linked_goal:
        lines.append(f"Goal: {linked_goal.get('title', '—')} ({linked_goal.get('seq_id', '')})")

    if existing_plan:
        lines.append("\nExisting plan (being updated):")
        if existing_plan.get("scope_md"):
            lines.append(f"  Scope: {existing_plan['scope_md'][:300]}")
        if existing_plan.get("success_criteria"):
            lines.append("  Success criteria: " + "; ".join(existing_plan["success_criteria"][:3]))

    return "\n".join(lines)


def start_project_plan_session(project: dict, existing_plan: "dict | None" = None,
                                goals: list[dict] | None = None) -> str:
    """Generate the opening message for a project planning session."""
    goals = goals or []
    ctx = _project_context(project, existing_plan, goals)

    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=PROJECT_PLAN_SYSTEM,
        messages=[{  # type: ignore[arg-type]
            "role": "user",
            "content": f"Let's plan this project.\n\n{ctx}"
        }],
    )
    return text_of(response).strip()


def project_plan_turn(history: list[dict], user_message: str,
                      project: dict) -> tuple[str, bool]:
    """
    Continue the project planning conversation.
    Returns (assistant_message, is_done).
    is_done is True when the user approves the plan.
    """
    done_kw = {"save", "done", "that's it", "thats it", "looks good",
               "confirm", "approve", "finish"}
    tl = user_message.strip().lower()
    is_done = any(kw in tl for kw in done_kw)

    messages = list(history) + [{"role": "user", "content": user_message}]
    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=PROJECT_PLAN_SYSTEM,
        messages=messages,  # type: ignore[arg-type]
    )
    reply = text_of(response).strip()
    return reply, is_done


def extract_project_plan(history: list[dict], project: dict) -> dict:
    """
    After the session ends, extract a structured ProjectPlan from the conversation.
    Returns a dict with keys: scope_md, success_criteria, out_of_scope,
    total_budget, notes, milestones (list of {title, due_date}).
    """
    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in history
    )

    extraction_prompt = f"""\
Extract a structured project plan from this project planning conversation.

Project: {project.get('title', 'Untitled')}

Conversation:
{conversation[:3000]}

Return ONLY valid JSON with this structure:
{{
  "scope_md": "2-4 sentence narrative of what this project is and what it covers",
  "success_criteria": ["done when X", "done when Y"],
  "out_of_scope": ["not including X", "not including Y"],
  "total_budget": 0.0,
  "notes": "key constraints, risks, or context in 1-2 sentences",
  "milestones": [
    {{"title": "milestone name", "due_date": "YYYY-MM-DD or null"}}
  ]
}}

If information wasn't discussed, use empty string / empty list / 0.0 as defaults."""

    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": extraction_prompt}],  # type: ignore[arg-type]
    )
    text = text_of(response).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except Exception:
        return {
            "scope_md": "",
            "success_criteria": [],
            "out_of_scope": [],
            "total_budget": 0.0,
            "notes": "",
            "milestones": [],
        }
