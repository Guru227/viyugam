"""
agents/chairman.py — The Chairman.
Handles inbox triage and daily schedule generation.
Fast, tactical, grounded in context.
"""
from __future__ import annotations

import json

from viyugam.engine.client import get_client, text_of
from viyugam.pii import redact

# ── Inbox Triage ───────────────────────────────────────────────────────────────

TRIAGE_SYSTEM = """You are the Chairman — a tactical planning agent for Viyugam, a personal Life OS.

Your job right now: triage raw inbox captures. Classify each one and extract metadata.

Rules:
- Be practical and grounded. Don't over-engineer classifications.
- Energy cost is cognitive load 1-10 (1 = mindless, 10 = deep focus required).
- Dimensions: health, wealth, career, relationships, joy, learning.
- context "ai-assisted" = uses Claude (research, planning, writing). Scheduleable anywhere with a laptop, including at office.
- Be honest, not sycophantic. If something looks like avoidance (e.g. vague tasks, tasks deferred repeatedly), flag it in the notes field.
- Additional output types beyond the array: if the input is clearly a JOURNAL ENTRY (reflection, feeling, event narrative), return type "journal". If it's a SLOW BURN ("learn Portuguese", "get fit eventually"), return type "slow_burn". If it's a GOAL ("I want to achieve X"), return type "goal". If it's a REVIEW FLAG ("I should reconsider my season"), return type "review_flag". If it's a HABIT ("do X every day"), return type "habit". If it's a TRANSACTION ("spent 500 on..." or "received salary..."), return type "transaction" with fields: amount (float), category (str), description (str), tx_type ("expense"|"income"|"transfer" — income for salary/payment received, expense for purchases/bills, transfer for moving money).

Return ONLY a JSON array, no other text:
[
  {
    "original": "...",
    "type": "task" | "project" | "note" | "journal" | "slow_burn" | "goal" | "review_flag" | "habit" | "transaction" | "event",
    "title": "...",
    "dimension": "career" | "health" | "wealth" | "relationships" | "joy" | "learning" | null,
    "energy_cost": 1-10,
    "estimated_minutes": 15-240,
    "context": "at-desk" | "errand" | "calls" | "anywhere" | "ai-assisted" | null,
    "notes": "any extra context worth keeping",
    "amount": null,
    "category": null,
    "description": null,
    "tx_type": null
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

    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=TRIAGE_SYSTEM,
        messages=[{"role": "user", "content": user_content}],  # type: ignore[arg-type]
    )

    text = text_of(response).strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Response was truncated — attempt to recover partial valid JSON
        # by closing the array at the last complete object boundary
        last_close = text.rfind("}")
        if last_close != -1:
            truncated = text[:last_close + 1]
            # Ensure it ends as a valid array
            try:
                return json.loads(truncated + "]")
            except json.JSONDecodeError:
                pass
        # Nothing salvageable — return a single catch-all task
        return [{
            "original": items[0] if items else "",
            "type": "task",
            "title": (items[0] if items else "")[:80],
            "dimension": None,
            "energy_cost": 5,
            "estimated_minutes": 30,
            "context": None,
            "notes": "Full text stored in inbox.",
            "amount": None,
            "category": None,
            "description": None,
            "tx_type": None,
        }]


# ── Daily Schedule ─────────────────────────────────────────────────────────────

PLAN_SYSTEM = """You are the Chairman — a tactical planning agent for Viyugam, a personal Life OS.

Your job: build a realistic, humane daily schedule.

Rules:
1. Use YOUR PERSONAL ENERGY PATTERN if provided — it overrides all defaults.
   If no pattern data: default to morning=deep, afternoon=shallow, evening=light.
2. High energy tasks (cost 7-10) go in peak energy windows.
3. Low energy tasks (cost 1-4) go in low energy windows.
4. Insert a 15-minute break after every 90 minutes of focused work.
5. If tasks exceed available hours, move lowest priority to backlog.
6. Always schedule habits that are due today.
7. Be realistic — don't schedule 10 hours of deep work. People need breathing room.
8. The schedule should feel good to look at, not anxiety-inducing.

WORK SCHEDULE RULES (apply when day_type is present):
9.  OFFICE DAY: work window is for career tasks ONLY.
    Personal tasks (health, relationships, joy, learning) go BEFORE start or AFTER end.
    EXCEPTION: context "ai-assisted" tasks (Claude research, planning, writing) may go
    anywhere in the day, including during office hours.
    Insert a 30m lunch block around 13:00 if the window crosses midday.
10. WFH DAY: work window is primary for deep work. Tasks with context "anywhere" or
    "ai-assisted" may be interspersed. Errands still go before/after work window.
11. OFF DAY: no career tasks. Focus on personal dimensions. Journals/energy still apply.
12. CALENDAR EVENTS: immovable hard blocks. Include in schedule as type "event".
    Nothing may overlap them. Note conflicts (if any) in energy_read.

PLANNING MODE — read carefully:
- FULL: Normal full-day plan. Start from day_start hour.
- MIDDAY: User is starting late or ran plan mid-day for the first time. Schedule ONLY from
  current_time forward. The catch_up_notes tell you what was already done — do NOT reschedule
  those. Fewer hours remain, so be selective. Acknowledge the late start briefly in energy_read.
- REPLAN: Circumstances changed. Schedule ONLY from current_time forward. The catch_up_notes
  explain what changed — factor this into task ordering and energy. Be pragmatic.

MIRROR PROTOCOL (apply always):
- Do not validate or comfort. Surface patterns honestly.
- If the same task appears more than twice across recent context, flag it in energy_read: "You've deferred [task] repeatedly — worth examining why."
- If the season focus dimension has no tasks this week, note it directly.
- If the user is overloaded (tasks > 8h), say so plainly in energy_read.

CONSTITUTION (if provided): Apply as hard constraints. Non-negotiables override scheduling preferences.
MEMORY CONTEXT (if provided): Use to inform energy patterns and flag drift.

Return ONLY a JSON object, no other text:
{
  "schedule": [
    {
      "time": "09:00",
      "duration_mins": 90,
      "type": "task" | "habit" | "break" | "event",
      "task_id": "...",
      "title": "...",
      "energy_cost": 7,
      "time_period": "morning" | "afternoon" | "evening" | "night"
    }
  ],
  "moved_to_backlog": ["task_id_1"],
  "energy_read": "Short note on energy patterns or acknowledgement of late start / changed circumstances",
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
    current_time: str = "09:00",
    mode: str = "full",
    catch_up_notes: str = "",
    work_schedule: dict | None = None,
    day_type: str = "wfh",
    calendar_events: list[dict] | None = None,
    memory_context: str = "",
    constitution: str = "",
    energy_pattern: dict | None = None,
) -> dict:
    """
    Generate a time-blocked daily schedule.
    mode: "full" | "midday" | "replan"
    Returns structured plan dict.
    """
    calendar_events = calendar_events or []

    journal_context = ""
    if recent_journals:
        journal_context = "RECENT JOURNAL ENTRIES (use these to understand energy patterns):\n"
        for d, content in recent_journals[:7]:
            journal_context += f"\n--- {d} ---\n{content[:800]}\n"
    else:
        journal_context = "No journal entries yet. Use default energy pattern assumptions."

    season_info = ""
    if config.get("season"):
        s = config["season"]
        season_info = f"Current season: {s.get('name', '')} | Focus: {s.get('focus', '')} | Secondary: {s.get('secondary', '')}"

    energy_section = ""
    if energy_pattern:
        ep = energy_pattern
        energy_section = (
            f"\nYOUR PERSONAL ENERGY PATTERN (from journal analysis — use instead of defaults):\n"
            f"  Peak hours: {ep.get('peak_hours', 'unknown')}\n"
            f"  Low energy: {ep.get('low_energy', 'unknown')}\n"
            f"  Best for deep work: {ep.get('best_for_deep_work', 'unknown')}\n"
            f"  Pattern: {ep.get('pattern_summary', '')}\n"
        )

    catch_up_section = ""
    if catch_up_notes:
        label = "ALREADY DONE TODAY" if mode == "midday" else "WHAT CHANGED"
        catch_up_section = f"\n{label}:\n{catch_up_notes}\n"

    constitution_section = f"\nCONSTITUTION (user's values and non-negotiables):\n{constitution}\n" if constitution else ""
    memory_section = f"\n{memory_context}\n" if memory_context else ""

    schedule_context = ""
    if work_schedule:
        schedule_context = (
            f"\nWORK SCHEDULE:\n"
            f"  Day type: {day_type.upper()}\n"
            f"  Work window: {work_schedule['start']} – {work_schedule['end']}\n"
        )

    calendar_context = ""
    if calendar_events:
        calendar_context = "\nCALENDAR BLOCKS (hard — do NOT schedule over these):\n"
        for e in calendar_events:
            t = f" {e['start_time']}" if e.get("start_time") else ""
            if e.get("end_time"):
                t += f"–{e['end_time']}"
            calendar_context += f"  - {e.get('title', 'Untitled')}{t} [{e.get('entry_type', 'event')}]\n"

    # GPS engine context
    gps_section = ""
    try:
        from viyugam.priority import format_context_for_prompt
        gps_text = format_context_for_prompt()
        if gps_text:
            gps_section = "\n" + gps_text + "\n"
    except Exception:
        pass

    user_content = f"""TODAY: {today}
PLANNING MODE: {mode.upper()}
CURRENT TIME: {current_time}
DAY START HOUR: {config.get('day_start', 10):02d}:00
USER: {config.get('user_name', 'friend')}
Work hours cap: {config.get('work_hours_cap', 8)}h
{season_info}{energy_section}
{schedule_context}{calendar_context}{catch_up_section}{constitution_section}{memory_section}{gps_section}
TASKS DUE TODAY OR OVERDUE (remaining):
{json.dumps(tasks, indent=2) if tasks else "None scheduled yet."}

HABITS:
{json.dumps(habits, indent=2) if habits else "No habits configured yet."}

ACTIVE PROJECTS (for context):
{json.dumps([{"id": p.get("id"), "title": p.get("title"), "dimension": p.get("dimension")} for p in projects[:5]], indent=2) if projects else "None."}

GOALS (for context):
{json.dumps([{"title": g.get("title"), "dimension": g.get("dimension")} for g in goals], indent=2) if goals else "None set yet."}

{journal_context}"""

    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=PLAN_SYSTEM,
        messages=[{"role": "user", "content": redact(user_content)}],  # type: ignore[arg-type]
    )

    text = text_of(response).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    result = json.loads(text)
    result["nudges"] = nudges
    return result


# ── Interactive Triage Session ─────────────────────────────────────────────────

CLASSIFY_ITEM_SYSTEM = """You are the Chairman classifying a single triage capture.
Return ONLY a JSON object — no other text:
{
  "type": "task" | "goal" | "project" | "note",
  "title": "Polished, clear title (≤80 chars)",
  "dimension": "career" | "health" | "wealth" | "relationships" | "joy" | "learning" | null,
  "priority": "high" | "medium" | "low",
  "due": "YYYY-MM-DD or null",
  "estimated_minutes": 15-480,
  "energy_cost": 1-10,
  "initial_draft": "Brief 1-2 sentence framing of this item for discussion",
  "aligns_to_goals": ["goal_id or seq_id if this clearly serves a goal"],
  "might_block": ["task_id or seq_id if this might block another task"]
}

GOALS and TASKS lists may be provided in context — use them to suggest relationships."""


def classify_item(content: str, context: str = "") -> dict:
    """Classify a single triage capture. Returns structured dict."""
    client = get_client()
    msg = f"{context}\n\nCapture: {redact(content)}" if context else f"Capture: {redact(content)}"
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=CLASSIFY_ITEM_SYSTEM,
        messages=[{"role": "user", "content": msg}],  # type: ignore[arg-type]
    )
    text = text_of(response).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except Exception:
        return {"type": "task", "title": content[:80], "dimension": None,
                "priority": "medium", "due": None, "estimated_minutes": 30,
                "energy_cost": 5, "initial_draft": content}


BOARDROOM_SYSTEM = """You are the Chairman running a boardroom discussion for Viyugam.
Three internal voices speak: Vision (long-term alignment), Resource (time/energy/money realism), Risk (what could go wrong).

For each turn:
1. Each voice gives ONE punchy sentence about the current proposal.
2. You synthesise into a revised draft (≤3 sentences).

Return ONLY a JSON object:
{
  "vision": "...",
  "resource": "...",
  "risk": "...",
  "synthesis": "Updated draft",
  "draft": "Current working version of the task/goal/project definition"
}"""


def boardroom_discuss_turn(
    original: str,
    current_draft: str,
    user_message: str,
    history: list[dict],
) -> dict:
    """One turn of the boardroom discussion. Returns {vision, resource, risk, synthesis, draft}."""
    client = get_client()
    messages = list(history)
    messages.append({
        "role": "user",
        "content": f"Original capture: {redact(original)}\nCurrent draft: {current_draft}\nUser says: {redact(user_message)}",
    })
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=BOARDROOM_SYSTEM,
        messages=messages,  # type: ignore[arg-type]
    )
    text = text_of(response).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except Exception:
        return {"vision": "", "resource": "", "risk": "",
                "synthesis": current_draft, "draft": current_draft}


DEDUP_SYSTEM = """You are finding near-duplicate pairs in a triage list.
Compare new captures against existing tasks.
Return ONLY a JSON array of pairs (may be empty):
[{"new_id": "...", "existing_id": "...", "reason": "why they might be duplicates"}]"""


def triage_dedup(new_items: list[dict], existing_tasks: list[dict]) -> list[dict]:
    """Find near-duplicate pairs between new triage items and existing tasks."""
    if not new_items or not existing_tasks:
        return []
    client = get_client()
    msg = (
        f"New triage items:\n{json.dumps([{'id': i['id'], 'content': i['content']} for i in new_items[:20]], indent=2)}\n\n"
        f"Existing tasks:\n{json.dumps([{'id': t.get('id'), 'title': t.get('title')} for t in existing_tasks[:30]], indent=2)}"
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=DEDUP_SYSTEM,
        messages=[{"role": "user", "content": redact(msg)}],  # type: ignore[arg-type]
    )
    text = text_of(response).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except Exception:
        return []


# ── Directive Boardroom Planning ───────────────────────────────────────────────

DIRECTIVE_PLAN_SYSTEM = """You are the Chairman running a directive planning session for Viyugam.
Three voices: Vision (long-term alignment), Resource (time/energy/money realism), Risk (what could go wrong).

Your role: Open with a CONCRETE proposal based on the user's current tasks, goals, and constraints.
Don't ask open-ended questions — make a specific, directional recommendation.

For each turn return ONLY a JSON object:
{
  "vision": "Vision voice (1 sentence)",
  "resource": "Resource voice (1 sentence)",
  "risk": "Risk voice (1 sentence)",
  "proposal": "Current working plan proposal (3-5 bullet points)",
  "constraint_summary": {"time_used": 0, "time_total": 0, "budget_used": 0, "budget_total": 0},
  "cascade_gaps": ["list of parent-goal items not covered by current tasks"],
  "values_alignment": "Brief note on values alignment (or null)",
  "canvas_items": [
    {"op": "+", "text": "item being added or newly emphasised"},
    {"op": "-", "text": "item being removed or deprioritised"},
    {"op": "=", "text": "item carried forward unchanged"}
  ]
}

canvas_items represents the live working plan as line-level changes.
Use op='+' for new or promoted items, op='-' for dropped items, op='=' for stable items.
Include all items currently in the proposal — not just changed ones.
If nothing changed from the previous turn, repeat the same items with op='='."""


def directive_boardroom_turn(
    scope: str,
    context: str,
    user_message: str,
    history: list[dict],
    current_proposal: str = "",
) -> dict:
    """One turn of directive boardroom planning. Returns structured plan dict."""
    client = get_client()
    messages = list(history)
    msg = (
        f"Scope: {scope.upper()} planning\n"
        f"Context:\n{context}\n\n"
        f"Current proposal:\n{current_proposal}\n\n"
        f"User says: {redact(user_message)}"
    )
    messages.append({"role": "user", "content": msg})
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=DIRECTIVE_PLAN_SYSTEM,
        messages=messages,  # type: ignore[arg-type]
    )
    text = text_of(response).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
        result["raw"] = text
        return result
    except Exception:
        return {"vision": "", "resource": "", "risk": "",
                "proposal": text, "constraint_summary": {},
                "cascade_gaps": [], "values_alignment": None, "raw": text}


def generate_initial_plan_proposal(
    scope: str,
    tasks: list[dict],
    goals: list[dict],
    parent_plan: dict,
    values: dict,
    budget_envelopes: list[dict],
    period_start: str,
    period_end: str,
    okrs: list[dict] | None = None,
) -> dict:
    """Generate initial directive plan proposal. Returns same structure as directive_boardroom_turn."""
    context = _build_plan_context(
        scope, tasks, goals, parent_plan, values, budget_envelopes, period_start, period_end,
        okrs=okrs,
    )
    return directive_boardroom_turn(
        scope=scope,
        context=context,
        user_message="Generate the initial plan proposal.",
        history=[],
        current_proposal="",
    )


def _build_plan_context(
    scope: str,
    tasks: list[dict],
    goals: list[dict],
    parent_plan: dict,
    values: dict,
    budget_envelopes: list[dict],
    period_start: str,
    period_end: str,
    okrs: list[dict] | None = None,
) -> str:
    import datetime as _dt
    lines = [
        f"Today: {_dt.date.today().isoformat()}",
        f"Period: {period_start} to {period_end} ({scope})",
        f"Goals: {json.dumps([{'title': g.get('title'), 'dimension': g.get('dimension')} for g in goals[:10]], indent=2)}",
        f"Tasks (active, due in period): {json.dumps([{'id': t.get('seq_id') or t.get('id'), 'title': t.get('title'), 'priority': t.get('priority'), 'due': t.get('due')} for t in tasks[:20]], indent=2)}",
    ]
    if okrs:
        okr_lines = []
        for o in okrs[:6]:
            obj = o.get("objective", "")
            dim = o.get("dimension") or ""
            krs = o.get("key_results", [])
            kr_text = "; ".join(
                kr.get("text", "") for kr in krs if not kr.get("is_done")
            )
            okr_lines.append(f"  [{dim}] {obj}" + (f" → {kr_text}" if kr_text else ""))
        lines.append(
            "Active OKRs (use these as the constraint — weekly priorities should "
            "visibly serve at least one OKR):\n" + "\n".join(okr_lines)
        )
    if parent_plan:
        lines.append(f"Parent plan: {json.dumps(parent_plan, indent=2)[:800]}")
    if values:
        prayer = values.get("prayer", "")
        if prayer:
            lines.append(f"Prayer/values: {prayer[:200]}")
    if budget_envelopes:
        lines.append(f"Budget envelopes: {json.dumps(budget_envelopes[:5], indent=2)}")
    return "\n\n".join(lines)
