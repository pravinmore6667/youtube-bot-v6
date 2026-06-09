"""
database/db.py
───────────────
SQLite database with full schema for all features.

Tables:
  jobs            — pipeline runs
  pipeline_steps  — step tracking per job
  videos          — uploaded YouTube videos
  agent_logs      — live log stream
  settings        — dashboard-configurable settings
  api_health      — provider health status
  provider_stats  — per-provider usage statistics
  content_history — generated content records
  brainstorm_sessions — brainstorm history
  agent_activity  — agent timing data
  strategy_memory — weekly strategy plans
"""

import sqlite3, json, os, threading
from datetime import datetime

_DB_PATH = None
_local   = threading.local()


def _get_db_path():
    global _DB_PATH
    if not _DB_PATH:
        from config import config
        _DB_PATH = config.DB_PATH
    return _DB_PATH


def _conn():
    if not hasattr(_local, "c") or _local.c is None:
        path = _get_db_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _local.c = sqlite3.connect(path, check_same_thread=False)
        _local.c.row_factory = sqlite3.Row
        _local.c.execute("PRAGMA journal_mode=WAL")
        _local.c.execute("PRAGMA synchronous=NORMAL")
        _local.c.execute("PRAGMA cache_size=10000")
    return _local.c


def init_db():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS jobs (
        id            TEXT PRIMARY KEY,
        started_at    TEXT,
        finished_at   TEXT,
        status        TEXT DEFAULT 'queued',
        topic         TEXT,
        niche         TEXT,
        language      TEXT DEFAULT 'en',
        video_url     TEXT,
        video_id      TEXT,
        error         TEXT,
        metadata      TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS pipeline_steps (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id      TEXT NOT NULL,
        step_name   TEXT NOT NULL,
        status      TEXT DEFAULT 'pending',
        started_at  TEXT,
        finished_at TEXT,
        output      TEXT,
        error       TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_steps_job ON pipeline_steps(job_id);

    CREATE TABLE IF NOT EXISTS videos (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id         TEXT UNIQUE,
        video_id       TEXT UNIQUE,
        title          TEXT,
        url            TEXT,
        studio_url     TEXT,
        thumbnail_url  TEXT,
        channel        TEXT,
        published_at   TEXT,
        duration       TEXT,
        views          INTEGER DEFAULT 0,
        likes          INTEGER DEFAULT 0,
        comments       INTEGER DEFAULT 0,
        verified       INTEGER DEFAULT 0,
        verified_at    TEXT,
        niche          TEXT,
        language       TEXT DEFAULT 'en'
    );
    CREATE INDEX IF NOT EXISTS idx_videos_niche ON videos(niche);

    CREATE TABLE IF NOT EXISTS agent_logs (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id     TEXT,
        ts         TEXT,
        level      TEXT DEFAULT 'INFO',
        agent      TEXT,
        message    TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_logs_job ON agent_logs(job_id);
    CREATE INDEX IF NOT EXISTS idx_logs_ts  ON agent_logs(ts);

    CREATE TABLE IF NOT EXISTS settings (
        key        TEXT PRIMARY KEY,
        value      TEXT,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS api_health (
        service    TEXT PRIMARY KEY,
        status     TEXT,
        checked_at TEXT,
        detail     TEXT
    );

    CREATE TABLE IF NOT EXISTS provider_stats (
        provider        TEXT PRIMARY KEY,
        total_requests  INTEGER DEFAULT 0,
        total_tokens    INTEGER DEFAULT 0,
        total_errors    INTEGER DEFAULT 0,
        success_rate    REAL DEFAULT 1.0,
        last_latency    REAL DEFAULT 0,
        health_score    REAL DEFAULT 1.0,
        updated_at      TEXT
    );

    CREATE TABLE IF NOT EXISTS content_history (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id                TEXT,
        title                 TEXT,
        niche                 TEXT,
        language              TEXT DEFAULT 'en',
        keywords              TEXT DEFAULT '[]',
        video_url             TEXT,
        views                 INTEGER DEFAULT 0,
        likes                 INTEGER DEFAULT 0,
        avg_view_duration_pct REAL DEFAULT 0,
        created_at            TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_ch_niche ON content_history(niche);

    CREATE TABLE IF NOT EXISTS brainstorm_sessions (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id           TEXT,
        topic            TEXT,
        contributions    TEXT DEFAULT '{}',
        final_direction  TEXT,
        created_at       TEXT
    );

    CREATE TABLE IF NOT EXISTS agent_activity (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id        TEXT,
        agent_name    TEXT,
        status        TEXT,
        started_at    TEXT,
        finished_at   TEXT,
        output_summary TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_act_job ON agent_activity(job_id);

    CREATE TABLE IF NOT EXISTS strategy_memory (
        week_of      TEXT PRIMARY KEY,
        niche        TEXT,
        top_topics   TEXT DEFAULT '[]',
        avoid_topics TEXT DEFAULT '[]',
        best_format  TEXT,
        best_hook_style TEXT,
        notes        TEXT,
        created_at   TEXT
    );
    """)
    c.commit()


# ── Jobs ──────────────────────────────────────────────────────

def save_job(job: dict):
    c = _conn()
    c.execute("""INSERT OR REPLACE INTO jobs
        (id,started_at,finished_at,status,topic,niche,language,
         video_url,video_id,error,metadata)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (job.get("id"), job.get("started_at"), job.get("finished_at"),
         job.get("status","queued"), job.get("topic"),
         job.get("niche"), job.get("language","en"),
         job.get("video_url"), job.get("video_id"),
         job.get("error"), json.dumps(job.get("metadata",{}))))
    c.commit()


def get_job(job_id: str) -> dict | None:
    row = _conn().execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row: return None
    d = dict(row)
    d["metadata"] = json.loads(d.get("metadata") or "{}")
    return d


def get_recent_jobs(limit: int = 20) -> list:
    rows = _conn().execute(
        "SELECT * FROM jobs ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["metadata"] = json.loads(d.get("metadata") or "{}")
        result.append(d)
    return result


def get_queue_stats() -> dict:
    c = _conn()
    running = c.execute("SELECT COUNT(*) FROM jobs WHERE status='running'").fetchone()[0]
    queued  = c.execute("SELECT COUNT(*) FROM jobs WHERE status='queued'").fetchone()[0]
    success = c.execute("SELECT COUNT(*) FROM jobs WHERE status='success'").fetchone()[0]
    failed  = c.execute("SELECT COUNT(*) FROM jobs WHERE status='failed'").fetchone()[0]
    return {"running": running, "queued": queued, "success": success, "failed": failed}


# ── Pipeline steps ────────────────────────────────────────────

def step_start(job_id: str, name: str):
    c = _conn()
    c.execute("""INSERT OR REPLACE INTO pipeline_steps
        (job_id,step_name,status,started_at) VALUES (?,?,?,?)""",
        (job_id, name, "running", datetime.utcnow().isoformat()))
    c.commit()


def step_done(job_id: str, name: str, output: str = "", error: str = ""):
    c   = _conn()
    st  = "error" if error else "done"
    now = datetime.utcnow().isoformat()
    c.execute("""UPDATE pipeline_steps
        SET status=?,finished_at=?,output=?,error=?
        WHERE job_id=? AND step_name=?""",
        (st, now, (output or "")[:500], (error or "")[:500], job_id, name))
    c.commit()


def get_steps(job_id: str) -> list:
    rows = _conn().execute(
        "SELECT * FROM pipeline_steps WHERE job_id=? ORDER BY id", (job_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# ── Videos ────────────────────────────────────────────────────

def save_video(data: dict):
    c = _conn()
    c.execute("""INSERT OR REPLACE INTO videos
        (job_id,video_id,title,url,studio_url,thumbnail_url,channel,
         published_at,duration,views,likes,comments,verified,verified_at,niche,language)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data.get("job_id"), data.get("video_id"), data.get("title"),
         data.get("url"), data.get("studio_url"), data.get("thumbnail_url"),
         data.get("channel"), data.get("published_at"), data.get("duration"),
         data.get("views",0), data.get("likes",0), data.get("comments",0),
         1 if data.get("verified") else 0,
         datetime.utcnow().isoformat() if data.get("verified") else None,
         data.get("niche",""), data.get("language","en")))
    c.commit()


def get_videos(limit: int = 30) -> list:
    rows = _conn().execute(
        "SELECT * FROM videos ORDER BY published_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def update_video_stats(video_id: str, stats: dict):
    c = _conn()
    c.execute("UPDATE videos SET views=?,likes=?,comments=? WHERE video_id=?",
        (stats.get("views",0), stats.get("likes",0),
         stats.get("comments",0), video_id))
    c.commit()


# ── Agent logs ────────────────────────────────────────────────

def add_log(job_id: str, agent: str, level: str, message: str):
    c = _conn()
    c.execute("INSERT INTO agent_logs (job_id,ts,level,agent,message) VALUES (?,?,?,?,?)",
        (job_id, datetime.utcnow().isoformat(), level, agent, message[:1000]))
    c.commit()


def get_logs(job_id: str = None, limit: int = 200) -> list:
    c = _conn()
    if job_id:
        rows = c.execute(
            "SELECT * FROM agent_logs WHERE job_id=? ORDER BY id DESC LIMIT ?",
            (job_id, limit)).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM agent_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_latest_log_id() -> int:
    row = _conn().execute("SELECT MAX(id) FROM agent_logs").fetchone()
    return row[0] or 0


def get_logs_since(log_id: int, limit: int = 100) -> list:
    rows = _conn().execute(
        "SELECT * FROM agent_logs WHERE id>? ORDER BY id LIMIT ?",
        (log_id, limit)).fetchall()
    return [dict(r) for r in rows]


# ── Settings ──────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    try:
        row = _conn().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default
    except Exception:
        return default


def set_setting(key: str, value: str):
    c = _conn()
    c.execute("INSERT OR REPLACE INTO settings (key,value,updated_at) VALUES (?,?,?)",
        (key, value, datetime.utcnow().isoformat()))
    c.commit()


def get_all_settings() -> dict:
    try:
        rows = _conn().execute("SELECT key,value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}


# ── API health ────────────────────────────────────────────────

def set_health(service: str, status: str, detail: str = ""):
    c = _conn()
    c.execute("INSERT OR REPLACE INTO api_health (service,status,checked_at,detail) VALUES (?,?,?,?)",
        (service, status, datetime.utcnow().isoformat(), detail[:300]))
    c.commit()


def get_health() -> dict:
    rows = _conn().execute("SELECT * FROM api_health").fetchall()
    return {r["service"]: dict(r) for r in rows}


# ── Provider stats ────────────────────────────────────────────

def upsert_provider_stat(provider: str, stats: dict):
    c   = _conn()
    now = datetime.utcnow().isoformat()
    c.execute("""INSERT OR REPLACE INTO provider_stats
        (provider,total_requests,total_tokens,total_errors,
         success_rate,last_latency,health_score,updated_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (provider,
         stats.get("total_requests",0), stats.get("total_tokens",0),
         stats.get("total_errors",0),   stats.get("success_rate",1.0),
         stats.get("last_latency",0),   stats.get("health_score",1.0), now))
    c.commit()


def get_provider_stats() -> list:
    rows = _conn().execute(
        "SELECT * FROM provider_stats ORDER BY provider"
    ).fetchall()
    return [dict(r) for r in rows]


# ── Content history ───────────────────────────────────────────

def save_content(data: dict):
    c = _conn()
    c.execute("""INSERT INTO content_history
        (job_id,title,niche,language,keywords,video_url,created_at)
        VALUES (?,?,?,?,?,?,?)""",
        (data.get("job_id"), data.get("title"), data.get("niche"),
         data.get("language","en"), json.dumps(data.get("keywords",[])),
         data.get("video_url"), datetime.utcnow().isoformat()))
    c.commit()


def get_recent_titles(limit: int = 30) -> list:
    rows = _conn().execute(
        "SELECT title FROM content_history ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [r["title"] for r in rows]


# ── Brainstorm ────────────────────────────────────────────────

def save_brainstorm(job_id, topic, contributions, final_direction):
    c = _conn()
    c.execute("""INSERT INTO brainstorm_sessions
        (job_id,topic,contributions,final_direction,created_at) VALUES (?,?,?,?,?)""",
        (job_id, topic, json.dumps(contributions), final_direction,
         datetime.utcnow().isoformat()))
    c.commit()


# ── Agent activity ────────────────────────────────────────────

def log_agent_activity(job_id, agent, status, started_at=None,
                       finished_at=None, summary=""):
    c = _conn()
    c.execute("""INSERT OR REPLACE INTO agent_activity
        (job_id,agent_name,status,started_at,finished_at,output_summary)
        VALUES (?,?,?,?,?,?)""",
        (job_id, agent, status,
         started_at or datetime.utcnow().isoformat(), finished_at, summary))
    c.commit()


# ── Strategy ──────────────────────────────────────────────────

def save_strategy(s: dict):
    week = datetime.utcnow().strftime("%Y-W%U")
    c    = _conn()
    c.execute("""INSERT OR REPLACE INTO strategy_memory
        (week_of,niche,top_topics,avoid_topics,best_format,best_hook_style,notes,created_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (week, s.get("niche"), json.dumps(s.get("top_topics",[])),
         json.dumps(s.get("avoid_topics",[])), s.get("best_format"),
         s.get("best_hook_style"), s.get("notes"), datetime.utcnow().isoformat()))
    c.commit()


def get_current_strategy() -> dict | None:
    week = datetime.utcnow().strftime("%Y-W%U")
    row  = _conn().execute(
        "SELECT * FROM strategy_memory WHERE week_of=?", (week,)
    ).fetchone()
    if not row: return None
    d = dict(row)
    d["top_topics"]   = json.loads(d.get("top_topics") or "[]")
    d["avoid_topics"] = json.loads(d.get("avoid_topics") or "[]")
    return d


def get_performance_data() -> list:
    rows = _conn().execute("""SELECT title,views,likes,avg_view_duration_pct
        FROM content_history WHERE views>0 ORDER BY views DESC LIMIT 20""").fetchall()
    return [dict(r) for r in rows]


# ── Summary stats ─────────────────────────────────────────────

def get_stats_summary() -> dict:
    c     = _conn()
    total = c.execute("SELECT COUNT(*) FROM jobs WHERE status='success'").fetchone()[0]
    fail  = c.execute("SELECT COUNT(*) FROM jobs WHERE status='failed'").fetchone()[0]
    run   = c.execute("SELECT COUNT(*) FROM jobs WHERE status='running'").fetchone()[0]
    views = c.execute("SELECT COALESCE(SUM(views),0) FROM videos").fetchone()[0]
    likes = c.execute("SELECT COALESCE(SUM(likes),0) FROM videos").fetchone()[0]
    return {"total_videos": total, "failed_jobs": fail,
            "pending_jobs": run,   "total_views": views, "total_likes": likes}


def update_analytics(video_id: str, stats: dict):
    update_video_stats(video_id, stats)
