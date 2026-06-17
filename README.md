# Doctor Noshy

**Health monitor and auto-healer for Hermes Agent.**

Hermes is powerful but it runs a lot of moving parts: gateway process, systemd services, provider connections, tunnels, dashboards, cron jobs, memory files, skills. When something breaks, you usually find out when a message doesn't get a reply. Doctor Noshy finds out first.

## Why You Need This

If you run Hermes as a daily driver, you have experienced at least one of these:

- The gateway crashed silently and you didn't notice for hours
- A provider went down and every request was failing with no visible error
- Disk filled up and memory writes started failing
- A cron job stopped running and you only found out when something didn't happen
- You restarted everything manually to fix something that should have been automatic

Doctor Noshy eliminates all of these. It runs 18 health checks, tells you what is wrong, and can fix common problems without you touching anything.

## What It Does

**Health Checks** -- 18 checks covering every layer of your Hermes install:

| Layer | Checks |
|-------|--------|
| Gateway | Process running, port listening, HTTP responding, systemd active |
| Dashboard | Service active, port listening |
| Network | Cloudflared/ngrok tunnel active |
| Providers | Nous Portal reachable, OpenRouter reachable, local API server |
| System | CPU usage, RAM usage, disk space |
| Hermes | Config exists, auth credentials, skills installed, memory file sizes, cron jobs |
| Kanban (NEW) | Dispatcher alive, zombie workers, stale-lock thrashing, blocked tasks, duplicate workers — see [Kanban Health](#kanban-health-new) |

**Auto-Healer** -- When something critical fails, Doctor Noshy restarts it:

- Gateway process dies -> restarts openclaw-gateway or hermes-gateway
- Gateway port unresponsive -> restarts the service
- Config missing -> tells you to run hermes setup

No more manually SSHing in to restart things.

**Alerts** -- Get notified when something goes wrong, before you even notice:

- Discord webhook (one line to configure)
- Telegram bot
- Email via SMTP

Configure with environment variables or a simple YAML file.

**Web Dashboard** -- Dark-themed status page at http://127.0.0.1:9200/:

- All 18 checks at a glance
- Color-coded status (green/yellow/red)
- Auto-refreshes every 30 seconds
- JSON API for custom integrations

**Continuous Monitoring** -- Run as a systemd service that watches everything:

- Checks every 2 minutes (configurable)
- Auto-heals on failure
- Sends alerts on degradation
- Logs to journalctl

## Quick Start

```bash
pip install doctor-noshy

# One-shot health check
doctor diagnose

# Start monitoring
doctor watch

# Auto-heal critical issues
doctor heal
```

Or install from source:

```bash
git clone https://github.com/Noshkoto/DoctorNoshy.git
cd DoctorNoshy
pip install -e ".[dashboard]"
```

## Commands

```bash
doctor diagnose              # Run all checks once
doctor diagnose --checks gateway,cpu  # Run specific checks
doctor watch -i 120          # Monitor every 2 minutes
doctor heal                  # Check + auto-fix
doctor heal -y               # Skip confirmation
doctor report                # Markdown report
doctor report --json         # JSON for scripting
doctor dashboard             # Web UI on :9200
doctor alerts                # Test notification channels
```

## Kanban Health (NEW)

Hermes' multi-agent Kanban board (v0.15+) lives at `~/.hermes/kanban.db`. The dispatcher catches *most* worker failures, but there are three documented failure modes it misses:

- **Zombie workers** — a SIGTERM'd worker can leave a `<defunct>` entry in the process table; Hermes' `os.kill(pid, 0)` heuristic returns truthy for zombies, so the claim is never released.
- **Stale-lock thrash loops** — long single tool calls can exceed the 15-minute claim TTL; the dispatcher reclaims and respawns, sometimes producing duplicate workers on the same `task_id` burning tokens.
- **Silent retry-cap exhaustion** — tasks that hit `kanban.failure_limit` go to `blocked` and can sit there indefinitely with nothing surfacing them outside the dashboard.

Doctor Noshy adds five checks for these (skipped cleanly if `kanban.db` isn't present):

| Check | What it does |
|-------|-------------|
| Kanban Dispatcher | Dispatcher daemon process is running |
| Kanban Zombie Workers | Detects in-progress tasks whose claimed PID is a zombie (`psutil.STATUS_ZOMBIE`, not just `os.kill(pid, 0)`) |
| Kanban Thrashing | Same `task_id` reclaimed N+ times in a rolling window (defaults: 3 reclaims / 30 min) |
| Kanban Blocked | Counts tasks in `blocked` state; warns above threshold (default 5) |
| Kanban Duplicate Workers | Multiple open `task_runs` for the same `task_id` |

### Kanban heal actions

`doctor heal` adds two new auto-heal flows for these criticals:

- **Reap zombie workers** — `SIGKILL`s the zombie PID and releases its claim in `kanban.db` (back to `pending`) so the dispatcher can re-pick it cleanly.
- **Release stale claims** — releases claims on thrashing tasks. Set `DOCTOR_KANBAN_AUTO_BLOCK_ON_THRASH=1` to also auto-set the task to `blocked` with a reason like `auto-blocked by doctor-noshy: thrashing detected, 4 reclaims in window`.

Both follow the existing confirm-before-acting pattern (`-y` to skip the prompt).

### Kanban tuning

| Env var | Default | What it controls |
|---------|---------|------------------|
| `DOCTOR_KANBAN_THRASH_RECLAIMS` | 3 | Reclaims in window to flag thrashing |
| `DOCTOR_KANBAN_THRASH_WINDOW_MIN` | 30 | Rolling window in minutes |
| `DOCTOR_KANBAN_BLOCKED_WARN` | 5 | Blocked-task count that promotes the check from `ok` to `warn` |
| `DOCTOR_KANBAN_AUTO_BLOCK_ON_THRASH` | unset | If `1`, healer auto-blocks instead of just releasing |

### Assumed kanban.db schema

Doctor Noshy inspects `kanban.db` read-only and assumes:

- `tasks(id, status, worker_pid, blocked_reason, updated_at)` with statuses `pending | in_progress | blocked | done | failed`
- `task_runs(task_id, worker_pid, started_at, ended_at, outcome)` with outcomes including `reclaimed` and `released`

Schema mismatches surface as `status: unknown` on the relevant check with the SQLite error attached — they won't crash the rest of the diagnose run.

## Alerts

Set one environment variable to start getting alerts:

```bash
# Discord (most common)
export DOCTOR_DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."

# Or Telegram
export DOCTOR_TELEGRAM_TOKEN="your-bot-token"
export DOCTOR_TELEGRAM_CHAT="chat-id"

# Or email
export DOCTOR_SMTP_HOST="smtp.gmail.com"
export DOCTOR_SMTP_USER="you@gmail.com"
export DOCTOR_SMTP_PASS="app-password"
export DOCTOR_ALERT_TO="you@gmail.com"
```

Or create `doctor-noshy.yaml` in your home directory:

```yaml
discord_webhook: https://discord.com/api/webhooks/...
```

## Systemd Service (Recommended)

Run Doctor Noshy as a background service:

```bash
cp systemd/doctor-noshy.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now doctor-noshy

# Check what it is doing
journalctl --user -u doctor-noshy -f
```

## Auto-Healer Details

The healer attempts to fix these critical issues:

| Issue | Action |
|-------|--------|
| Gateway process not running | Restarts openclaw-gateway, falls back to hermes-gateway |
| Gateway port not listening | Restarts the gateway service |
| Gateway HTTP not responding | Restarts the gateway service |
| Config file missing | Reports (manual fix required) |
| Kanban zombie workers | SIGKILLs zombie PID, releases claim in kanban.db |
| Kanban thrashing tasks | Releases stale claim (optionally auto-blocks via `DOCTOR_KANBAN_AUTO_BLOCK_ON_THRASH=1`) |

The healer asks for confirmation before acting. Use `doctor heal -y` to skip confirmation for automated workflows.

## Use Cases

**Personal Hermes setup** -- You run Hermes on a VPS or home server and want to know immediately when something breaks. Set up Discord alerts and the systemd service and forget about it.

**Multi-instance monitoring** -- Run `doctor diagnose --json` on each instance and pipe the output to a central dashboard or log aggregation system.

**CI/CD health gate** -- Run `doctor diagnose` before deploying updates. If anything is critical, block the deploy.

**Incident response** -- When Hermes stops responding, run `doctor heal` to automatically restart failed components instead of guessing what is wrong.

## Architecture

```
doctor_noshy/
  checks.py      18 health checks (gateway, providers, system, hermes)
  healer.py      Auto-heal logic for critical failures
  alerts.py      Discord / Telegram / Email dispatch
  dashboard.py   Flask web UI and JSON API
  cli.py         argparse CLI interface
```

## License

MIT
