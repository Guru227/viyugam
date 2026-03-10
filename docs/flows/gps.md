# GPS Engine — Priority & Navigation

The GPS engine is Viyugam's core computation layer. It answers one question: **"What should I do right now?"**

## Architecture

```
storage.py (tasks, goals, projects)
    ↓
priority.py  →  PriorityContext (ephemeral)
    ↓
dashboard.py (GPS panel)  +  agents (enriched prompts)
```

**Zero API calls.** The priority engine is pure Python computation, sub-second. It reads from storage and returns a `PriorityContext` object.

## `get_context() → PriorityContext`

The main entry point. Returns:

| Field | Type | Description |
|-------|------|-------------|
| `directive_task` | dict | The single highest-priority task |
| `why_bottleneck` | str | Why this task matters (blocks, aligns, urgency) |
| `unblocks` | list[str] | Task titles that completing this would unblock |
| `nudges` | list[Nudge] | Active nudges (deadline, streak, snooze, etc.) |
| `goal_trajectories` | list[dict] | Progress + trajectory for each active goal |
| `energy_fit` | str | Current energy window description |

## Scoring Algorithm

Each active task gets a composite score from 5 signals:

```
composite = 0.30 * goal_impact
          + 0.30 * constraint_score
          + 0.20 * urgency
          + 0.15 * criticality
          + 0.05 * energy_fit
```

### Signal definitions

- **goal_impact** (0-1): `aligned_goals / total_active_goals` — how many active goals does this task serve?
- **constraint_score** (0-1): `downstream_count / max_downstream` — how many other tasks does this block? (Theory of Constraints)
- **urgency** (0-1): time pressure from due date (overdue=1.0, today=0.95, 2d=0.8, 7d=0.5, 14d=0.3)
- **criticality** (0-1): from task.priority field (high=1.0, medium=0.5, low=0.2)
- **energy_fit** (0-1): how well task energy_cost matches current time-of-day energy window

### Bottleneck tracing

The `why_bottleneck` string explains why the directive task was chosen. It traces the `blocks` relationships to show what completing this task would unblock.

## Goal Trajectories

`compute_goal_trajectories()` classifies each active goal:

- **on_track**: progress >= 80% of expected (based on quarter elapsed)
- **at_risk**: progress >= 50% of expected
- **off_track**: progress < 50% of expected

Each goal's `bottleneck_task` is the undone aligned task with highest constraint_score.

## Task Relationships

Two relationship types stored on Task:

- `blocks: list[str]` — IDs of tasks this blocks (downstream)
- `aligns_to: list[str]` — goal IDs this task serves

Set via dashboard commands:
- `T-001 blocks T-002`
- `T-001 serves G-001`

Or suggested during triage by the Chairman agent.

## GPS Panel

Default panel in execute mode. Layout:

```
NOW ─────────────────────────────────────
● Task Title                    [T-NNN]
  Project: P-003 · Goal: G-001
  Why: blocks 3 other tasks
  Unblocks: "Deploy staging", "Write tests"
  Energy: 7/10 · ~90m · Due: Mar 12

NUDGES ──────────────────────────────────
! Goal 'Ship MVP' at risk (34%)
! 'Call dentist' snoozed 4 times

GOALS ───────────────────────────────────
G-001  Ship MVP       █████░░░░░  52%  +
G-002  Get fit         ██░░░░░░░░  18%  ~

PATTERNS ────────────────────────────────
· Deep work best before 11am
```

## Files

| File | Role |
|------|------|
| `viyugam/priority.py` | Engine: scoring, trajectories, nudges |
| `viyugam/models.py` | Task.blocks/aligns_to, Goal.trajectory/progress_pct, Nudge, PriorityContext |
| `viyugam/storage.py` | Nudge/pattern persistence, cascade helpers |
| `viyugam/dashboard.py` | GPS panel renderer |
