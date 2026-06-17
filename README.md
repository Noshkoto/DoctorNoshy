# Doctor Noshy

**Health monitor and auto-healer for Hermes Agent.**

Doctor Noshy watches your Hermes install and tells you when something breaks. It checks the gateway, providers, system resources, and Hermes-specific components. When things go critical, it can restart services automatically and send alerts.

## Quick Start

```bash
# Install
pip install doctor-noshy

# Or install from source
git clone https://github.com/Noshkoto/DoctorNoshy.git
cd DoctorNoshy
pip install -e ".[dashboard]"
```

## Commands

```bash
# Run all health checks once
doctor diagnose

# Continuous monitoring (checks every 60s)
doctor watch

# Auto-heal critical issues
doctor heal

# Generate a report
doctor report
doctor report --json

# Start web dashboard (port 9200)
doctor dashboard

# Test alert channels
doctor alerts
```

## What It Checks

| Check | What it does |
|-------|-------------|
| Config File | Hermes config.yaml exists |
| Auth Store | Provider credentials configured |
| Gateway Process | Gateway process is running |
| Gateway Port | Listening on :18789 |
| Gateway HTTP | Responds to HTTP requests |
| Gateway Service | Systemd service active |
| Dashboard Service | Dashboard service active |
| Dashboard Port | Dashboard listening on :9119 |
| Tunnel | Cloudflared or ngrok active |
| Local API Server | Hermes API on :8642 |
| Nous Portal | Nous Portal API reachable |
| OpenRouter | OpenRouter API reachable |
| CPU Usage | System CPU load |
| Memory | RAM usage |
| Disk Space | Free disk space |
| Skills | Installed skill count |
| Memory Files | MEMORY.md / USER.md sizes |
| Cron Jobs | Scheduled job counts |

## Alerts

Configure alerts via environment variables or `doctor-noshy.yaml`:

```bash
# Discord
export DOCTOR_DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."

# Telegram
export DOCTOR_TELEGRAM_TOKEN="your-bot-token"
export DOCTOR_TELEGRAM_CHAT="chat-id"

# Email (SMTP)
export DOCTOR_SMTP_HOST="smtp.gmail.com"
export DOCTOR_SMTP_PORT="587"
export DOCTOR_SMTP_USER="you@gmail.com"
export DOCTOR_SMTP_PASS="app-password"
export DOCTOR_ALERT_TO="you@gmail.com"
```

Or create `doctor-noshy.yaml`:

```yaml
discord_webhook: https://discord.com/api/webhooks/...
telegram_bot_token: your-bot-token
telegram_chat_id: chat-id
```

## Web Dashboard

```bash
# Requires Flask
pip install doctor-noshy[dashboard]

doctor dashboard
# → http://127.0.0.1:9200/
```

Dark-themed dashboard with auto-refresh every 30 seconds. Shows all check results with color-coded status.

## Systemd Service

```bash
# Install the service
cp systemd/doctor-noshy.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now doctor-noshy

# Check status
systemctl --user status doctor-noshy
journalctl --user -u doctor-noshy -f
```

## Auto-Healer

The `doctor heal` command attempts to fix critical issues automatically:

- **Gateway not running** → restarts `openclaw-gateway` or `hermes-gateway` service
- **Gateway port unresponsive** → restarts the gateway service
- **Config missing** → tells you to run `hermes setup`

It asks for confirmation before acting (use `-y` to skip).

## Architecture

```
doctor diagnose
    │
    ├── checks.py       (18 health checks)
    ├── healer.py        (auto-heal logic)
    ├── alerts.py        (Discord/Telegram/Email)
    ├── dashboard.py     (Flask web UI)
    └── cli.py           (argparse interface)
```

## License

MIT
