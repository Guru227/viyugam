"""
agents/researcher.py — The Researcher.
Uses Claude with Anthropic's built-in web search to produce comprehensive markdown reports.
Web search is server-side: Anthropic executes searches, no client-side tool_result loop needed.
"""
from __future__ import annotations
import os
from typing import Callable, Optional

import anthropic


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to your environment or ~/.viyugam/config.yaml"
        )
    return anthropic.Anthropic(api_key=api_key)


RESEARCH_SYSTEM = """You are a thorough research assistant. When given a topic, use web search to
gather current, accurate information and produce a well-structured markdown report.

Your report must include:
1. **Executive Summary** — 2-4 sentences covering the core answer
2. **Overview** — background and context
3. Relevant sections that cover the topic comprehensively (options, comparisons, pricing,
   key facts, how-to steps — whatever is most useful for this topic)
4. **Recommendations** — concrete, actionable takeaways
5. **Sources** — cite sources inline and list them at the end

Formatting rules:
- Use markdown headers (##, ###)
- Use bullet points and tables where they add clarity
- Be thorough but not padded — every sentence should earn its place
- Write for someone making a real decision, not just curious"""


def run_research(
    topic: str,
    on_status: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Research a topic using Claude with Anthropic's built-in web search.
    Web search is executed server-side — no client-side tool loop needed.
    Handles pause_turn for long responses by re-submitting.
    Returns the final markdown report as a string.
    """
    client = _client()

    messages: list[dict] = [
        {"role": "user", "content": f"Research this topic thoroughly: {topic}"}
    ]

    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}]

    while True:
        if on_status:
            on_status("Researching...")

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            system=RESEARCH_SYSTEM,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            return _extract_text(response.content)

        if response.stop_reason == "pause_turn":
            # Long response paused — re-submit to let Claude continue
            messages.append({"role": "assistant", "content": response.content})
            if on_status:
                on_status("Continuing research...")
            continue

        # Any other stop reason — return whatever text we have
        return _extract_text(response.content)


def _extract_text(content: list) -> str:
    """Extract and join all text blocks from a response content list."""
    parts = []
    for block in content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n\n".join(parts).strip()
