#!/usr/bin/env bash
# Forge hook: pre-push safety check
# Runs before any Bash tool call that looks like a git push

set -euo pipefail

TOOL_INPUT="${TOOL_INPUT:-}"

# Block force pushes
if echo "$TOOL_INPUT" | grep -qE 'push\s+.*--force|push\s+-f'; then
  echo "BLOCK: Force push detected. Use regular push or get explicit user approval."
  exit 1
fi

# Block pushes to main/master without confirmation
if echo "$TOOL_INPUT" | grep -qE 'push\s+(origin\s+)?(main|master)'; then
  echo "WARN: Pushing directly to main/master. Make sure this is intentional."
fi

exit 0
