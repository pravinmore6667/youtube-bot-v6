import asyncio
from router.ai_router import ask
from utils.logger import get_logger

log = get_logger("RetentionAgent")

async def optimize_retention(script: str) -> str:
    """
    Deep Retention Optimization:
    Insert curiosity loops, add pattern interrupts every 20-40 sec,
    detect boring segments, improve pacing dynamically, add emotional
    transitions, and dopamine spikes.
    """
    if "[Optimized for Retention]" in script:
        return script

    prompt = f"""
You are a YouTube Retention Optimization Engine.
Your task is to deeply rewrite the following script to maximize watch time, session duration, and replay value.
Apply the following retention strategies:
1. Insert "curiosity loops" (e.g., teasing a massive reveal for later in the video).
2. Insert "[Pattern Interrupt]" or "[Visual Hook]" markers where pacing slows down (every 20-40 seconds).
3. Enhance emotional transitions between points.
4. Add dopamine spikes (exciting phrasing, high energy words).
5. Remove any boring, generic, or robotic fluff.

Do not output any reasoning or conversational text. Output ONLY the optimized script.

Script to optimize:
{script}
"""
    log.info("Applying deep retention optimization to script...")
    try:
        optimized = await ask(prompt, is_fast=False)
        return "[Optimized for Retention]\n" + optimized.strip()
    except Exception as e:
        log.warning(f"Retention optimization failed, using original script. Error: {e}")
        return script
