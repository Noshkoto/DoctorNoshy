"""Lightweight web dashboard for Doctor Noshy.

Serves a single-page status overview on http://127.0.0.1:9200/
Requires Flask (pip install doctor-noshy[dashboard]).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .checks import run_all_checks, summary, CheckResult


def create_app():
    try:
        from flask import Flask, jsonify, render_template_string
    except ImportError:
        raise ImportError("Flask required: pip install doctor-noshy[dashboard]")

    app = Flask(__name__)

    DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Doctor Noshy</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0d1117; color: #c9d1d9; padding: 2rem; }
  .header { text-align: center; margin-bottom: 2rem; }
  .header h1 { font-size: 2rem; color: #f0f6fc; }
  .header .subtitle { color: #8b949e; margin-top: 0.5rem; }
  .overall { text-align: center; padding: 1.5rem; border-radius: 12px;
             margin-bottom: 2rem; font-size: 1.3rem; font-weight: 600; }
  .overall.ok { background: #0d4429; color: #3fb950; border: 1px solid #238636; }
  .overall.warn { background: #4d3800; color: #d29922; border: 1px solid #9e6a03; }
  .overall.critical { background: #490202; color: #f85149; border: 1px solid #da3633; }
  .checks { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1rem; }
  .check { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
           padding: 1rem; }
  .check.ok { border-left: 4px solid #3fb950; }
  .check.warn { border-left: 4px solid #d29922; }
  .check.critical { border-left: 4px solid #f85149; }
  .check.unknown { border-left: 4px solid #8b949e; }
  .check-name { font-weight: 600; color: #f0f6fc; margin-bottom: 0.3rem; }
  .check-msg { color: #8b949e; font-size: 0.9rem; }
  .footer { text-align: center; margin-top: 2rem; color: #484f58; font-size: 0.8rem; }
  .counts { display: flex; justify-content: center; gap: 2rem; margin-bottom: 2rem; }
  .count { text-align: center; }
  .count .num { font-size: 2rem; font-weight: 700; }
  .count .label { color: #8b949e; font-size: 0.85rem; }
  .count.ok .num { color: #3fb950; }
  .count.warn .num { color: #d29922; }
  .count.critical .num { color: #f85149; }
</style>
</head>
<body>
<div class="header">
  <h1>&#x1FA7A; Doctor Noshy</h1>
  <div class="subtitle">Hermes Agent Health Monitor</div>
</div>
<div id="content">Loading...</div>
<div class="footer" id="footer"></div>
<script>
async function load() {
  const resp = await fetch('/api/status');
  const data = await resp.json();
  let html = '';
  const s = data.summary;
  html += '<div class="overall ' + s.overall + '">';
  html += s.overall.toUpperCase() + '</div>';
  html += '<div class="counts">';
  for (const [k, v] of Object.entries(s.counts)) {
    if (v > 0) html += '<div class="count ' + k + '"><div class="num">' + v + '</div><div class="label">' + k + '</div></div>';
  }
  html += '</div>';
  html += '<div class="checks">';
  for (const c of data.checks) {
    html += '<div class="check ' + c.status + '">';
    html += '<div class="check-name">' + c.icon + ' ' + c.name + '</div>';
    html += '<div class="check-msg">' + c.message + '</div>';
    html += '</div>';
  }
  html += '</div>';
  document.getElementById('content').innerHTML = html;
  document.getElementById('footer').textContent = 'Last check: ' + data.timestamp;
}
load();
setInterval(load, 30000);
</script>
</body>
</html>
"""

    @app.route("/")
    def index():
        return render_template_string(DASHBOARD_HTML)

    @app.route("/api/status")
    def api_status():
        results = run_all_checks()
        return jsonify({
            "summary": summary(results),
            "checks": [
                {
                    "name": r.name,
                    "status": r.status,
                    "message": r.message,
                    "details": r.details,
                    "icon": r.icon,
                }
                for r in results
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @app.route("/api/check/<name>")
    def api_check(name: str):
        results = run_all_checks(checks=[name])
        if not results:
            return jsonify({"error": f"Check '{name}' not found"}), 404
        r = results[0]
        return jsonify({
            "name": r.name,
            "status": r.status,
            "message": r.message,
            "details": r.details,
            "icon": r.icon,
        })

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok", "service": "doctor-noshy"})

    return app
