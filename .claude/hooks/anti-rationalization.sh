#!/usr/bin/env bash
# Forge hook: anti-rationalization
# Detects when agent might be skipping tests or quality checks

set -euo pipefail

TOOL_INPUT="${TOOL_INPUT:-}"

# Flag common rationalization patterns
if echo "$TOOL_INPUT" | grep -qiE 'skip.*(test|lint|check)|--no-verify|--no-check'; then
  echo "BLOCK: Detected attempt to skip quality checks. Fix the underlying issue instead."
  exit 1
fi

exit 0
