import asyncio
from typing import Dict, Any
from router.ai_router import ask

async def optimize_for_shorts(script: str, video_data: Dict[str, Any]) -> str:
    """
    1-second hook optimization, replay-loop ending, mobile-first editing,
    dynamic subtitles, and fast pacing specifically for short-form content.
    """
    prompt = f"""
You are an expert YouTube Shorts and TikTok editor.
Rewrite the following script to be highly optimized for a 60-second vertical format:
1. Extract or create an intense 1-2 second opening hook.
2. Ensure fast pacing — no fluff, constant pattern interrupts in the wording.
3. Add a replay-loop ending (the last sentence should naturally lead into the first sentence).

Original Script:
{script}

Return ONLY the rewritten script, ready to be read.
"""
    try:
        optimized = await ask(prompt, is_fast=True)
        return optimized.strip()
    except Exception:
        # Fallback to the original stub behavior
        return "[Shorts Hook]\n" + script + "\n[Replay Loop Ending]"
