"""
utils/check_setup.py
─────────────────────
Run this to diagnose any setup issue before starting the bot.
Checks every component and gives exact fix instructions.

Usage:  python utils/check_setup.py
        python main.py --setup-check
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from colorama import Fore, Style, init
init()

def ok(msg):  print(f"  {Fore.GREEN}✅ {msg}{Style.RESET_ALL}")
def fail(msg):print(f"  {Fore.RED}❌ {msg}{Style.RESET_ALL}")
def warn(msg):print(f"  {Fore.YELLOW}⚠️  {msg}{Style.RESET_ALL}")
def info(msg):print(f"  {Fore.CYAN}ℹ️  {msg}{Style.RESET_ALL}")

def check_env():
    print(f"\n{Fore.WHITE}── .env file ────────────────────────────────{Style.RESET_ALL}")
    from dotenv import load_dotenv
    load_dotenv()
    from config import config

    keys = {
        "GEMINI_API_KEY":         (config.GEMINI_API_KEY,        "https://aistudio.google.com/"),
        "PEXELS_API_KEY":         (config.PEXELS_API_KEY,        "https://www.pexels.com/api/"),
        "PIXABAY_API_KEY":        (config.PIXABAY_API_KEY,       "https://pixabay.com/api/docs/"),
        "YOUTUBE_CLIENT_ID":      (config.YOUTUBE_CLIENT_ID,     "https://console.cloud.google.com/"),
        "YOUTUBE_CLIENT_SECRET":  (config.YOUTUBE_CLIENT_SECRET, "https://console.cloud.google.com/"),
        "YOUTUBE_REFRESH_TOKEN":  (config.YOUTUBE_REFRESH_TOKEN, "Run: python auth_setup.py"),
    }
    all_ok = True
    for name, (val, link) in keys.items():
        if not val or val.startswith("your_") or val.startswith("run_auth"):
            fail(f"{name} — NOT SET  →  {link}")
            all_ok = False
        else:
            ok(f"{name} — set ({val[:12]}...)")
    return all_ok


import asyncio

def check_providers():
    print(f"\n{Fore.WHITE}── AI Providers ───────────────────────────────{Style.RESET_ALL}")
    import router.provider_manager
    from router.provider_manager import manager
    from router.gemini_pool import pool

    gemini_keys = pool.get_all_keys()
    if gemini_keys:
        ok(f"Loaded Gemini Keys: {len(gemini_keys)}")
    else:
        warn("No Gemini Keys found")

    for provider_name, provider in manager.providers.items():
        if provider.is_configured():
            ok(f"{provider_name.capitalize()}: OK")
        else:
            if provider_name in ["gemini", "groq", "mistral", "grok"]:
                warn(f"{provider_name.capitalize()}: Not Configured")

    if not any(p.is_configured() for p in manager.providers.values()):
        fail("No AI providers are correctly configured. Bot cannot run.")
        return False

    return True


def check_pexels():
    print(f"\n{Fore.WHITE}── Pexels (video footage) ───────────────────{Style.RESET_ALL}")
    try:
        import requests
        from config import config
        r = requests.get("https://api.pexels.com/videos/search",
                         headers={"Authorization": config.PEXELS_API_KEY},
                         params={"query":"nature","per_page":1}, timeout=10)
        if r.status_code == 200:
            ok(f"Pexels API working")
            return True
        elif r.status_code == 401:
            fail("Pexels key invalid → https://www.pexels.com/api/")
        else:
            warn(f"Pexels returned {r.status_code}")
        return False
    except Exception as e:
        fail(f"Pexels error: {e}"); return False


def check_pixabay():
    print(f"\n{Fore.WHITE}── Pixabay (footage + music) ────────────────{Style.RESET_ALL}")
    try:
        import requests
        from config import config
        r = requests.get("https://pixabay.com/api/videos/",
                         params={"key":config.PIXABAY_API_KEY,"q":"nature","per_page":1},
                         timeout=10)
        if r.status_code == 200:
            ok("Pixabay API working"); return True
        elif r.status_code == 400:
            fail("Pixabay key invalid → https://pixabay.com/api/docs/")
        else:
            warn(f"Pixabay returned {r.status_code}")
        return False
    except Exception as e:
        fail(f"Pixabay error: {e}"); return False


def check_youtube():
    print(f"\n{Fore.WHITE}── YouTube API ──────────────────────────────{Style.RESET_ALL}")
    try:
        from agents.upload_agent import _yt_client
        yt = _yt_client()
        # Try a cheap read-only call
        resp = yt.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items", [])
        if items:
            ch = items[0]["snippet"]["title"]
            ok(f"YouTube connected — channel: '{ch}'")
        else:
            ok("YouTube API connected (no channel name found)")
        return True
    except Exception as e:
        err = str(e)
        if "invalid_grant" in err or "Token" in err:
            fail("YouTube token expired\n"
                 "     → Run: python auth_setup.py\n"
                 "     → Paste the new YOUTUBE_REFRESH_TOKEN into .env")
        elif "quota" in err.lower():
            warn("YouTube quota exceeded (10,000 units/day free)\n"
                 "     → Wait until midnight UTC for quota to reset")
        else:
            fail(f"YouTube error: {err[:120]}")
        return False


def check_ffmpeg():
    print(f"\n{Fore.WHITE}── FFmpeg (video rendering) ─────────────────{Style.RESET_ALL}")
    try:
        import subprocess
        r = subprocess.run(["ffmpeg","-version"], capture_output=True, timeout=10)
        if r.returncode == 0:
            ver = r.stdout.decode().split("\n")[0]
            ok(f"FFmpeg installed — {ver[:50]}")
            return True
        fail("FFmpeg not working")
        return False
    except FileNotFoundError:
        fail("FFmpeg NOT installed\n"
             "     → Ubuntu/Debian: sudo apt install -y ffmpeg\n"
             "     → Windows: https://ffmpeg.org/download.html")
        return False


def check_edge_tts():
    print(f"\n{Fore.WHITE}── edge-tts (voice) ─────────────────────────{Style.RESET_ALL}")
    try:
        import subprocess
        r = subprocess.run(["edge-tts","--list-voices"],
                           capture_output=True, timeout=20)
        if r.returncode == 0:
            count = r.stdout.decode().count("ShortName")
            ok(f"edge-tts working — {count} voices available")
            return True
        fail("edge-tts not working"); return False
    except FileNotFoundError:
        fail("edge-tts not installed — run: pip install edge-tts")
        return False


def check_output_dirs():
    print(f"\n{Fore.WHITE}── Output folders ───────────────────────────{Style.RESET_ALL}")
    from config import config
    dirs = [config.OUTPUT_VIDEO, config.OUTPUT_AUDIO,
            config.OUTPUT_THUMBNAIL, config.OUTPUT_CAPTIONS,
            config.OUTPUT_MUSIC, config.LOGS_DIR, "database"]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        ok(f"{d}/ — ready")
    return True


def check_recent_videos():
    print(f"\n{Fore.WHITE}── Recent videos ────────────────────────────{Style.RESET_ALL}")
    try:
        from database.db import init_db, get_recent_jobs
        init_db()
        jobs = get_recent_jobs(10)
        if not jobs:
            info("No videos made yet. Run: python main.py --run-now")
            return
        for j in jobs[:5]:
            import json as _j
            status_icon = "✅" if j["status"] == "success" else "❌"
            print(f"  {status_icon} [{j['status']:8}] {(j.get('topic') or '—')[:50]}")
            if j.get("video_url"):
                print(f"          🔗 {j['video_url']}")
            if j.get("error"):
                print(f"          ⚠️  {j['error'][:80]}")
    except Exception as e:
        warn(f"Could not read job history: {e}")


def run_all():
    print(f"""
{Fore.CYAN}╔═══════════════════════════════════════════════╗
║  🔍 YouTube AI Bot — Setup Check             ║
╚═══════════════════════════════════════════════╝{Style.RESET_ALL}""")

    results = []
    results.append(("API Keys in .env",    check_env()))
    results.append(("AI Providers",        check_providers()))
    results.append(("Pexels footage",      check_pexels()))
    results.append(("Pixabay footage",     check_pixabay()))
    results.append(("YouTube upload",      check_youtube()))
    results.append(("FFmpeg rendering",    check_ffmpeg()))
    results.append(("edge-tts voice",      check_edge_tts()))
    check_output_dirs()
    check_recent_videos()

    passed = sum(1 for _, r in results if r)
    total  = len(results)
    print(f"\n{Fore.WHITE}── Summary ──────────────────────────────────{Style.RESET_ALL}")
    print(f"  {passed}/{total} checks passed\n")

    if passed == total:
        print(f"{Fore.GREEN}🎉 Everything is working! Start the bot:{Style.RESET_ALL}")
        print(f"  python main.py --run-now      (make one video now)")
        print(f"  python main.py                (start 24/7 bot)\n")
    else:
        print(f"{Fore.YELLOW}⚠️  Fix the ❌ items above, then run this check again:{Style.RESET_ALL}")
        print(f"  python main.py --setup-check\n")
    return passed == total


if __name__ == "__main__":
    run_all()
