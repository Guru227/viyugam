"""
agents/intent.py — Intent classifier for the natural language REPL.
classify_intent(text, context_summary) -> list[dict]
"""
from __future__ import annotations
import json
import os

import anthropic

from viyugam.pii import redact


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to your environment or ~/.viyugam/config.yaml"
        )
    return anthropic.Anthropic(api_key=api_key)


INTENT_SYSTEM = """You are the intent router for Viyugam, a personal Life OS.
Your sole job: classify natural language input into one or more structured actions.

VALID ACTIONS:
  plan_day        — build / replan today's schedule
  log_content     — add task / journal / habit / goal / note to inbox (chairman triage handles it)
  mark_done       — mark a task as complete
  run_think       — boardroom debate on a proposal / decision
  run_review      — weekly / monthly / quarterly review
  show_status     — quick overview of today (tasks, habits, inbox)
  show_finance    — finance summary
  log_finance     — log a transaction (expense/income) — use when text describes money spent/received
  finance_history — browse transactions month-by-month
  finance_recurring — manage recurring items (EMIs, salary)
  finance_insights  — AI finance analysis
  show_goals      — view long-term goals
  add_goal        — add a new goal
  show_decisions  — browse past boardroom decisions
  show_backlog    — browse backlog
  show_horizon    — 4-12 week forward view
  show_okrs       — OKRs by quarter
  show_slow_burns — long-horizon aspirations
  run_research    — research a topic using web search
  run_find        — semantic search across tasks and journals
  show_calendar   — view calendar events
  show_constitution — view values document
  help            — explain what Viyugam can do
  unknown         — cannot classify; ask for clarification

ROUTING RULES (apply in order):
1. "morning", "hi", "good morning", "what's up", "hey", "start my day" → show_status
2. "done with X", "finished X", "completed X", "just did X", "wrapped up X" → mark_done (task_title_hint = X)
3. "plan", "plan my day", "schedule", "what should I do", "let's plan", "replan" → plan_day
4. "should I...", "thinking about...", "debate...", "decide...", "help me decide" → run_think (proposal = the idea)
5. "review", "weekly review", "monthly review", "quarterly review" → run_review (review_cadence = weekly/monthly/quarterly)
6. "spent X on Y", "paid X for Y", "bought X", "received X", "got paid", "salary", "expense", "income" → log_finance (text = full original)
7. "finance", "spending", "budget", "money", "transactions" → show_finance
8. "goals", "show goals", "my goals" → show_goals
9. "add goal", "new goal", "I want to" → add_goal (text = full original)
10. "decisions", "past decisions" → show_decisions
11. "backlog" → show_backlog
12. "horizon", "next few weeks" → show_horizon
13. "okrs", "OKRs", "objectives" → show_okrs
14. "slow burns", "aspirations" → show_slow_burns
15. "research X", "look up X", "find information about X" → run_research (query = X)
16. "find X", "search for X", "look for X" in my data → run_find (query = X)
17. "calendar", "events", "schedule view" → show_calendar
18. "constitution", "values", "principles" → show_constitution
19. "help", "what can you do", "commands", "features" → help
20. Anything that looks like a task, journal entry, habit, note → log_content (text = full original)
21. Compound inputs → multiple actions (e.g. "finished X, also spent Y on Z" → [mark_done, log_finance])

RETURN FORMAT — always a JSON array, even for single actions:
[
  {
    "action": "<one of the valid actions above>",
    "args": {
      "text": null,
      "proposal": null,
      "task_title_hint": null,
      "review_cadence": null,
      "query": null
    },
    "preview": "One line: what this will do",
    "clarify": null
  }
]

RULES:
- Return ONLY the JSON array, no other text.
- For unknown: set clarify to a short question to ask the user.
- For mark_done: task_title_hint should be the task name/description from user input.
- For run_think: proposal should be the full decision/question text.
- For log_finance: text should be the full original user input.
- For log_content: text should be the full original user input.
- For run_research / run_find: query should be the search topic.
- For run_review: review_cadence should be "weekly", "monthly", or "quarterly" (default "weekly").
- Never include more fields than the args schema above.
- Keep preview concise (under 60 chars).
"""


def classify_intent(text: str, context_summary: str = "") -> list[dict]:
    """
    Classify natural language input into a list of actions.
    Each action dict has: action, args, preview, clarify.
    """
    user_content = f"CONTEXT:\n{context_summary}\n\nUSER INPUT: {text}" if context_summary else f"USER INPUT: {text}"

    client = _client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=INTENT_SYSTEM,
        messages=[{"role": "user", "content": redact(user_content)}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(raw)
