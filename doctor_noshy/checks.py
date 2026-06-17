"""Core health checks for Hermes Agent components.

Each check returns a CheckResult with status, name, message, and optional details.
Statuses: ok, warn, critical, unknown
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    status: str  # "ok" | "warn" | "critical" | "unknown"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0

    @property
    def icon(self) -> str:
        return {"ok": "\u2705", "warn": "\u26a0\ufe0f", "critical": "\U0001f534", "unknown": "\u2753"}.get(
            self.status, "?"
        )

    def __str__(self) -> str:
        return f"{self.icon} {self.name}: {self.message}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: str, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )


def _http_get(url: str, timeout: int = 5) -> Optional["requests.Response"]:
    if requests is None:
        return None
    try:
        return requests.get(url, timeout=timeout)
    except Exception:
        return None


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


def _systemctl_user(action: str, service: str) -> subprocess.CompletedProcess:
    return _run(f"systemctl --user {action} {service}")


# ---------------------------------------------------------------------------
# Gateway checks
# ---------------------------------------------------------------------------

def check_gateway_process() -> CheckResult:
    """Check if the Hermes gateway process is running."""
    t0 = time.monotonic()
    result = _run("pgrep -f 'hermes.*gateway' || pgrep -f 'openclaw.*gateway'")
    elapsed = (time.monotonic() - t0) * 1000
    pids = result.stdout.strip().split("\n") if result.stdout.strip() else []
    pids = [p for p in pids if p]

    if pids:
        return CheckResult(
            name="Gateway Process",
            status="ok",
            message=f"Running (PID {', '.join(pids[:3])})",
            details={"pids": pids},
            elapsed_ms=elapsed,
        )
    return CheckResult(
        name="Gateway Process",
        status="critical",
        message="Not running",
        elapsed_ms=elapsed,
    )


def check_gateway_port() -> CheckResult:
    """Check if the gateway is listening on its expected port (18789)."""
    t0 = time.monotonic()
    result = _run("ss -tlnp")
    elapsed = (time.monotonic() - t0) * 1000

    if "18789" in result.stdout:
        return CheckResult(
            name="Gateway Port",
            status="ok",
            message="Listening on :18789",
            elapsed_ms=elapsed,
        )
    return CheckResult(
        name="Gateway Port",
        status="critical",
        message="Not listening on :18789",
        elapsed_ms=elapsed,
    )


def check_gateway_http() -> CheckResult:
    """Check if the gateway responds to HTTP."""
    t0 = time.monotonic()
    resp = _http_get("http://127.0.0.1:18789/health", timeout=5)
    elapsed = (time.monotonic() - t0) * 1000

    if resp and resp.status_code < 500:
        return CheckResult(
            name="Gateway HTTP",
            status="ok",
            message=f"Responding (HTTP {resp.status_code})",
            details={"status_code": resp.status_code},
            elapsed_ms=elapsed,
        )
    return CheckResult(
        name="Gateway HTTP",
        status="critical",
        message="Not responding" if resp is None else f"HTTP {resp.status_code}",
        elapsed_ms=elapsed,
    )


def check_gateway_service() -> CheckResult:
    """Check systemd status of the gateway service."""
    t0 = time.monotonic()
    # Try openclaw-gateway first, then hermes-gateway
    for svc in ("openclaw-gateway", "hermes-gateway"):
        result = _systemctl_user("is-active", svc)
        if result.stdout.strip() == "active":
            elapsed = (time.monotonic() - t0) * 1000
            return CheckResult(
                name="Gateway Service",
                status="ok",
                message=f"{svc} is active",
                details={"service": svc},
                elapsed_ms=elapsed,
            )
    elapsed = (time.monotonic() - t0) * 1000
    return CheckResult(
        name="Gateway Service",
        status="warn",
        message="No active gateway service found",
        elapsed_ms=elapsed,
    )


# ---------------------------------------------------------------------------
# Dashboard checks
# ---------------------------------------------------------------------------

def check_dashboard_service() -> CheckResult:
    t0 = time.monotonic()
    result = _systemctl_user("is-active", "hermes-dashboard")
    elapsed = (time.monotonic() - t0) * 1000

    if result.stdout.strip() == "active":
        return CheckResult(
            name="Dashboard Service",
            status="ok",
            message="hermes-dashboard is active",
            elapsed_ms=elapsed,
        )
    return CheckResult(
        name="Dashboard Service",
        status="warn",
        message="hermes-dashboard is not active",
        elapsed_ms=elapsed,
    )


def check_dashboard_port() -> CheckResult:
    t0 = time.monotonic()
    result = _run("ss -tlnp")
    elapsed = (time.monotonic() - t0) * 1000

    if "9119" in result.stdout:
        return CheckResult(
            name="Dashboard Port",
            status="ok",
            message="Listening on :9119",
            elapsed_ms=elapsed,
        )
    return CheckResult(
        name="Dashboard Port",
        status="warn",
        message="Not listening on :9119",
        elapsed_ms=elapsed,
    )


# ---------------------------------------------------------------------------
# Provider checks
# ---------------------------------------------------------------------------

def check_nous_portal() -> CheckResult:
    """Check Nous Portal API reachability."""
    t0 = time.monotonic()
    resp = _http_get("https://portal.nousresearch.com/api/v1/models", timeout=8)
    elapsed = (time.monotonic() - t0) * 1000

    if resp and resp.status_code == 200:
        return CheckResult(
            name="Nous Portal",
            status="ok",
            message="Reachable",
            elapsed_ms=elapsed,
        )
    code = resp.status_code if resp else "timeout"
    return CheckResult(
        name="Nous Portal",
        status="warn",
        message=f"Unreachable (HTTP {code})",
        elapsed_ms=elapsed,
    )


def check_openrouter() -> CheckResult:
    t0 = time.monotonic()
    resp = _http_get("https://openrouter.ai/api/v1/models", timeout=8)
    elapsed = (time.monotonic() - t0) * 1000

    if resp and resp.status_code == 200:
        return CheckResult(
            name="OpenRouter",
            status="ok",
            message="Reachable",
            elapsed_ms=elapsed,
        )
    code = resp.status_code if resp else "timeout"
    return CheckResult(
        name="OpenRouter",
        status="warn",
        message=f"Unreachable (HTTP {code})",
        elapsed_ms=elapsed,
    )


def check_local_api() -> CheckResult:
    """Check if the local Hermes API server is up."""
    t0 = time.monotonic()
    resp = _http_get("http://127.0.0.1:8642/v1/models", timeout=5)
    elapsed = (time.monotonic() - t0) * 1000

    if resp and resp.status_code == 200:
        return CheckResult(
            name="Local API Server",
            status="ok",
            message="Listening on :8642",
            elapsed_ms=elapsed,
        )
    return CheckResult(
        name="Local API Server",
        status="warn",
        message="Not listening on :8642",
        elapsed_ms=elapsed,
    )


# ---------------------------------------------------------------------------
# System resource checks
# ---------------------------------------------------------------------------

def check_cpu() -> CheckResult:
    t0 = time.monotonic()
    usage = psutil.cpu_percent(interval=1)
    elapsed = (time.monotonic() - t0) * 1000

    if usage < 80:
        status = "ok"
    elif usage < 95:
        status = "warn"
    else:
        status = "critical"

    return CheckResult(
        name="CPU Usage",
        status=status,
        message=f"{usage:.1f}%",
        details={"usage_percent": usage},
        elapsed_ms=elapsed,
    )


def check_memory() -> CheckResult:
    t0 = time.monotonic()
    mem = psutil.virtual_memory()
    elapsed = (time.monotonic() - t0) * 1000

    used_gb = mem.used / (1024**3)
    total_gb = mem.total / (1024**3)
    pct = mem.percent

    if pct < 80:
        status = "ok"
    elif pct < 95:
        status = "warn"
    else:
        status = "critical"

    return CheckResult(
        name="Memory",
        status=status,
        message=f"{used_gb:.1f}/{total_gb:.1f} GB ({pct:.1f}%)",
        details={"used_gb": used_gb, "total_gb": total_gb, "percent": pct},
        elapsed_ms=elapsed,
    )


def check_disk() -> CheckResult:
    t0 = time.monotonic()
    usage = shutil.disk_usage("/")
    elapsed = (time.monotonic() - t0) * 1000

    used_gb = usage.used / (1024**3)
    total_gb = usage.total / (1024**3)
    free_gb = usage.free / (1024**3)
    pct = (usage.used / usage.total) * 100

    if pct < 85:
        status = "ok"
    elif pct < 95:
        status = "warn"
    else:
        status = "critical"

    return CheckResult(
        name="Disk Space",
        status=status,
        message=f"{free_gb:.1f} GB free / {total_gb:.1f} GB total ({pct:.1f}% used)",
        details={"free_gb": free_gb, "total_gb": total_gb, "percent": pct},
        elapsed_ms=elapsed,
    )


# ---------------------------------------------------------------------------
# Hermes-specific checks
# ---------------------------------------------------------------------------

def check_config_exists() -> CheckResult:
    t0 = time.monotonic()
    config = _hermes_home() / "config.yaml"
    elapsed = (time.monotonic() - t0) * 1000

    if config.exists():
        return CheckResult(
            name="Config File",
            status="ok",
            message=f"Found at {config}",
            elapsed_ms=elapsed,
        )
    return CheckResult(
        name="Config File",
        status="critical",
        message=f"Missing at {config}",
        elapsed_ms=elapsed,
    )


def check_auth() -> CheckResult:
    t0 = time.monotonic()
    auth_dir = _hermes_home() / "auth"
    elapsed = (time.monotonic() - t0) * 1000

    if not auth_dir.exists():
        return CheckResult(
            name="Auth Store",
            status="warn",
            message="No auth directory found",
            elapsed_ms=elapsed,
        )

    providers = [d.name for d in auth_dir.iterdir() if d.is_dir()]
    if providers:
        return CheckResult(
            name="Auth Store",
            status="ok",
            message=f"Providers: {', '.join(providers)}",
            details={"providers": providers},
            elapsed_ms=elapsed,
        )
    return CheckResult(
        name="Auth Store",
        status="warn",
        message="Auth directory exists but no providers configured",
        elapsed_ms=elapsed,
    )


def check_skills() -> CheckResult:
    t0 = time.monotonic()
    skills_dir = _hermes_home() / "skills"
    elapsed = (time.monotonic() - t0) * 1000

    if not skills_dir.exists():
        return CheckResult(
            name="Skills",
            status="warn",
            message="No skills directory found",
            elapsed_ms=elapsed,
        )

    count = sum(1 for _ in skills_dir.rglob("SKILL.md"))
    return CheckResult(
        name="Skills",
        status="ok",
        message=f"{count} skills installed",
        details={"count": count},
        elapsed_ms=elapsed,
    )


def check_memory_files() -> CheckResult:
    t0 = time.monotonic()
    mem_dir = _hermes_home() / "memories"
    elapsed = (time.monotonic() - t0) * 1000

    memory_file = mem_dir / "MEMORY.md"
    user_file = mem_dir / "USER.md"

    memory_size = memory_file.stat().st_size if memory_file.exists() else 0
    user_size = user_file.stat().st_size if user_file.exists() else 0

    issues = []
    if memory_size > 2200:
        issues.append(f"MEMORY.md over limit ({memory_size}/2200 chars)")
    if user_size > 1375:
        issues.append(f"USER.md over limit ({user_size}/1375 chars)")

    if issues:
        return CheckResult(
            name="Memory Files",
            status="warn",
            message="; ".join(issues),
            details={"memory_bytes": memory_size, "user_bytes": user_size},
            elapsed_ms=elapsed,
        )
    return CheckResult(
        name="Memory Files",
        status="ok",
        message=f"MEMORY.md: {memory_size}/2200, USER.md: {user_size}/1375",
        details={"memory_bytes": memory_size, "user_bytes": user_size},
        elapsed_ms=elapsed,
    )


def check_cron_jobs() -> CheckResult:
    t0 = time.monotonic()
    jobs_file = _hermes_home() / "cron" / "jobs.json"
    elapsed = (time.monotonic() - t0) * 1000

    if not jobs_file.exists():
        return CheckResult(
            name="Cron Jobs",
            status="ok",
            message="No cron jobs configured",
            elapsed_ms=elapsed,
        )

    try:
        import json
        data = json.loads(jobs_file.read_text())
        jobs = data if isinstance(data, list) else data.get("jobs", [])
        enabled = sum(1 for j in jobs if j.get("enabled", True))
        return CheckResult(
            name="Cron Jobs",
            status="ok",
            message=f"{enabled}/{len(jobs)} enabled",
            details={"total": len(jobs), "enabled": enabled},
            elapsed_ms=elapsed,
        )
    except Exception as e:
        return CheckResult(
            name="Cron Jobs",
            status="warn",
            message=f"Could not parse jobs.json: {e}",
            elapsed_ms=elapsed,
        )


def check_tunnel() -> CheckResult:
    """Check if cloudflared or ngrok tunnel is active."""
    t0 = time.monotonic()
    for svc in ("cloudflared-tunnel", "ngrok-gateway"):
        result = _systemctl_user("is-active", svc)
        if result.stdout.strip() == "active":
            elapsed = (time.monotonic() - t0) * 1000
            return CheckResult(
                name="Tunnel",
                status="ok",
                message=f"{svc} is active",
                details={"service": svc},
                elapsed_ms=elapsed,
            )
    elapsed = (time.monotonic() - t0) * 1000
    return CheckResult(
        name="Tunnel",
        status="warn",
        message="No active tunnel (cloudflared or ngrok)",
        elapsed_ms=elapsed,
    )


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    check_config_exists,
    check_auth,
    check_gateway_process,
    check_gateway_port,
    check_gateway_http,
    check_gateway_service,
    check_dashboard_service,
    check_dashboard_port,
    check_tunnel,
    check_local_api,
    check_nous_portal,
    check_openrouter,
    check_cpu,
    check_memory,
    check_disk,
    check_skills,
    check_memory_files,
    check_cron_jobs,
]


def run_all_checks(
    checks: Optional[List[str]] = None,
) -> List[CheckResult]:
    """Run all checks, or a filtered subset by name."""
    results = []
    for check_fn in ALL_CHECKS:
        name = check_fn.__name__.replace("check_", "").replace("_", " ")
        if checks and not any(c.lower() in name for c in checks):
            continue
        try:
            results.append(check_fn())
        except Exception as e:
            results.append(
                CheckResult(
                    name=name,
                    status="unknown",
                    message=f"Check failed: {e}",
                )
            )
    return results


def summary(results: List[CheckResult]) -> Dict[str, Any]:
    counts = {"ok": 0, "warn": 0, "critical": 0, "unknown": 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    if counts["critical"] > 0:
        overall = "critical"
    elif counts["warn"] > 0:
        overall = "warn"
    elif counts["unknown"] > 0:
        overall = "unknown"
    else:
        overall = "ok"

    return {
        "overall": overall,
        "counts": counts,
        "total": len(results),
    }
