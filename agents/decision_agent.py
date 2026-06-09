import asyncio
import json
from typing import Dict, Any
from router.ai_router import ask_json
from utils.logger import get_logger

log = get_logger("DecisionAgent")

async def make_autonomous_decisions(context: Any) -> Dict[str, Any]:
    """
    Autonomously decide best title, best thumbnail concept, best upload timing,
    best video length, best pacing, best provider, best niche expansion.
    Uses AI reasoning over historical data and current context.
    """
    topic_or_niche = context if isinstance(context, str) else context.get("title", str(context))

    prompt = f"""
You are a highly advanced Autonomous Decision Engine for a YouTube media company.
Based on the current topic/niche: "{topic_or_niche}"

You need to make real autonomous decisions. Consider:
- Upload timing based on general US/Global peak engagement times for this niche.
- Video length (in seconds) tailored to maximize retention for this specific topic (usually between 300 and 600 seconds).
- Editing pacing (e.g. "Fast-paced, cut every 2 seconds", "Moderate, emphasize emotion").
- A highly clickable title.
- A strong thumbnail concept.

Return a valid JSON object strictly matching this schema:
{{
    "title": str,
    "thumbnail_concept": str,
    "upload_timing": str (e.g., "17:00 UTC"),
    "target_length": int (in seconds),
    "pacing": str
}}
"""

    log.info(f"Making autonomous decisions for: {topic_or_niche[:50]}")
    try:
        decision = await ask_json(prompt, is_fast=True)
        if decision and "target_length" in decision:
            log.success("Successfully generated autonomous decisions.")
            return decision
    except Exception as e:
        log.warning(f"AI Decision making failed, falling back to heuristics: {e}")

    # Heuristic fallback if AI fails
    result = {}
    if isinstance(context, dict):
        result = dict(context)
    elif isinstance(context, str):
        result = {"title": context}

    result["upload_timing"] = "17:00 UTC"
    result["target_length"] = 420
    result["pacing"] = "Fast-paced, pattern interrupt every 15s"
    result["thumbnail_concept"] = f"Shocking revelation about {topic_or_niche}"
    return result
