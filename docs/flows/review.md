# Review Flow — Full Laminar Cycle

## Purpose

The canonical cycle. Review always ends with planning — they are phases of the same flow,
not separate actions. The depth of each phase scales with the time horizon and whether the
trigger is end-of-period or mid-period.

```
retrospective → journal → socratic (L4 only) → cascade + plan
```

For mid-period triggers, the retrospective compresses to "what changed?" and flows
directly into replanning. The phases are not skippable — but their depth is proportional.

Invocation: `review` (daily L1) · `review week` (L2) · `review month` (L3) · `review quarter` (L4)

---

## High-Level (four phases)

```mermaid
flowchart TB
    START([User: 'review']) --> SCOPE{Scope\nL1 L2 L3 L4}
    SCOPE --> TIMING{Trigger\ntiming}

    TIMING -->|end of period| R1
    TIMING -->|mid-period\nout-of-cycle| MCHANGE[Claude: flag mid-period\nAsk: what has changed?]
    MCHANGE --> MCTX[Change context captured\nthreaded through all phases]
    MCTX --> R1

    subgraph R1 [Phase 1 — Retrospective]
        R1A[Load: plan for period + triage logs\n+ completed + carried-over tasks]
        R1A --> R1B[Claude: planned vs done · patterns\nwins · misses · open questions]
        R1B --> R1C[Open conversation]
        R1C --> R1D{User: 'next'}
    end

    subgraph R2 [Phase 2 — Journal by Dimension]
        direction LR
        DA[career] --> DAJ[reflect + draft]
        DB[wealth] --> DBJ[reflect + draft]
        DC[health] --> DCJ[reflect + draft]
        DD[relationships] --> DDJ[reflect + draft]
        DE[joy] --> DEJ[reflect + draft]
        DF[learning] --> DFJ[reflect + draft]
        DAJ & DBJ & DCJ & DDJ & DEJ & DFJ --> R2W[Write entries per dimension]
    end

    R3CHK{L4\nquarterly?}

    subgraph R3 [Phase 3 — Socratic Values Session]
        R3A[Synthesize patterns\nacross journal entries]
        R3A --> R3B[Socratic dialogue\nwhat do you value?\nwhere do you want to be?]
        R3B --> R3C[User explores]
        R3C --> R3D{User: 'next'\nor 'skip'}
        R3D -->|next| R3E[Claude: draft values.yaml diff]
        R3E --> R3F{User: approve / edit}
        R3F --> R3G[Write values.yaml]
        R3D -->|skip| R3S[values.yaml unchanged\nskip recorded]
    end

    subgraph R4 [Phase 4 — Cascade and Plan]
        R4CK[Cascade check:\nparent-layer goals vs current plan\ngaps flagged for boardroom]
        R4CK --> R4A[Claude: load full context\n+ values + season weights if L4]
        R4A --> R4B[Boardroom: plan next period\naggregate: time · scope · budget\nvalues as persistent lens]
        R4B --> R4C{User}
        R4C -->|challenge / refine| R4B
        R4C -->|approve| R4D[Write plan\n+ season weights if L4]
    end

    R1D --> R2 --> R3CHK
    R3CHK -->|yes| R3
    R3CHK -->|no| R4
    R3 --> R4
    R4 --> DONE([Done])
```

---

## Retrospective depth by horizon

| Scope | Mid-period trigger | End-of-period retrospective |
|-------|-------------------|---------------------------|
| daily | "What changed today?" → replan | How did today go? 2–4 exchanges |
| week | "What changed this week?" → replan | Full week reflection, 5–10 exchanges |
| month | "N days into month — what changed?" → replan | Full month reflection, journal |
| quarter | "N weeks into quarter — what changed?" → replan | Full quarter + Socratic + values |

---

## Phase 1 — Retrospective (swimlane)

```mermaid
sequenceDiagram
    participant U  as User
    participant ML as Main Loop
    participant BG as Background Thread
    participant CA as Claude API (Chairman)
    participant FS as Storage

    U->>ML: 'review [scope]' + Enter
    ML->>BG: spawn review session
    activate BG
    BG->>BG: _capture_rich() active
    BG->>BG: detect trigger timing\n(current date vs period start/end)

    alt mid-period trigger
        BG->>ML: 'You are N days into the period. What changed?'
        ML->>ML: app.invalidate()
        U->>ML: change context
        ML->>BG: context captured
        note over BG: mid-period context threaded\nthrough all phases
    end

    BG->>FS: load plan for this period (daily/weekly/monthly/quarterly .json)
    BG->>FS: load triage logs (period)
    BG->>FS: load completed tasks (period)
    BG->>FS: load pending / carried-over tasks
    BG->>CA: retrospective prompt\n(planned vs done, logs, mid-period context if any)
    CA-->>BG: opening reflection\n(wins · misses · patterns · open questions)
    BG->>ML: display
    ML->>ML: app.invalidate()

    loop open reflection
        U->>ML: thoughts / memories / clarifications
        ML->>BG: forward
        BG->>CA: deepen
        CA-->>BG: follow-up or synthesis
        BG->>ML: display
        ML->>ML: app.invalidate()
    end

    U->>ML: 'next'
    BG->>ML: 'Moving to journal'
    deactivate BG
```

---

## Phase 2 — Journal by Dimension (swimlane)

```mermaid
sequenceDiagram
    participant U  as User
    participant ML as Main Loop
    participant BG as Background Thread
    participant CA as Claude API (Chairman)
    participant FS as Storage

    note over BG: same session — re-activate for this phase
    activate BG
    note over BG: dimensions: career · wealth · health\nrelationships · joy · learning

    loop for each dimension
        BG->>CA: dimension lens prompt\n(logs + dimension context + mid-period context if any)
        CA-->>BG: reflection starter
        BG->>ML: display
        ML->>ML: app.invalidate()

        loop dimension conversation
            U->>ML: response / memory / feeling
            ML->>BG: forward
            BG->>CA: continue
            CA-->>BG: deeper reflection or question
            BG->>ML: display
            ML->>ML: app.invalidate()
        end

        U->>ML: 'next' or 'skip'

        alt 'next'
            BG->>CA: synthesize journal entry
            CA-->>BG: draft entry
            BG->>FS: write journal/YYYY-MM-DD-{scope}-{dim}.md
            BG->>ML: 'Journal: {dim} saved'
        else 'skip'
            BG->>FS: write journal/YYYY-MM-DD-{scope}-{dim}.md\ncontent: skipped
            BG->>ML: 'Journal: {dim} skipped'
        end
        ML->>ML: app.invalidate()
    end

    BG->>ML: 'Journal complete'
    deactivate BG
```

---

## Phase 3 — Socratic Values Session (swimlane — L4 only)

```mermaid
sequenceDiagram
    participant U  as User
    participant ML as Main Loop
    participant BG as Background Thread
    participant CA as Claude API (Socratic)
    participant FS as Storage

    note over BG: L4 quarterly only — skipped for L1/L2/L3
    activate BG

    BG->>FS: load all journal entries (this period)
    BG->>FS: load values.yaml (current snapshot)
    BG->>CA: synthesize cross-dimension patterns\nfrom journal entries
    CA-->>BG: pattern summary\n(what recurs · avoided · energises · drains)
    BG->>ML: display pattern summary
    ML->>ML: app.invalidate()

    loop Socratic dialogue
        BG->>CA: next question derived from patterns + prior answers
        CA-->>BG: probing question
        BG->>ML: display
        ML->>ML: app.invalidate()
        U->>ML: reflection
        ML->>BG: forward
        BG->>CA: integrate, identify next question or signal readiness
        CA-->>BG: follow-up or synthesis signal
        BG->>ML: display
        ML->>ML: app.invalidate()
    end

    U->>ML: 'next' or 'skip'

    alt 'next' — update values
        BG->>CA: draft values.yaml diff\n(what changed · reinforced · removed)
        CA-->>BG: proposed diff
        BG->>ML: display proposed changes
        ML->>ML: app.invalidate()
        loop user edits
            U->>ML: approve specific change / edit
            ML->>BG: forward
            BG->>ML: show updated draft
            ML->>ML: app.invalidate()
        end
        U->>ML: 'approve'
        BG->>FS: write values.yaml
        BG->>ML: 'Values updated'
    else 'skip'
        BG->>ML: 'Values session skipped — values.yaml unchanged'
    end

    ML->>ML: app.invalidate()
    deactivate BG
```

---

## Phase 4 — Cascade and Plan (swimlane)

```mermaid
sequenceDiagram
    participant U  as User
    participant ML as Main Loop
    participant BG as Background Thread
    participant CA as Claude API (Boardroom)
    participant FS as Storage

    note over BG: continues from previous phase — same session
    activate BG

    BG->>FS: load parent-layer plan\n(monthly plan if weekly, quarterly if monthly, etc.)
    BG->>FS: load active goals + projects
    BG->>FS: load values.yaml (just updated if L4)
    BG->>FS: load budget.yaml + calendar.ics (period)
    BG->>FS: load energy score (Claude-inferred from journals, user-confirmed)

    note over BG: cascade check
    BG->>CA: compare parent-layer goals to current task list\nidentify gaps and misalignments
    CA-->>BG: cascade alignment summary\n(what the parent layer says · what exists · gaps)
    BG->>ML: display cascade check
    ML->>ML: app.invalidate()

    alt L4 quarterly — set season weights
        BG->>CA: based on goals just set and values\npropose season weights for next quarter
        CA-->>BG: proposed weights per dimension
        BG->>ML: display proposed weights
        ML->>ML: app.invalidate()
        U->>ML: adjust / approve weights
        ML->>BG: confirmed weights
    end

    BG->>BG: init constraint tracker\ntime: 0/total · budget: 0/envelope · scope: 0
    BG->>CA: build planning context:\nretrospective insights + journals + values + cascade gaps\n+ constraints: time · scope · budget
    CA-->>BG: proposed plan for next period\ngrounded in retrospective + values\nconstraint summary: time X/Y · budget $X/$Y · scope N
    BG->>ML: display proposal with constraint bar
    ML->>ML: app.invalidate()

    loop boardroom refinement
        U->>ML: challenge / adjust
        ML->>BG: forward
        BG->>CA: refine — recompute constraints\ncheck values alignment
        CA-->>BG: updated proposal + constraint delta
        BG->>ML: display
        ML->>ML: app.invalidate()
    end

    U->>ML: 'approve'
    BG->>FS: write plan (daily/weekly/monthly/quarterly .json)
    alt L4
        BG->>FS: write season weights
    end
    BG->>ML: 'Review complete. Plan ready.'
    BG->>ML: app.invalidate()
    deactivate BG
```

---

## Rules

- Review always ends with planning — they are one laminar flow, not two commands.
- Mid-period triggers are detected automatically; change context threads through all phases.
- Retrospective depth scales with horizon — daily can be 2 exchanges; quarterly can be long.
- Journal entries written after each dimension — partial progress is preserved if interrupted.
- Each journal dimension can be skipped — recorded as skipped, not blank.
- Socratic session (Phase 3) runs only at L4 quarterly. It can be skipped; values.yaml is unchanged.
- `values.yaml` written only after explicit user approval of the proposed diff.
- Cascade check always runs at Phase 4 — parent-layer goals vs current task list, gaps flagged.
- Season weights set only at L4, after goals are finalised, before the boardroom opens.
- Values loaded as a persistent lens at every boardroom exchange, every horizon.
- Constraints (time · scope · budget) measured in aggregate across all items in the period.
- The boardroom in Phase 4 is **adaptive**: it reshapes existing tasks based on retrospective
  insights, not just generative. Boardroom notes from triage are available as context.
- Nothing written to storage until user says 'next' or 'approve'.
