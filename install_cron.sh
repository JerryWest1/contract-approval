#!/usr/bin/env bash
# Installs the daily email agent cron job (runs at 07:00 every morning).
# Run once after completing setup:  chmod +x install_cron.sh && ./install_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(command -v python3)"
AGENT_SCRIPT="$SCRIPT_DIR/email_agent.py"
LOG_FILE="$SCRIPT_DIR/email_agent.log"
CRON_ENTRY="0 7 * * * $PYTHON_BIN $AGENT_SCRIPT >> $LOG_FILE 2>&1"

if ! crontab -l 2>/dev/null | grep -q "email_agent.py"; then
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    echo "Cron job installed successfully."
else
    echo "Cron job is already installed."
fi

echo ""
echo "  Schedule : every day at 07:00"
echo "  Script   : $AGENT_SCRIPT"
echo "  Log      : $LOG_FILE"
echo ""
echo "Current crontab entry:"
crontab -l | grep "email_agent.py"
