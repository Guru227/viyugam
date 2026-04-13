# Test Quality Strategy

## Metrics Overview

Viyugam uses four complementary metrics to measure test effectiveness:

| Metric | What it measures | Tool | Badge |
|--------|-----------------|------|-------|
| **Line Coverage** | What code ran during tests | pytest-cov | `coverage.svg` |
| **Assertion Density** | How many behaviors each test verifies | scripts/test_quality.py | `test_quality.svg` |
| **UAT Coverage** | End-to-end scenario count | scripts/test_quality.py | `uat.svg` |
| **Mutation Score** | Whether tests catch real bugs | mutmut | `mutation.svg` |

### Why four metrics?

**Line coverage** (e.g., 80%) tells you *what code executed*, but a test that runs code
without asserting anything inflates coverage without verifying behavior.

**Assertion density** (assertions per test) catches this: a test with 0 assertions is
dead weight. Target: >= 2.0 assertions/test.

**UAT tests** verify that layers work together (storage + connector + engine + tools).
Unit tests can pass individually while integration breaks.

**Mutation score** is the gold standard. It injects small code changes (e.g., `>` to `>=`,
`True` to `False`) and checks if tests catch them. A mutant that *survives* means tests
have a blind spot. Target: >= 70%.

## Test Categories

### Unit Tests (`tests/test_storage*.py`, `tests/test_engine*.py`, `tests/test_connector*.py`)

Test individual functions in isolation. Each storage submodule, engine component,
and connector method has dedicated unit tests.

**Coverage targets by module:**
- storage/ submodules: >= 85%
- engine/: >= 90%
- connectors/: >= 95%

### UAT Tests (`tests/test_uat.py`)

Integration tests that verify end-to-end flows:

| Scenario | What it tests |
|----------|--------------|
| Capture -> Plan cycle | Triage capture, processing, retrieval |
| Task lifecycle | Create -> query -> mark done -> verify status |
| Goal -> Task alignment | Task completion cascades to goal progress |
| Finance round-trip | Budget -> transaction -> spent update -> cashflow |
| Tool pipeline | Registry -> executor -> connector -> storage round-trip |
| Engine state | build_context() loads from all storage domains |
| Session persistence | Save/load chat history |
| Journal -> Summary | Embedded JSON extraction from markdown |
| Multi-domain coherence | Cross-dimension scoring with season alignment |

### Existing Tests (pre-restructuring)

313 tests covering models, storage CRUD, finance calculations, GPS priority engine,
coherence scoring, PII redaction, and data migrations.

## Running

```bash
# All tests
make coverage

# Test quality metrics (assertion density, UAT count)
make test-quality

# Mutation testing (slow — runs tests N times)
make mutation

# Everything + badges
make quality
```

## Badge Thresholds

| Badge | Green | Yellow | Red |
|-------|-------|--------|-----|
| Coverage | >= 60% | >= 40% | < 40% |
| UAT | >= 15 tests | >= 5 tests | < 5 tests |
| Test Quality | >= 2.0 asserts/test | >= 1.0 | < 1.0 |
| Mutation Score | >= 70% | >= 50% | < 50% |
