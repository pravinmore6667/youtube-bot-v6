import asyncio
from router.ai_router import ask

async def humanize_script(script: str) -> str:
    """
    Apply human speech pacing, emotional emphasis, natural pauses,
    imperfect speech rhythm, and storytelling enhancement.
    Avoids robotic outputs for TTS processing.
    """
    if "[Humanized]" in script:
        return script

    prompt = f"""
You are a Humanization Speech Engine for Text-to-Speech (TTS).
Your task is to take the following script and insert natural speech patterns.
Feel free to add minor filler words (like "well,", "you see,"), and use punctuation like ellipses (...) or em-dashes (—) to force the TTS engine to pause naturally.

Do not output any reasoning or conversational text. Output ONLY the humanized script.

Script to humanize:
{script}
"""
    try:
        humanized = await ask(prompt, is_fast=False)
        return "[Humanized]\n" + humanized.strip()
    except Exception:
        return script
