"""
agents/intent.py — Intent classifier for the natural language REPL.
classify_intent(text, context_summary) -> list[dict]
"""
from __future__ import annotations

import json

from viyugam.engine.client import get_client, text_of
from viyugam.pii import redact

INTENT_SYSTEM = """You are the intent router for Viyugam, a personal Life OS.
Your sole job: classify natural language input into one or more structured actions.

VALID ACTIONS:
  plan_day        — build / replan a plan (scope: daily/weekly/monthly/quarterly)
  log_content     — capture to triage (instant, no AI) — tasks, thoughts, ideas, notes
  mark_done       — mark a task/goal/project done by hint text or seq_id (T-NNN etc)
  run_review      — laminar review session (weekly/monthly/quarterly)
  show_finance    — finance summary
  log_finance     — log a transaction (expense/income)
  finance_history — browse transactions month-by-month
  finance_recurring — manage recurring items (EMIs, salary)
  finance_insights  — AI finance analysis
  show_goals      — view long-term goals
  add_goal        — add a new goal
  delete_goal     — permanently delete a goal
  show_decisions  — browse past boardroom decisions
  show_backlog    — browse backlog
  show_horizon    — 4-12 week forward view
  show_okrs       — OKRs by quarter
  show_slow_burns — long-horizon aspirations
  run_research    — research a topic using web search
  run_find        — semantic search across tasks and journals
  show_calendar   — view calendar events
  show_values     — view values document (was: constitution)
  show_dashboard  — open full-screen dashboard
  help            — explain what Viyugam can do
  unknown         — cannot classify; ask for clarification

ROUTING RULES (apply in order):
1. "done T-NNN", "done G-NNN", "done P-NNN" (sequential ID pattern [TGPN]-\\d+) → mark_done (task_title_hint = the full id like T-001)
2. "done with X", "finished X", "completed X", "just did X", "wrapped up X" → mark_done (task_title_hint = X)
3. "plan", "plan my day", "plan week", "plan month", "plan quarter", "schedule", "replan" → plan_day (review_cadence = daily/weekly/monthly/quarterly based on input, default daily)
4. "review", "weekly review", "monthly review", "quarterly review" → run_review (review_cadence = weekly/monthly/quarterly)
5. "spent X on Y", "paid X for Y", "bought X", "received X", "got paid", "salary", "expense", "income" → log_finance (text = full original)
6. "finance", "spending", "budget", "money", "transactions" → show_finance
7. "goals", "show goals", "my goals" → show_goals
8. "add goal", "new goal", "I want to" → add_goal (text = full original)
9. "delete goal X", "remove goal X" → delete_goal (task_title_hint = X)
10. "decisions", "past decisions" → show_decisions
11. "backlog" → show_backlog
12. "horizon", "next few weeks" → show_horizon
13. "okrs", "OKRs", "objectives" → show_okrs
14. "slow burns", "aspirations" → show_slow_burns
15. "research X", "look up X", "find information about X" → run_research (query = X)
16. "find X", "search for X", "look for X" in my data → run_find (query = X)
17. "calendar", "events", "schedule view" → show_calendar
18. "constitution", "values", "principles" → show_values
19. "dashboard", "show dashboard", "open dashboard", "overview" → show_dashboard
20. "help", "what can you do", "commands", "features" → help
21. Anything that looks like a task, thought, habit, note, idea → log_content (text = full original)
22. Compound inputs → multiple actions (e.g. "finished X, also spent Y on Z" → [mark_done, log_finance])

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
- For mark_done: task_title_hint should be the T-NNN id or task name from user input.
- For log_finance: text should be the full original user input.
- For log_content: text should be the full original user input.
- For run_research / run_find: query should be the search topic.
- For run_review / plan_day: review_cadence should be "daily", "weekly", "monthly", or "quarterly".
- Never include more fields than the args schema above.
- Keep preview concise (under 60 chars).
- IMPORTANT: For long brain-dumps with many tasks/habits/goals mixed together,
  return a SINGLE log_content action with the full text — do NOT enumerate each
  item as a separate action.
  Only split into multiple actions when the input contains clearly distinct ACTION
  TYPES (e.g. "finished X" + "spent Y on Z" → mark_done + log_finance).
"""


def classify_intent(text: str, context_summary: str = "") -> list[dict]:
    """
    Classify natural language input into a list of actions.
    Each action dict has: action, args, preview, clarify.
    """
    user_content = f"CONTEXT:\n{context_summary}\n\nUSER INPUT: {text}" if context_summary else f"USER INPUT: {text}"

    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=INTENT_SYSTEM,
        messages=[{"role": "user", "content": redact(user_content)}],  # type: ignore[arg-type]
    )

    raw = text_of(response).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Truncated or malformed response — fall back to logging the full input
        return [{
            "action": "log_content",
            "args": {"text": text, "proposal": None, "task_title_hint": None,
                     "review_cadence": None, "query": None},
            "preview": "Capture to triage",
            "clarify": None,
        }]
