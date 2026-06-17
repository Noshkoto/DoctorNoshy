"""Auto-healer — restart failed services and attempt recovery."""

from __future__ import annotations

import logging
import os
import signal
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from .checks import CheckResult, _kanban_db_path, _run, _systemctl_user

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


# ---------------------------------------------------------------------------
# Kanban healers
# ---------------------------------------------------------------------------

# Default SIGKILL for zombie reaping. The signal handler bug means SIGTERM
# won't actually exit the process; SIGKILL bypasses the handler entirely.
_KANBAN_KILL_SIGNAL = getattr(signal, "SIGKILL", signal.SIGTERM)


def _open_kanban_db_rw() -> Optional[sqlite3.Connection]:
    """Read-write handle for healer use. Short timeout so we yield to the
    dispatcher rather than blocking it."""
    db = _kanban_db_path()
    if not db.exists():
        return None
    try:
        return sqlite3.connect(str(db), timeout=2.0)
    except sqlite3.Error:
        return None


def _release_claim(
    conn: sqlite3.Connection, task_id: str, block_reason: Optional[str] = None
) -> bool:
    """Clear a task's claim. If ``block_reason`` is given, also set status=blocked.

    Returns True on success. Schema mismatches are caught and surfaced via False.
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        if block_reason:
            conn.execute(
                "UPDATE tasks "
                "SET status = 'blocked', worker_pid = NULL, "
                "    blocked_reason = ?, updated_at = ? "
                "WHERE id = ?",
                (block_reason, now, task_id),
            )
        else:
            conn.execute(
                "UPDATE tasks "
                "SET status = 'pending', worker_pid = NULL, updated_at = ? "
                "WHERE id = ?",
                (now, task_id),
            )
        conn.execute(
            "UPDATE task_runs SET ended_at = ?, outcome = 'released' "
            "WHERE task_id = ? AND ended_at IS NULL",
            (now, task_id),
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        log.warning("kanban release failed for %s: %s", task_id, e)
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        return False


def reap_zombie_kanban_workers(result: CheckResult) -> List[HealAction]:
    """SIGKILL each zombie worker PID and release its claim back to pending."""
    actions: List[HealAction] = []
    zombies = (result.details or {}).get("zombies", [])
    if not zombies:
        return actions

    conn = _open_kanban_db_rw()
    if conn is None:
        actions.append(HealAction(
            check=result.name,
            action="reap-zombie",
            success=False,
            message="Could not open kanban.db read-write",
        ))
        return actions

    try:
        for z in zombies:
            pid = z.get("pid")
            task_id = z.get("task_id")
            if pid is None or task_id is None:
                continue

            kill_err = None
            try:
                os.kill(int(pid), _KANBAN_KILL_SIGNAL)
            except ProcessLookupError:
                # Zombie already reaped by init; releasing the claim is still useful.
                pass
            except (PermissionError, OSError, ValueError) as e:
                kill_err = str(e)

            released = _release_claim(conn, task_id)
            if kill_err is None and released:
                actions.append(HealAction(
                    check=result.name,
                    action="reap-zombie",
                    success=True,
                    message=f"Reaped PID {pid} and released task {task_id}",
                ))
            else:
                parts = []
                if kill_err is not None:
                    parts.append(f"kill failed: {kill_err}")
                if not released:
                    parts.append("DB release failed")
                actions.append(HealAction(
                    check=result.name,
                    action="reap-zombie",
                    success=False,
                    message=f"Task {task_id} (PID {pid}): " + "; ".join(parts),
                ))
    finally:
        conn.close()
    return actions


def force_release_stale_claim(result: CheckResult) -> List[HealAction]:
    """Release claims on thrashing tasks. If
    DOCTOR_KANBAN_AUTO_BLOCK_ON_THRASH=1, also mark them blocked with a reason
    that explains the doctor-noshy intervention."""
    actions: List[HealAction] = []
    thrashing = (result.details or {}).get("thrashing", [])
    if not thrashing:
        return actions

    auto_block = os.environ.get(
        "DOCTOR_KANBAN_AUTO_BLOCK_ON_THRASH", ""
    ).lower() in ("1", "true", "yes", "on")

    conn = _open_kanban_db_rw()
    if conn is None:
        actions.append(HealAction(
            check=result.name,
            action="release-stale",
            success=False,
            message="Could not open kanban.db read-write",
        ))
        return actions

    try:
        for t in thrashing:
            task_id = t.get("task_id")
            count = t.get("reclaim_count")
            if not task_id:
                continue
            reason = (
                f"auto-blocked by doctor-noshy: thrashing detected, "
                f"{count} reclaims in window"
            ) if auto_block else None
            ok = _release_claim(conn, task_id, block_reason=reason)
            verb = "auto-blocked" if auto_block else "released"
            action_name = "release-stale+block" if auto_block else "release-stale"
            actions.append(HealAction(
                check=result.name,
                action=action_name,
                success=ok,
                message=(
                    f"Task {task_id} {verb} ({count} reclaims)"
                    if ok else f"Task {task_id} {verb} failed"
                ),
            ))
    finally:
        conn.close()
    return actions


# ---------------------------------------------------------------------------
# Heal dispatcher
# ---------------------------------------------------------------------------

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

        # Kanban zombie workers — SIGKILL + release claim
        elif r.name == "Kanban Zombie Workers":
            actions.extend(reap_zombie_kanban_workers(r))

        # Kanban thrashing — release claim (optionally auto-block)
        elif r.name == "Kanban Thrashing":
            actions.extend(force_release_stale_claim(r))

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
        elif r.name == "Kanban Zombie Workers":
            zombies = (r.details or {}).get("zombies", [])
            plan.append(
                f"Reap {len(zombies)} zombie Kanban worker(s) and release claims"
            )
        elif r.name == "Kanban Thrashing":
            thrashing = (r.details or {}).get("thrashing", [])
            auto_block = os.environ.get(
                "DOCTOR_KANBAN_AUTO_BLOCK_ON_THRASH", ""
            ).lower() in ("1", "true", "yes", "on")
            suffix = " and auto-block" if auto_block else ""
            plan.append(
                f"Release stale claims on {len(thrashing)} thrashing task(s)"
                f"{suffix}"
            )
    return plan
