"""
agents/analytics_agent.py
──────────────────────────
Analytics + Learning Agent.
Fetches CTR, views, watch time from YouTube Studio API.
Analyzes patterns and updates weekly strategy.
Feeds learnings back into the channel memory ChromaDB.
"""

import asyncio
from datetime import datetime
from router.ai_router import ask_json
from utils.logger import get_logger
from database import db
from config import config
from agents.channel_memory_agent import save_channel_memory, get_channel_memory

log = get_logger("AnalyticsAgent")


def collect_all_analytics():
    """Fetch latest stats for all uploaded videos and update DB."""
    try:
        from agents.upload_agent import fetch_analytics
    except ImportError:
        def fetch_analytics(vid_id): return None

    jobs = db.get_recent_jobs(50)
    updated = 0
    for job in jobs:
        vid_id = job.get("video_id")
        if vid_id and job.get("status") == "success":
            stats = fetch_analytics(vid_id)
            if stats:
                db.update_analytics(vid_id, stats)
                updated += 1
    log.success(f"Analytics collected for {updated} videos")
    return updated


async def analyse_and_learn() -> dict:
    """
    Self-Learning Feedback Loop.
    Upload -> Fetch Analytics -> Analyze Retention -> Analyze CTR ->
    Analyze audience behavior -> Learn -> Improve future generations automatically.
    """
    perf = db.get_performance_data()
    if not perf or len(perf) < 3:
        log.info("Not enough data for deep self-learning yet (need 3+ videos)")
        return {}

    # Prepare data for analysis
    data_str = "\n".join([
        f"• \"{v['title']}\" — {v['views']} views, "
        f"{v['likes']} likes, {v.get('avg_view_duration_pct', 0):.0f}% retention"
        for v in sorted(perf, key=lambda x: x["views"], reverse=True)
    ])

    log.info("🧠 Executing Self-Learning Feedback Loop...")

    prompt = f"""You are a YouTube Channel Performance Analyst and Machine Learning Engine.
Channel: {config.CHANNEL_NAME} | Niche: {config.CHANNEL_NICHE}

Historical video performance data:
{data_str}

Analyze retention patterns, CTR performance, and audience behavior.
Learn from this and output actionable insights to improve future generations.
Return strict JSON:
{{
  "top_performing_patterns": ["what the best videos have in common"],
  "underperforming_reasons": ["why some videos didn't perform"],
  "best_title_style": "description of what title styles get most clicks",
  "best_topic_types": ["topic category 1", "topic category 2"],
  "optimal_video_length_seconds": 360,
  "improvement_actions": ["action 1 for next video", "action 2"],
  "avoid_next_week": ["what to avoid based on low performers"],
  "predicted_next_winner": "topic idea most likely to outperform based on patterns",
  "audience_preferences": "What the audience actually responds to",
  "best_upload_timing": "17:00 UTC"
}}"""

    try:
        result = await ask_json(prompt, is_fast=False)

        # Save learnings to persistent vector memory (ChromaDB)
        current_memory = await get_channel_memory("default_channel")

        # Update memory with new learnings
        current_memory["audience_preferences"] = result.get("audience_preferences", current_memory.get("audience_preferences"))
        current_memory["best_upload_timing"] = result.get("best_upload_timing", current_memory.get("best_upload_timing"))
        current_memory["best_title_style"] = result.get("best_title_style", current_memory.get("best_title_style"))
        current_memory["optimal_video_length_seconds"] = result.get("optimal_video_length_seconds", current_memory.get("optimal_video_length_seconds", 420))

        await save_channel_memory(current_memory)
        log.success("Learnings saved to persistent Vector Memory.")

        # Update strategy table
        strategy = db.get_current_strategy() or {}
        if result.get("avoid_next_week"):
            strategy["avoid_topics"] = result["avoid_next_week"]
        if result.get("best_topic_types"):
            strategy["top_topics"] = result["best_topic_types"]
        strategy["niche"] = config.CHANNEL_NICHE
        db.save_strategy(strategy)

        log.success(f"Self-Learning complete — predicted winner: {result.get('predicted_next_winner','')[:60]}")
        return result
    except Exception as e:
        log.warning(f"Self-Learning loop failed: {e}")
        return {}
