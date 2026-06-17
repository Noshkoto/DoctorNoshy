#!/usr/bin/env bash
# Doctor Noshy — quick installer
set -euo pipefail

REPO="https://github.com/Noshkoto/DoctorNoshy.git"
INSTALL_DIR="${HOME}/doctor-noshy"

echo "🩺 Installing Doctor Noshy..."

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 is required"
    exit 1
fi

# Clone or update
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing install..."
    cd "$INSTALL_DIR" && git pull
else
    echo "Cloning to $INSTALL_DIR..."
    git clone "$REPO" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Install
pip3 install -e ".[dashboard]" --break-system-packages 2>/dev/null || \npip3 install -e ".[dashboard]"

# Install systemd service
mkdir -p "${HOME}/.config/systemd/user"
cp systemd/doctor-noshy.service "${HOME}/.config/systemd/user/"
systemctl --user daemon-reload

echo ""
echo "✅ Installed! Available commands:"
echo ""
echo "  doctor diagnose       Run all health checks"
echo "  doctor watch          Continuous monitoring"
echo "  doctor heal           Auto-heal critical issues"
echo "  doctor report         Generate report"
echo "  doctor dashboard      Start web dashboard"
echo ""
echo "To enable auto-start:"
echo "  systemctl --user enable --now doctor-noshy"
echo ""
echo "For alerts, create doctor-noshy.yaml or set env vars:"
echo "  DOCTOR_DISCORD_WEBHOOK=https://discord.com/api/webhooks/..."
