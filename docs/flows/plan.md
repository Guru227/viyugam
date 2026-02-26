# Plan Flow — Rapid Replan

## Purpose

Fast path for replanning without a full review cycle. Use when context has shifted urgently
(project cancelled, priorities changed, returning from absence) and you need to replan now.

The boardroom posture is **directive**: Claude opens with a concrete proposal based on current
state. The user can challenge it, but the default is fast convergence, not open exploration.
That is what `review` is for.

`review` is the canonical cycle — it always ends with planning. Use `plan` only when
the reflection phases can genuinely be skipped.

Invocation: `plan` (daily L1) · `plan week` (L2) · `plan month` (L3) · `plan quarter` (L4)

---

## High-Level

```mermaid
flowchart TB
    START([User: 'plan']) --> SCOPE{Scope}
    SCOPE -->|daily default| DEDUP
    SCOPE -->|plan week| DEDUP
    SCOPE -->|plan month| DEDUP
    SCOPE -->|plan quarter| DEDUP

    DEDUP[Dedup: check triage against\ncurrent tasks — confirm merges]
    DEDUP --> P1

    subgraph P1 [Phase 1 — Triage]
        T1{Unprocessed items\nor expired snoozes?}
        T1 -->|yes| T2[Load item\ncheck for snoozed similar]
        T2 --> TSNZ{Snoozed\nsimilar exists?}
        TSNZ -->|yes| TSNZA[Ask: resurface\nsnoozed item now?]
        TSNZA --> T3
        TSNZ -->|no| T3
        T3[Claude: classify + initial draft\ncategory · title · due · priority]
        T3 --> T4{User — must resolve}
        T4 -->|discuss| T5[Boardroom: time · scope · budget\ndraft + boardroom notes updated each turn]
        T5 --> T4
        T4 -->|accept| T6[Create entity\nsave boardroom notes with it]
        T4 -->|snooze| T9[Default: next weekly review\nor user sets date]
        T4 -->|split| T10[Create N items\nreturn to triage queue]
        T4 -->|delete| T8[Remove]
        T6 & T8 & T9 & T10 --> T1
        T1 -->|none left| NEXT
    end

    NEXT[ ] --> P2

    subgraph P2 [Phase 2 — Directive Boardroom]
        P2A[Load: tasks · goals · calendar · energy\nbudget · values · parent-layer plan]
        P2A --> P2CK[Cascade check:\nparent layer goals vs current plan\ndo they still align?]
        P2CK --> P2B[Claude: directive proposal\nbased on current state + constraints]
        P2B --> P2C{User}
        P2C -->|challenge / adjust| P2D[Boardroom refinement\naggregate: time · scope · budget]
        P2D --> P2C
        P2C -->|approve| P2E[Write plan]
    end

    P2E --> DONE([Done])
```

---

## Phase 1 — Triage (swimlane)

```mermaid
sequenceDiagram
    participant U  as User
    participant ML as Main Loop
    participant BG as Background Thread
    participant CA as Claude API (Chairman)
    participant FS as Storage

    U->>ML: 'plan [scope]' + Enter
    ML->>BG: spawn plan session
    activate BG
    BG->>BG: _capture_rich() active
    BG->>FS: load triage (processed:false, snooze_until <= today or unset)
    BG->>FS: load current tasks (for dedup check)
    BG->>CA: find near-duplicates across triage + current tasks
    CA-->>BG: duplicate pairs + rationale

    loop for each duplicate pair
        BG->>ML: display pair card with rationale
        ML->>ML: app.invalidate()
        U->>ML: merge / keep both / delete one
        ML->>BG: decision
        BG->>FS: apply decision (explicit, never silent)
    end

    BG->>ML: 'Triage: N items'

    loop for each unprocessed item
        BG->>FS: search snoozed items for semantic similarity
        alt similar snoozed item found
            BG->>ML: 'Similar item snoozed on DATE — resurface now?'
            ML->>ML: app.invalidate()
            U->>ML: yes / no
            alt yes
                BG->>FS: clear snooze_until
            end
        end

        BG->>CA: classify item\n(category, title, rationale, due, priority, energy_est, initial draft)
        CA-->>BG: classification + initial draft
        BG->>ML: display card\n──────────────────────────\n[task / goal / project / note]\nTitle · Due · Priority\nDraft: ...\n──────────────────────────\n(D)iscuss (A)ccept (S)nooze (/)Split (X)Delete
        ML->>ML: app.invalidate()
        U->>ML: D / A / S / / / X

        alt D — discuss
            loop boardroom (values + time · scope · budget)
                ML->>BG: user message
                BG->>CA: continue — anchor to values + constraints
                CA-->>BG: response
                BG->>CA: synthesize updated draft
                CA-->>BG: updated draft
                BG->>ML: display response + live draft card
                ML->>ML: app.invalidate()
            end
            note over U,ML: must resolve with A / S / / / X after discuss
        else A — accept
            BG->>FS: create entity (T/G/P/N) with boardroom_notes attached
            BG->>FS: triage item: processed = true
        else S — snooze
            BG->>ML: 'Snooze until? [next weekly review]'
            U->>ML: Enter (default) or YYYY-MM-DD
            BG->>FS: triage item: snooze_until = date
        else / — split
            BG->>ML: 'Split into how many items? Describe each:'
            U->>ML: N items with descriptions
            BG->>FS: create N new triage items (processed:false)
            BG->>FS: original item: processed = true
            BG->>ML: 'N items added to triage queue'
        else X — delete
            BG->>FS: remove triage item
        end
    end

    BG->>ML: 'Triage complete — moving to planning'
```

---

## Phase 2 — Directive Boardroom (swimlane)

```mermaid
sequenceDiagram
    participant U  as User
    participant ML as Main Loop
    participant BG as Background Thread
    participant CA as Claude API (Boardroom)
    participant FS as Storage

    note over BG: continues from triage — same thread, still active
    activate BG

    BG->>FS: load tasks (todo + backlog) with due dates + priorities
    BG->>FS: load active goals + projects
    BG->>FS: load calendar.ics (period events + available time)
    BG->>FS: load energy score (derived from last journal — Claude-inferred, user-confirmed)
    BG->>FS: load budget.yaml (period envelopes)
    BG->>FS: load values.yaml
    BG->>FS: load parent-layer plan (weekly plan if daily, monthly if weekly, etc.)

    BG->>BG: cascade check\ncompare parent-layer goals to current task list
    BG->>ML: 'Cascade check: [parent goal] — current tasks align / gap detected'
    ML->>ML: app.invalidate()

    BG->>BG: init constraint tracker\ntime: 0/total · budget: 0/envelope · scope: 0 items
    BG->>CA: directive prompt:\ncurrent state + cascade alignment + constraints\n(values as lens throughout)
    CA-->>BG: concrete proposal\ntime blocks · priorities anchored to values\nconstraint summary: time X/Y · budget $X/$Y · scope N
    BG->>ML: display proposal with constraint bar
    ML->>ML: app.invalidate()

    loop boardroom refinement (as short or long as needed)
        U->>ML: challenge / adjust / question
        ML->>BG: forward
        BG->>CA: refine — recompute aggregate constraints\ncheck values alignment
        CA-->>BG: updated proposal + constraint delta + values note if relevant
        BG->>ML: display
        ML->>ML: app.invalidate()
    end

    U->>ML: 'approve'
    BG->>FS: write plan file (daily/weekly/monthly/quarterly .json)
    BG->>ML: 'Plan confirmed'
    BG->>ML: app.invalidate()
    deactivate BG
```

---

## Boardroom Depth by Horizon

| Scope | Review before plan | Boardroom posture | Typical length |
|-------|-------------------|-------------------|----------------|
| daily | none (rapid) | directive — Claude leads with concrete proposal | 1–3 exchanges |
| week | none (rapid) | directive with challenge space | 3–7 exchanges |
| month | recommend full `review month` instead | open if time allows | 5–15 exchanges |
| quarter | strongly recommend full `review quarter` | full boardroom | 15+ exchanges |

---

## Rules

- Every triage item must be resolved: (A)ccept · (S)nooze · (/)Split · (X)Delete. No limbo.
- Discuss is a tool to arrive at a resolution — user must still choose A/S///X after.
- Boardroom notes are saved with the entity on Accept — the reasoning trail is preserved.
- Split items return to the triage queue for the current session.
- Snooze default is next weekly review; user can override with a specific date.
- Snoozed items are hidden from triage until `snooze_until` is reached.
- Dedup checks triage against current tasks only — not goals or projects.
- Constraints (time · scope · budget) are measured in aggregate across all items in the period.
- Values are loaded and used as a lens at every boardroom exchange.
- Parent-layer plan is loaded for cascade alignment check before the boardroom opens.
- Plan written only after explicit 'approve' — nothing written silently.
