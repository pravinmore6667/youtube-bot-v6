import os
import requests
import time
from utils.logger import get_logger

log = get_logger("MusicGen")

HF_TOKEN = os.getenv("HF_TOKEN", "")

MUSICGEN_MODELS = [
    "facebook/musicgen-small",   # Fastest, 300M params
    "facebook/musicgen-medium",  # Better quality, 1.5B params
]

NICHE_MUSIC_PROMPTS = {
    "technology":  "cinematic electronic ambient, subtle tension, "
                   "futuristic pads, 120bpm, no vocals, background music",
    "finance":     "corporate cinematic, confident strings, subtle piano, "
                   "professional tone, 100bpm, no vocals",
    "history":     "epic orchestral, dramatic strings, cinematic score, "
                   "historical grandeur, 90bpm, no vocals",
    "science":     "mysterious ambient electronic, discovery theme, "
                   "evolving pads, 110bpm, no vocals",
    "gaming":      "energetic electronic, driving beat, intense, "
                   "150bpm, no vocals",
    "health":      "calm uplifting, light piano, positive energy, "
                   "85bpm, no vocals",
    "motivation":  "inspiring cinematic, building strings, triumphant, "
                   "120bpm, no vocals",
    "default":     "cinematic background music, neutral tone, "
                   "atmospheric, 100bpm, no vocals",
}

MIN_VALID_BYTES = 50_000

def generate_background_music(niche: str, duration_hint: int = 60,
                               output_path: str = None) -> str | None:
    """
    Generate background music with fallback chain:
    1. Pixabay Music
    2. Jamendo Music
    3. Silent track (fallback)
    """
    if output_path is None:
        output_path = f"output/music/_music_{niche}_{int(time.time())}.mp3"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    from utils.music_providers.pixabay_music import pixabay_music, PIXABAY_API_KEY
    from utils.music_providers.jamendo_music import jamendo_music, JAMENDO_CLIENT_ID

    if PIXABAY_API_KEY:
        try:
            log.info("Generating music via Pixabay...")
            return pixabay_music(niche, output_path)
        except Exception as e:
            log.warning(f"Pixabay failed: {e}")

    if JAMENDO_CLIENT_ID:
        try:
            log.info("Generating music via Jamendo...")
            return jamendo_music(niche, output_path)
        except Exception as e:
            log.warning(f"Jamendo failed: {e}")

    log.warning("All music providers failed (or none configured) — using silent track")
    return _create_silent_track(duration_hint, output_path)


def _create_silent_track(duration_secs: int,
                          output_path: str) -> str | None:
    """Creates a valid but silent audio file as absolute last resort."""
    try:
        from pydub import AudioSegment
        silence = AudioSegment.silent(duration=duration_secs * 1000)
        silence.export(output_path, format="mp3", bitrate="64k")
        log.info(f"Silent track created: {output_path}")
        return output_path
    except Exception as e:
        log.warning(f"Silent track creation failed: {e}")
        return None