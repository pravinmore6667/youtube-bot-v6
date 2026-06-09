"""
dashboard/app.py
─────────────────
FastAPI + Bootstrap 5 admin dashboard.

Pages:
  /            → System overview (health, queue, stats)
  /providers   → AI provider monitoring
  /outputs     → Generated videos, scripts, content
  /library     → Content reuse library
  /settings    → All configurable settings
  /logs        → Full log viewer

API:
  /api/status  → JSON system health
  /api/jobs    → Recent jobs
  /api/queue   → Queue stats
  /stream/logs → SSE live log stream
  /api/run     → Trigger manual video generation
  /api/stop    → Stop running job
  /api/retry   → Retry failed job
"""

import os, json, time, threading, queue, psutil
from datetime import datetime
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from database import db
from config import config, load_live_config
from utils.logger import get_logger

log = get_logger("Dashboard")

app = FastAPI(title="YouTube AI Bot Dashboard", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# ── SSE broadcaster ───────────────────────────────────────────
_sse_queues: list[queue.Queue] = []
_sse_lock   = threading.Lock()


def broadcast_log(msg: dict):
    with _sse_lock:
        dead = []
        for q in _sse_queues:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_queues.remove(q)


# ── Running job tracking ──────────────────────────────────────
_running_job_thread: threading.Thread = None
_stop_event = threading.Event()


# ── HTML ──────────────────────────────────────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YouTube AI Bot — Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
<style>
:root {
  --brand: #7c3aed;
  --brand-glow: #a855f780;
  --surface: #0f0f1a;
  --surface2: #161628;
  --surface3: #1e1e38;
  --text-muted: #8b8baa;
  --success-col: #22c55e;
  --danger-col: #ef4444;
  --warning-col: #f59e0b;
  --info-col: #3b82f6;
}
body { background: var(--surface); font-family: 'Segoe UI', system-ui, sans-serif; }
.sidebar {
  width: 220px; min-height: 100vh; background: var(--surface2);
  border-right: 1px solid #ffffff10; position: fixed; top: 0; left: 0;
  z-index: 100; padding-top: 1rem;
}
.sidebar .brand {
  padding: .75rem 1.25rem; font-size: 1rem; font-weight: 700;
  color: #fff; display: flex; align-items: center; gap: .5rem;
  border-bottom: 1px solid #ffffff10; margin-bottom: .5rem;
}
.sidebar .brand .badge { background: var(--brand); font-size: .6rem; }
.sidebar .nav-link {
  color: var(--text-muted); padding: .55rem 1.25rem;
  border-radius: .5rem; margin: .1rem .5rem;
  transition: all .15s; font-size: .88rem; display: flex; align-items: center; gap: .6rem;
}
.sidebar .nav-link:hover { color: #fff; background: var(--surface3); }
.sidebar .nav-link.active { color: #fff; background: var(--brand); }
.sidebar .nav-link .bi { font-size: 1rem; width: 1.1rem; }
.main-content { margin-left: 220px; padding: 1.5rem; }
.stat-card {
  background: var(--surface2); border: 1px solid #ffffff0f;
  border-radius: 1rem; padding: 1.25rem; transition: border-color .2s;
}
.stat-card:hover { border-color: var(--brand-glow); }
.stat-card .number { font-size: 2rem; font-weight: 700; line-height: 1; }
.stat-card .label { color: var(--text-muted); font-size: .8rem; margin-top: .25rem; }
.stat-card .icon { font-size: 2rem; opacity: .25; }
.provider-card {
  background: var(--surface2); border: 1px solid #ffffff0f;
  border-radius: .875rem; padding: 1rem 1.25rem;
}
.health-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.health-dot.ok      { background: var(--success-col); box-shadow: 0 0 6px var(--success-col); }
.health-dot.warning { background: var(--warning-col); box-shadow: 0 0 6px var(--warning-col); }
.health-dot.error   { background: var(--danger-col);  box-shadow: 0 0 6px var(--danger-col); }
.health-dot.off     { background: #444; }
.log-container {
  background: #0a0a14; border: 1px solid #ffffff0f; border-radius: .875rem;
  height: 380px; overflow-y: auto; font-family: 'Cascadia Code','JetBrains Mono','Fira Code',monospace;
  font-size: .75rem; padding: .75rem 1rem;
}
.log-line { margin: 0; padding: .1rem 0; border-bottom: 1px solid #ffffff05; }
.log-line.ERROR   { color: #fca5a5; }
.log-line.WARNING { color: #fcd34d; }
.log-line.INFO    { color: #93c5fd; }
.log-line.DEBUG   { color: #9ca3af; }
.log-line.SUCCESS { color: #86efac; }
.log-ts   { color: #6b7280; margin-right: .35rem; }
.log-agent { color: #c084fc; margin-right: .35rem; font-weight: 600; }
.badge-status { font-size: .7rem; padding: .3em .6em; border-radius: .4em; }
.badge-running { background: var(--info-col); }
.badge-success { background: var(--success-col); }
.badge-failed  { background: var(--danger-col); }
.badge-queued  { background: #6b7280; }
.job-row td { vertical-align: middle; }
.progress-bar-brand { background: var(--brand); }
.page { display: none; }
.page.active { display: block; }
.section-title { font-size: .7rem; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; color: var(--text-muted); margin-bottom: .75rem; }
.action-btn { border-radius: .625rem; font-size: .82rem; font-weight: 600;
  padding: .45rem 1rem; }
.metric-bar { height: 6px; border-radius: 3px; background: #ffffff15; overflow: hidden; }
.metric-fill { height: 100%; border-radius: 3px; transition: width .4s; }
.toast-container { position: fixed; top: 1rem; right: 1rem; z-index: 9999; }
</style>
</head>
<body>

<!-- Sidebar -->
<nav class="sidebar">
  <div class="brand">
    <i class="bi bi-robot"></i>
    YT AI Bot
    <span class="badge rounded-pill">v4</span>
  </div>
  <ul class="nav flex-column">
    <li><a class="nav-link active" onclick="showPage('overview')" href="#"><i class="bi bi-grid-1x2"></i> Overview</a></li>
    <li><a class="nav-link" onclick="showPage('providers')" href="#"><i class="bi bi-cpu"></i> Providers</a></li>
    <li><a class="nav-link" onclick="showPage('queue')" href="#"><i class="bi bi-list-task"></i> Jobs & Queue</a></li>
    <li><a class="nav-link" onclick="showPage('outputs')" href="#"><i class="bi bi-play-circle"></i> Outputs</a></li>
    <li><a class="nav-link" onclick="showPage('library')" href="#"><i class="bi bi-archive"></i> Library</a></li>
    <li><a class="nav-link" onclick="showPage('logs')" href="#"><i class="bi bi-terminal"></i> Live Logs</a></li>
    <li><a class="nav-link" onclick="showPage('settings')" href="#"><i class="bi bi-gear"></i> Settings</a></li>
  </ul>
  <div class="px-3 py-2 mt-auto" style="position:absolute;bottom:1rem;left:0;right:0">
    <div class="text-muted" style="font-size:.72rem">
      <div id="sys-cpu">CPU: —</div>
      <div id="sys-mem">RAM: —</div>
      <div id="sys-disk">Disk: —</div>
    </div>
  </div>
</nav>

<!-- Toast container -->
<div class="toast-container" id="toasts"></div>

<!-- Main -->
<div class="main-content">

<!-- ═══ OVERVIEW ═══ -->
<div class="page active" id="page-overview">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h5 class="mb-0 fw-bold">System Overview</h5>
      <small class="text-muted" id="last-updated">—</small>
    </div>
    <div class="d-flex gap-2">
      <button class="btn btn-success action-btn" onclick="triggerRun()">
        <i class="bi bi-play-fill"></i> Run Now
      </button>
      <button class="btn btn-outline-secondary action-btn" onclick="refresh()">
        <i class="bi bi-arrow-clockwise"></i>
      </button>
    </div>
  </div>

  <!-- Quick stats -->
  <div class="row g-3 mb-3">
    <div class="col-6 col-lg-3">
      <div class="stat-card d-flex justify-content-between align-items-start">
        <div>
          <div class="number text-success" id="stat-total">—</div>
          <div class="label">Videos Made</div>
        </div>
        <div class="icon"><i class="bi bi-camera-video text-success"></i></div>
      </div>
    </div>
    <div class="col-6 col-lg-3">
      <div class="stat-card d-flex justify-content-between align-items-start">
        <div>
          <div class="number text-primary" id="stat-running">—</div>
          <div class="label">Running</div>
        </div>
        <div class="icon"><i class="bi bi-lightning text-primary"></i></div>
      </div>
    </div>
    <div class="col-6 col-lg-3">
      <div class="stat-card d-flex justify-content-between align-items-start">
        <div>
          <div class="number text-info" id="stat-views">—</div>
          <div class="label">Total Views</div>
        </div>
        <div class="icon"><i class="bi bi-eye text-info"></i></div>
      </div>
    </div>
    <div class="col-6 col-lg-3">
      <div class="stat-card d-flex justify-content-between align-items-start">
        <div>
          <div class="number text-warning" id="stat-failed">—</div>
          <div class="label">Failed Jobs</div>
        </div>
        <div class="icon"><i class="bi bi-exclamation-triangle text-warning"></i></div>
      </div>
    </div>
  </div>

  <!-- Active provider + cache -->
  <div class="row g-3 mb-3">
    <div class="col-md-4">
      <div class="stat-card">
        <div class="section-title">Active Provider</div>
        <div class="d-flex align-items-center gap-2">
          <span class="health-dot ok" id="prov-dot"></span>
          <span class="fw-bold" id="active-prov">—</span>
        </div>
        <div class="text-muted mt-1" style="font-size:.8rem" id="prov-score">Health: —</div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="stat-card">
        <div class="section-title">Cache Today</div>
        <div class="fw-bold text-success" id="cache-rate">—% hit rate</div>
        <div class="text-muted mt-1" style="font-size:.8rem" id="cache-detail">—</div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="stat-card">
        <div class="section-title">Library</div>
        <div class="fw-bold" id="lib-total">—</div>
        <div class="text-muted mt-1" style="font-size:.8rem" id="lib-detail">—</div>
      </div>
    </div>
  </div>

  <!-- Live log mini -->
  <div class="stat-card mb-3">
    <div class="d-flex justify-content-between align-items-center mb-2">
      <div class="section-title mb-0">Live Logs</div>
      <button class="btn btn-sm btn-outline-secondary" onclick="showPage('logs')">
        Full logs <i class="bi bi-arrow-right"></i>
      </button>
    </div>
    <div class="log-container" id="mini-log" style="height:200px;"></div>
  </div>

  <!-- Recent jobs -->
  <div class="stat-card">
    <div class="section-title">Recent Jobs</div>
    <div class="table-responsive">
      <table class="table table-sm table-dark mb-0" style="font-size:.83rem">
        <thead><tr>
          <th>Topic</th><th>Status</th><th>Started</th><th>Duration</th><th>Actions</th>
        </tr></thead>
        <tbody id="jobs-table">
          <tr><td colspan="5" class="text-muted text-center py-3">Loading...</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- ═══ PROVIDERS ═══ -->
<div class="page" id="page-providers">
  <h5 class="mb-3 fw-bold">AI Provider Monitoring</h5>
  <div class="row g-3" id="provider-cards">
    <!-- populated by JS -->
  </div>
  <div class="mt-3 stat-card">
    <div class="section-title">Token Usage</div>
    <div id="token-chart" style="font-size:.85rem"></div>
  </div>
</div>

<!-- ═══ QUEUE ═══ -->
<div class="page" id="page-queue">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h5 class="mb-0 fw-bold">Jobs & Queue</h5>
    <div class="d-flex gap-2">
      <input class="form-control form-control-sm" id="manual-topic"
             placeholder="Optional topic..." style="width:220px">
      <button class="btn btn-success action-btn" onclick="triggerRun()">
        <i class="bi bi-play-fill"></i> Start
      </button>
      <button class="btn btn-warning action-btn" onclick="stopJob()">
        <i class="bi bi-stop-fill"></i> Stop
      </button>
    </div>
  </div>
  <div class="stat-card">
    <div class="table-responsive">
      <table class="table table-dark table-hover mb-0" style="font-size:.83rem">
        <thead><tr>
          <th>ID</th><th>Topic</th><th>Niche</th><th>Status</th>
          <th>Started</th><th>Duration</th><th>Actions</th>
        </tr></thead>
        <tbody id="queue-table">
          <tr><td colspan="7" class="text-muted text-center py-3">Loading...</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- ═══ OUTPUTS ═══ -->
<div class="page" id="page-outputs">
  <h5 class="mb-3 fw-bold">Generated Outputs</h5>
  <div class="row g-3" id="outputs-grid">
    <div class="col-12 text-muted text-center py-4">Loading...</div>
  </div>
</div>

<!-- ═══ LIBRARY ═══ -->
<div class="page" id="page-library">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h5 class="mb-0 fw-bold">Content Library</h5>
    <input class="form-control form-control-sm w-auto" id="lib-search"
           placeholder="Search..." oninput="searchLibrary()">
  </div>
  <div class="row g-3 mb-3">
    <div class="col-md-3">
      <div class="stat-card text-center">
        <div class="number" id="lib-total2">—</div>
        <div class="label">Total Entries</div>
      </div>
    </div>
    <div class="col-md-3">
      <div class="stat-card text-center">
        <div class="number text-success" id="lib-facts">—</div>
        <div class="label">Research Facts</div>
      </div>
    </div>
    <div class="col-md-3">
      <div class="stat-card text-center">
        <div class="number text-info" id="lib-scripts">—</div>
        <div class="label">Scripts</div>
      </div>
    </div>
    <div class="col-md-3">
      <div class="stat-card text-center">
        <div class="number text-warning" id="lib-niches">—</div>
        <div class="label">Niches Covered</div>
      </div>
    </div>
  </div>
  <div class="stat-card">
    <div class="table-responsive">
      <table class="table table-dark table-sm mb-0" style="font-size:.82rem">
        <thead><tr><th>Topic</th><th>Type</th><th>Niche</th><th>Words</th><th>Reused</th><th>Created</th></tr></thead>
        <tbody id="lib-table">
          <tr><td colspan="6" class="text-muted text-center py-3">Loading...</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- ═══ LOGS ═══ -->
<div class="page" id="page-logs">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h5 class="mb-0 fw-bold">Live Logs</h5>
    <div class="d-flex gap-2 align-items-center">
      <select class="form-select form-select-sm w-auto" id="log-level-filter" onchange="filterLogs()">
        <option value="">All levels</option>
        <option value="ERROR">ERROR</option>
        <option value="WARNING">WARNING</option>
        <option value="INFO">INFO</option>
        <option value="DEBUG">DEBUG</option>
      </select>
      <button class="btn btn-sm btn-outline-secondary" onclick="clearLogs()">
        <i class="bi bi-trash"></i>
      </button>
      <div class="health-dot ok" id="sse-dot" title="SSE connected"></div>
    </div>
  </div>
  <div class="stat-card p-0">
    <div class="log-container" id="full-log" style="height:65vh; border-radius:.875rem;"></div>
  </div>
</div>

<!-- ═══ SETTINGS ═══ -->
<div class="page" id="page-settings">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h5 class="mb-0 fw-bold">Settings</h5>
    <button class="btn btn-success action-btn" onclick="saveSettings()">
      <i class="bi bi-check2-circle"></i> Save All
    </button>
  </div>

  <div class="row g-3">
    <div class="col-md-6">
      <div class="stat-card">
        <div class="section-title">Channel</div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size:.8rem">Channel Name</label>
          <input class="form-control form-control-sm" id="s-name" placeholder="My Channel">
        </div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size:.8rem">Niche</label>
          <select class="form-select form-select-sm" id="s-niche">
            <option>technology</option><option>finance</option><option>science</option>
            <option>history</option><option>health</option><option>gaming</option>
            <option>motivation</option><option>business</option><option>documentary</option>
            <option>news</option><option>education</option>
          </select>
        </div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size:.8rem">Language</label>
          <select class="form-select form-select-sm" id="s-lang">
            <option value="en">English</option>
            <option value="hi">Hindi</option>
          </select>
        </div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size:.8rem">Tone</label>
          <input class="form-control form-control-sm" id="s-tone" placeholder="engaging and informative">
        </div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size:.8rem">Target Audience</label>
          <input class="form-control form-control-sm" id="s-audience" placeholder="general audience">
        </div>
      </div>
    </div>

    <div class="col-md-6">
      <div class="stat-card mb-3">
        <div class="section-title">Schedule</div>
        <div class="row g-2">
          <div class="col">
            <label class="form-label text-muted" style="font-size:.8rem">Upload Hour (UTC)</label>
            <input type="number" class="form-control form-control-sm" id="s-hour" min="0" max="23">
          </div>
          <div class="col">
            <label class="form-label text-muted" style="font-size:.8rem">Minute</label>
            <input type="number" class="form-control form-control-sm" id="s-minute" min="0" max="59">
          </div>
        </div>
        <div class="mt-2">
          <label class="form-label text-muted" style="font-size:.8rem">Voice Gender</label>
          <select class="form-select form-select-sm" id="s-voice">
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
        </div>
      </div>

      <div class="stat-card">
        <div class="section-title">Script & Quality</div>
        <div class="row g-2 mb-2">
          <div class="col">
            <label class="form-label text-muted" style="font-size:.8rem">Min Words</label>
            <input type="number" class="form-control form-control-sm" id="s-wmin" value="800">
          </div>
          <div class="col">
            <label class="form-label text-muted" style="font-size:.8rem">Max Words</label>
            <input type="number" class="form-control form-control-sm" id="s-wmax" value="1200">
          </div>
        </div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size:.8rem">Provider Order</label>
          <input class="form-control form-control-sm" id="s-providers" placeholder="gemini,groq,mistral,grok">
        </div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size:.8rem">Log Level</label>
          <select class="form-select form-select-sm" id="s-loglevel">
            <option>INFO</option><option>DEBUG</option>
            <option>WARNING</option><option>ERROR</option>
          </select>
        </div>
        <div class="form-check form-switch mt-2">
          <input class="form-check-input" type="checkbox" id="s-cache" checked>
          <label class="form-check-label text-muted" style="font-size:.8rem">Enable Caching</label>
        </div>
        <div class="form-check form-switch">
          <input class="form-check-input" type="checkbox" id="s-music" checked>
          <label class="form-check-label text-muted" style="font-size:.8rem">Background Music</label>
        </div>
      </div>
    </div>

    <div class="col-12">
      <div class="stat-card">
        <div class="section-title">API Keys</div>
        <div class="row g-2">
          <div class="col-md-6">
            <label class="form-label text-muted" style="font-size:.8rem">Groq API Key</label>
            <input type="password" class="form-control form-control-sm" id="s-groq" placeholder="gsk_...">
          </div>
          <div class="col-md-6">
            <label class="form-label text-muted" style="font-size:.8rem">Gemini API Key</label>
            <input type="password" class="form-control form-control-sm" id="s-gemini" placeholder="AIza...">
          </div>
          <div class="col-md-6">
            <label class="form-label text-muted" style="font-size:.8rem">Mistral API Key</label>
            <input type="password" class="form-control form-control-sm" id="s-mistral" placeholder="mistral-...">
          </div>
          <div class="col-md-6">
            <label class="form-label text-muted" style="font-size:.8rem">Grok API Key</label>
            <input type="password" class="form-control form-control-sm" id="s-grok" placeholder="grok-...">
          </div>
        </div>
        <div class="mt-2">
          <button class="btn btn-sm btn-outline-info" onclick="testProviders()">
            <i class="bi bi-lightning-charge"></i> Test All Providers
          </button>
          <span id="test-result" class="ms-2 text-muted" style="font-size:.8rem"></span>
        </div>
      </div>
    </div>
  </div>
</div>

</div><!-- /main-content -->

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
// ── Navigation ─────────────────────────────────────────────
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  event.currentTarget.classList.add('active');
  if (name === 'logs')     startSSE();
  if (name === 'providers') loadProviders();
  if (name === 'outputs')   loadOutputs();
  if (name === 'library')   loadLibrary();
  if (name === 'queue')     loadQueue();
  if (name === 'settings')  loadSettings();
}

// ── Toast ──────────────────────────────────────────────────
function toast(msg, type='info') {
  const id = 'toast-' + Date.now();
  const icons = {success:'check-circle-fill', danger:'x-circle-fill', info:'info-circle-fill', warning:'exclamation-triangle-fill'};
  document.getElementById('toasts').insertAdjacentHTML('beforeend', `
    <div id="${id}" class="toast show align-items-center text-bg-${type} border-0 mb-2" role="alert" style="min-width:240px">
      <div class="d-flex">
        <div class="toast-body"><i class="bi bi-${icons[type]||'info-circle-fill'} me-2"></i>${msg}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" onclick="document.getElementById('${id}').remove()"></button>
      </div>
    </div>`);
  setTimeout(() => { const el = document.getElementById(id); if (el) el.remove(); }, 4000);
}

// ── Main refresh ────────────────────────────────────────────
async function refresh() {
  try {
    const [status, jobs] = await Promise.all([
      fetch('/api/status').then(r => r.json()),
      fetch('/api/jobs').then(r => r.json()),
    ]);
    // Stats
    document.getElementById('stat-total').textContent   = status.stats?.total_videos ?? '—';
    document.getElementById('stat-running').textContent = status.stats?.pending_jobs ?? '—';
    document.getElementById('stat-views').textContent   = fmtNum(status.stats?.total_views ?? 0);
    document.getElementById('stat-failed').textContent  = status.stats?.failed_jobs ?? '—';
    document.getElementById('last-updated').textContent = 'Updated ' + new Date().toLocaleTimeString();
    // Provider
    const prov = status.active_provider || '—';
    document.getElementById('active-prov').textContent = prov.toUpperCase();
    const score = status.providers?.[prov]?.health_score ?? 0;
    document.getElementById('prov-score').textContent = 'Health: ' + Math.round(score * 100) + '%';
    // Cache
    const cs = status.cache || {};
    document.getElementById('cache-rate').textContent = (cs.hit_rate_pct || 0) + '% hit rate';
    document.getElementById('cache-detail').textContent =
      `${cs.today_hits||0} hits · ${cs.today_misses||0} misses · ${cs.total_entries||0} entries`;
    // Library
    const ls = status.library || {};
    document.getElementById('lib-total').textContent = (ls.total_entries || 0) + ' stored items';
    document.getElementById('lib-detail').textContent =
      Object.entries(ls.by_type || {}).map(([k,v]) => `${k}: ${v}`).join(' · ') || '—';
    // System
    const sys = status.system || {};
    document.getElementById('sys-cpu').textContent  = 'CPU: ' + (sys.cpu_pct  || 0) + '%';
    document.getElementById('sys-mem').textContent  = 'RAM: ' + (sys.mem_pct  || 0) + '%';
    document.getElementById('sys-disk').textContent = 'Disk: '+ (sys.disk_pct || 0) + '%';
    // Jobs table
    renderJobsTable(jobs, 'jobs-table', 5);
  } catch(e) { console.error(e); }
}

function fmtNum(n) {
  if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n/1e3).toFixed(1) + 'K';
  return n;
}

function fmtDuration(start, end) {
  if (!start) return '—';
  const s = (new Date(end || Date.now()) - new Date(start)) / 1000;
  if (s < 60) return Math.round(s) + 's';
  return Math.floor(s/60) + 'm ' + (Math.round(s%60)) + 's';
}

function statusBadge(st) {
  const cls = {running:'badge-running', success:'badge-success',
               failed:'badge-failed', queued:'badge-queued'}[st] || 'badge-queued';
  return `<span class="badge badge-status ${cls}">${st}</span>`;
}

function renderJobsTable(jobs, tid, max=20) {
  const tb = document.getElementById(tid);
  if (!jobs.length) { tb.innerHTML = '<tr><td colspan="7" class="text-muted text-center py-3">No jobs yet</td></tr>'; return; }
  tb.innerHTML = jobs.slice(0, max).map(j => {
    const topic = (j.topic || '—').substring(0, 45);
    const dur   = fmtDuration(j.started_at, j.finished_at);
    return `<tr class="job-row">
      <td><code style="font-size:.7rem">${j.id}</code></td>
      <td title="${j.topic||''}">${topic}</td>
      <td><span class="badge bg-secondary" style="font-size:.68rem">${j.niche||'—'}</span></td>
      <td>${statusBadge(j.status)}</td>
      <td style="font-size:.75rem">${(j.started_at||'').replace('T',' ').substring(0,16)}</td>
      <td style="font-size:.75rem">${dur}</td>
      <td>
        ${j.status==='failed'?`<button class="btn btn-xs btn-outline-warning py-0 px-1" onclick="retryJob('${j.id}')"><i class="bi bi-arrow-repeat"></i></button>`:''}
        ${j.video_url?`<a class="btn btn-xs btn-outline-success py-0 px-1 ms-1" href="${j.video_url}" target="_blank"><i class="bi bi-youtube"></i></a>`:''}
      </td>
    </tr>`;
  }).join('');
}

// ── Providers page ──────────────────────────────────────────
async function loadProviders() {
  const status = await fetch('/api/status').then(r => r.json());
  const provs  = status.providers || {};
  const html   = Object.entries(provs).map(([name, p]) => {
    const dot = p.available && !p.in_cooldown ? 'ok' : p.in_cooldown ? 'warning' : 'error';
    const bar = Math.round((p.health_score||0) * 100);
    return `<div class="col-md-6">
      <div class="provider-card">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <div class="d-flex align-items-center gap-2">
            <span class="health-dot ${dot}"></span>
            <span class="fw-bold text-uppercase">${name}</span>
          </div>
          <span class="badge ${p.available?'bg-success':'bg-secondary'}">${p.available?'Active':'Offline'}</span>
        </div>
        ${p.in_cooldown ? `<div class="alert alert-warning py-1 px-2 mb-2" style="font-size:.75rem">⏳ Cooldown: ${p.cooldown_secs}s</div>` : ''}
        <div class="metric-bar mb-1"><div class="metric-fill" style="width:${bar}%;background:${bar>60?'#22c55e':bar>30?'#f59e0b':'#ef4444'}"></div></div>
        <div class="row g-2 mt-1" style="font-size:.78rem;color:#9ca3af">
          <div class="col-6">Requests: <b class="text-white">${p.total_requests||0}</b></div>
          <div class="col-6">Tokens: <b class="text-white">${fmtNum(p.total_tokens||0)}</b></div>
          <div class="col-6">Errors: <b class="${(p.total_errors||0)>0?'text-warning':'text-white'}">${p.total_errors||0}</b></div>
          <div class="col-6">Success: <b class="text-white">${Math.round((p.success_rate||0)*100)}%</b></div>
          <div class="col-6">Latency: <b class="text-white">${(p.last_latency_s||0).toFixed(1)}s</b></div>
          <div class="col-6">Score: <b class="text-white">${bar}%</b></div>
        </div>
        ${p.last_error ? `<div class="mt-2 text-danger" style="font-size:.72rem;word-break:break-all">⚠ ${p.last_error.substring(0,100)}</div>` : ''}
      </div>
    </div>`;
  }).join('');
  document.getElementById('provider-cards').innerHTML = html || '<div class="col-12 text-muted">No providers configured</div>';
  // Token chart
  const rows = Object.entries(provs).map(([n,p]) =>
    `<div class="d-flex align-items-center gap-2 mb-1">
       <div style="width:100px;font-size:.8rem">${n}</div>
       <div class="metric-bar flex-grow-1"><div class="metric-fill" style="width:${Math.min(100,((p.total_tokens||0)/1000).toFixed(1))}%;background:var(--brand)"></div></div>
       <div style="font-size:.78rem;width:60px;text-align:right">${fmtNum(p.total_tokens||0)}</div>
     </div>`).join('');
  document.getElementById('token-chart').innerHTML = rows || '<div class="text-muted">No usage yet</div>';
}

// ── Outputs ─────────────────────────────────────────────────
async function loadOutputs() {
  const videos = await fetch('/api/videos').then(r => r.json());
  if (!videos.length) {
    document.getElementById('outputs-grid').innerHTML = '<div class="col-12 text-muted text-center py-4">No videos yet. Run the pipeline to generate content!</div>';
    return;
  }
  document.getElementById('outputs-grid').innerHTML = videos.map(v => `
    <div class="col-md-6 col-lg-4">
      <div class="stat-card h-100">
        ${v.thumbnail_url ? `<img src="${v.thumbnail_url}" class="img-fluid rounded mb-2" style="width:100%;height:140px;object-fit:cover">` : ''}
        <div class="fw-semibold" style="font-size:.88rem;line-height:1.3">${v.title||'Untitled'}</div>
        <div class="text-muted mt-1 mb-2" style="font-size:.75rem">
          ${v.niche||'—'} · ${v.language||'en'} · ${(v.published_at||'').substring(0,10)}
        </div>
        <div class="d-flex gap-2" style="font-size:.78rem">
          <span><i class="bi bi-eye"></i> ${fmtNum(v.views||0)}</span>
          <span><i class="bi bi-hand-thumbs-up"></i> ${fmtNum(v.likes||0)}</span>
          <span class="ms-auto">${v.verified ? '<span class="text-success">✓ Live</span>' : '<span class="text-warning">⏳ Pending</span>'}</span>
        </div>
        <div class="d-flex gap-1 mt-2">
          ${v.url ? `<a href="${v.url}" target="_blank" class="btn btn-sm btn-outline-danger py-0 flex-fill"><i class="bi bi-youtube"></i></a>` : ''}
          ${v.studio_url ? `<a href="${v.studio_url}" target="_blank" class="btn btn-sm btn-outline-secondary py-0 flex-fill"><i class="bi bi-pencil"></i></a>` : ''}
        </div>
      </div>
    </div>`).join('');
}

// ── Library ─────────────────────────────────────────────────
async function loadLibrary() {
  const [data, stats] = await Promise.all([
    fetch('/api/library?limit=50').then(r => r.json()),
    fetch('/api/library/stats').then(r => r.json()),
  ]);
  document.getElementById('lib-total2').textContent  = stats.total_entries || 0;
  document.getElementById('lib-facts').textContent   = stats.research_facts || 0;
  document.getElementById('lib-scripts').textContent = stats.by_type?.script || 0;
  document.getElementById('lib-niches').textContent  = Object.keys(stats.by_niche||{}).length;
  const rows = (data.items||[]).map(i => `<tr>
    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${i.topic}">${i.topic}</td>
    <td><span class="badge bg-secondary" style="font-size:.68rem">${i.content_type}</span></td>
    <td><span class="badge bg-dark border" style="font-size:.68rem">${i.niche||'—'}</span></td>
    <td>${i.word_count||0}</td>
    <td>${i.reuse_count||0}</td>
    <td style="font-size:.72rem">${(i.created_at||'').substring(0,10)}</td>
  </tr>`).join('');
  document.getElementById('lib-table').innerHTML = rows || '<tr><td colspan="6" class="text-muted text-center py-3">Empty library</td></tr>';
}

async function searchLibrary() {
  const q = document.getElementById('lib-search').value;
  if (!q) return loadLibrary();
  const data = await fetch(`/api/library/search?q=${encodeURIComponent(q)}`).then(r => r.json());
  const rows = (data.items||[]).map(i => `<tr>
    <td>${i.topic}</td><td><span class="badge bg-secondary">${i.content_type}</span></td>
    <td>${i.niche||'—'}</td><td>${i.word_count||0}</td>
    <td>${i.reuse_count||0}</td><td>${(i.created_at||'').substring(0,10)}</td>
  </tr>`).join('');
  document.getElementById('lib-table').innerHTML = rows || '<tr><td colspan="6" class="text-muted text-center">No results</td></tr>';
}

// ── Queue ───────────────────────────────────────────────────
async function loadQueue() {
  const jobs = await fetch('/api/jobs?limit=50').then(r => r.json());
  renderJobsTable(jobs, 'queue-table', 50);
}

// ── Settings ────────────────────────────────────────────────
async function loadSettings() {
  const s = await fetch('/api/settings').then(r => r.json());
  const set = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) { if (el.type==='checkbox') el.checked = val==='true'||val===true; else el.value = val||''; }};
  set('s-name',      s.CHANNEL_NAME);
  set('s-niche',     s.CHANNEL_NICHE);
  set('s-lang',      s.CHANNEL_LANGUAGE);
  set('s-tone',      s.CHANNEL_TONE);
  set('s-audience',  s.TARGET_AUDIENCE);
  set('s-hour',      s.UPLOAD_HOUR);
  set('s-minute',    s.UPLOAD_MINUTE);
  set('s-voice',     s.TTS_VOICE_GENDER);
  set('s-wmin',      s.TARGET_WORD_COUNT_MIN || '800');
  set('s-wmax',      s.TARGET_WORD_COUNT_MAX || '1200');
  set('s-providers', s.PROVIDER_ORDER || 'gemini,groq,mistral,grok');
  set('s-loglevel',  s.LOG_LEVEL || 'INFO');
  set('s-cache',     s.CACHE_ENABLED !== 'false');
  set('s-music',     s.ENABLE_MUSIC !== 'false');
}

async function saveSettings() {
  const get = (id) => { const el = document.getElementById(id); return el ? (el.type==='checkbox' ? String(el.checked) : el.value) : ''; };
  const settings = {
    CHANNEL_NAME: get('s-name'), CHANNEL_NICHE: get('s-niche'),
    CHANNEL_LANGUAGE: get('s-lang'), CHANNEL_TONE: get('s-tone'),
    TARGET_AUDIENCE: get('s-audience'), UPLOAD_HOUR: get('s-hour'),
    UPLOAD_MINUTE: get('s-minute'), TTS_VOICE_GENDER: get('s-voice'),
    TARGET_WORD_COUNT_MIN: get('s-wmin'), TARGET_WORD_COUNT_MAX: get('s-wmax'),
    PROVIDER_ORDER: get('s-providers'), LOG_LEVEL: get('s-loglevel'),
    CACHE_ENABLED: get('s-cache'), ENABLE_MUSIC: get('s-music'),
  };
  // API keys (only send if non-empty)
  const keys = {groq:'s-groq', gemini:'s-gemini', mistral:'s-mistral', grok:'s-grok'};
  for (const [k,id] of Object.entries(keys)) {
    const val = document.getElementById(id)?.value;
    if (val) settings[k.toUpperCase()+'_API_KEY'] = val;
  }
  const r = await fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(settings)});
  if (r.ok) toast('Settings saved!', 'success'); else toast('Save failed', 'danger');
}

async function testProviders() {
  document.getElementById('test-result').textContent = 'Testing...';
  const r = await fetch('/api/providers/test', {method:'POST'});
  const d = await r.json();
  document.getElementById('test-result').textContent = d.message || 'Done';
  loadProviders();
}

// ── Job actions ─────────────────────────────────────────────
async function triggerRun() {
  const topicEl = document.getElementById('manual-topic');
  const topic   = topicEl ? topicEl.value.trim() : '';
  const body    = topic ? JSON.stringify({topic}) : '{}';
  toast('Starting pipeline...', 'info');
  const r = await fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json'}, body});
  const d = await r.json();
  if (d.job_id) toast('Job started: ' + d.job_id, 'success');
  else          toast('Start failed: ' + (d.error||'unknown'), 'danger');
  if (topicEl) topicEl.value = '';
  refresh();
}

async function stopJob() {
  const r = await fetch('/api/stop', {method:'POST'});
  const d = await r.json();
  toast(d.message || 'Stopped', d.ok ? 'warning' : 'danger');
}

async function retryJob(id) {
  const r = await fetch(`/api/retry/${id}`, {method:'POST'});
  const d = await r.json();
  toast(d.message || 'Retried', d.ok ? 'success' : 'danger');
  refresh();
}

// ── SSE log stream ───────────────────────────────────────────
let _sse = null;
let _logLines = [];
const MAX_LOG_LINES = 500;

function startSSE() {
  if (_sse) return;
  _sse = new EventSource('/stream/logs');
  document.getElementById('sse-dot').className = 'health-dot ok';

  _sse.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      appendLog(msg, 'full-log');
      appendLog(msg, 'mini-log');
    } catch {}
  };
  _sse.onerror = () => {
    document.getElementById('sse-dot').className = 'health-dot error';
    _sse.close(); _sse = null;
    setTimeout(startSSE, 3000);
  };
}

function appendLog(msg, containerId) {
  const filter = document.getElementById('log-level-filter')?.value;
  if (filter && msg.level !== filter) return;
  const el = document.getElementById(containerId);
  if (!el) return;
  const lvl  = msg.level || 'INFO';
  const cls  = lvl === 'WARNING' ? 'WARNING' : lvl;
  const ts   = msg.ts || new Date().toLocaleTimeString();
  const line = document.createElement('p');
  line.className = `log-line ${cls} mb-0`;
  line.innerHTML = `<span class="log-ts">${ts}</span><span class="log-agent">${msg.agent||''}</span>${escHtml(msg.message||'')}`;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
  // Trim
  while (el.children.length > MAX_LOG_LINES) el.removeChild(el.firstChild);
}

function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function clearLogs() { ['full-log','mini-log'].forEach(id => { const el=document.getElementById(id); if(el) el.innerHTML=''; }); }
function filterLogs() { /* just filter future logs — existing cleared */ clearLogs(); }

// ── Init ─────────────────────────────────────────────────────
startSSE();
refresh();
setInterval(refresh, 15000);
loadSettings();
</script>
</body>
</html>"""


# ── API Routes ─────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return DASHBOARD_HTML


@app.get("/api/status")
async def api_status():
    try:
        stats = db.get_stats_summary()
    except Exception:
        stats = {}
    try:
        from router.ai_router import ask, ask_json, get_status
        from router.health_monitor import monitor
        from router.provider_manager import manager
        providers = {name: monitor.get_health(name).__dict__ for name in manager.providers.keys()}
        from router.ai_router import get_status
        active = get_status()['active_provider']
    except Exception:
        providers, active = {}, "none"
    try:
        from utils.cache import get_stats as cache_stats
        cache = cache_stats()
    except Exception:
        cache = {}
    try:
        from utils.content_library import get_library_stats
        library = get_library_stats()
    except Exception:
        library = {}
    # System metrics
    try:
        system = {
            "cpu_pct":  round(psutil.cpu_percent(interval=0.1), 1),
            "mem_pct":  round(psutil.virtual_memory().percent, 1),
            "disk_pct": round(psutil.disk_usage("/").percent, 1),
            "disk_gb":  round(psutil.disk_usage("/").used / 1e9, 2),
        }
    except Exception:
        system = {}

    return JSONResponse({
        "stats":           stats,
        "providers":       providers,
        "active_provider": active,
        "cache":           cache,
        "library":         library,
        "system":          system,
        "ts":              datetime.utcnow().isoformat(),
    })


@app.get("/api/jobs")
async def api_jobs(limit: int = 20):
    try:
        return JSONResponse(db.get_recent_jobs(limit))
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.get("/api/videos")
async def api_videos(limit: int = 30):
    try:
        return JSONResponse(db.get_videos(limit))
    except Exception as e:
        return JSONResponse([], 200)


@app.get("/api/settings")
async def api_get_settings():
    try:
        s = db.get_all_settings()
        # Merge with live config defaults (don't expose actual key values)
        s.setdefault("CHANNEL_NAME",         config.CHANNEL_NAME)
        s.setdefault("CHANNEL_NICHE",        config.CHANNEL_NICHE)
        s.setdefault("CHANNEL_LANGUAGE",     config.CHANNEL_LANGUAGE)
        s.setdefault("CHANNEL_TONE",         config.CHANNEL_TONE)
        s.setdefault("TARGET_AUDIENCE",      config.TARGET_AUDIENCE)
        s.setdefault("UPLOAD_HOUR",          str(config.UPLOAD_HOUR))
        s.setdefault("UPLOAD_MINUTE",        str(config.UPLOAD_MINUTE))
        s.setdefault("TTS_VOICE_GENDER",     config.TTS_VOICE_GENDER)
        s.setdefault("ENABLE_MUSIC",         str(config.ENABLE_MUSIC).lower())
        s.setdefault("PROVIDER_ORDER",       config.PROVIDER_ORDER)
        s.setdefault("CACHE_ENABLED",        str(config.CACHE_ENABLED).lower())
        s.setdefault("TARGET_WORD_COUNT_MIN","800")
        s.setdefault("TARGET_WORD_COUNT_MAX","1200")
        s.setdefault("LOG_LEVEL",            config.LOG_LEVEL)
        return JSONResponse(s)
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)


@app.post("/api/settings")
async def api_save_settings(request: Request):
    try:
        data = await request.json()
        safe_keys = {
            "CHANNEL_NAME", "CHANNEL_NICHE", "CHANNEL_LANGUAGE", "CHANNEL_TONE",
            "TARGET_AUDIENCE", "UPLOAD_HOUR", "UPLOAD_MINUTE", "TTS_VOICE_GENDER",
            "ENABLE_MUSIC", "PROVIDER_ORDER", "CACHE_ENABLED",
            "TARGET_WORD_COUNT_MIN", "TARGET_WORD_COUNT_MAX", "LOG_LEVEL",
            "GROQ_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY", "GROK_API_KEY",
        }
        for k, v in data.items():
            if k in safe_keys and v:
                db.set_setting(k, str(v))
        load_live_config()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, 500)


@app.get("/api/library")
async def api_library(limit: int = 50, niche: str = ""):
    try:
        from utils.content_library import get_recent
        items = get_recent(limit, niche or None)
        return JSONResponse({"items": items})
    except Exception as e:
        return JSONResponse({"items": []})


@app.get("/api/library/search")
async def api_library_search(q: str = ""):
    try:
        from utils.content_library import search
        items = search(q, limit=30)
        return JSONResponse({"items": items})
    except Exception as e:
        return JSONResponse({"items": []})


@app.get("/api/library/stats")
async def api_library_stats():
    try:
        from utils.content_library import get_library_stats
        return JSONResponse(get_library_stats())
    except Exception:
        return JSONResponse({})


@app.post("/api/run")
async def api_run(request: Request, background_tasks: BackgroundTasks):
    global _running_job_thread, _stop_event
    try:
        data  = await request.json()
        topic = data.get("topic", "")
    except Exception:
        topic = ""

    if _running_job_thread and _running_job_thread.is_alive():
        return JSONResponse({"error": "A job is already running"}, 409)

    _stop_event.clear()
    job_id = [None]

    def _run():
        from pipeline import run
        result = run(manual_topic=topic or None)
        job_id[0] = result.get("id")

    _running_job_thread = threading.Thread(target=_run, daemon=True)
    _running_job_thread.start()

    import time; time.sleep(0.3)
    return JSONResponse({"ok": True, "job_id": job_id[0] or "started"})


@app.post("/api/stop")
async def api_stop():
    global _running_job_thread, _stop_event
    _stop_event.set()
    return JSONResponse({"ok": True, "message": "Stop signal sent"})


@app.post("/api/retry/{job_id}")
async def api_retry(job_id: str, background_tasks: BackgroundTasks):
    job = db.get_job(job_id)
    if not job:
        return JSONResponse({"ok": False, "error": "Job not found"}, 404)
    topic = job.get("topic", "")

    def _run():
        from pipeline import run
        run(manual_topic=topic or None)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return JSONResponse({"ok": True, "message": f"Retrying job {job_id}"})




@app.get("/health")
async def health_endpoint():
    try:
        from router.health_monitor import monitor
        from router.provider_manager import manager
        import psutil
        healthy_providers = sum(1 for p in manager.providers.keys() if monitor.get_health(p).healthy)
        return JSONResponse({
            "status": "healthy",
            "providers_healthy": healthy_providers,
            "disk_ok": psutil.disk_usage('/').percent < 90,
            "memory_ok": psutil.virtual_memory().percent < 90
        })
    except Exception as e:
        return JSONResponse({"status": "degraded", "error": str(e)}, 500)

@app.get("/api/provider-status")
async def api_provider_status():
    try:
        from router.ai_router import get_status
        return JSONResponse(get_status())
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)

@app.post("/api/providers/test")
async def api_test_providers():
    try:
        from router.provider_manager import manager
        avail = [n for n, p in manager.providers.items() if p.is_configured()]
        return JSONResponse({"ok": True, "message": f"Available: {', '.join(avail) or 'none'}"})
    except Exception as e:
        return JSONResponse({"ok": False, "message": str(e)}, 500)


@app.get("/stream/logs")
async def stream_logs():
    q = queue.Queue(maxsize=300)
    with _sse_lock:
        _sse_queues.append(q)

    async def generate():
        # Send recent DB history
        try:
            for entry in db.get_logs(limit=50):
                data = json.dumps({
                    "ts":      (entry.get("ts") or "")[-8:],
                    "level":   entry.get("level", "INFO"),
                    "agent":   entry.get("agent", ""),
                    "message": entry.get("message", ""),
                    "job_id":  entry.get("job_id", ""),
                })
                yield f"data: {data}\n\n"
        except Exception:
            pass

        yield 'data: {"message":"── Live stream connected ──","level":"INFO","agent":"Dashboard","ts":""}\n\n'

        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield f"data: {json.dumps(msg)}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
        finally:
            with _sse_lock:
                if q in _sse_queues:
                    _sse_queues.remove(q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Server startup ────────────────────────────────────────────

def start_dashboard(background: bool = True, host: str = "0.0.0.0"):
    """Start the dashboard server."""
    db.init_db()

    if background:
        t = threading.Thread(
            target=lambda: uvicorn.run(
                app, host=host, port=config.PORT,
                log_level="error", access_log=False,
            ),
            daemon=True
        )
        t.start()
        log.success(f"Dashboard → http://{host}:{config.PORT}")
    else:
        log.success(f"Dashboard → http://{host}:{config.PORT}")
        uvicorn.run(app, host=host, port=config.PORT,
                    log_level="error", access_log=False)
