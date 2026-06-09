"""
main.py — Single entry point.

python main.py                           → 24/7 bot (scheduler + dashboard)
python main.py --run-now                 → One video now (auto topic)
python main.py --run-now --topic "X"     → One video on topic X
python main.py --niche technology        → Set niche then start bot
python main.py --dashboard               → Dashboard only
python main.py --strategy                → Run weekly strategy
python main.py --analyse                 → Run analytics + learning
python main.py --list-voices             → List TTS voices
python main.py --setup-check             → Verify all API keys
python main.py --startup-check           → Comprehensive startup self-test
python main.py --cache-stats             → Show cache statistics
python main.py --library                 → Show content library stats

FREE-ONLY ARCHITECTURE:
  Approved: GEMINI, GROQ, CEREBRAS, OPENROUTER, POLLINATIONS, AI_HORDE
  Optional: NVIDIA (free tier)
  Blocked:  TOGETHER, DEEPINFRA, SAMBANOVA, GROK
"""

import sys, os

# Apply PIL patch before anything else that might import moviepy/PIL
import PIL
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = getattr(PIL.Image, 'Resampling', PIL.Image).LANCZOS

from colorama import Fore, Style, init
init()

from config import config, load_live_config
from database import db
from utils.logger import get_logger

log = get_logger("Main")
log.info(f"Pillow version: {PIL.__version__}")


def banner():
    load_live_config()
    from agents.niche_profiles import get_profile
    profile    = get_profile(config.CHANNEL_NICHE)
    lang_label = "Hindi 🇮🇳" if config.CHANNEL_LANGUAGE == "hi" else "English 🇺🇸"

    # Detect configured free providers only
    providers = []
    if config.GEMINI_API_KEY and not config.GEMINI_API_KEY.startswith("your_"):
        providers.append("Gemini")
    if config.GROQ_API_KEY and not config.GROQ_API_KEY.startswith("your_"):
        providers.append("Groq")
    if config.MISTRAL_API_KEY and not config.MISTRAL_API_KEY.startswith("your_"):
        providers.append("Mistral")
    if config.GROK_API_KEY and not config.GROK_API_KEY.startswith("your_"):
        providers.append("Grok")
    if config.NVIDIA_API_KEY and not config.NVIDIA_API_KEY.startswith("your_"):
        providers.append("NVIDIA")
    if config.CEREBRAS_API_KEY and not config.CEREBRAS_API_KEY.startswith("your_"):
        providers.append("Cerebras")
    if config.OPENROUTER_API_KEY and not config.OPENROUTER_API_KEY.startswith("your_"):
        providers.append("OpenRouter")
    if config.OLLAMA_URL:
        providers.append("Ollama")
    if config.POLLINATIONS_ENABLED:
        providers.append("Pollinations")
    if config.AI_HORDE_ENABLED:
        providers.append("AI-Horde")
    prov_str = " → ".join(providers) if providers else "⚠ No providers configured!"

    print(f"""
{Fore.CYAN}╔═══════════════════════════════════════════════════════════╗
║   🤖  YouTube AI Bot  v4.0  ·  Free-Only Edition           ║
╠═══════════════════════════════════════════════════════════╣
║  Industry: {profile['emoji']} {profile['label']:<46}║
║  Channel:  {config.CHANNEL_NAME:<48}║
║  Language: {lang_label:<48}║
║  Voice:    {config.get_tts_voice():<48}║
╠═══════════════════════════════════════════════════════════╣
║  AI:        {prov_str:<46}║
║  Script:    {config.TARGET_WORD_COUNT_MIN}-{config.TARGET_WORD_COUNT_MAX} words (~{config.TARGET_DURATION_MIN}-{config.TARGET_DURATION_MAX} min){'':<28}║
║  AI Calls:  1 per video (unified agent, was 9+)           ║
║  Cache:     {'✓ Enabled (SQLite)' if config.CACHE_ENABLED else '✗ Disabled':<46}║
║  Voice:     edge-tts Microsoft Neural (free, unlimited)   ║
║  Footage:   Pexels + Pixabay (free)                       ║
║  Trends:    Google Trends + HackerNews + News RSS + Wiki  ║
║  Thumbnails:Pollinations.ai (free, unlimited)             ║
╠═══════════════════════════════════════════════════════════╣
║  Dashboard: http://0.0.0.0:{config.PORT:<31}║
║  Daily post:{config.UPLOAD_HOUR:02d}:{config.UPLOAD_MINUTE:02d} UTC{' '*42}║
╚═══════════════════════════════════════════════════════════╝{Style.RESET_ALL}
""")


def _startup_self_test() -> dict:
    """
    Comprehensive startup self-test.
    Returns a dict with 'passed', 'failed', and 'warnings' lists.
    """
    passed   = []
    failed   = []
    warnings = []

    # ── 1. Import Validation ─────────────────────────────────
    critical_imports = [
        ("config",                      "config"),
        ("database.db",                 "init_db"),
        ("utils.logger",                "get_logger"),
        ("agents.strategy_agent",       "pick_todays_topic"),
        ("agents.unified_agent",        "generate"),
        ("agents.voice_agent",          "generate_voice"),
        ("agents.video_agent",          "build_video"),
        ("agents.thumbnail_agent",      "generate_thumbnail"),
        ("agents.caption_agent",        "generate_srt"),
        ("agents.upload_agent",         "upload_video"),
        ("agents.holistic_agent",       "init_job"),
        ("agents.niche_profiles",       "get_profile"),
        ("agents.analytics_agent",      "collect_all_analytics"),
        ("router.ai_router",            "ask"),
        ("router.provider_manager",     "manager"),
        ("router.health_monitor",       "monitor"),
        ("router.failover_engine",      "get_best_provider"),
        ("utils.checkpoint",            "save_checkpoint"),
        ("utils.cache",                 "get"),
        ("utils.db_logger",             "get_logger"),
        ("scheduler.jobs",              "build_scheduler"),
        ("pipeline",                    "run"),
    ]

    for module, symbol in critical_imports:
        try:
            mod = __import__(module, fromlist=[symbol])
            if not hasattr(mod, symbol):
                failed.append(f"IMPORT: '{symbol}' not found in '{module}'")
            else:
                passed.append(f"IMPORT: {module}.{symbol}")
        except ImportError as e:
            failed.append(f"IMPORT: Cannot import '{module}': {e}")
        except Exception as e:
            failed.append(f"IMPORT: Error loading '{module}': {e}")

    # ── 2. Provider Validation ────────────────────────────────
    free_providers_found = []
    from config import Config as C

    if C.GEMINI_API_KEY and not C.GEMINI_API_KEY.startswith("your_"):
        free_providers_found.append("Gemini")
        passed.append("PROVIDER: Gemini API key present")
    if C.GROQ_API_KEY and not C.GROQ_API_KEY.startswith("your_"):
        free_providers_found.append("Groq")
        passed.append("PROVIDER: Groq API key present")
    if C.MISTRAL_API_KEY and not C.MISTRAL_API_KEY.startswith("your_"):
        free_providers_found.append("Mistral")
        passed.append("PROVIDER: Mistral API key present")
    if C.GROK_API_KEY and not C.GROK_API_KEY.startswith("your_"):
        free_providers_found.append("Grok")
        passed.append("PROVIDER: Grok API key present")
    if C.NVIDIA_API_KEY and not C.NVIDIA_API_KEY.startswith("your_"):
        free_providers_found.append("NVIDIA")
        passed.append("PROVIDER: NVIDIA API key present (optional free tier)")
    if C.CEREBRAS_API_KEY and not C.CEREBRAS_API_KEY.startswith("your_"):
        free_providers_found.append("Cerebras")
        passed.append("PROVIDER: Cerebras API key present")
    if C.OPENROUTER_API_KEY and not C.OPENROUTER_API_KEY.startswith("your_"):
        free_providers_found.append("OpenRouter")
        passed.append("PROVIDER: OpenRouter API key present")
    if getattr(C, 'OLLAMA_URL', None):
        free_providers_found.append("Ollama")
        passed.append("PROVIDER: Ollama local API present")
    if C.POLLINATIONS_ENABLED:
        free_providers_found.append("Pollinations")
        passed.append("PROVIDER: Pollinations enabled (always-free)")
    if C.AI_HORDE_ENABLED:
        free_providers_found.append("AI-Horde")
        passed.append("PROVIDER: AI-Horde enabled (always-free)")

    if not free_providers_found:
        failed.append("PROVIDER: No approved free providers configured")
    else:
        passed.append(f"PROVIDER: {len(free_providers_found)} free provider(s) active: {', '.join(free_providers_found)}")

    # Check blocked providers
    blocked_env = {"TOGETHER_API_KEY": "Together AI",
                   "DEEPINFRA_API_KEY": "DeepInfra",
                   "SAMBANOVA_API_KEY": "SambaNova",
                   "GROK_API_KEY": "Grok (xAI)"}
    for env_key, name in blocked_env.items():
        val = os.getenv(env_key, "")
        if val and not val.startswith("your_"):
            warnings.append(f"PROVIDER: {name} ({env_key}) is a blocked paid provider — ignored")

    # ── 3. Filesystem / Directory Validation ─────────────────
    required_dirs = [
        config.OUTPUT_VIDEO,
        config.OUTPUT_AUDIO,
        config.OUTPUT_THUMBNAIL,
        config.OUTPUT_CAPTIONS,
        config.OUTPUT_MUSIC,
        config.LOGS_DIR,
        os.path.dirname(config.DB_PATH),
    ]
    for d in required_dirs:
        if d:
            try:
                os.makedirs(d, exist_ok=True)
                passed.append(f"FILESYSTEM: {d}/ exists/created")
            except Exception as e:
                failed.append(f"FILESYSTEM: Cannot create {d}/: {e}")

    # ── 4. Database Validation ────────────────────────────────
    try:
        from database import db as _db
        _db.init_db()
        passed.append("DATABASE: SQLite initialized OK")
    except Exception as e:
        failed.append(f"DATABASE: Initialization failed: {e}")

    # ── 5. Configuration Validation ───────────────────────────
    if config.CHANNEL_NICHE:
        passed.append(f"CONFIG: Channel niche = '{config.CHANNEL_NICHE}'")
    else:
        warnings.append("CONFIG: CHANNEL_NICHE not set (using default: 'technology')")

    if config.YOUTUBE_CLIENT_ID and config.YOUTUBE_REFRESH_TOKEN:
        passed.append("CONFIG: YouTube OAuth credentials present")
    else:
        warnings.append("CONFIG: YouTube OAuth not configured (upload will fail)")

    if config.PEXELS_API_KEY or config.PIXABAY_API_KEY:
        passed.append("CONFIG: Media API key present")
    else:
        warnings.append("CONFIG: No media API key (PEXELS/PIXABAY) — footage unavailable")

    return {"passed": passed, "failed": failed, "warnings": warnings}


def main():
    from config import Config
    args = sys.argv[1:]

    # ── Startup Self-Test ─────────────────────────────────────
    if "--startup-check" in args:
        print(f"\n{Fore.CYAN}━━━ STARTUP SELF-TEST ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Style.RESET_ALL}")
        result = _startup_self_test()

        for item in result["passed"]:
            print(f"  {Fore.GREEN}✓{Style.RESET_ALL}  {item}")
        for item in result["warnings"]:
            print(f"  {Fore.YELLOW}⚠{Style.RESET_ALL}  {item}")
        for item in result["failed"]:
            print(f"  {Fore.RED}✗{Style.RESET_ALL}  {item}")

        total  = len(result["passed"]) + len(result["failed"])
        status = "PASS" if not result["failed"] else "FAIL"
        color  = Fore.GREEN if status == "PASS" else Fore.RED

        print(f"\n{color}━━━ RESULT: {status} — {len(result['passed'])}/{total} checks passed "
              f"({len(result['warnings'])} warnings) ━━━{Style.RESET_ALL}\n")

        if result["failed"]:
            sys.exit(1)
        return

    # ── Startup Validation (Free-Only Enforcement) ────────────
    has_free = any([
        Config.GROQ_API_KEY and not Config.GROQ_API_KEY.startswith("your_"),
        Config.GEMINI_API_KEY and not Config.GEMINI_API_KEY.startswith("your_"),
        Config.MISTRAL_API_KEY and not Config.MISTRAL_API_KEY.startswith("your_"),
        Config.GROK_API_KEY and not Config.GROK_API_KEY.startswith("your_"),
        Config.NVIDIA_API_KEY and not Config.NVIDIA_API_KEY.startswith("your_"),
        Config.CEREBRAS_API_KEY and not Config.CEREBRAS_API_KEY.startswith("your_"),
        Config.OPENROUTER_API_KEY and not Config.OPENROUTER_API_KEY.startswith("your_"),
        Config.POLLINATIONS_ENABLED,
        Config.AI_HORDE_ENABLED,
        getattr(Config, 'OLLAMA_URL', None)
    ])
    if not has_free:
        print(f"\n{Fore.RED}❌ CRITICAL STARTUP ERROR: No approved free AI providers configured.\n"
              f"   Please set at least one of: GROQ_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY,\n"
              f"   GROK_API_KEY, NVIDIA_API_KEY — or enable free fallbacks:\n"
              f"   POLLINATIONS_ENABLED=true, AI_HORDE_ENABLED=true{Style.RESET_ALL}\n")
        sys.exit(1)

    db.init_db()

    # ── List voices ───────────────────────────────────────────
    if "--list-voices" in args:
        import subprocess
        print("\n🎙️  Available voices:\n")
        subprocess.run(["edge-tts", "--list-voices"])
        return

    # ── Setup check ───────────────────────────────────────────
    if "--setup-check" in args:
        from utils.check_setup import run_all
        run_all()
        return

    # ── Show videos ───────────────────────────────────────────
    if "--videos" in args:
        from utils.show_videos import show
        show()
        return

    # ── Cache stats ───────────────────────────────────────────
    if "--cache-stats" in args:
        from utils.cache import get_stats
        s = get_stats()
        print(f"\n📦 Cache Statistics:")
        print(f"  Entries:    {s['total_entries']}")
        print(f"  Today hits: {s['today_hits']}")
        print(f"  Today miss: {s['today_misses']}")
        print(f"  Hit rate:   {s['hit_rate_pct']}%")
        print(f"  Saves:      {s['saves_today']}\n")
        return

    # ── Library stats ─────────────────────────────────────────
    if "--library" in args:
        from utils.content_library import get_library_stats
        s = get_library_stats()
        print(f"\n📚 Content Library:")
        print(f"  Total entries:   {s['total_entries']}")
        print(f"  Research facts:  {s['research_facts']}")
        print(f"  By type:  {s['by_type']}")
        print(f"  By niche: {s['by_niche']}\n")
        return

    # ── Set niche ─────────────────────────────────────────────
    if "--niche" in args:
        idx = args.index("--niche")
        if idx + 1 < len(args):
            niche = args[idx + 1]
            from agents.niche_profiles import get_profile, NICHE_PROFILES
            if niche not in NICHE_PROFILES:
                print(f"Unknown niche '{niche}'. Options: {', '.join(NICHE_PROFILES.keys())}")
                return
            profile = get_profile(niche)
            db.set_setting("CHANNEL_NICHE",    niche)
            db.set_setting("CHANNEL_LANGUAGE", profile.get("force_language", "en"))
            db.set_setting("CHANNEL_TONE",     profile["tone"])
            load_live_config()
            print(f"✅ Niche set to: {profile['emoji']} {profile['label']}")
            if "--run-now" not in args:
                return

    banner()

    # ── One-shot run ──────────────────────────────────────────
    if "--run-now" in args:
        topic = None
        if "--topic" in args:
            idx = args.index("--topic")
            if idx + 1 < len(args):
                topic = args[idx + 1]
        from pipeline import run
        log.info(f"Manual run — topic: {topic or 'auto'}")
        job = run(manual_topic=topic)
        print(f"\nResult:  {job['status']}")
        if job.get("video_url"): print(f"Video:   {job['video_url']}")
        if job.get("error"):     print(f"Error:   {job['error']}")
        return

    # ── Dashboard only ────────────────────────────────────────
    if "--dashboard" in args:
        from dashboard.app import start_dashboard
        log.info(f"Dashboard only → http://0.0.0.0:{config.PORT}")
        start_dashboard(background=False)
        return

    # ── Weekly strategy ───────────────────────────────────────
    if "--strategy" in args:
        from agents.strategy_agent import generate_weekly_strategy
        generate_weekly_strategy()
        return

    # ── Analytics ─────────────────────────────────────────────
    if "--analyse" in args:
        from agents.analytics_agent import collect_all_analytics, analyse_and_learn
        collect_all_analytics()
        analyse_and_learn()
        return

    # ── Full 24/7 mode ────────────────────────────────────────
    from dashboard.app import start_dashboard
    start_dashboard(background=True)

    from scheduler.jobs import build_scheduler
    scheduler = build_scheduler(blocking=True)
    log.success(f"Bot live 24/7 — dashboard: http://0.0.0.0:{config.PORT}")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped.")


if __name__ == "__main__":
    main()
