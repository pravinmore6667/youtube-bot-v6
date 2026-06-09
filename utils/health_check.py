"""
utils/health_check.py
──────────────────────
Tests all external APIs and updates the health table in SQLite.
Called on startup and every 30 minutes by scheduler.
Dashboard reads this for the "API Status" panel.
"""

import os
from database import db
from utils.logger import get_logger

log = get_logger("HealthCheck")


def _check(service: str, fn) -> dict:
    try:
        detail = fn()
        db.set_health(service, "ok", detail or "working")
        log.success(f"{service}: OK")
        return {"status": "ok", "detail": detail}
    except Exception as e:
        msg = str(e)[:200]
        db.set_health(service, "error", msg)
        log.warning(f"{service}: FAILED — {msg[:80]}")
        return {"status": "error", "detail": msg}


def check_gemini() -> dict:
    def _fn():
        import google.generativeai as genai
        from config import config
        key = getattr(config, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        if not key or key.startswith("your_"):
            raise Exception("GEMINI_API_KEY not set in .env")
        genai.configure(api_key=key)
        models = [m.name for m in genai.list_models()
                  if "generateContent" in m.supported_generation_methods]
        if not models:
            raise Exception("No models available for this key")
        best = next((m for m in models if "flash" in m.lower()), models[0])
        return f"Key valid · {len(models)} models · using {best.split('/')[-1]}"
    return _check("gemini", _fn)


def check_groq() -> dict:
    def _fn():
        from config import config
        key = getattr(config, "GROQ_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
        if not key or key.startswith("your_"):
            raise Exception("GROQ_API_KEY not set (optional)")
        from groq import Groq
        client = Groq(api_key=key)
        models = client.models.list()
        names  = [m.id for m in models.data][:3]
        return f"Key valid · models: {', '.join(names)}"
    return _check("groq", _fn)


def check_pexels() -> dict:
    def _fn():
        import requests
        from config import config
        r = requests.get("https://api.pexels.com/videos/search",
                         headers={"Authorization": config.PEXELS_API_KEY},
                         params={"query": "nature", "per_page": 1}, timeout=8)
        if r.status_code == 401: raise Exception("Invalid API key")
        if r.status_code == 200:
            total = r.json().get("total_results", "?")
            return f"Key valid · {total} results for test query"
        raise Exception(f"HTTP {r.status_code}")
    return _check("pexels", _fn)


def check_pixabay() -> dict:
    def _fn():
        import requests
        from config import config
        r = requests.get("https://pixabay.com/api/videos/",
                         params={"key": config.PIXABAY_API_KEY,
                                 "q": "nature", "per_page": 1}, timeout=8)
        if r.status_code == 400: raise Exception("Invalid API key")
        if r.status_code == 200:
            total = r.json().get("totalHits", "?")
            return f"Key valid · {total} results for test query"
        raise Exception(f"HTTP {r.status_code}")
    return _check("pixabay", _fn)


def check_youtube() -> dict:
    def _fn():
        from agents.upload_agent import _yt_client
        yt   = _yt_client()
        resp = yt.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items", [])
        if items:
            ch = items[0]["snippet"]["title"]
            return f"Connected · channel: '{ch}'"
        return "Connected (no channel name)"
    return _check("youtube", _fn)


def check_ffmpeg() -> dict:
    def _fn():
        import subprocess
        r = subprocess.run(["ffmpeg","-version"], capture_output=True, timeout=8)
        if r.returncode != 0: raise Exception("ffmpeg not working")
        ver = r.stdout.decode().split("\n")[0].replace("ffmpeg version ","")[:40]
        return f"Installed · {ver}"
    return _check("ffmpeg", _fn)


def check_edge_tts() -> dict:
    def _fn():
        import subprocess
        r = subprocess.run(["edge-tts","--list-voices"],
                           capture_output=True, timeout=15)
        if r.returncode != 0: raise Exception("edge-tts not working")
        count = r.stdout.decode().count("ShortName")
        return f"Working · {count} voices available"
    return _check("edge_tts", _fn)


def run_all_checks() -> dict:
    """Run all health checks. Returns dict of results."""
    log.info("Running health checks...")
    results = {
        "gemini":   check_gemini(),
        "groq":     check_groq(),
        "pexels":   check_pexels(),
        "pixabay":  check_pixabay(),
        "youtube":  check_youtube(),
        "ffmpeg":   check_ffmpeg(),
        "edge_tts": check_edge_tts(),
    }
    ok  = sum(1 for r in results.values() if r["status"] == "ok")
    log.info(f"Health check done: {ok}/{len(results)} services OK")
    return results
