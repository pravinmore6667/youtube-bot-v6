"""
utils/cache.py
───────────────
SQLite-based intelligent caching system.

Caches:
  - Generated scripts
  - SEO metadata (titles, descriptions, tags)
  - Research outputs
  - Thumbnail prompts
  - Topic analysis

Features:
  - Hash-based cache keys (SHA256)
  - Configurable TTL (default 7 days)
  - Similarity detection (topic deduplication)
  - Partial cache reuse
  - Cache hit statistics
"""
import hashlib, json, os, sqlite3, threading, time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any
from utils.logger import get_logger

log = get_logger("Cache")

_DB_PATH     = os.getenv("CACHE_DB_PATH", "database/cache.db")
_DEFAULT_TTL = int(os.getenv("CACHE_TTL_DAYS", "7")) * 86400   # seconds
_local       = threading.local()


def _conn():
    if not hasattr(_local, "c") or _local.c is None:
        Path(os.path.dirname(_DB_PATH)).mkdir(parents=True, exist_ok=True)
        _local.c = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _local.c.row_factory = sqlite3.Row
        _local.c.execute("PRAGMA journal_mode=WAL")
        _local.c.execute("PRAGMA synchronous=NORMAL")
    return _local.c


def init_cache():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS cache_entries (
        key         TEXT PRIMARY KEY,
        topic_hash  TEXT,
        cache_type  TEXT,      -- 'script'|'seo'|'research'|'thumbnail'|'unified'
        topic_text  TEXT,
        niche       TEXT,
        language    TEXT DEFAULT 'en',
        data        TEXT,      -- JSON blob
        hit_count   INTEGER DEFAULT 0,
        created_at  TEXT,
        expires_at  TEXT,
        updated_at  TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_cache_topic    ON cache_entries(topic_hash);
    CREATE INDEX IF NOT EXISTS idx_cache_type     ON cache_entries(cache_type);
    CREATE INDEX IF NOT EXISTS idx_cache_expires  ON cache_entries(expires_at);
    CREATE INDEX IF NOT EXISTS idx_cache_niche    ON cache_entries(niche);

    CREATE TABLE IF NOT EXISTS cache_stats (
        date    TEXT PRIMARY KEY,
        hits    INTEGER DEFAULT 0,
        misses  INTEGER DEFAULT 0,
        saves   INTEGER DEFAULT 0
    );
    """)
    c.commit()

init_cache()


# ── Key generation ────────────────────────────────────────────

def _make_key(topic: str, cache_type: str, niche: str = "", lang: str = "en") -> str:
    """Stable SHA256 key from topic + type + context."""
    norm = f"{topic.strip().lower()}::{cache_type}::{niche}::{lang}"
    return hashlib.sha256(norm.encode()).hexdigest()[:32]

def _topic_hash(topic: str) -> str:
    """Topic-only hash for similarity search."""
    return hashlib.sha256(topic.strip().lower().encode()).hexdigest()[:16]


# ── Core cache operations ─────────────────────────────────────

def get(topic: str, cache_type: str,
        niche: str = "", lang: str = "en") -> Optional[Any]:
    """Return cached data if valid, else None."""
    key = _make_key(topic, cache_type, niche, lang)
    now = datetime.utcnow().isoformat()
    row = _conn().execute(
        "SELECT data, expires_at FROM cache_entries WHERE key=?", (key,)
    ).fetchone()

    if not row:
        _bump_miss()
        return None

    if row["expires_at"] and row["expires_at"] < now:
        log.debug(f"Cache expired: {cache_type}/{topic[:30]}")
        _bump_miss()
        return None

    # Update hit count
    _conn().execute(
        "UPDATE cache_entries SET hit_count=hit_count+1, updated_at=? WHERE key=?",
        (now, key))
    _conn().commit()
    _bump_hit()
    log.info(f"✅ Cache HIT: {cache_type} for '{topic[:40]}'")
    return json.loads(row["data"])


def put(topic: str, cache_type: str, data: Any,
        niche: str = "", lang: str = "en", ttl: int = None):
    """Store data in cache."""
    key  = _make_key(topic, cache_type, niche, lang)
    th   = _topic_hash(topic)
    now  = datetime.utcnow().isoformat()
    exp  = (datetime.utcnow() + timedelta(seconds=ttl or _DEFAULT_TTL)).isoformat()
    blob = json.dumps(data, ensure_ascii=False)
    c    = _conn()
    c.execute("""
        INSERT OR REPLACE INTO cache_entries
        (key, topic_hash, cache_type, topic_text, niche, language,
         data, created_at, expires_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (key, th, cache_type, topic[:200], niche, lang, blob, now, exp, now))
    c.commit()
    _bump_save()
    log.debug(f"Cached {cache_type} for '{topic[:40]}'")


def invalidate(topic: str, cache_type: str = None,
               niche: str = "", lang: str = "en"):
    """Remove cache entry (or all types for a topic)."""
    c = _conn()
    if cache_type:
        key = _make_key(topic, cache_type, niche, lang)
        c.execute("DELETE FROM cache_entries WHERE key=?", (key,))
    else:
        th = _topic_hash(topic)
        c.execute("DELETE FROM cache_entries WHERE topic_hash=?", (th,))
    c.commit()


def find_similar(topic: str, cache_type: str,
                 niche: str = "", lang: str = "en",
                 threshold: float = 0.7) -> Optional[Any]:
    """
    Find a cached entry for a similar topic (simple keyword overlap).
    Returns data if overlap ratio >= threshold, else None.
    """
    now   = datetime.utcnow().isoformat()
    rows  = _conn().execute(
        """SELECT topic_text, data FROM cache_entries
           WHERE cache_type=? AND niche=? AND language=?
                 AND (expires_at IS NULL OR expires_at > ?)
           ORDER BY hit_count DESC LIMIT 50""",
        (cache_type, niche, lang, now)
    ).fetchall()

    words = set(_tokenize(topic))
    best_score, best_data = 0.0, None
    for row in rows:
        cached_words = set(_tokenize(row["topic_text"]))
        if not words or not cached_words:
            continue
        score = len(words & cached_words) / len(words | cached_words)
        if score > best_score:
            best_score, best_data = score, row["data"]

    if best_score >= threshold:
        log.info(f"Partial cache match ({best_score:.0%}) for '{topic[:40]}'")
        _bump_hit()
        return json.loads(best_data)
    return None


def get_stats() -> dict:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    row   = _conn().execute(
        "SELECT * FROM cache_stats WHERE date=?", (today,)
    ).fetchone()
    total = _conn().execute(
        "SELECT COUNT(*) FROM cache_entries WHERE expires_at > ?",
        (datetime.utcnow().isoformat(),)
    ).fetchone()[0]
    if row:
        h, m = row["hits"], row["misses"]
        rate = round(h / max(h + m, 1) * 100, 1)
        return {"today_hits": h, "today_misses": m, "hit_rate_pct": rate,
                "total_entries": total, "saves_today": row["saves"]}
    return {"today_hits": 0, "today_misses": 0, "hit_rate_pct": 0,
            "total_entries": total, "saves_today": 0}


def purge_expired():
    now = datetime.utcnow().isoformat()
    c   = _conn()
    n   = c.execute("DELETE FROM cache_entries WHERE expires_at < ?", (now,)).rowcount
    c.commit()
    if n:
        log.info(f"Purged {n} expired cache entries")


# ── Helpers ───────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return [w for w in text.lower().split() if len(w) > 3]


def _bump_hit():
    _bump("hits")

def _bump_miss():
    _bump("misses")

def _bump_save():
    _bump("saves")

def _bump(col: str):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    c = _conn()
    c.execute(f"""
        INSERT INTO cache_stats (date, {col}) VALUES (?, 1)
        ON CONFLICT(date) DO UPDATE SET {col}={col}+1
    """, (today,))
    c.commit()
