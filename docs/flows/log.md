# Log Flow

## Purpose

Two functions in one mode:
1. **Capture** — frictionless entry of any raw thought into the triage inbox, <100ms, no AI.
2. **Complete** — mark any entity done using its ID (`done T-001`).

## High-Level

```mermaid
flowchart LR
    A([User]) -->|press L\nor 'log: ...'| B[Log mode\ninput hint: 'log »']
    B -->|type entry| C[any raw text\nideas · tasks · feelings · captures]
    C -->|Enter| D[timestamp prepended\nno AI call]
    D --> E[(triage.json\nappend)]
    E --> F[chat: captured]
    F --> B
    B -->|done T-001| G[mark entity complete\ntriage or tasks/goals/projects]
    G --> H[chat: T-001 done]
    H --> B
    B -->|Esc| I[Normal mode]
```

## Low-Level (swimlane)

```mermaid
sequenceDiagram
    participant U  as User
    participant ML as Main Loop
    participant FS as Storage

    U->>ML: press L (or 'log: ...')
    ML->>ML: state.mode = "log"
    note over ML: input bar: 'log »'

    loop capture or complete
        U->>ML: text + Enter

        alt 'done T-NNN' (or G-NNN / P-NNN / N-NNN)
            ML->>FS: set entity status = done, ts: utc_now()
            ML->>ML: chat ← 'T-NNN done'
        else raw capture
            ML->>FS: append {text, ts: utc_now(), raw: true, processed: false}
            ML->>ML: chat ← 'captured'
        end

        ML->>ML: app.invalidate()
    end

    U->>ML: Esc
    ML->>ML: state.mode = "normal"
```

## Rules

- No AI roundtrip — must complete in <100ms for both capture and completion.
- Raw text preserved exactly as typed.
- `processed: false` flag marks captured items for triage during the next plan or review.
- `done` works on any entity type: T-NNN, G-NNN, P-NNN, N-NNN.
- Multiple entries per session; Esc exits to normal mode.
- Timestamp is UTC ISO-8601.
