"""CLI interface for Doctor Noshy.

Usage:
    doctor diagnose          Run all health checks
    doctor watch             Continuous monitoring (loop)
    doctor heal              Run checks and auto-heal critical issues
    doctor report            Generate a formatted report
    doctor alerts            Test alert channels
    doctor dashboard         Start the web dashboard
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from typing import List

from . import __version__
from .checks import CheckResult, run_all_checks, summary
from .healer import get_heal_plan, heal
from .alerts import send_alerts, format_alert

log = logging.getLogger("doctor")


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _print_results(results: List[CheckResult], verbose: bool = False) -> None:
    """Pretty-print check results to terminal."""
    print()
    for r in results:
        print(f"  {r.icon}  {r.name:<22s} {r.message}")
        if verbose and r.details:
            for k, v in r.details.items():
                print(f"      {k}: {v}")
    print()

    s = summary(results)
    icon = {"ok": "\u2705", "warn": "\u26a0\ufe0f", "critical": "\U0001f534", "unknown": "\u2753"}
    print(f"  Overall: {icon.get(s['overall'], '?')} {s['overall'].upper()}")
    print(f"  {s['counts']['ok']} ok | {s['counts']['warn']} warn | {s['counts']['critical']} critical | {s['counts']['unknown']} unknown")
    print()


def _print_report(results: List[CheckResult]) -> None:
    """Print a markdown-formatted report."""
    s = summary(results)
    print(f"# Doctor Noshy Report\n")
    print(f"**Overall Status:** {s['overall'].upper()}\n")
    print(f"| Status | Count |")
    print(f"|--------|-------|")
    for status, count in s["counts"].items():
        if count > 0:
            print(f"| {status} | {count} |")
    print()
    for r in results:
        print(f"## {r.icon} {r.name}")
        print(f"**Status:** {r.status}")
        print(f"**Message:** {r.message}")
        if r.details:
            print(f"**Details:**")
            for k, v in r.details.items():
                print(f"- {k}: {v}")
        print()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_diagnose(args: argparse.Namespace) -> int:
    """Run all health checks and print results."""
    checks = args.checks.split(",") if args.checks else None
    results = run_all_checks(checks)
    _print_results(results, verbose=args.verbose)
    s = summary(results)
    return 1 if s["overall"] == "critical" else 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Continuous monitoring loop."""
    interval = args.interval
    print(f"\U0001fa7a Doctor Noshy v{__version__} — watching every {interval}s (Ctrl+C to stop)\n")

    while True:
        try:
            results = run_all_checks()
            _print_results(results)

            # Send alerts on failures
            s = summary(results)
            if s["overall"] in ("critical", "warn"):
                send_alerts(results)

            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\nStopped watching.")
            break
    return 0


def cmd_heal(args: argparse.Namespace) -> int:
    """Run checks and auto-heal critical issues."""
    results = run_all_checks()
    _print_results(results)

    plan = get_heal_plan(results)
    if not plan:
        print("  No critical issues to heal.")
        return 0

    print("  Heal plan:")
    for item in plan:
        print(f"    \u2192 {item}")
    print()

    if not args.yes:
        confirm = input("  Proceed? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("  Aborted.")
            return 1

    actions = heal(results, auto=True)
    print("  Actions taken:")
    for a in actions:
        print(f"    {a}")
    print()

    # Re-check after healing
    print("  Re-checking...")
    results2 = run_all_checks()
    _print_results(results2)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Generate a formatted report."""
    results = run_all_checks()
    if args.json:
        data = [
            {"name": r.name, "status": r.status, "message": r.message, "details": r.details}
            for r in results
        ]
        print(json.dumps({"summary": summary(results), "checks": data}, indent=2))
    else:
        _print_report(results)
    return 0


def cmd_alerts(args: argparse.Namespace) -> int:
    """Test alert channels."""
    from .checks import CheckResult
    test_results = [
        CheckResult(name="Test Check", status="warn", message="This is a test alert from Doctor Noshy"),
    ]
    outcomes = send_alerts(test_results)
    if not outcomes:
        print("  No alert channels configured. Set env vars or create doctor-noshy.yaml")
        return 1
    for channel, ok in outcomes.items():
        icon = "\u2705" if ok else "\u274c"
        print(f"  {icon} {channel}: {'sent' if ok else 'failed'}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Start the web dashboard."""
    try:
        from .dashboard import create_app
        app = create_app()
        print(f"\U0001fa7a Doctor Noshy Dashboard — http://127.0.0.1:{args.port}/")
        app.run(host="127.0.0.1", port=args.port, debug=args.debug)
    except ImportError:
        print("  Dashboard requires Flask: pip install doctor-noshy[dashboard]")
        return 1
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="doctor",
        description="\U0001fa7a Doctor Noshy — Health monitor for Hermes Agent",
    )
    parser.add_argument("--version", action="version", version=f"doctor-noshy {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # diagnose
    p_diag = sub.add_parser("diagnose", help="Run all health checks")
    p_diag.add_argument("--checks", help="Comma-separated check names to run")
    p_diag.set_defaults(func=cmd_diagnose)

    # watch
    p_watch = sub.add_parser("watch", help="Continuous monitoring")
    p_watch.add_argument("-i", "--interval", type=int, default=60, help="Check interval in seconds")
    p_watch.set_defaults(func=cmd_watch)

    # heal
    p_heal = sub.add_parser("heal", help="Run checks and auto-heal")
    p_heal.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    p_heal.set_defaults(func=cmd_heal)

    # report
    p_report = sub.add_parser("report", help="Generate a report")
    p_report.add_argument("--json", action="store_true", help="Output as JSON")
    p_report.set_defaults(func=cmd_report)

    # alerts
    p_alerts = sub.add_parser("alerts", help="Test alert channels")
    p_alerts.set_defaults(func=cmd_alerts)

    # dashboard
    p_dash = sub.add_parser("dashboard", help="Start web dashboard")
    p_dash.add_argument("-p", "--port", type=int, default=9200)
    p_dash.add_argument("--debug", action="store_true")
    p_dash.set_defaults(func=cmd_dashboard)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
