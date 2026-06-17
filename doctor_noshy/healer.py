"""Auto-healer — restart failed services and attempt recovery."""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from typing import List, Optional

from .checks import CheckResult, _run, _systemctl_user

log = logging.getLogger("doctor.healer")


@dataclass
class HealAction:
    check: str
    action: str
    success: bool
    message: str

    def __str__(self) -> str:
        icon = "\u2705" if self.success else "\u274c"
        return f"{icon} {self.check}: {self.message}"


def _restart_service(service: str) -> HealAction:
    """Restart a systemd user service."""
    result = _systemctl_user("restart", service)
    time.sleep(2)

    # Verify it came back
    status = _systemctl_user("is-active", service)
    is_active = status.stdout.strip() == "active"

    return HealAction(
        check=f"Service {service}",
        action="restart",
        success=is_active,
        message=f"{service} is now {status.stdout.strip()}" if is_active else f"Restart failed: {result.stderr.strip()}",
    )


def _kill_and_restart(pattern: str, start_cmd: str) -> HealAction:
    """Kill a process by pattern and restart it."""
    _run(f"pkill -f '{pattern}'")
    time.sleep(2)
    result = _run(start_cmd, timeout=15)
    time.sleep(3)

    verify = _run(f"pgrep -f '{pattern}'")
    if verify.stdout.strip():
        return HealAction(
            check=f"Process {pattern}",
            action="kill+restart",
            success=True,
            message=f"Restarted successfully",
        )
    return HealAction(
        check=f"Process {pattern}",
        action="kill+restart",
        success=False,
        message=f"Restart failed: {result.stderr.strip()}",
    )


def heal(results: List[CheckResult], auto: bool = False) -> List[HealAction]:
    """Attempt to heal critical issues found by checks.

    Args:
        results: Check results from run_all_checks()
        auto: If True, heal without confirmation. If False, return planned actions.

    Returns:
        List of HealAction describing what was done or would be done.
    """
    actions = []

    for r in results:
        if r.status != "critical":
            continue

        # Gateway process not running
        if r.name == "Gateway Process":
            action = _restart_service("openclaw-gateway")
            actions.append(action)
            if not action.success:
                action = _restart_service("hermes-gateway")
                actions.append(action)

        # Gateway not responding on port
        elif r.name == "Gateway Port":
            action = _restart_service("openclaw-gateway")
            actions.append(action)
            if not action.success:
                action = _restart_service("hermes-gateway")
                actions.append(action)

        # Gateway HTTP not responding
        elif r.name == "Gateway HTTP":
            action = _restart_service("openclaw-gateway")
            actions.append(action)
            if not action.success:
                action = _restart_service("hermes-gateway")
                actions.append(action)

        # Config missing — can't heal this
        elif r.name == "Config File":
            actions.append(HealAction(
                check=r.name,
                action="none",
                success=False,
                message="Config file missing. Run `hermes setup` to create it.",
            ))

    return actions


def get_heal_plan(results: List[CheckResult]) -> List[str]:
    """Return human-readable descriptions of what would be healed."""
    plan = []
    for r in results:
        if r.status != "critical":
            continue
        if r.name == "Gateway Process":
            plan.append("Restart openclaw-gateway service")
        elif r.name in ("Gateway Port", "Gateway HTTP"):
            plan.append("Restart gateway service (port/HTTP unresponsive)")
        elif r.name == "Config File":
            plan.append("Cannot auto-heal: config file missing")
    return plan
