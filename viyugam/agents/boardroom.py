"""
agents/boardroom.py — The Boardroom.
Three-voice debate: Vision, Resource, Risk.
Used by the think command for significant decisions.
"""
from __future__ import annotations
import json
import os

import anthropic

from viyugam.pii import redact


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    return anthropic.Anthropic(api_key=api_key)


BOARDROOM_SYSTEM = """You are facilitating a Board Meeting for a personal life decision.

The board has three voices:

VISION — asks: Does this align with what we're building right now?
  Considers: current season, long-term goals, personal values, identity
  Tone: expansive, possibility-oriented, but honest about misalignment

RESOURCE — asks: Can we actually afford this?
  Considers: time budget, energy levels (from recent journals), financial cost
  Tone: grounded, pragmatic, risk-aware but not fearful

RISK — asks: What could go wrong? What are we giving up?
  Considers: opportunity costs, second-order effects, reversibility
  Tone: honest about downsides, never catastrophizing

Rules:
- Each voice speaks once. Concise and direct — 2-4 sentences max per voice.
- Each voice casts a vote: YES / NO / CONDITIONAL
- The consensus is a synthesis, not a majority vote. It should reflect the most important considerations.
- If something feels like it belongs to the human dimension (relationships, gifts, emotional texture of life), RISK should note that some things are better lived than optimized.

Return ONLY a JSON object:
{{
  "transcript": [
    {{
      "voice": "Vision",
      "text": "...",
      "vote": "yes|no|conditional"
    }},
    {{
      "voice": "Resource",
      "text": "...",
      "vote": "yes|no|conditional"
    }},
    {{
      "voice": "Risk",
      "text": "...",
      "vote": "yes|no|conditional"
    }}
  ],
  "consensus": "approved|rejected|conditional",
  "summary": "One sentence synthesis of what matters most here.",
  "condition": "If conditional: what needs to be true before proceeding. Otherwise null.",
  "suggested_next": "approve|defer|someday"
}}"""


def run_debate(
    proposal: str,
    season: dict | None,
    dimension_scores: list[dict],
    active_projects: list[dict],
    goals: list[dict],
    actual_season: str | None = None,
    revisit_context: dict | None = None,
) -> dict:
    """
    Run a 3-voice boardroom debate on a proposal.
    Returns the full debate result as a dict.
    """
    # Build context
    season_text = "No season configured."
    if season:
        season_text = (
            f"Intended season: {season.get('name', '')} | "
            f"Focus: {season.get('focus', '')} | "
            f"Secondary: {season.get('secondary', '')}"
        )
        if actual_season:
            season_text += f"\nActual season (derived from behavior): {actual_season}"

    scores_text = "No recent journal data."
    if dimension_scores:
        scores_text = "Recent dimension scores (last 14 days):\n" + "\n".join(
            f"  {s['dimension']}: {s['score']}/10"
            + (f" — {s['note']}" if s.get("note") else "")
            for s in dimension_scores
        )

    projects_text = "No active projects."
    if active_projects:
        projects_text = "Active commitments:\n" + "\n".join(
            f"  - {p.get('title', 'Untitled')} ({p.get('dimension', 'unset')})"
            for p in active_projects[:5]
        )

    goals_text = "No goals set."
    if goals:
        goals_text = "Long-term goals:\n" + "\n".join(
            f"  - {g.get('title', 'Untitled')} ({g.get('dimension', 'unset')})"
            for g in goals
        )

    revisit_text = ""
    if revisit_context:
        revisit_text = (
            f"\nNote: This proposal was previously deferred on {revisit_context.get('created_at', '')[:10]}.\n"
            f"Original deferred reason: {revisit_context.get('deferred_reason', 'not specified')}\n"
            f"Previous consensus: {revisit_context.get('consensus', 'not recorded')}"
        )

    user_content = f"""PROPOSAL: "{redact(proposal)}"

{season_text}

{scores_text}

{projects_text}

{goals_text}
{revisit_text}

Run the board meeting."""

    client = _client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        system=BOARDROOM_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(text)
