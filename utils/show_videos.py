"""
utils/show_videos.py
─────────────────────
Shows all videos made by the bot — local files + YouTube URLs.
Run: python utils/show_videos.py

Also shows where to find local output files if they weren't deleted.
"""

import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from colorama import Fore, Style, init
init()
from config import config


def show():
    print(f"""
{Fore.CYAN}╔═══════════════════════════════════════════╗
║  📺 YouTube AI Bot — Video Status         ║
╚═══════════════════════════════════════════╝{Style.RESET_ALL}""")

    # ── Local output files ────────────────────────────────
    print(f"\n{Fore.WHITE}── Local Output Files ───────────────────────{Style.RESET_ALL}")
    print(f"  Videos:     {os.path.abspath(config.OUTPUT_VIDEO)}/")
    print(f"  Thumbnails: {os.path.abspath(config.OUTPUT_THUMBNAIL)}/")
    print(f"  Audio:      {os.path.abspath(config.OUTPUT_AUDIO)}/")
    print(f"  Captions:   {os.path.abspath(config.OUTPUT_CAPTIONS)}/")
    print()

    for folder, label in [
        (config.OUTPUT_VIDEO,     "Videos (.mp4)"),
        (config.OUTPUT_THUMBNAIL, "Thumbnails (.jpg)"),
    ]:
        files = []
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder)
                     if not f.startswith("_tmp")]
        if files:
            print(f"  📁 {label}: {len(files)} file(s)")
            for f in sorted(files)[-3:]:
                fpath = os.path.join(folder, f)
                size  = os.path.getsize(fpath) / (1024*1024)
                print(f"     • {f}  ({size:.1f} MB)")
        else:
            print(f"  📁 {label}: empty")
            print(f"     (Videos are auto-deleted after upload to save disk space)")

    # ── Database history ──────────────────────────────────
    print(f"\n{Fore.WHITE}── Published Videos (YouTube URLs) ─────────{Style.RESET_ALL}")
    try:
        from database.db import init_db, get_recent_jobs
        init_db()
        jobs = get_recent_jobs(20)
        if not jobs:
            print(f"  {Fore.YELLOW}No videos in database yet.{Style.RESET_ALL}")
            print(f"  Run: {Fore.CYAN}python main.py --run-now{Style.RESET_ALL}")
            return

        success = [j for j in jobs if j["status"] == "success"]
        failed  = [j for j in jobs if j["status"] == "failed"]

        print(f"  Total made: {len(jobs)} | Published: {len(success)} | Failed: {len(failed)}\n")

        for i, j in enumerate(jobs, 1):
            meta   = {}
            if j.get("metadata"):
                try: meta = json.loads(j["metadata"]) if isinstance(j["metadata"], str) else j["metadata"]
                except: pass

            icon   = "✅" if j["status"] == "success" else "❌"
            date   = (j.get("started_at") or "")[:10]
            title  = j.get("topic") or meta.get("title") or "Unknown"
            lang   = meta.get("language","en").upper()
            niche  = meta.get("niche", "—")

            print(f"  {icon} #{i:02d} [{date}] [{lang}] {title[:55]}")
            if j.get("video_url"):
                print(f"       🔗 {Fore.CYAN}{j['video_url']}{Style.RESET_ALL}")
            elif j.get("error"):
                print(f"       ⚠️  {Fore.RED}{j['error'][:80]}{Style.RESET_ALL}")
            print()

    except Exception as e:
        print(f"  {Fore.RED}Error reading database: {e}{Style.RESET_ALL}")

    # ── Log file ──────────────────────────────────────────
    print(f"\n{Fore.WHITE}── Log File ──────────────────────────────────{Style.RESET_ALL}")
    log_path = os.path.join(config.LOGS_DIR, "bot.log")
    if os.path.exists(log_path):
        size = os.path.getsize(log_path) / 1024
        print(f"  {log_path}  ({size:.0f} KB)")
        print(f"  View live logs: {Fore.CYAN}tail -f {log_path}{Style.RESET_ALL}")
        # Show last 5 lines
        with open(log_path) as f:
            lines = f.readlines()
        print(f"\n  Last 5 log lines:")
        for line in lines[-5:]:
            print(f"  {line.rstrip()}")
    else:
        print(f"  No log file yet (bot hasn't run)")

    print()


if __name__ == "__main__":
    show()
