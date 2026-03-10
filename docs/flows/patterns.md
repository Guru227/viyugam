# Pattern Learning

Patterns are recurring observations extracted from journal and review sessions. When a pattern is observed 3+ times, it "precipitates" and becomes part of the agent context.

## Lifecycle

```
Journal session → patterns_noted → merge_pattern(source="journal")
Review session → key_insights   → merge_pattern(source="review")
                                         ↓
                              ~/.viyugam/data/patterns.json
                                         ↓
                              occurrences >= 3 → precipitated = True
                                         ↓
                              Appended to agent system prompts
                              Shown in GPS panel PATTERNS section
```

## Merging Algorithm

`merge_pattern(text, source, tags)`:

1. Compute word-level overlap between `text` and each existing pattern
2. If overlap >= 70% with an existing pattern: increment `occurrences`, update `last_seen`
3. If no match: create new PatternInsight with `occurrences=1`
4. Set `precipitated=True` when `occurrences >= 3`

This uses simple word-set intersection — no AI calls, no embeddings.

## Data Model

```python
class PatternInsight(BaseModel):
    id: str
    pattern: str            # the observation text
    occurrences: int        # how many times seen
    source: str             # journal | review | coach | system
    precipitated: bool      # True when occurrences >= 3
    first_seen: str         # ISO datetime
    last_seen: str          # ISO datetime
    tags: list[str]
```

## Where patterns appear

1. **GPS panel** — PATTERNS section shows precipitated patterns
2. **Coach system prompt** — precipitated patterns appended so coach can reference them
3. **Review briefing** — included in the review data context

## Storage API

```python
get_patterns(precipitated_only=False) -> list[PatternInsight]
save_pattern(pattern: PatternInsight) -> None
merge_pattern(text, source, tags) -> PatternInsight  # find-or-create with dedup
```
