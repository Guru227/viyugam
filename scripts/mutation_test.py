#!/usr/bin/env python3
"""Lightweight in-place mutation testing for uv-managed projects.

Applies small mutations to source files, runs the test suite, and records
which mutations are caught (killed) vs missed (survived).

Usage::

    python3 scripts/mutation_test.py [--max-mutants N]

Produces ``reports/mutation.json`` with results.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Mutation operators: (pattern, replacement, description)
# The > and < patterns use negative lookbehinds to avoid matching >>, <<, >=, <=, !=, ->
OPERATORS = [
    (r"==", "!=", "eq_to_neq"),
    (r"!=", "==", "neq_to_eq"),
    (r">=", ">", "gte_to_gt"),
    (r"<=", "<", "lte_to_lt"),
    (r"(?<![>!<])>(?![>=])", ">=", "gt_to_gte"),
    (r"(?<![<\-])(?<!>)<(?![<=])", "<=", "lt_to_lte"),
    (r"\bTrue\b", "False", "true_to_false"),
    (r"\bFalse\b", "True", "false_to_true"),
    (r"\breturn \[\]", "return [None]", "empty_list_to_nonempty"),
    (r"\breturn 0\b", "return 1", "zero_to_one"),
    (r"\breturn None\b", "return 0", "none_to_zero"),
    (r"\+ 1\b", "+ 2", "plus_one_to_two"),
    (r"- 1\b", "- 2", "minus_one_to_two"),
]

# Pre-build lookup dict for apply_mutation
_OPERATORS_BY_NAME: dict[str, tuple[str, str]] = {
    name: (pat, repl) for pat, repl, name in OPERATORS
}

# Files to mutate (high-value, well-tested code)
TARGET_FILES = [
    "viyugam/storage/tasks.py",
    "viyugam/storage/goals.py",
    "viyugam/storage/finance.py",
    "viyugam/storage/core.py",
    "viyugam/storage/notes.py",
    "viyugam/engine/tools/registry.py",
    "viyugam/storage/_paths.py",
]

# Tests to run (fast subset covering the mutated files)
TEST_CMD = [
    sys.executable, "-m", "pytest",
    "tests/test_storage.py",
    "tests/test_storage_gps.py",
    "tests/test_storage_extended.py",
    "tests/test_storage_package.py",
    "tests/test_uat.py",
    "tests/test_engine_registry.py",
    "tests/test_connector_local.py",
    "tests/test_finance.py",
    "tests/test_finance_v2.py",
    "tests/test_coherence.py",
    "tests/test_mutation_killers.py",
    "-x", "-q", "--tb=no",
]


def find_mutations(filepath: Path) -> list[dict]:
    """Find all applicable mutations in a file."""
    lines = filepath.read_text().splitlines()
    mutations = []
    for line_no, line in enumerate(lines, 1):
        # Skip comments, docstrings, imports
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith(("import ", "from ")):
            continue
        if stripped.startswith(('"""', "'''")):
            continue

        for pattern, replacement, name in OPERATORS:
            matches = list(re.finditer(pattern, line))
            for match in matches:
                # Don't mutate inside strings (check quote parity before match)
                col = match.start()
                before = line[:col]
                if before.count('"') % 2 == 1 or before.count("'") % 2 == 1:
                    continue

                mutated_line = line[:col] + re.sub(pattern, replacement, line[col:], count=1)
                if mutated_line != line:
                    mutations.append({
                        "file": str(filepath),
                        "line": line_no,
                        "operator": name,
                        "original": line.strip(),
                        "mutated": mutated_line.strip(),
                    })
    return mutations


def apply_mutation(filepath: Path, mutation: dict, lines: list[str]) -> str:
    """Apply a single mutation and return the mutated file content."""
    mutated_lines = lines.copy()
    line_idx = mutation["line"] - 1
    original_line = lines[line_idx]

    pattern, replacement = _OPERATORS_BY_NAME[mutation["operator"]]
    col = re.search(pattern, original_line)
    if col:
        mutated_lines[line_idx] = (
            original_line[:col.start()]
            + re.sub(pattern, replacement, original_line[col.start():], count=1)
        )
    return "\n".join(mutated_lines) + "\n"


def run_tests() -> bool:
    """Run the test suite. Returns True if tests pass (mutant survived)."""
    result = subprocess.run(
        TEST_CMD, capture_output=True, timeout=60,
    )
    return result.returncode == 0


def main():
    max_mutants = 100
    if "--max-mutants" in sys.argv:
        idx = sys.argv.index("--max-mutants")
        max_mutants = int(sys.argv[idx + 1])

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Baseline: verify tests pass before mutating
    print("Running baseline tests...")
    if not run_tests():
        print("ERROR: Baseline tests fail. Fix tests before running mutation testing.")
        sys.exit(1)
    print("  Baseline: PASS")

    # Collect all mutations
    all_mutations = []
    for target in TARGET_FILES:
        filepath = Path(target)
        if filepath.exists():
            mutations = find_mutations(filepath)
            all_mutations.extend(mutations)

    print(f"Found {len(all_mutations)} potential mutations across {len(TARGET_FILES)} files")

    if len(all_mutations) > max_mutants:
        import random
        random.seed(42)
        random.shuffle(all_mutations)
        all_mutations = all_mutations[:max_mutants]
        print(f"Sampling {max_mutants} mutations")

    killed = 0
    survived = 0
    errors = 0
    survived_details = []

    for i, mutation in enumerate(all_mutations, 1):
        filepath = Path(mutation["file"])
        original_content = filepath.read_text()
        original_lines = original_content.splitlines()

        try:
            mutated_content = apply_mutation(filepath, mutation, original_lines)
            filepath.write_text(mutated_content)

            tests_pass = run_tests()

            if tests_pass:
                survived += 1
                survived_details.append(mutation)
            else:
                killed += 1

        except subprocess.TimeoutExpired:
            killed += 1  # timeout = test hung on mutation = effectively caught
        except Exception:
            errors += 1
        finally:
            # Always restore original — critical for correctness
            try:
                filepath.write_text(original_content)
            except OSError:
                print(f"  WARNING: Failed to restore {filepath} — manual fix needed")

        if i % 10 == 0 or i == len(all_mutations):
            total_done = killed + survived + errors
            score = round(killed / total_done * 100, 1) if total_done else 0
            print(f"  [{i}/{len(all_mutations)}] killed={killed} survived={survived} errors={errors} score={score}%")

    total = killed + survived + errors
    score = round(killed / (killed + survived) * 100, 1) if (killed + survived) else 0

    result = {
        "mutation_total": total,
        "mutation_killed": killed,
        "mutation_survived": survived,
        "mutation_errors": errors,
        "mutation_score": score,
        "survived_mutations": survived_details[:20],
    }

    (reports_dir / "mutation.json").write_text(json.dumps(result, indent=2))

    print(f"\n{'='*50}")
    print(f"Mutation Score: {score}%")
    print(f"  Killed:   {killed}")
    print(f"  Survived: {survived}")
    print(f"  Errors:   {errors}")
    print(f"  Total:    {total}")
    if survived_details:
        print("\nSurvived mutations (test blind spots):")
        for m in survived_details[:10]:
            print(f"  {m['file']}:{m['line']} [{m['operator']}]")
            print(f"    - {m['original']}")
            print(f"    + {m['mutated']}")
    print(f"\nReport: reports/mutation.json")


if __name__ == "__main__":
    main()
