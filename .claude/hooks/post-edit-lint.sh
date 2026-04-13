#!/usr/bin/env bash
# Forge hook: post-edit lint nudge
# Reminds to run quality checks after file edits

set -euo pipefail

FILE_PATH="${TOOL_INPUT:-}"

# Only nudge for Python files
if echo "$FILE_PATH" | grep -qE '\.py$'; then
  echo "Reminder: Run 'make quality' or 'uv run pytest' after edits to verify nothing broke."
fi

exit 0
