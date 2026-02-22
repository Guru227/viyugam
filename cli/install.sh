#!/usr/bin/env bash
set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

echo ""
echo -e "${BOLD}Viyugam — Personal Life OS${RESET}"
echo "─────────────────────────────────────"

# ── Check uv ──────────────────────────────────────────────────────────────────
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}uv not found. Installing...${RESET}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add to current session
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}uv install failed. Please install manually: https://docs.astral.sh/uv/${RESET}"
        exit 1
    fi
    echo -e "${GREEN}uv installed.${RESET}"
fi

# ── Check ANTHROPIC_API_KEY ────────────────────────────────────────────────────
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo ""
    echo -e "${YELLOW}ANTHROPIC_API_KEY is not set.${RESET}"
    echo "You can:"
    echo "  1. Add it to your shell profile (~/.bashrc or ~/.zshrc):"
    echo "       export ANTHROPIC_API_KEY=\"your-key-here\""
    echo "  2. Or add it to ~/.viyugam/config.yaml after setup:"
    echo "       api_key: \"your-key-here\""
    echo ""
    read -p "Enter your Anthropic API key now (or press Enter to skip): " api_key
    if [ -n "$api_key" ]; then
        # Add to shell profile
        SHELL_PROFILE=""
        if [ -f "$HOME/.zshrc" ]; then
            SHELL_PROFILE="$HOME/.zshrc"
        elif [ -f "$HOME/.bashrc" ]; then
            SHELL_PROFILE="$HOME/.bashrc"
        fi
        if [ -n "$SHELL_PROFILE" ]; then
            echo "" >> "$SHELL_PROFILE"
            echo "# Viyugam" >> "$SHELL_PROFILE"
            echo "export ANTHROPIC_API_KEY=\"$api_key\"" >> "$SHELL_PROFILE"
            export ANTHROPIC_API_KEY="$api_key"
            echo -e "${GREEN}API key saved to ${SHELL_PROFILE}.${RESET}"
        else
            export ANTHROPIC_API_KEY="$api_key"
            echo -e "${YELLOW}No shell profile found. Key set for this session only.${RESET}"
            echo "Add manually: export ANTHROPIC_API_KEY=\"$api_key\""
        fi
    fi
fi

# ── Install viyugam ────────────────────────────────────────────────────────────
echo ""
echo "Installing viyugam..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
uv tool install "$SCRIPT_DIR" --no-cache --force

# ── Update PATH ────────────────────────────────────────────────────────────────
uv tool update-shell 2>/dev/null || true
# Also try common tool bin locations for this session
for bin_path in "$HOME/.local/bin" "$HOME/.cargo/bin" "$(uv tool dir 2>/dev/null)/../bin"; do
    if [ -f "$bin_path/viyugam" ]; then
        export PATH="$bin_path:$PATH"
        break
    fi
done

# ── Verify install ─────────────────────────────────────────────────────────────
if ! command -v viyugam &> /dev/null; then
    echo ""
    echo -e "${YELLOW}viyugam installed. Restart your terminal to use it.${RESET}"
    echo "Or run now with: uv tool run viyugam"
else
    echo -e "${GREEN}viyugam installed successfully.${RESET}"
fi

# ── First-time setup ───────────────────────────────────────────────────────────
if [ ! -f "$HOME/.viyugam/config.yaml" ]; then
    echo ""
    echo "Running first-time setup..."
    echo ""
    viyugam setup
else
    echo ""
    echo -e "${GREEN}All done.${RESET}"
    echo ""
    echo "Commands:"
    echo "  viyugam capture \"thought\"  — add to inbox"
    echo "  viyugam plan               — build today's schedule"
    echo "  viyugam done <id>          — mark task complete"
    echo "  viyugam status             — quick overview"
    echo "  viyugam log                — evening journal  (Session 2)"
    echo "  viyugam think \"proposal\"   — decision gateway (Session 2)"
    echo "  viyugam review             — weekly review    (Session 3)"
    echo ""
fi
