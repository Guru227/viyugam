# Viyugam — Flow Documentation

**Source of Truth.** Any code that conflicts with these diagrams is wrong — challenge it.

## Principles

- **4 user actions**: `log` · `review` · `plan` (rapid) · `/done`
- **Dashboard always on**: the TUI is the permanent shell; tabbed panels, left/right to switch, up/down to scroll
- **Triage is the universal inbox**: everything unprocessed lives in triage.json
- **Long-form discussion is the point, not the overhead**: the boardroom is where clarity is built
- **Laminar flow**: review always ends with planning; `plan` is the rapid path when reflection can be skipped
- **Values as persistent lens**: values.yaml is loaded at every boardroom session, every horizon
- **Entity hierarchy**: Goal (G-001) → Project (P-001) → Task (T-001); Note (N-001) is knowledge, not action
- **Pseudo-goals**: `~maintenance` (planned, proactive) and `~unplanned` (minimise); always present
- **Life dimensions**: career · wealth · health · joy · learning (+ relationships for journaling)
- **Layer model**: L1 daily · L2 weekly · L3 monthly · L4 quarterly

## Command Model

| Command | When to use |
|---------|-------------|
| `log` | Frictionless capture of any thought; also `done T-001` to mark complete |
| `review [scope]` | Full laminar cycle — retrospective → journal → Socratic (L4 only) → plan |
| `plan [scope]` | Rapid replan — minimal review, triage, directive boardroom; for urgent context changes |
| `/done T-001` | Mark any entity (T/G/P/N) complete from anywhere |

`scope`: daily (default) · week · month · quarter

## Docs

- [Architecture](architecture.md) — system components, storage, dashboard panels, threading model
- [GPS Engine](gps.md) — priority engine, constraint scoring, GPS panel, `get_context()`
- [Nudges](nudges.md) — nudge lifecycle: compute → surface → dismiss → recompute
- [Patterns](patterns.md) — pattern extraction, merging, precipitation, prompt integration
- [Cadence Loops](cadence-loops.md) — the three feedback loops, rolling quarterly, unclosed gaps
- [Log](log.md) — triage capture and task completion
- [Plan](plan.md) — rapid replan: triage + directive boardroom
- [Review](review.md) — full laminar cycle: retrospective · journal · Socratic · cascade · plan

## Future Scope

| Feature | Description |
|---------|-------------|
| `~unplanned` trend analysis | Flag when unplanned items are growing as a pattern across reviews |
| Task delegation to research | Route tasks to a background research agent; results surface in Research panel |
| Real-time nudges | Ticker monitors current plan; flags when a time block starts or you stray |
| Course correction | Mid-session drift detection with lightweight re-anchoring prompt |
| Analytics and trends | Cross-period stats: completion rates, energy patterns, dimension balance |
| Notes → Knowledge base | N-001 notes upgraded to internal KB; Research panel draws from it |
| Google Drive archival | Encrypted archival of journal/plan history; active storage pruned and compacted |
| Claude Code integration | Link terminal coding sessions back to tasks and goals in Viyugam |
| Claude CoWork | Collaborative mode — shared context between users or user + agent |
