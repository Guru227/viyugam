#!/usr/bin/env bash
# Forge hook: docs nudge
# Reminds to update docs when key files change

set -euo pipefail

FILE_PATH="${TOOL_INPUT:-}"

# Nudge when changing models or public API
if echo "$FILE_PATH" | grep -qE '(models\.py|main\.py|__init__\.py|priority\.py)'; then
  echo "Reminder: This file is part of the public API. Consider updating docs/ if behavior changed."
fi

# Nudge when changing agents
if echo "$FILE_PATH" | grep -qE 'agents/'; then
  echo "Reminder: Agent changed. Update docs/flows/ if the agent's behavior or interface changed."
fi

exit 0
