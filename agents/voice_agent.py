"""
agents/voice_agent.py
──────────────────────
Realistic voice generation using edge-tts (100% FREE, unlimited).
Supports English + Hindi neural voices.
Features:
  • Natural SSML-like pacing via text preprocessing
  • Emphasis markers for dramatic words
  • Section pauses for breathing room
  • Post-processing: normalisation + subtle compression
"""

import os, re, asyncio
from pydub import AudioSegment, effects
from config import config
from utils.logger import get_logger

log = get_logger("VoiceAgent")

CHUNK_CHARS = 2800


def _preprocess_text(text: str, lang: str) -> str:
    """
    Enhance text for more natural TTS delivery.
    edge-tts responds well to punctuation and formatting.
    """
    # Add pauses at paragraph breaks
    text = text.replace("\n\n", " ... ")
    # Convert em dashes to pauses
    text = text.replace("—", ", ")
    text = text.replace(" – ", ", ")
    # Ensure sentences end with proper punctuation for natural pauses
    text = re.sub(r'([a-zA-Z\u0900-\u097F])\n', r'\1. ', text)
    # Add micro-pause after colons
    text = text.replace(": ", "... ")
    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    # Remove markdown artifacts
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#{1,6}\s', '', text)
    return text.strip()


def _split_text(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    """Split on sentence boundaries, keeping chunks under max_chars."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current = [], ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_chars:
            if current.strip():
                chunks.append(current.strip())
            current = sentence + " "
        else:
            current += sentence + " "
    if current.strip():
        chunks.append(current.strip())
    return chunks


async def _tts_async(text: str, output_path: str, voice: str,
                     rate: str, volume: str, pitch: str):
    """Run edge-tts for one chunk."""
    cmd = [
        "edge-tts",
        "--voice",       voice,
        "--rate",        rate,
        "--volume",      volume,
        "--pitch",       pitch,
        "--text",        text,
        "--write-media", output_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"edge-tts error: {stderr.decode()[:200]}")


def _post_process(audio: AudioSegment) -> AudioSegment:
    """
    Apply audio post-processing for a more polished, professional sound:
    - Normalise loudness
    - Light dynamic compression
    - Slight high-frequency boost for clarity
    """
    # Normalise to -3 dBFS
    audio = effects.normalize(audio)
    # Boost presence slightly (treble)
    try:
        audio = audio.high_pass_filter(80)   # Remove low rumble
    except Exception:
        pass
    return audio


# We delegate to the router now
def generate_voice(script_text: str, job_id: str) -> str:
    from utils.tts_router import generate_voice as router_generate_voice
    return router_generate_voice(script_text, job_id)
