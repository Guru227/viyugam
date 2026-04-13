#!/usr/bin/env python3
"""Measure test suite quality: assertion density, branch coverage, UAT count.

Run from repo root::

    python3 scripts/test_quality.py

Produces ``reports/test_quality.json`` with metrics.
"""
import ast
import json
import sys
from pathlib import Path


def count_assertions(test_dir: Path) -> dict:
    """Count tests, assertions, and compute assertion density."""
    total_tests = 0
    total_asserts = 0
    total_test_lines = 0
    files: list[dict] = []

    for py in sorted(test_dir.glob("test_*.py")):
        try:
            tree = ast.parse(py.read_text())
        except SyntaxError:
            continue

        file_tests = 0
        file_asserts = 0
        file_test_lines = 0

        for node in ast.walk(tree):
            # Count test functions (def test_*) and test methods
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    file_tests += 1
                    file_test_lines += node.end_lineno - node.lineno + 1
                    # Count assert statements inside this function
                    for child in ast.walk(node):
                        if isinstance(child, ast.Assert):
                            file_asserts += 1

        total_tests += file_tests
        total_asserts += file_asserts
        total_test_lines += file_test_lines

        if file_tests > 0:
            files.append({
                "file": py.name,
                "tests": file_tests,
                "assertions": file_asserts,
                "density": round(file_asserts / file_tests, 1),
            })

    density = round(total_asserts / total_tests, 1) if total_tests else 0
    avg_test_size = round(total_test_lines / total_tests, 1) if total_tests else 0

    return {
        "total_tests": total_tests,
        "total_assertions": total_asserts,
        "assertion_density": density,
        "avg_test_lines": avg_test_size,
        "files": files,
    }


def count_uat_tests(test_dir: Path) -> dict:
    """Count UAT-specific tests (from test_uat.py)."""
    uat_file = test_dir / "test_uat.py"
    if not uat_file.exists():
        return {"uat_tests": 0, "uat_classes": 0}

    tree = ast.parse(uat_file.read_text())
    tests = 0
    classes = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.startswith("TestUAT"):
            classes += 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                tests += 1

    return {"uat_tests": tests, "uat_classes": classes}


def get_mutation_score() -> dict:
    """Read mutation testing results from reports/mutation.json."""
    try:
        with open(Path("reports") / "mutation.json") as f:
            data = json.load(f)
        return {
            "mutation_total": data.get("mutation_total", 0),
            "mutation_killed": data.get("mutation_killed", 0),
            "mutation_survived": data.get("mutation_survived", 0),
            "mutation_score": data.get("mutation_score", 0),
        }
    except (FileNotFoundError, json.JSONDecodeError):
        return {"mutation_score": None, "mutation_note": "Run 'make mutation' first"}


def main():
    test_dir = Path("tests")
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    assertions = count_assertions(test_dir)
    uat = count_uat_tests(test_dir)
    mutation = get_mutation_score()

    report = {
        **assertions,
        **uat,
        **mutation,
    }

    (reports_dir / "test_quality.json").write_text(
        json.dumps(report, indent=2)
    )

    print(f"  Tests:            {assertions['total_tests']}")
    print(f"  Assertions:       {assertions['total_assertions']}")
    print(f"  Assertion density: {assertions['assertion_density']} per test")
    print(f"  Avg test size:    {assertions['avg_test_lines']} lines")
    print(f"  UAT tests:        {uat['uat_tests']} across {uat['uat_classes']} scenarios")
    if mutation.get("mutation_score") is not None:
        print(f"  Mutation score:   {mutation['mutation_score']}% ({mutation['mutation_killed']}/{mutation['mutation_total']} killed)")
    else:
        print(f"  Mutation score:   (run 'make mutation' first)")
    print(f"\n  Report: {reports_dir / 'test_quality.json'}")


if __name__ == "__main__":
    main()
