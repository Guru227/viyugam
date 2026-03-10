# Nudge System

Nudges are proactive alerts computed by the GPS engine. They surface things that need attention without the user asking.

## Lifecycle

```
compute_nudges()  →  Nudge objects  →  GPS panel / agent prompts
       ↓                                      ↓
  dedup against                         user dismisses
  dismissed keys                              ↓
                                      dismiss_nudge()
                                              ↓
                                      ~/.viyugam/data/nudges.json
```

## Nudge Types

| Type | Trigger | Severity |
|------|---------|----------|
| `DEADLINE` | Task due within 2 days | critical (overdue), warn (tomorrow), info (2d) |
| `STREAK` | Habit streak broken | warn |
| `SNOOZE` | Task snoozed 3+ times | warn |
| `GOAL_RISK` | Goal trajectory at_risk or off_track | warn / critical |
| `BUDGET_DRIFT` | Budget >80% spent | warn / critical |
| `STALE_TASK` | TODO task older than 14 days | info |
| `SEASON_DRIFT` | Actual vs intended season misalignment | warn |

## Deduplication

Nudges are keyed by `entity_id:nudge_type`. Once dismissed, the same combination won't resurface until the underlying condition changes (e.g., a new deadline nudge for a different task).

Dismissed nudges are stored in `~/.viyugam/data/nudges.json`.

## Storage API

```python
get_stored_nudges() -> list[dict]     # all stored (including dismissed)
save_nudge(nudge: Nudge) -> None      # upsert by id
dismiss_nudge(entity_id, nudge_type)  # mark as dismissed
```

## Where nudges appear

1. **GPS panel** — shown in the NUDGES section
2. **plan_day()** — included in Claude's context for daily planning
3. **generate_briefing()** — included in review session context
