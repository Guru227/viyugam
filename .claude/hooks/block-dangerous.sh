#!/usr/bin/env bash
# Forge hook: block dangerous commands
# Prevents destructive operations without explicit approval

set -euo pipefail

TOOL_INPUT="${TOOL_INPUT:-}"

# Block rm -rf on broad paths
if echo "$TOOL_INPUT" | grep -qE 'rm\s+-rf\s+(/|~|\.\.)'; then
  echo "BLOCK: Destructive rm -rf on broad path. This needs explicit user approval."
  exit 1
fi

# Block git reset --hard
if echo "$TOOL_INPUT" | grep -qE 'git\s+reset\s+--hard'; then
  echo "BLOCK: git reset --hard discards work. Use a safer alternative or get explicit approval."
  exit 1
fi

# Block git clean -f
if echo "$TOOL_INPUT" | grep -qE 'git\s+clean\s+-f'; then
  echo "BLOCK: git clean -f deletes untracked files. Get explicit approval first."
  exit 1
fi

exit 0
