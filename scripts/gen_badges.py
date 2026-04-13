#!/usr/bin/env python3
"""Generate quality badge SVGs from static analysis reports.

Run from the repo root after ``make report``::

    python3 scripts/gen_badges.py
"""
import csv
import json
import re

import anybadge


def lint_badge() -> None:
    try:
        with open("reports/ruff.json") as f:
            issues = len(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        label, color = "N/A", "lightgrey"
    else:
        label = f"{issues} issues"
        color = "green" if issues == 0 else "yellow" if issues <= 20 else "red"
    badge = anybadge.Badge("lint", label, default_color=color)
    badge.write_badge("badges/lint.svg", overwrite=True)
    print(f"  lint: {label} ({color})")


def typecheck_badge() -> None:
    try:
        with open("reports/mypy.txt") as f:
            errors = sum(1 for line in f if ": error:" in line)
    except FileNotFoundError:
        label, color = "N/A", "lightgrey"
    else:
        label = f"{errors} errors"
        color = "green" if errors == 0 else "yellow" if errors <= 50 else "red"
    badge = anybadge.Badge("type check", label, default_color=color)
    badge.write_badge("badges/typecheck.svg", overwrite=True)
    print(f"  typecheck: {label} ({color})")


def security_badge() -> None:
    try:
        with open("reports/bandit.json") as f:
            data = json.load(f)
        issues = [
            r for r in data.get("results", [])
            if r["issue_severity"] in ("MEDIUM", "HIGH")
        ]
        count = len(issues)
    except (FileNotFoundError, json.JSONDecodeError):
        label, color = "N/A", "lightgrey"
    else:
        label = f"{count} issues"
        color = "green" if count == 0 else "yellow" if count <= 5 else "red"
    badge = anybadge.Badge("security", label, default_color=color)
    badge.write_badge("badges/security.svg", overwrite=True)
    print(f"  security: {label} ({color})")


def deps_badge() -> None:
    try:
        with open("reports/pip-audit.json") as f:
            data = json.load(f)
        packages = data.get("dependencies", data) if isinstance(data, dict) else data
        vulns = sum(
            len(pkg.get("vulns", []))
            for pkg in packages
            if isinstance(pkg, dict)
        )
    except (FileNotFoundError, json.JSONDecodeError):
        label, color = "N/A", "lightgrey"
    else:
        label = "vulnerable" if vulns else "clean"
        color = "red" if vulns else "green"
    badge = anybadge.Badge("dependencies", label, default_color=color)
    badge.write_badge("badges/deps.svg", overwrite=True)
    print(f"  deps: {label} ({color})")


def complexity_badge() -> None:
    try:
        with open("reports/complexity.json") as f:
            blocks = json.load(f)
        grades = [b["rank"] for file_blocks in blocks.values() for b in file_blocks]
        avg = sorted(grades)[len(grades) // 2] if grades else "A"
    except (FileNotFoundError, json.JSONDecodeError):
        avg = "N/A"
        color = "lightgrey"
    else:
        color = {
            "A": "green", "B": "green", "C": "yellow",
            "D": "orange", "E": "red", "F": "red",
        }.get(avg, "lightgrey")
    badge = anybadge.Badge("complexity", f"grade {avg}", default_color=color)
    badge.write_badge("badges/complexity.svg", overwrite=True)
    print(f"  complexity: grade {avg} ({color})")


def docs_badge() -> None:
    try:
        with open("reports/interrogate.txt") as f:
            content = f.read()
        match = re.search(r"actual: (\d+\.\d+)%", content)
        pct = float(match.group(1)) if match else 0.0
    except FileNotFoundError:
        label, color = "N/A", "lightgrey"
    else:
        label = f"{pct:.1f}%"
        color = "green" if pct >= 60 else "yellow" if pct >= 30 else "red"
    badge = anybadge.Badge("docs", label, default_color=color)
    badge.write_badge("badges/docs.svg", overwrite=True)
    print(f"  docs: {label} ({color})")


def deadcode_badge() -> None:
    try:
        with open("reports/vulture.txt") as f:
            lines = [line for line in f if line.strip() and "unused" in line.lower()]
        count = len(lines)
    except FileNotFoundError:
        label, color = "N/A", "lightgrey"
    else:
        label = f"{count} items"
        color = "green" if count == 0 else "yellow" if count <= 10 else "red"
    badge = anybadge.Badge("dead code", label, default_color=color)
    badge.write_badge("badges/deadcode.svg", overwrite=True)
    print(f"  deadcode: {label} ({color})")


def coverage_badge() -> None:
    try:
        with open("reports/coverage.json") as f:
            data = json.load(f)
        pct = data.get("totals", {}).get("percent_covered", 0.0)
    except (FileNotFoundError, json.JSONDecodeError):
        label, color = "N/A", "lightgrey"
    else:
        label = f"{pct:.1f}%"
        color = "green" if pct >= 60 else "yellow" if pct >= 40 else "red"
    badge = anybadge.Badge("coverage", label, default_color=color)
    badge.write_badge("badges/coverage.svg", overwrite=True)
    print(f"  coverage: {label} ({color})")


def funcmetrics_badge() -> None:
    try:
        with open("reports/lizard.csv") as f:
            rows = list(csv.reader(f))
        lengths = [
            int(row[4])
            for row in rows
            if len(row) > 4 and row[4].strip().isdigit()
        ]
        if not lengths:
            raise ValueError("empty")
        avg_loc = sum(lengths) / len(lengths)
    except Exception:
        label, color = "N/A", "lightgrey"
    else:
        label = f"avg {avg_loc:.0f} loc/fn"
        color = "green" if avg_loc <= 20 else "yellow" if avg_loc <= 40 else "red"
    badge = anybadge.Badge("func length", label, default_color=color)
    badge.write_badge("badges/funcmetrics.svg", overwrite=True)
    print(f"  func length: {label} ({color})")


def uat_badge() -> None:
    try:
        with open("reports/test_quality.json") as f:
            data = json.load(f)
        uat_tests = data.get("uat_tests", 0)
        uat_classes = data.get("uat_classes", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        label, color = "N/A", "lightgrey"
    else:
        label = f"{uat_tests} tests / {uat_classes} scenarios"
        color = "green" if uat_tests >= 15 else "yellow" if uat_tests >= 5 else "red"
    badge = anybadge.Badge("UAT", label, default_color=color)
    badge.write_badge("badges/uat.svg", overwrite=True)
    print(f"  UAT: {label} ({color})")


def test_quality_badge() -> None:
    try:
        with open("reports/test_quality.json") as f:
            data = json.load(f)
        density = data.get("assertion_density", 0)
        total = data.get("total_tests", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        label, color = "N/A", "lightgrey"
    else:
        label = f"{density} asserts/test ({total} tests)"
        color = "green" if density >= 2.0 else "yellow" if density >= 1.0 else "red"
    badge = anybadge.Badge("test quality", label, default_color=color)
    badge.write_badge("badges/test_quality.svg", overwrite=True)
    print(f"  test quality: {label} ({color})")


def mutation_badge() -> None:
    try:
        # Prefer dedicated mutation report, fall back to test_quality.json
        for path in ("reports/mutation.json", "reports/test_quality.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                if data.get("mutation_score") is not None:
                    break
            except FileNotFoundError:
                continue
        score = data.get("mutation_score")
        if score is None:
            raise ValueError("no data")
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        label, color = "N/A", "lightgrey"
    else:
        label = f"{score:.0f}%"
        color = "green" if score >= 70 else "yellow" if score >= 50 else "red"
    badge = anybadge.Badge("mutation score", label, default_color=color)
    badge.write_badge("badges/mutation.svg", overwrite=True)
    print(f"  mutation score: {label} ({color})")


if __name__ == "__main__":
    print("Generating badges...")
    lint_badge()
    typecheck_badge()
    security_badge()
    deps_badge()
    complexity_badge()
    docs_badge()
    deadcode_badge()
    coverage_badge()
    funcmetrics_badge()
    uat_badge()
    test_quality_badge()
    mutation_badge()
    print("Done. badges/ updated.")
