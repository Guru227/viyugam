"""
agents/reviewer.py — The Reviewer.
Runs weekly / monthly / quarterly review sessions.
Three phases: Reflect → Analyse → Intent.
"""
from __future__ import annotations

import json
from typing import Literal

from viyugam.engine.client import get_client, text_of
from viyugam.pii import redact

Cadence = Literal["weekly", "monthly", "quarterly"]


# ── System prompts ─────────────────────────────────────────────────────────────

def _review_system(cadence: Cadence) -> str:
    period_map = {"weekly": "week", "monthly": "month", "quarterly": "quarter"}
    period = period_map[cadence]
    return f"""You are running a {cadence} review session for Viyugam — a personal Life OS.

Your role here is different from daily journaling. You are a Life Strategist:
- Analytical and structured, but warm and human
- Present patterns with supporting data — don't just list facts
- Ask sharp questions that prompt honest reflection, not comfortable ones
- Never give generic praise or empty encouragement
- "Get out of your head and into action" is your core mantra

The review has three phases you move through naturally:
1. REFLECT: What happened this {period}? Present the data with your honest observations.
   What's the headline? What would you flag if you were a coach reviewing someone else's {period}?

2. ANALYSE: What patterns emerge? Use the Socratic method — challenge assumptions.
   If the user says "I didn't do well", ask "What's the data supporting that?"
   If they're too hard on themselves, reframe with evidence.

3. INTENT: Close with clarity. One clear focus for next {period}.
   Ask: "Given everything we've discussed — what is the one thing that matters most next {period}?"

Rules:
- Keep your responses focused. This is a structured session, not open journaling.
- One question at a time.
- When the session has reached natural completion (intent has been set),
  include [REVIEW_COMPLETE] on its own line at the end of your message.
- Total session: aim for 6-10 exchanges.

Tone reference: ex-McKinsey strategist who genuinely cares about this person thriving.
Direct. Warm. No fluff.

MIRROR PROTOCOL: Be direct and specific. Reference the user's actual history when available. Do not soften uncomfortable truths. Name patterns honestly."""


BRIEFING_SYSTEM = """You are generating a data briefing to open a {cadence} review session.

Based on the data provided, write a concise, honest opening briefing.
Structure:
- Headline: One sentence that captures the essence of this {period} (honest, not cheerful by default)
- What happened: 3-5 bullet points of key facts from the data
- What stands out: 1-2 observations that are worth paying attention to (patterns, tensions, surprises)

Tone: Clear and direct. A good coach's opening observation — not a report card.
Length: ~150 words maximum.
Do NOT ask questions yet. Just present what you see.

MIRROR PROTOCOL: Be direct. Surface patterns without softening. If the data shows avoidance or drift, name it."""


REVIEW_SUMMARY_SYSTEM = """Based on this review conversation, generate a structured summary.

Return ONLY a JSON object:
{{
  "date": "{date}",
  "cadence": "{cadence}",
  "headline": "one sentence capturing the essence",
  "key_insights": ["insight 1", "insight 2", "insight 3"],
  "next_focus": "the one thing they committed to for next {period}",
  "dimension_notes": {{
    "health": "brief note or null",
    "wealth": "brief note or null",
    "career": "brief note or null",
    "relationships": "brief note or null",
    "joy": "brief note or null",
    "learning": "brief note or null"
  }},
  "coach_note": "one sentence the user should remember from this session"
}}"""


# ── Data gathering ─────────────────────────────────────────────────────────────

def build_review_data(
    cadence: Cadence,
    tasks_done: list[dict],
    tasks_backlogged: list[dict],
    habits: list[dict],
    projects: list[dict],
    goals: list[dict],
    someday_items: list[dict],
    dimension_scores: list[dict],
    journal_summaries: list[dict],
    season: dict | None,
    actual_season: str | None,
    today: str,
    finance_summary: str = "",
) -> str:
    """Format all review data into a readable context string for Claude."""
    days_map = {"weekly": 7, "monthly": 30, "quarterly": 90}
    days = days_map[cadence]

    lines = [f"REVIEW PERIOD: Last {days} days (as of {today})\n"]

    # Season
    if season:
        lines.append(f"INTENDED SEASON: {season.get('name')} | Focus: {season.get('focus')}")
        if actual_season and actual_season != season.get("focus"):
            lines.append(f"ACTUAL SEASON (derived): {actual_season} ← diverges from intended")
        else:
            lines.append("ACTUAL SEASON: aligned with intended")
        lines.append("")

    # Tasks
    lines.append(f"TASKS COMPLETED: {len(tasks_done)}")
    if tasks_done:
        by_dim: dict[str, int] = {}
        for t in tasks_done:
            d = t.get("dimension") or "unset"
            by_dim[d] = by_dim.get(d, 0) + 1
        breakdown = ", ".join(f"{d}: {c}" for d, c in sorted(by_dim.items(), key=lambda x: -x[1]))
        lines.append(f"  By dimension: {breakdown}")
    lines.append(f"TASKS BACKLOGGED (not done): {len(tasks_backlogged)}")
    lines.append("")

    # Habits
    if habits:
        lines.append("HABITS:")
        for h in habits:
            streak = h.get("streak", 0)
            status = "strong" if streak >= 7 else ("building" if streak >= 3 else "needs attention")
            lines.append(f"  {h.get('title')}: streak {streak} ({status})")
        lines.append("")

    # Projects
    active = [p for p in projects if p.get("status") == "active"]
    paused = [p for p in projects if p.get("status") == "paused"]
    lines.append(f"PROJECTS: {len(active)} active, {len(paused)} paused")
    for p in active[:5]:
        lines.append(f"  + {p.get('title')} ({p.get('dimension', 'unset')})")
    lines.append("")

    # Goals
    if goals:
        lines.append("ACTIVE GOALS:")
        for g in goals:
            lines.append(f"  - {g.get('title')} ({g.get('dimension')})")
        lines.append("")

    # Someday
    if someday_items:
        old_items = [s for s in someday_items if _days_old(s.get("created_at", "")) > 14]
        lines.append(f"SOMEDAY LIST: {len(someday_items)} items ({len(old_items)} older than 2 weeks)")
        for s in someday_items[:3]:
            lines.append(f"  - \"{s.get('proposal')}\" ({_days_old(s.get('created_at', ''))}d old)")
        lines.append("")

    # Dimension scores
    if dimension_scores:
        lines.append("DIMENSION SCORES (trailing average):")
        for ds in sorted(dimension_scores, key=lambda x: x.get("score", 5)):
            score = ds.get("score", 0)
            bar = "█" * int(score) + "░" * (10 - int(score))
            lines.append(f"  {ds.get('dimension'):15} [{bar}] {score}")
        lines.append("")

    # Finance (monthly/quarterly only)
    if finance_summary and cadence in ("monthly", "quarterly"):
        lines.append("FINANCE:")
        lines.append(finance_summary)
        lines.append("")

    # Journal patterns
    if journal_summaries:
        all_wins = []
        all_challenges = []
        all_patterns = []
        energy_levels = []
        for s in journal_summaries:
            all_wins.extend(s.get("wins", []))
            all_challenges.extend(s.get("challenges", []))
            all_patterns.extend(s.get("patterns_noted", []))
            if s.get("energy_level"):
                energy_levels.append(s["energy_level"])

        if energy_levels:
            from collections import Counter
            most_common = Counter(energy_levels).most_common(1)[0]
            lines.append(f"ENERGY PATTERN: mostly {most_common[0]} ({most_common[1]}/{len(energy_levels)} days)")
        if all_patterns:
            lines.append("PATTERNS FROM JOURNALS:")
            for p in list(set(all_patterns))[:5]:
                lines.append(f"  - {p}")
        lines.append("")

    return "\n".join(lines)


def _days_old(iso_str: str) -> int:
    from datetime import date, datetime
    if not iso_str:
        return 0
    try:
        d = datetime.fromisoformat(iso_str).date()
        return (date.today() - d).days
    except Exception:
        return 0


# ── Review session ─────────────────────────────────────────────────────────────

def generate_briefing(
    review_data: str,
    cadence: Cadence,
    constitution: str = "",
    memory_context: str = "",
    coherence: dict | None = None,
    decisions_for_review: list[dict] | None = None,
) -> str:
    """Generate the opening briefing for the review session."""
    period_map = {"weekly": "week", "monthly": "month", "quarterly": "quarter"}
    period = period_map[cadence]
    client = get_client()

    extra_context = ""
    if constitution:
        extra_context += f"\nCONSTITUTION:\n{constitution}\n"
    if memory_context:
        extra_context += f"\n{memory_context}\n"
    if coherence and coherence.get("score") is not None:
        extra_context += f"\nCOHERENCE SCORE: {coherence['score']}/100 — {coherence.get('narrative', '')}\n"
    if decisions_for_review:
        extra_context += f"\nPENDING DECISIONS FOR REVIEW: {len(decisions_for_review)}\n"

    # GPS engine context: goal trajectories and nudges
    try:
        from viyugam.priority import format_context_for_prompt
        gps_text = format_context_for_prompt()
        if gps_text:
            extra_context += "\n" + gps_text + "\n"
    except Exception:
        pass

    content = redact(review_data) + extra_context

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=BRIEFING_SYSTEM.format(cadence=cadence, period=period),
        messages=[{"role": "user", "content": content}],  # type: ignore[arg-type]
    )
    return text_of(response).strip()


def review_turn(
    history: list[dict],
    user_message: str,
    cadence: Cadence,
    constitution: str = "",
    memory_context: str = "",
    coherence: dict | None = None,
    decisions_for_review: list[dict] | None = None,
) -> tuple[str, bool]:
    """
    One turn of the review conversation.
    Returns (response, is_complete).
    """
    client = get_client()
    messages = history + [{"role": "user", "content": redact(user_message)}]

    system = _review_system(cadence)
    if constitution:
        system += f"\n\nCONSTITUTION:\n{constitution}"
    if memory_context:
        system += f"\n\n{memory_context}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=system,
        messages=messages,  # type: ignore[arg-type]
    )

    text = text_of(response).strip()
    complete = "[REVIEW_COMPLETE]" in text
    clean = text.replace("[REVIEW_COMPLETE]", "").strip()
    return clean, complete


def generate_review_summary(
    conversation: list[dict],
    cadence: Cadence,
    today: str,
) -> dict:
    """Generate structured summary after review conversation."""
    period_map = {"weekly": "week", "monthly": "month", "quarterly": "quarter"}
    period = period_map[cadence]

    conv_text = "\n".join(
        f"{'Reviewer' if m['role'] == 'assistant' else 'User'}: {m['content']}"
        for m in conversation
    )

    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system="You generate structured JSON summaries of review conversations. Return only valid JSON.",
        messages=[{  # type: ignore[arg-type]
            "role": "user",
            "content": REVIEW_SUMMARY_SYSTEM.format(
                date=today,
                cadence=cadence,
                period=period,
            ) + f"\n\nConversation:\n{conv_text}"
        }],
    )

    text = text_of(response).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    summary = json.loads(text)

    # GPS Pattern Learning: feed key_insights into the pattern store
    try:
        import viyugam.storage as _storage
        for insight in summary.get("key_insights", []):
            if insight and len(insight) > 5:
                _storage.merge_pattern(insight, source="review")
    except Exception:
        pass

    return summary


WEEKLY_LETTER_SYSTEM = """You are writing a personal weekly letter to the user — from the perspective of a wise, honest mentor who has been watching their week unfold.

Style:
- Narrative, not bullet points
- Warm but direct — you name patterns, not just events
- 3-4 paragraphs
- End with one question worth sitting with

Structure:
1. What happened this week (based on data)
2. The pattern you're noticing (honest, specific)
3. What this says about where they're headed
4. The question

Do NOT be sycophantic. Do NOT just summarise tasks. Find the human story in the data.
Return plain text, no JSON."""


def generate_weekly_letter(
    review_data,
    coherence: dict,
    actuals: list[dict],
    constitution: str = "",
    memory_context: str = "",
) -> str:
    client = get_client()
    # review_data may be a dict or pre-formatted string
    if isinstance(review_data, str):
        review_data_str = review_data[:3000]
    else:
        review_data_str = json.dumps(review_data, indent=2)[:3000]
    content = f"""REVIEW DATA:
{review_data_str}

COHERENCE SCORE: {coherence.get('score', 'N/A')}/100
{coherence.get('narrative', '')}

PLANNED VS ACTUAL:
{json.dumps(actuals, indent=2)}

{f'CONSTITUTION:{chr(10)}{constitution}' if constitution else ''}
{memory_context}

Write the weekly letter."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=WEEKLY_LETTER_SYSTEM,
        messages=[{"role": "user", "content": content}],  # type: ignore[arg-type]
    )
    return text_of(response).strip()


OKR_SYSTEM = """You are a strategic planning agent. Given a quarterly review and the user's goals,
generate specific, measurable OKRs for the next quarter.

Return ONLY a JSON array:
[
  {
    "objective": "Clear, inspiring objective statement",
    "dimension": "career" | "health" | "wealth" | "relationships" | "joy" | "learning",
    "key_results": [
      {"text": "Specific measurable outcome", "target": "metric or milestone"}
    ]
  }
]

Rules:
- 2-4 objectives maximum. Quality over quantity.
- 2-4 key results per objective.
- Key results must be measurable or clearly completable.
- Be realistic for a single quarter.
- Align with the user's season focus if present."""


def generate_okrs(
    review_summary: str,
    goals: list[dict],
    current_quarter: str,
    next_quarter: str,
    season_focus: str = "",
    constitution: str = "",
) -> list[dict]:
    client = get_client()
    content = f"""Current quarter: {current_quarter}
Planning for: {next_quarter}
Season focus: {season_focus or 'not set'}

Review summary:
{review_summary}

Active goals:
{json.dumps(goals, indent=2) if goals else "None set."}"""

    system = OKR_SYSTEM
    if constitution:
        system += f"\n\nCONSTITUTION:\n{constitution}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": content}],  # type: ignore[arg-type]
    )
    text = text_of(response).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def format_review_markdown(
    briefing: str,
    conversation: list[dict],
    summary: dict,
    cadence: Cadence,
    today: str,
) -> str:
    """Format the full review as markdown."""
    cadence_label = cadence.capitalize()
    lines = [f"# {cadence_label} Review · {today}\n"]

    if summary.get("headline"):
        lines.append(f"_{summary['headline']}_\n")

    lines.append("## Briefing\n")
    lines.append(briefing + "\n")

    lines.append("## Session\n")
    for msg in conversation:
        role = "**Reviewer**" if msg["role"] == "assistant" else "**You**"
        lines.append(f"{role}: {msg['content']}\n")

    if summary.get("next_focus"):
        lines.append(f"\n## Next {cadence.capitalize()} Focus\n")
        lines.append(f"**{summary['next_focus']}**\n")

    if summary.get("key_insights"):
        lines.append("\n## Key Insights\n")
        for insight in summary["key_insights"]:
            lines.append(f"- {insight}")

    lines.append("\n```json")
    lines.append(json.dumps(summary, indent=2, ensure_ascii=False))
    lines.append("```\n")

    return "\n".join(lines)


# ── Laminar Review — Phase 1: Retrospective ────────────────────────────────────

RETRO_SYSTEM = """You are running the Retrospective phase of a {scope} review for Viyugam.
Analyse planned-vs-done, surfacing patterns honestly.
Rules:
- Be direct, not validating.
- Reference actual data (planned tasks vs completed, triage logs).
- One key question to open. When user says 'next', reply with [PHASE_COMPLETE] on its own line.

After each response (except the very first opening), append a PLAN_STATE block summarising what has been surfaced in the retro so far:

PLAN_STATE:
+ Insight: task completion 2/5 — 40% rate
+ Pattern: GCC deferred 3 days running
= Context: Samarthyam has external deadline
- Dropped: "I was productive" — data says otherwise

Use + for new insights or patterns surfaced, = for stable context, - for assumptions debunked or tasks that didn't happen.
Update the block each turn to reflect cumulative retro findings, not just the latest message.
"""


def retro_turn(
    history: list[dict],
    user_message: str,
    scope: str,
    review_data: dict,
) -> tuple[str, bool]:
    """One turn of retrospective phase. Returns (response, is_complete)."""
    client = get_client()
    system = RETRO_SYSTEM.format(scope=scope)
    messages = list(history)
    messages.append({"role": "user", "content": redact(user_message)})
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=system,
        messages=messages,  # type: ignore[arg-type]
    )
    text = text_of(response).strip()
    complete = "[PHASE_COMPLETE]" in text
    text = text.replace("[PHASE_COMPLETE]", "").strip()
    return text, complete


# ── Laminar Review — Phase 2: Journal by Dimension ────────────────────────────

DIM_JOURNAL_SYSTEM = """You are running the {dimension} dimension journal in a {scope} review.
Use the lens of {dimension} to reflect on this period.
Prompt the user with one focused question about their {dimension} life.
When user says 'next' or 'skip', write [PHASE_COMPLETE] on its own line.
Keep responses concise (≤120 words).
{prior_context}"""


def dim_journal_turn(
    history: list[dict],
    user_message: str,
    dimension: str,
    scope: str,
    prior_summaries: dict | None = None,
) -> tuple[str, bool]:
    """One turn of per-dimension journal. Returns (response, is_complete)."""
    client = get_client()
    prior_context = ""
    if prior_summaries:
        relevant = {k: v for k, v in prior_summaries.items() if v != "skipped"}
        if relevant:
            lines = ["\nContext from earlier dimensions in this session (use to make connections):"]
            for dim, summary in relevant.items():
                lines.append(f"- {dim}: {summary[:200]}")
            prior_context = "\n".join(lines)
    system = DIM_JOURNAL_SYSTEM.format(
        dimension=dimension, scope=scope, prior_context=prior_context
    )
    messages = list(history)
    messages.append({"role": "user", "content": redact(user_message)})
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=system,
        messages=messages,  # type: ignore[arg-type]
    )
    text = text_of(response).strip()
    complete = "[PHASE_COMPLETE]" in text
    text = text.replace("[PHASE_COMPLETE]", "").strip()
    return text, complete


def synthesize_dim_journal(history: list[dict], dimension: str, scope: str, today: str) -> str:
    """Synthesise a dimension journal conversation into a markdown entry."""
    client = get_client()
    history_text = "\n".join(
        f"{'Reviewer' if m['role']=='assistant' else 'You'}: {m['content']}"
        for m in history
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=f"You are synthesising a {dimension} journal entry from a {scope} review conversation. Write 2-3 sentences capturing the essence. No preamble.",
        messages=[{"role": "user", "content": f"Date: {today}\nConversation:\n{history_text}"}],  # type: ignore[arg-type]
    )
    return text_of(response).strip()


def extract_review_tasks(dim_summaries: dict) -> dict:
    """Extract new tasks and completed hints from dimension journal summaries.

    Returns dict with keys:
      new_tasks: list[str]       — action items or commitments mentioned
      completed_hints: list[str] — things mentioned as already done
    """
    if not dim_summaries:
        return {"new_tasks": [], "completed_hints": []}

    client = get_client()
    combined = "\n\n".join(
        f"[{dim.upper()}]\n{summary}"
        for dim, summary in dim_summaries.items()
        if summary and summary != "skipped"
    )
    if not combined.strip():
        return {"new_tasks": [], "completed_hints": []}

    system = """You extract action items and completed work from journal summaries.

Return ONLY a JSON object with two keys:
{
  "new_tasks": ["task 1", "task 2"],
  "completed_hints": ["thing done 1", "thing done 2"]
}

new_tasks: concrete action items, commitments, or intentions the person mentioned they want to do.
completed_hints: things they mentioned they already finished or accomplished.

Rules:
- Only include specific, actionable items (not vague goals)
- Max 6 new tasks, max 4 completed hints
- Keep each item short (under 60 chars)
- If nothing found, return empty lists
- Return ONLY the JSON object, no other text"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": f"Journal summaries:\n\n{combined}"}],  # type: ignore[arg-type]
        )
        text = text_of(response).strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        return {
            "new_tasks": [str(t) for t in data.get("new_tasks", [])[:6]],
            "completed_hints": [str(t) for t in data.get("completed_hints", [])[:4]],
        }
    except Exception:
        return {"new_tasks": [], "completed_hints": []}
