"""
agents/holistic_agent.py
─────────────────────────
The Holistic Agent — Brain of the entire operation.

Responsibilities:
 • Tracks every agent's status in real-time
 • Coordinates parallel execution
 • Runs pre-pipeline brainstorming with all agents
 • Detects failures and triggers retries
 • Learns from past performance and feeds insights back
 • Publishes live progress to dashboard via shared state
"""

import time, threading
from datetime import datetime
from collections import defaultdict
from database import db
from utils.logger import get_logger

log = get_logger("HolisticAgent")

# Shared state — all agents write here, dashboard reads it
_state: dict = {
    "job_id":       None,
    "started_at":   None,
    "current_step": None,
    "agents":       {},   # agent_name → {status, started, finished, summary, pct}
    "brainstorm":   {},
    "errors":       [],
    "done":         False,
}
_lock = threading.Lock()


# ── Public API ────────────────────────────────────────────────────

def init_job(job_id: str):
    with _lock:
        _state.update({
            "job_id":       job_id,
            "started_at":   datetime.utcnow().isoformat(),
            "current_step": "Initialising",
            "agents":       {},
            "brainstorm":   {},
            "errors":       [],
            "done":         False,
        })
    db.log_agent_activity(job_id, "HolisticAgent", "running",
                          started_at=datetime.utcnow().isoformat())
    log.info(f"[Holistic] Job {job_id} initialised")


def agent_start(job_id: str, agent_name: str):
    ts = datetime.utcnow().isoformat()
    with _lock:
        _state["agents"][agent_name] = {
            "status":   "running",
            "started":  ts,
            "finished": None,
            "summary":  "",
            "pct":      0,
        }
        _state["current_step"] = agent_name
    db.log_agent_activity(job_id, agent_name, "running", started_at=ts)
    log.info(f"[Holistic] ▶ {agent_name} started")


def agent_progress(agent_name: str, pct: int, note: str = ""):
    with _lock:
        if agent_name in _state["agents"]:
            _state["agents"][agent_name]["pct"]     = pct
            _state["agents"][agent_name]["summary"] = note


def agent_done(job_id: str, agent_name: str, summary: str = "", success: bool = True):
    ts = datetime.utcnow().isoformat()
    with _lock:
        _state["agents"][agent_name] = {
            **_state["agents"].get(agent_name, {}),
            "status":   "success" if success else "failed",
            "finished": ts,
            "summary":  summary,
            "pct":      100 if success else _state["agents"].get(agent_name, {}).get("pct", 0),
        }
        if not success:
            _state["errors"].append(f"{agent_name}: {summary}")
    db.log_agent_activity(job_id, agent_name, "success" if success else "failed",
                          finished_at=ts, summary=summary)
    icon = "✅" if success else "❌"
    log.info(f"[Holistic] {icon} {agent_name} finished — {summary[:80]}")


def job_complete(job_id: str):
    with _lock:
        _state["done"] = True
        _state["current_step"] = "Complete"
    db.log_agent_activity(job_id, "HolisticAgent", "success",
                          finished_at=datetime.utcnow().isoformat(),
                          summary=f"All agents finished. Errors: {len(_state['errors'])}")
    log.success(f"[Holistic] Job {job_id} complete")


def save_brainstorm_result(result: dict):
    with _lock:
        _state["brainstorm"] = result


def get_state() -> dict:
    with _lock:
        return dict(_state)


# ── Performance insight loader ────────────────────────────────────

def get_performance_insights() -> str:
    """Load past video performance data and summarise for agents."""
    try:
        data = db.get_performance_data()
        if not data:
            return "No performance data yet — this is an early video."
        top    = sorted(data, key=lambda x: x["views"], reverse=True)[:3]
        bottom = sorted(data, key=lambda x: x["views"])[:3]
        lines  = ["Past performance insights:"]
        lines.append("TOP performing videos (high views):")
        for v in top:
            lines.append(f"  • \"{v['title']}\" — {v['views']} views, CTR {v['ctr']:.1f}%, retention {v['avg_view_duration_pct']:.0f}%")
        lines.append("UNDERPERFORMING videos (to learn from):")
        for v in bottom:
            lines.append(f"  • \"{v['title']}\" — {v['views']} views")
        return "\n".join(lines)
    except Exception:
        return ""


# ── Retry wrapper ─────────────────────────────────────────────────

def run_with_retry(fn, agent_name: str, job_id: str, max_retries: int = 2, **kwargs):
    """
    Run an agent function with automatic retry on failure.
    Tracks status via Holistic Agent.
    """
    agent_start(job_id, agent_name)
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            result = fn(**kwargs)
            agent_done(job_id, agent_name, summary=str(result)[:120] if result else "OK")
            return result
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                wait = 10 * (attempt + 1)
                log.warning(f"[Holistic] {agent_name} failed (attempt {attempt+1}), retrying in {wait}s: {e}")
                agent_progress(agent_name, 0, f"Retry {attempt+1}/{max_retries}")
                time.sleep(wait)
            else:
                agent_done(job_id, agent_name, summary=str(e)[:120], success=False)
                raise last_err
