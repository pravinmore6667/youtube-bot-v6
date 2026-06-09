"""
utils/content_library.py
─────────────────────────
Project-wide Knowledge Storage & Reuse System

Every generated output is stored in a searchable library.
Future projects can reuse research, facts, scripts, titles, tags, SEO.

Features:
  - Full-text search (SQLite FTS5)
  - Keyword similarity search
  - Topic matching (Jaccard similarity)
  - Reuse recommendations
  - Script/title/tag retrieval by niche
"""
import json, os, sqlite3, threading
from datetime import datetime
from typing import Optional
from utils.logger import get_logger

log = get_logger("ContentLibrary")

_DB_PATH = os.getenv("LIBRARY_DB_PATH", "database/content_library.db")
_local   = threading.local()


def _conn():
    if not hasattr(_local, "c") or _local.c is None:
        import pathlib
        pathlib.Path(os.path.dirname(_DB_PATH)).mkdir(parents=True, exist_ok=True)
        _local.c = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _local.c.row_factory = sqlite3.Row
        _local.c.execute("PRAGMA journal_mode=WAL")
    return _local.c


def init_library():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS library (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id       TEXT,
        topic        TEXT NOT NULL,
        niche        TEXT,
        language     TEXT DEFAULT 'en',
        content_type TEXT,     -- 'script'|'title'|'description'|'tags'|'seo'|'research'
        content      TEXT,     -- raw content
        metadata     TEXT DEFAULT '{}',
        keywords     TEXT DEFAULT '[]',  -- JSON array
        word_count   INTEGER DEFAULT 0,
        quality_score REAL DEFAULT 0,
        reuse_count  INTEGER DEFAULT 0,
        created_at   TEXT,
        video_url    TEXT
    );

    CREATE VIRTUAL TABLE IF NOT EXISTS library_fts USING fts5(
        topic,
        content,
        keywords,
        content_rowid='id',
        content='library'
    );

    CREATE TRIGGER IF NOT EXISTS lib_ai AFTER INSERT ON library BEGIN
        INSERT INTO library_fts(rowid, topic, content, keywords)
        VALUES (new.id, new.topic, COALESCE(new.content,''), COALESCE(new.keywords,''));
    END;

    CREATE TRIGGER IF NOT EXISTS lib_ad AFTER DELETE ON library BEGIN
        DELETE FROM library_fts WHERE rowid = old.id;
    END;

    CREATE TABLE IF NOT EXISTS research_facts (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        fact      TEXT NOT NULL,
        source    TEXT,
        topic     TEXT,
        niche     TEXT,
        verified  INTEGER DEFAULT 0,
        reuse_ct  INTEGER DEFAULT 0,
        created_at TEXT
    );

    CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
        fact, topic, source,
        content_rowid='id',
        content='research_facts'
    );

    CREATE INDEX IF NOT EXISTS idx_lib_niche ON library(niche);
    CREATE INDEX IF NOT EXISTS idx_lib_type  ON library(content_type);
    CREATE INDEX IF NOT EXISTS idx_lib_lang  ON library(language);
    """)
    c.commit()
    log.debug("Content library initialised")

init_library()


# ── Store content ──────────────────────────────────────────────

def store(job_id: str, topic: str, content_type: str,
          content: str, niche: str = "", language: str = "en",
          metadata: dict = None, keywords: list = None,
          quality_score: float = 0, video_url: str = ""):
    """Store any generated content in the library."""
    c   = _conn()
    now = datetime.utcnow().isoformat()
    wc  = len(content.split()) if isinstance(content, str) else 0
    c.execute("""
        INSERT INTO library
        (job_id, topic, niche, language, content_type, content,
         metadata, keywords, word_count, quality_score, created_at, video_url)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        job_id, topic, niche, language, content_type, content,
        json.dumps(metadata or {}),
        json.dumps(keywords or []),
        wc, quality_score, now, video_url
    ))
    c.commit()
    log.debug(f"Stored {content_type} for '{topic[:40]}'")


def store_unified(job_id: str, topic: str, result: dict,
                  niche: str = "", language: str = "en", video_url: str = ""):
    """Convenience: store all fields from a unified agent result."""
    fields = {
        "script":      result.get("full_narration", ""),
        "title":       result.get("title", ""),
        "description": result.get("description", ""),
        "tags":        json.dumps(result.get("tags", [])),
        "seo":         json.dumps({k: result.get(k) for k in
                                   ["title","description","tags","hashtags","primary_keyword"]}),
    }
    keywords = result.get("seo_keywords", []) + result.get("tags", [])[:5]
    for ctype, content in fields.items():
        if content:
            store(job_id, topic, ctype, content,
                  niche=niche, language=language,
                  keywords=keywords, video_url=video_url)


def store_facts(facts: list[str], topic: str, niche: str = "", source: str = ""):
    """Store individual research facts."""
    c   = _conn()
    now = datetime.utcnow().isoformat()
    for fact in facts:
        if fact and len(fact) > 20:
            c.execute("""
                INSERT INTO research_facts (fact, topic, niche, source, created_at)
                VALUES (?,?,?,?,?)
            """, (fact.strip(), topic, niche, source, now))
    c.commit()


# ── Search & Reuse ─────────────────────────────────────────────

def search(query: str, content_type: str = None,
           niche: str = None, limit: int = 10) -> list[dict]:
    """Full-text search across all stored content."""
    if not query:
        return []
    c      = _conn()
    params = [query]
    sql    = """
        SELECT l.id, l.topic, l.content_type, l.content, l.niche,
               l.language, l.quality_score, l.reuse_count, l.created_at,
               l.video_url
        FROM library l
        JOIN library_fts f ON f.rowid = l.id
        WHERE library_fts MATCH ?
    """
    if content_type:
        sql += " AND l.content_type=?"
        params.append(content_type)
    if niche:
        sql += " AND l.niche=?"
        params.append(niche)
    sql += f" ORDER BY rank LIMIT {int(limit)}"
    rows = c.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def find_similar_topics(topic: str, niche: str = "",
                        limit: int = 5) -> list[dict]:
    """Find stored items with similar topics (keyword overlap)."""
    words = set(w.lower() for w in topic.split() if len(w) > 3)
    if not words:
        return []
    c    = _conn()
    rows = c.execute("""
        SELECT DISTINCT topic, content_type, id, quality_score, reuse_count
        FROM library
        WHERE niche=? OR niche=''
        ORDER BY created_at DESC
        LIMIT 200
    """, (niche,)).fetchall()

    scored = []
    for row in rows:
        row_words = set(w.lower() for w in row["topic"].split() if len(w) > 3)
        if not row_words:
            continue
        score = len(words & row_words) / len(words | row_words)
        if score > 0.25:
            scored.append((score, dict(row)))

    scored.sort(key=lambda x: -x[0])
    return [item for _, item in scored[:limit]]


def get_reuse_recommendations(topic: str, niche: str = "") -> dict:
    """
    Return recommendations for reusing existing content.
    Returns: { 'can_reuse': bool, 'items': list, 'score': float }
    """
    similar = find_similar_topics(topic, niche, limit=3)
    if not similar:
        return {"can_reuse": False, "items": [], "score": 0.0}

    # Check if we have scripts for these similar topics
    reusable = []
    for item in similar:
        if item["content_type"] in ("script", "seo", "description"):
            reusable.append(item)

    return {
        "can_reuse":    bool(reusable),
        "items":        reusable,
        "score":        similar[0].get("quality_score", 0) if similar else 0,
        "similar_topics": [i["topic"] for i in similar],
    }


def get_tags_for_niche(niche: str, limit: int = 50) -> list[str]:
    """Get commonly used tags from the library for a niche."""
    c    = _conn()
    rows = c.execute("""
        SELECT content FROM library
        WHERE content_type='tags' AND niche=?
        ORDER BY quality_score DESC, reuse_count DESC
        LIMIT 20
    """, (niche,)).fetchall()

    tags = []
    seen = set()
    for row in rows:
        try:
            t = json.loads(row["content"])
            if isinstance(t, list):
                for tag in t:
                    if tag not in seen and len(tags) < limit:
                        tags.append(tag)
                        seen.add(tag)
        except Exception:
            pass
    return tags


def increment_reuse(entry_id: int):
    c = _conn()
    c.execute("UPDATE library SET reuse_count=reuse_count+1 WHERE id=?", (entry_id,))
    c.commit()


def get_recent(limit: int = 20, niche: str = None) -> list[dict]:
    """Get recently stored content."""
    c      = _conn()
    params = []
    sql    = "SELECT * FROM library"
    if niche:
        sql += " WHERE niche=?"
        params.append(niche)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = c.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_library_stats() -> dict:
    c = _conn()
    total    = c.execute("SELECT COUNT(*) FROM library").fetchone()[0]
    by_type  = c.execute("""
        SELECT content_type, COUNT(*) as cnt FROM library
        GROUP BY content_type
    """).fetchall()
    by_niche = c.execute("""
        SELECT niche, COUNT(*) as cnt FROM library
        GROUP BY niche ORDER BY cnt DESC LIMIT 10
    """).fetchall()
    facts    = c.execute("SELECT COUNT(*) FROM research_facts").fetchone()[0]
    return {
        "total_entries": total,
        "research_facts": facts,
        "by_type":  {r["content_type"]: r["cnt"] for r in by_type},
        "by_niche": {r["niche"]: r["cnt"] for r in by_niche},
    }
