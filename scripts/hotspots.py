#!/usr/bin/env python3
"""Parse radon raw metrics and print the top 10 largest files by SLOC."""
import re
import sys
from pathlib import Path

REPORTS_PATH = Path("reports/raw-metrics.txt")

if not REPORTS_PATH.exists():
    print("reports/raw-metrics.txt not found. Run 'make complexity' first.")
    sys.exit(1)

content = REPORTS_PATH.read_text()

# Each file block looks like:
#   path/to/file.py
#       LOC: 123
#       LLOC: 100
#       SLOC: 80
#       ...
file_blocks = re.split(r"\n(?=\S)", content.strip())

results = []
for block in file_blocks:
    lines = block.strip().splitlines()
    if not lines:
        continue
    path = lines[0].strip()
    if not path.endswith(".py"):
        continue
    sloc_match = re.search(r"SLOC:\s*(\d+)", block)
    loc_match = re.search(r"^\s+LOC:\s*(\d+)", block, re.MULTILINE)
    if sloc_match:
        results.append((int(sloc_match.group(1)), path))
    elif loc_match:
        results.append((int(loc_match.group(1)), path))

results.sort(reverse=True)
for sloc, path in results[:10]:
    print(f"  {sloc:>6} SLOC  {path}")
