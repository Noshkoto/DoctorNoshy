"""Alert dispatcher — send notifications when checks fail.

Supports Discord webhooks, Telegram bot, and email (SMTP).
Configure via doctor-noshy.yaml or environment variables.
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import subprocess
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

from .checks import CheckResult

log = logging.getLogger("doctor.alerts")


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_config() -> Dict[str, Any]:
    """Load alert config from doctor-noshy.yaml or env vars."""
    config_path = Path("doctor-noshy.yaml")
    if config_path.exists():
        try:
            import yaml
            return yaml.safe_load(config_path.read_text()) or {}
        except ImportError:
            # Fallback: basic YAML parsing for simple key: value
            config: Dict[str, Any] = {}
            for line in config_path.read_text().splitlines():
                line = line.strip()
                if ":" in line and not line.startswith("#"):
                    k, v = line.split(":", 1)
                    config[k.strip()] = v.strip().strip("\"'")
            return config

    # Environment variable fallbacks
    return {
        "discord_webhook": os.environ.get("DOCTOR_DISCORD_WEBHOOK", ""),
        "telegram_bot_token": os.environ.get("DOCTOR_TELEGRAM_TOKEN", ""),
        "telegram_chat_id": os.environ.get("DOCTOR_TELEGRAM_CHAT", ""),
        "smtp_host": os.environ.get("DOCTOR_SMTP_HOST", ""),
        "smtp_port": int(os.environ.get("DOCTOR_SMTP_PORT", "587")),
        "smtp_user": os.environ.get("DOCTOR_SMTP_USER", ""),
        "smtp_pass": os.environ.get("DOCTOR_SMTP_PASS", ""),
        "alert_email_to": os.environ.get("DOCTOR_ALERT_TO", ""),
        "alert_email_from": os.environ.get("DOCTOR_ALERT_FROM", "doctor-noshy@localhost"),
    }


# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------

def _send_discord(message: str, color: int = 0xE74C3C) -> bool:
    config = _load_config()
    webhook = config.get("discord_webhook", "")
    if not webhook:
        return False

    payload = {
        "embeds": [{
            "title": "\U0001fa7a Doctor Noshy Alert",
            "description": message,
            "color": color,
        }]
    }

    if requests:
        try:
            resp = requests.post(webhook, json=payload, timeout=10)
            return resp.status_code < 300
        except Exception as e:
            log.warning("Discord alert failed: %s", e)
            return False
    else:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", webhook,
             "-H", "Content-Type: application/json",
             "-d", json.dumps(payload)],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def _send_telegram(message: str) -> bool:
    config = _load_config()
    token = config.get("telegram_bot_token", "")
    chat_id = config.get("telegram_chat_id", "")
    if not token or not chat_id:
        return False

    if requests:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            resp = requests.post(url, json={
                "chat_id": chat_id,
                "text": f"\U0001fa7a Doctor Noshy\n\n{message}",
                "parse_mode": "Markdown",
            }, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            log.warning("Telegram alert failed: %s", e)
            return False
    else:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST",
             f"https://api.telegram.org/bot{token}/sendMessage",
             "-d", f"chat_id={chat_id}",
             "-d", f"text=\U0001fa7a Doctor Noshy\n\n{message}"],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def _send_email(subject: str, body: str) -> bool:
    config = _load_config()
    host = config.get("smtp_host", "")
    if not host:
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config.get("alert_email_from", "doctor-noshy@localhost")
    msg["To"] = config.get("alert_email_to", "")

    try:
        with smtplib.SMTP(host, config.get("smtp_port", 587)) as server:
            server.starttls()
            user = config.get("smtp_user", "")
            pwd = config.get("smtp_pass", "")
            if user and pwd:
                server.login(user, pwd)
            server.send_message(msg)
        return True
    except Exception as e:
        log.warning("Email alert failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_alert(results: List[CheckResult]) -> str:
    """Format check results into a readable alert message."""
    lines = []
    criticals = [r for r in results if r.status == "critical"]
    warns = [r for r in results if r.status == "warn"]

    if criticals:
        lines.append("**CRITICAL:**")
        for r in criticals:
            lines.append(f"  \U0001f534 {r.name}: {r.message}")

    if warns:
        lines.append("**WARNINGS:**")
        for r in warns:
            lines.append(f"  \u26a0\ufe0f {r.name}: {r.message}")

    if not lines:
        return "All checks passed."

    return "\n".join(lines)


def send_alerts(results: List[CheckResult], channels: Optional[List[str]] = None) -> Dict[str, bool]:
    """Send alerts to configured channels.

    Args:
        results: Check results to alert on
        channels: List of channels to use ("discord", "telegram", "email").
                  If None, sends to all configured channels.

    Returns:
        Dict of channel -> success status
    """
    criticals = [r for r in results if r.status in ("critical", "warn")]
    if not criticals:
        return {}

    message = format_alert(results)
    color = 0xE74C3C if any(r.status == "critical" for r in criticals) else 0xF39C12
    outcomes: Dict[str, bool] = {}

    all_channels = channels or ["discord", "telegram", "email"]

    if "discord" in all_channels:
        outcomes["discord"] = _send_discord(message, color)
    if "telegram" in all_channels:
        outcomes["telegram"] = _send_telegram(message)
    if "email" in all_channels:
        outcomes["email"] = _send_email("Doctor Noshy Alert", message)

    return outcomes
