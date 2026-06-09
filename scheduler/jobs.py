"""
scheduler/jobs.py — All 24/7 automated tasks

UTC Schedule:
  Daily UPLOAD_HOUR     → Full pipeline (research → upload)
  Daily UPLOAD_HOUR+2h  → Analytics collection
  Sunday  08:00         → Weekly strategy + learning analysis
  Daily   03:00         → Analytics deep analysis + learning
  Saturday 02:00        → Database vacuum
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import config
from utils.logger import get_logger

log = get_logger("Scheduler")


def job_daily_video():
    log.info("⏰ Daily video pipeline triggered")
    from pipeline import run
    run()


def job_collect_analytics():
    log.info("📊 Collecting analytics...")
    from agents.analytics_agent import collect_all_analytics
    collect_all_analytics()


def job_deep_analysis():
    log.info("🧠 Running deep performance analysis + learning...")
    from agents.analytics_agent import analyse_and_learn
    import asyncio

    insights = asyncio.run(analyse_and_learn())

    if insights:
        log.info(
            f"Predicted winner: "
            f"{insights.get('predicted_next_winner', '')[:60]}"
        )


def job_weekly_strategy():
    log.info("📅 Weekly strategy review")

    from agents.strategy_agent import generate_weekly_strategy
    import asyncio

    asyncio.run(generate_weekly_strategy())
    job_deep_analysis()


def job_db_maintenance():
    log.info("🗄️ DB maintenance")

    import sqlite3

    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("VACUUM")
    conn.close()

    log.info("Database vacuumed")


def build_scheduler(blocking: bool = True):
    Cls = BlockingScheduler if blocking else BackgroundScheduler

    scheduler = Cls(timezone="UTC")


    # Enterprise-grade AI router health check background recovery
    from router.failover_engine import check_all_health
    scheduler.add_job(
        check_all_health,
        'interval',
        minutes=5,
        id="ai_health_recovery",
        name="AI Router Health Recovery",
        max_instances=1,
        coalesce=True
    )


    # Watchdog Service: Resume hung processes
    from database import db
    import time
    def watchdog_service():
        jobs = db.get_recent_jobs(50)
        for job in jobs:
            # If job is running for more than 2 hours, it's hung
            if job["status"] == "running":
                try:
                    from datetime import datetime
                    start_dt = datetime.fromisoformat(job["started_at"])
                    if (datetime.utcnow() - start_dt).total_seconds() > 7200:
                        job["status"] = "failed"
                        job["error"] = "Watchdog detected hung process."
                        db.save_job(job)
                        log.warning(f"Watchdog killed hung job: {job['id']}")
                except Exception: pass

    scheduler.add_job(
        watchdog_service, 'interval', minutes=5, id="watchdog", coalesce=True
    )

    # Automatic Cleanup System
    import os, shutil
    def automatic_cleanup():
        for d in ["output/videos", "output/audio", "output/captions", "output/thumbnails", "output/music"]:
            if not os.path.exists(d): continue
            for f in os.listdir(d):
                path = os.path.join(d, f)
                if os.path.isfile(path):
                    # Remove files older than 2 days
                    if time.time() - os.path.getmtime(path) > 172800:
                        try: os.remove(path)
                        except: pass

    scheduler.add_job(
        automatic_cleanup, 'interval', hours=12, id="auto_cleanup", coalesce=True
    )

    scheduler.add_job(
        job_daily_video,
        CronTrigger(
            hour=config.UPLOAD_HOUR,
            minute=config.UPLOAD_MINUTE
        ),
        id="daily_video",
        name="Daily Video Pipeline",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600
    )

    scheduler.add_job(
        job_collect_analytics,
        CronTrigger(
            hour=(config.UPLOAD_HOUR + 2) % 24,
            minute=30
        ),
        id="analytics",
        name="Analytics Collection",
        max_instances=1
    )

    scheduler.add_job(
        job_deep_analysis,
        CronTrigger(hour=3, minute=0),
        id="deep_analysis",
        name="Daily Deep Analysis + Learning"
    )

    scheduler.add_job(
        job_weekly_strategy,
        CronTrigger(day_of_week="sun", hour=8, minute=0),
        id="weekly_strategy",
        name="Weekly Strategy Review"
    )

    scheduler.add_job(
        job_db_maintenance,
        CronTrigger(day_of_week="sat", hour=2, minute=0),
        id="db_maintenance",
        name="DB Maintenance"
    )

    log.info(
        f"Scheduler ready — {len(scheduler.get_jobs())} jobs"
    )

    for job in scheduler.get_jobs():
        try:
            next_run = getattr(job, "next_run_time", "N/A")
        except Exception:
            next_run = "N/A"

        log.info(
            f" • {job.name:<35} next: {next_run}"
        )

    return scheduler