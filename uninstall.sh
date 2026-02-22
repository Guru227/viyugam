#!/usr/bin/env bash
set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

echo ""
echo -e "${BOLD}Viyugam — Uninstall${RESET}"
echo "─────────────────────────────────────"

# ── Remove the tool ────────────────────────────────────────────────────────────
if command -v viyugam &> /dev/null; then
    uv tool uninstall viyugam
    echo -e "${GREEN}viyugam uninstalled.${RESET}"
else
    echo -e "${YELLOW}viyugam is not installed as a uv tool.${RESET}"
fi

# ── Optionally remove data ─────────────────────────────────────────────────────
if [ -d "$HOME/.viyugam" ]; then
    echo ""
    echo -e "${YELLOW}Data directory found at ~/.viyugam/${RESET}"
    echo "This contains all your tasks, journals, goals, and config."
    echo ""
    read -p "Remove all data? This cannot be undone. [y/N] " confirm
    if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
        # Offer a backup first
        read -p "Create a backup at ~/viyugam_backup_$(date +%Y%m%d).tar.gz first? [Y/n] " backup
        if [[ "$backup" != "n" && "$backup" != "N" ]]; then
            BACKUP_FILE="$HOME/viyugam_backup_$(date +%Y%m%d).tar.gz"
            tar -czf "$BACKUP_FILE" -C "$HOME" .viyugam
            echo -e "${GREEN}Backup saved to ${BACKUP_FILE}.${RESET}"
        fi
        rm -rf "$HOME/.viyugam"
        echo -e "${GREEN}Data removed.${RESET}"
    else
        echo "Data kept at ~/.viyugam/ — you can remove it manually later."
    fi
fi

echo ""
echo "Done. Hope to see you back."
echo ""
