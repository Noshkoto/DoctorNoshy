"""Lightweight web dashboard for Doctor Noshy.

Serves a single-page status overview on http://127.0.0.1:9200/
Requires Flask (pip install doctor-noshy[dashboard]).
"""

from __future__ import annotations

from datetime import datetime, timezone

from .checks import run_all_checks, summary


def create_app():
    try:
        from flask import Flask, jsonify
    except ImportError:
        raise ImportError("Flask required: pip install doctor-noshy[dashboard]")

    app = Flask(__name__)

    @app.route("/")
    def index():
        return DASHBOARD_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}

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
                    "elapsed_ms": round(r.elapsed_ms, 1),
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
            "elapsed_ms": round(r.elapsed_ms, 1),
        })

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok", "service": "doctor-noshy"})

    return app


# ---------------------------------------------------------------------------
# Single-page UI
# ---------------------------------------------------------------------------

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Doctor Noshy</title>
<meta name="color-scheme" content="light dark">
<style>
:root {
  color-scheme: light dark;
  --bg: #0a0c10;
  --surface: #131720;
  --surface-2: #1a1f2b;
  --border: #232a37;
  --text: #e6edf3;
  --muted: #7d8590;
  --accent: #7aa2f7;
  --ok: #3fb950;
  --warn: #d29922;
  --crit: #f85149;
  --unknown: #8b949e;
  --shadow: 0 1px 3px rgba(0,0,0,0.4), 0 8px 24px rgba(0,0,0,0.18);
  --font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, "JetBrains Mono", Menlo, Consolas, monospace;
}
:root[data-theme="light"] {
  --bg: #f6f8fa;
  --surface: #ffffff;
  --surface-2: #f6f8fa;
  --border: #d0d7de;
  --text: #1f2328;
  --muted: #59636e;
  --accent: #0969da;
  --ok: #1a7f37;
  --warn: #9a6700;
  --crit: #cf222e;
  --unknown: #59636e;
  --shadow: 0 1px 3px rgba(31,35,40,0.08), 0 6px 20px rgba(31,35,40,0.06);
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) {
    --bg: #f6f8fa;
    --surface: #ffffff;
    --surface-2: #f6f8fa;
    --border: #d0d7de;
    --text: #1f2328;
    --muted: #59636e;
    --accent: #0969da;
    --ok: #1a7f37;
    --warn: #9a6700;
    --crit: #cf222e;
    --unknown: #59636e;
    --shadow: 0 1px 3px rgba(31,35,40,0.08), 0 6px 20px rgba(31,35,40,0.06);
  }
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: var(--font-sans);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  min-height: 100vh;
}

.shell { max-width: 1200px; margin: 0 auto; padding: 24px 20px 60px; }

/* ---------- Header ---------- */
.header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}
.brand { display: flex; align-items: center; gap: 12px; }
.brand-mark {
  width: 36px; height: 36px;
  display: grid; place-items: center;
  border-radius: 9px;
  background: linear-gradient(135deg, var(--accent), color-mix(in srgb, var(--accent) 55%, #c084fc));
  font-size: 20px;
  box-shadow: var(--shadow);
}
.brand-title { font-weight: 700; font-size: 18px; letter-spacing: -0.01em; line-height: 1.1; }
.brand-sub { color: var(--muted); font-weight: 400; font-size: 12.5px; margin-top: 2px; }
.header-actions { margin-left: auto; display: flex; gap: 8px; align-items: center; }
.icon-btn {
  appearance: none;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  width: 36px; height: 36px;
  border-radius: 8px;
  display: grid; place-items: center;
  cursor: pointer;
  transition: background 120ms, border-color 120ms, transform 120ms;
}
.icon-btn:hover { background: var(--surface-2); border-color: color-mix(in srgb, var(--border) 50%, var(--accent)); }
.icon-btn:active { transform: translateY(1px); }
.icon-btn svg { width: 16px; height: 16px; stroke: currentColor; fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.icon-btn.spinning svg { animation: spin 700ms ease-in-out; }
@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }

/* ---------- Banner ---------- */
.banner {
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 22px;
  background: var(--surface);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 28px;
  align-items: center;
  margin-bottom: 18px;
  box-shadow: var(--shadow);
  position: relative;
  overflow: hidden;
}
.banner::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--unknown);
  transition: background 240ms;
}
.banner[data-overall="ok"]::before { background: var(--ok); }
.banner[data-overall="warn"]::before { background: var(--warn); }
.banner[data-overall="critical"]::before { background: var(--crit); }

.overall-status {
  display: flex; align-items: center; gap: 14px;
  min-width: 0;
}
.status-dot {
  width: 14px; height: 14px;
  border-radius: 50%;
  background: var(--unknown);
  flex-shrink: 0;
}
.status-dot.ok { background: var(--ok); box-shadow: 0 0 0 5px color-mix(in srgb, var(--ok) 18%, transparent); }
.status-dot.warn { background: var(--warn); box-shadow: 0 0 0 5px color-mix(in srgb, var(--warn) 18%, transparent); }
.status-dot.critical { background: var(--crit); box-shadow: 0 0 0 5px color-mix(in srgb, var(--crit) 18%, transparent); animation: pulse 2s ease-in-out infinite; }
.status-dot.unknown { background: var(--unknown); box-shadow: 0 0 0 5px color-mix(in srgb, var(--unknown) 18%, transparent); }
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 5px color-mix(in srgb, var(--crit) 18%, transparent); }
  50% { box-shadow: 0 0 0 9px color-mix(in srgb, var(--crit) 8%, transparent); }
}
.overall-text { font-size: 24px; font-weight: 700; letter-spacing: -0.02em; }

.stat-strip { display: flex; gap: 18px; align-items: center; }
.stat { display: flex; flex-direction: column; align-items: center; min-width: 54px; }
.stat-num {
  font-size: 22px; font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em; line-height: 1;
}
.stat-label {
  font-size: 10.5px; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--muted); margin-top: 5px;
}
.stat.ok .stat-num { color: var(--ok); }
.stat.warn .stat-num { color: var(--warn); }
.stat.critical .stat-num { color: var(--crit); }

.last-check { color: var(--muted); font-size: 12px; text-align: right; font-variant-numeric: tabular-nums; min-width: 100px; }
.last-check .relative { display: block; font-size: 13px; color: var(--text); font-weight: 500; margin-bottom: 2px; }

/* ---------- Toolbar ---------- */
.toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 18px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip {
  appearance: none;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px 12px;
  border-radius: 999px;
  font: inherit; font-size: 12px; font-weight: 500;
  cursor: pointer;
  display: inline-flex; align-items: center; gap: 6px;
  transition: background 120ms, border-color 120ms, color 120ms;
}
.chip:hover { background: var(--surface-2); }
.chip[aria-pressed="true"] {
  background: color-mix(in srgb, var(--accent) 18%, var(--surface));
  border-color: color-mix(in srgb, var(--accent) 60%, var(--border));
}
.chip[data-filter="critical"][aria-pressed="true"] { border-color: var(--crit); background: color-mix(in srgb, var(--crit) 18%, var(--surface)); color: var(--crit); }
.chip[data-filter="warn"][aria-pressed="true"] { border-color: var(--warn); background: color-mix(in srgb, var(--warn) 18%, var(--surface)); color: var(--warn); }
.chip[data-filter="ok"][aria-pressed="true"] { border-color: var(--ok); background: color-mix(in srgb, var(--ok) 18%, var(--surface)); color: var(--ok); }
.chip .badge {
  background: color-mix(in srgb, currentColor 12%, transparent);
  padding: 1px 7px; border-radius: 999px;
  font-variant-numeric: tabular-nums; font-size: 11px;
}

.search { flex: 1; min-width: 200px; max-width: 360px; position: relative; }
.search input {
  width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 8px 38px 8px 34px;
  border-radius: 8px;
  font: inherit; outline: none;
  transition: border-color 120ms, box-shadow 120ms;
}
.search input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 22%, transparent); }
.search svg {
  position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
  width: 16px; height: 16px;
  stroke: var(--muted); fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round;
}
.search kbd {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
  font: inherit; font-family: var(--font-mono); font-size: 11px; color: var(--muted);
}

.interval {
  background: var(--surface); border: 1px solid var(--border); color: var(--text);
  padding: 7px 28px 7px 10px; border-radius: 8px;
  font: inherit; font-size: 12px; cursor: pointer;
  appearance: none;
  background-image: linear-gradient(45deg, transparent 50%, var(--muted) 50%), linear-gradient(135deg, var(--muted) 50%, transparent 50%);
  background-position: calc(100% - 14px) 12px, calc(100% - 10px) 12px;
  background-size: 4px 4px; background-repeat: no-repeat;
}

.raw-link {
  color: var(--muted); font-size: 12px; text-decoration: none;
  padding: 6px 10px; border-radius: 6px; border: 1px solid transparent;
  transition: color 120ms, background 120ms, border-color 120ms;
}
.raw-link:hover { color: var(--text); background: var(--surface); border-color: var(--border); }

/* ---------- Category ---------- */
.category {
  margin-bottom: 14px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  overflow: hidden;
}
.category-head {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px;
  cursor: pointer; user-select: none;
  background: var(--surface);
  border-bottom: 1px solid transparent;
  transition: background 120ms, border-color 120ms;
}
.category-head:hover { background: var(--surface-2); }
.category.open .category-head { border-bottom-color: var(--border); }
.category-name { font-weight: 600; font-size: 13.5px; letter-spacing: -0.01em; }
.category-counts { margin-left: auto; display: flex; gap: 5px; font-size: 11px; }
.category-counts .pill {
  padding: 1px 8px; border-radius: 999px;
  font-variant-numeric: tabular-nums; font-weight: 600;
  background: color-mix(in srgb, var(--text) 8%, transparent);
  color: var(--muted);
}
.category-counts .pill.ok { color: var(--ok); background: color-mix(in srgb, var(--ok) 14%, transparent); }
.category-counts .pill.warn { color: var(--warn); background: color-mix(in srgb, var(--warn) 14%, transparent); }
.category-counts .pill.critical { color: var(--crit); background: color-mix(in srgb, var(--crit) 14%, transparent); }
.category-chevron {
  width: 16px; height: 16px;
  stroke: var(--muted); fill: none; stroke-width: 1.8;
  stroke-linecap: round; stroke-linejoin: round;
  transition: transform 200ms;
}
.category.open .category-chevron { transform: rotate(90deg); }

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 10px;
  padding: 12px;
}
.category:not(.open) .cards { display: none; }

/* ---------- Card ---------- */
.card {
  position: relative;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  padding: 11px 14px 11px 18px;
  cursor: pointer;
  transition: border-color 120ms, transform 80ms;
}
.card:hover { border-color: color-mix(in srgb, var(--accent) 35%, var(--border)); }
.card:active { transform: translateY(1px); }
.card::before {
  content: '';
  position: absolute; inset: 0 auto 0 0;
  width: 3px; border-radius: 10px 0 0 10px;
  background: var(--unknown);
}
.card[data-status="ok"]::before { background: var(--ok); }
.card[data-status="warn"]::before { background: var(--warn); }
.card[data-status="critical"]::before { background: var(--crit); }
.card[data-changed="true"] { animation: flash 2.4s ease-out; }
@keyframes flash {
  0% { box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 50%, transparent); }
  100% { box-shadow: 0 0 0 0 transparent; }
}

.card-top { display: flex; align-items: center; gap: 8px; }
.card-name {
  font-weight: 600; font-size: 13.5px; letter-spacing: -0.01em;
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.latency {
  font-size: 10.5px; color: var(--muted);
  font-variant-numeric: tabular-nums; font-family: var(--font-mono);
  background: var(--surface-2);
  padding: 2px 6px; border-radius: 4px;
  flex-shrink: 0;
}
.card-msg { margin-top: 4px; font-size: 12.5px; color: var(--muted); word-break: break-word; }
.card[data-status="critical"] .card-msg { color: color-mix(in srgb, var(--crit) 55%, var(--text)); }

.details {
  margin-top: 10px; padding-top: 10px;
  border-top: 1px dashed var(--border);
  display: none;
}
.card[aria-expanded="true"] .details { display: block; }
.details pre {
  margin: 0;
  font-family: var(--font-mono); font-size: 11.5px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  padding: 8px 10px;
  border-radius: 6px;
  white-space: pre-wrap; word-break: break-word;
  color: var(--text);
  max-height: 280px; overflow: auto;
}
.details .empty { color: var(--muted); font-style: italic; font-size: 12px; }

/* ---------- Skeleton ---------- */
.skel-row { padding: 12px; display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 10px; }
.skel-card {
  border: 1px solid var(--border); border-radius: 10px;
  padding: 14px; height: 72px;
  position: relative; overflow: hidden;
  background: var(--surface);
}
.skel-card::after {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--text) 7%, transparent), transparent);
  animation: shimmer 1.4s infinite;
}
@keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }

/* ---------- States ---------- */
.empty-state {
  border: 1px dashed var(--border); border-radius: 12px;
  padding: 40px 20px; text-align: center; color: var(--muted);
}
.error-state {
  border: 1px solid color-mix(in srgb, var(--crit) 50%, var(--border));
  background: color-mix(in srgb, var(--crit) 8%, var(--surface));
  border-radius: 12px;
  padding: 14px 18px;
  margin-bottom: 16px;
  display: none;
}
.error-state.visible { display: block; }
.error-state code { font-family: var(--font-mono); font-size: 12px; color: var(--crit); }

/* ---------- Footer ---------- */
.footer {
  margin-top: 32px; padding-top: 18px;
  border-top: 1px solid var(--border);
  text-align: center; color: var(--muted); font-size: 11.5px;
}
.footer a { color: var(--muted); text-decoration: none; }
.footer a:hover { color: var(--text); }
.footer kbd {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 4px; padding: 1px 6px;
  font: inherit; font-family: var(--font-mono); font-size: 10.5px; color: var(--muted);
}

@media (max-width: 720px) {
  .shell { padding: 16px 12px 40px; }
  .banner { grid-template-columns: 1fr; gap: 14px; text-align: left; }
  .last-check { text-align: left; }
  .stat-strip { flex-wrap: wrap; gap: 14px; }
  .overall-text { font-size: 20px; }
  .search { max-width: none; }
}
@media (prefers-reduced-motion: reduce) {
  *, ::before, ::after { animation: none !important; transition: none !important; }
}
</style>
</head>
<body>
<div class="shell">

  <div class="header">
    <div class="brand">
      <div class="brand-mark">&#x1FA7A;</div>
      <div>
        <div class="brand-title">Doctor Noshy</div>
        <div class="brand-sub">Hermes Agent health monitor</div>
      </div>
    </div>
    <div class="header-actions">
      <button class="icon-btn" id="refresh" title="Refresh (R)" aria-label="Refresh">
        <svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>
      </button>
      <button class="icon-btn" id="theme" title="Toggle theme" aria-label="Toggle theme">
        <svg viewBox="0 0 24 24" id="theme-icon"></svg>
      </button>
    </div>
  </div>

  <div class="error-state" id="error"></div>

  <div class="banner" id="banner" data-overall="unknown">
    <div class="overall-status">
      <span class="status-dot unknown" id="overall-dot"></span>
      <span class="overall-text" id="overall-text">Loading</span>
    </div>
    <div class="stat-strip" id="stats"></div>
    <div class="last-check" id="last-check">
      <span class="relative" id="relative-time">--</span>
      <span id="absolute-time"></span>
    </div>
  </div>

  <div class="toolbar">
    <div class="chips" id="chips">
      <button class="chip" data-filter="all" aria-pressed="true">All <span class="badge" id="badge-all">0</span></button>
      <button class="chip" data-filter="critical" aria-pressed="false">Critical <span class="badge" id="badge-critical">0</span></button>
      <button class="chip" data-filter="warn" aria-pressed="false">Warn <span class="badge" id="badge-warn">0</span></button>
      <button class="chip" data-filter="ok" aria-pressed="false">OK <span class="badge" id="badge-ok">0</span></button>
      <button class="chip" data-filter="unknown" aria-pressed="false">Unknown <span class="badge" id="badge-unknown">0</span></button>
    </div>
    <div class="search">
      <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      <input id="search" type="search" placeholder="Search checks..." autocomplete="off" spellcheck="false">
      <kbd>/</kbd>
    </div>
    <select class="interval" id="interval" title="Auto-refresh interval">
      <option value="0">Manual</option>
      <option value="10">10s</option>
      <option value="30" selected>30s</option>
      <option value="60">1m</option>
      <option value="300">5m</option>
    </select>
    <a class="raw-link" href="/api/status" target="_blank" rel="noopener">Raw JSON</a>
  </div>

  <div id="categories">
    <div class="category open">
      <div class="category-head">
        <svg class="category-chevron" viewBox="0 0 24 24"><path d="m9 18 6-6-6-6"/></svg>
        <div class="category-name">Loading checks</div>
      </div>
      <div class="cards skel-row">
        <div class="skel-card"></div><div class="skel-card"></div><div class="skel-card"></div>
        <div class="skel-card"></div><div class="skel-card"></div><div class="skel-card"></div>
      </div>
    </div>
  </div>

  <div class="footer">
    Press <kbd>/</kbd> to search, <kbd>R</kbd> to refresh
    &middot;
    <a href="https://github.com/Noshkoto/DoctorNoshy" target="_blank" rel="noopener">github.com/Noshkoto/DoctorNoshy</a>
  </div>
</div>

<script>
'use strict';

const CATEGORY_ORDER = ['Gateway & Network', 'Providers', 'System', 'Dashboard', 'Hermes', 'Kanban', 'Other'];
const STATUS_RANK = { critical: 0, warn: 1, unknown: 2, ok: 3 };

const els = {
  banner: document.getElementById('banner'),
  overallDot: document.getElementById('overall-dot'),
  overallText: document.getElementById('overall-text'),
  stats: document.getElementById('stats'),
  relativeTime: document.getElementById('relative-time'),
  absoluteTime: document.getElementById('absolute-time'),
  categories: document.getElementById('categories'),
  search: document.getElementById('search'),
  chips: document.getElementById('chips'),
  interval: document.getElementById('interval'),
  refresh: document.getElementById('refresh'),
  theme: document.getElementById('theme'),
  themeIcon: document.getElementById('theme-icon'),
  error: document.getElementById('error'),
};

let filterStatus = 'all';
let searchTerm = '';
let lastData = null;
let lastTimestamp = null;
let lastStatuses = {};
const changeTimes = {};
let pollTimer = null;
let pendingFetch = false;
let collapsed = {};
try { collapsed = JSON.parse(localStorage.getItem('dn-collapsed') || '{}'); } catch (e) { collapsed = {}; }
const expanded = new Set();

function categorize(name) {
  if (name.startsWith('Kanban')) return 'Kanban';
  if (name.startsWith('Gateway') || name === 'Tunnel') return 'Gateway & Network';
  if (name.startsWith('Dashboard')) return 'Dashboard';
  if (name === 'Nous Portal' || name === 'OpenRouter' || name === 'Local API Server') return 'Providers';
  if (name === 'CPU Usage' || name === 'Memory' || name === 'Disk Space') return 'System';
  if (['Config File', 'Auth Store', 'Skills', 'Memory Files', 'Cron Jobs'].includes(name)) return 'Hermes';
  return 'Other';
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
  ));
}

function relTime(iso) {
  if (!iso) return '--';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 5) return 'just now';
  if (diff < 60) return Math.floor(diff) + 's ago';
  if (diff < 3600) return Math.floor(diff/60) + 'm ago';
  return Math.floor(diff/3600) + 'h ago';
}

function setTheme(theme) {
  if (theme === 'system') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', theme);
  try { localStorage.setItem('dn-theme', theme); } catch (e) {}
  updateThemeIcon(theme);
}

function cycleTheme() {
  const order = ['system', 'light', 'dark'];
  let cur = 'system';
  try { cur = localStorage.getItem('dn-theme') || 'system'; } catch (e) {}
  setTheme(order[(order.indexOf(cur) + 1) % order.length]);
}

function updateThemeIcon(theme) {
  // System: half-disc. Light: sun. Dark: moon.
  let svg = '';
  if (theme === 'dark') {
    svg = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
  } else if (theme === 'light') {
    svg = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>';
  } else {
    svg = '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor" stroke="none"/>';
  }
  els.themeIcon.innerHTML = svg;
}

function renderStats(counts) {
  const order = ['ok', 'warn', 'critical', 'unknown'];
  els.stats.innerHTML = order.map(k => `
    <div class="stat ${k}">
      <div class="stat-num">${counts[k] || 0}</div>
      <div class="stat-label">${k}</div>
    </div>
  `).join('');
}

function renderBadges(counts, total) {
  document.getElementById('badge-all').textContent = total;
  document.getElementById('badge-critical').textContent = counts.critical || 0;
  document.getElementById('badge-warn').textContent = counts.warn || 0;
  document.getElementById('badge-ok').textContent = counts.ok || 0;
  document.getElementById('badge-unknown').textContent = counts.unknown || 0;
}

function setOverall(overall) {
  els.banner.setAttribute('data-overall', overall);
  els.overallDot.className = 'status-dot ' + overall;
  els.overallText.textContent =
    overall === 'ok' ? 'All systems healthy' :
    overall === 'warn' ? 'Degraded' :
    overall === 'critical' ? 'Critical' :
    'Unknown';
}

function cardHtml(c) {
  const recentlyChanged = changeTimes[c.name] && (Date.now() - changeTimes[c.name]) < 2500;
  const isExpanded = expanded.has(c.name);
  const hasDetails = c.details && Object.keys(c.details).length > 0;
  const detailsInner = hasDetails
    ? `<pre>${esc(JSON.stringify(c.details, null, 2))}</pre>`
    : `<span class="empty">No additional details</span>`;
  const lat = (typeof c.elapsed_ms === 'number' ? c.elapsed_ms : 0).toFixed(0);
  return `
    <div class="card" data-status="${esc(c.status)}" data-name="${esc(c.name)}"${recentlyChanged ? ' data-changed="true"' : ''} aria-expanded="${isExpanded ? 'true' : 'false'}">
      <div class="card-top">
        <div class="card-name" title="${esc(c.name)}">${esc(c.name)}</div>
        <span class="latency">${lat}ms</span>
      </div>
      <div class="card-msg">${esc(c.message)}</div>
      <div class="details">${detailsInner}</div>
    </div>
  `;
}

function renderChecks(checks) {
  const groups = {};
  for (const c of checks) {
    const cat = categorize(c.name);
    (groups[cat] = groups[cat] || []).push(c);
  }

  // Apply filter + search
  const term = searchTerm.trim().toLowerCase();
  const visibleByCat = {};
  let totalVisible = 0;
  for (const cat of Object.keys(groups)) {
    const filtered = groups[cat].filter(c => {
      if (filterStatus !== 'all' && c.status !== filterStatus) return false;
      if (term && !(c.name.toLowerCase().includes(term) || c.message.toLowerCase().includes(term))) return false;
      return true;
    });
    if (filtered.length) {
      visibleByCat[cat] = filtered;
      totalVisible += filtered.length;
    }
  }

  if (totalVisible === 0) {
    els.categories.innerHTML = `<div class="empty-state">No checks match your filter.</div>`;
    return;
  }

  // Include any unseen categories at the end of CATEGORY_ORDER
  const seenCats = new Set();
  const orderedCats = [];
  for (const c of CATEGORY_ORDER) {
    if (visibleByCat[c]) { orderedCats.push(c); seenCats.add(c); }
  }
  for (const c of Object.keys(visibleByCat)) {
    if (!seenCats.has(c)) orderedCats.push(c);
  }

  const html = orderedCats.map(cat => {
    const items = visibleByCat[cat].slice().sort((a, b) => {
      const ra = STATUS_RANK[a.status]; const rb = STATUS_RANK[b.status];
      const r = (ra == null ? 9 : ra) - (rb == null ? 9 : rb);
      return r !== 0 ? r : a.name.localeCompare(b.name);
    });
    const catCounts = items.reduce((acc, c) => { acc[c.status] = (acc[c.status]||0)+1; return acc; }, {});
    const isOpen = !collapsed[cat];
    const pills = ['critical','warn','ok','unknown']
      .filter(s => catCounts[s])
      .map(s => `<span class="pill ${s}">${catCounts[s]} ${s}</span>`)
      .join('');
    return `
      <div class="category${isOpen ? ' open' : ''}" data-cat="${esc(cat)}">
        <div class="category-head" data-toggle="${esc(cat)}">
          <svg class="category-chevron" viewBox="0 0 24 24"><path d="m9 18 6-6-6-6"/></svg>
          <div class="category-name">${esc(cat)}</div>
          <div class="category-counts">${pills}</div>
        </div>
        <div class="cards">${items.map(cardHtml).join('')}</div>
      </div>
    `;
  }).join('');

  els.categories.innerHTML = html;

  els.categories.querySelectorAll('.category-head').forEach(h => {
    h.addEventListener('click', () => {
      const cat = h.dataset.toggle;
      const node = h.closest('.category');
      if (node.classList.contains('open')) { node.classList.remove('open'); collapsed[cat] = true; }
      else { node.classList.add('open'); delete collapsed[cat]; }
      try { localStorage.setItem('dn-collapsed', JSON.stringify(collapsed)); } catch (e) {}
    });
  });

  els.categories.querySelectorAll('.card').forEach(card => {
    card.addEventListener('click', () => {
      const name = card.dataset.name;
      const isOpen = card.getAttribute('aria-expanded') === 'true';
      card.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
      if (isOpen) expanded.delete(name); else expanded.add(name);
    });
  });
}

function reRender() {
  if (!lastData) return;
  renderChecks(lastData.checks);
}

async function fetchStatus() {
  if (pendingFetch) return;
  pendingFetch = true;
  els.refresh.classList.add('spinning');
  try {
    const resp = await fetch('/api/status', { cache: 'no-store' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    els.error.classList.remove('visible');

    // Diff vs last
    for (const c of data.checks) {
      const prev = lastStatuses[c.name];
      if (prev !== undefined && prev !== c.status) changeTimes[c.name] = Date.now();
      lastStatuses[c.name] = c.status;
    }

    lastData = data;
    lastTimestamp = data.timestamp;
    setOverall(data.summary.overall);
    renderStats(data.summary.counts);
    renderBadges(data.summary.counts, data.summary.total);
    renderChecks(data.checks);
    els.absoluteTime.textContent = new Date(data.timestamp).toLocaleTimeString();
    updateRelativeTime();
  } catch (e) {
    els.error.innerHTML = 'Failed to fetch status: <code>' + esc(e.message) + '</code>';
    els.error.classList.add('visible');
  } finally {
    pendingFetch = false;
    setTimeout(() => els.refresh.classList.remove('spinning'), 700);
  }
}

function updateRelativeTime() {
  els.relativeTime.textContent = relTime(lastTimestamp);
}

function setupAutoRefresh() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  const seconds = parseInt(els.interval.value, 10);
  if (seconds > 0) pollTimer = setInterval(fetchStatus, seconds * 1000);
  try { localStorage.setItem('dn-interval', String(seconds)); } catch (e) {}
}

// ---- init ----
(function init() {
  let savedTheme = 'system';
  try { savedTheme = localStorage.getItem('dn-theme') || 'system'; } catch (e) {}
  setTheme(savedTheme);

  try {
    const savedInterval = localStorage.getItem('dn-interval');
    if (savedInterval !== null) els.interval.value = savedInterval;
  } catch (e) {}

  els.theme.addEventListener('click', cycleTheme);
  els.refresh.addEventListener('click', fetchStatus);
  els.interval.addEventListener('change', setupAutoRefresh);
  els.search.addEventListener('input', e => {
    searchTerm = e.target.value;
    reRender();
  });
  els.chips.addEventListener('click', e => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    filterStatus = chip.dataset.filter;
    els.chips.querySelectorAll('.chip').forEach(c => {
      c.setAttribute('aria-pressed', String(c === chip));
    });
    reRender();
  });

  document.addEventListener('keydown', e => {
    const tag = (e.target.tagName || '').toUpperCase();
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
    if (e.key === '/') { e.preventDefault(); els.search.focus(); els.search.select(); }
    else if (e.key === 'r' || e.key === 'R') { e.preventDefault(); fetchStatus(); }
  });

  setInterval(updateRelativeTime, 5000);

  fetchStatus();
  setupAutoRefresh();
})();
</script>
</body>
</html>
"""
