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
    Generate background music via HuggingFace MusicGen.
    Returns path to valid audio file, or None on failure.
    Falls back to silent track if all generation fails.
    """
    if not HF_TOKEN:
        log.warning("HF_TOKEN not set — cannot generate music")
        return _create_silent_track(duration_hint, output_path)

    if output_path is None:
        output_path = f"output/music/_music_{niche}_{int(time.time())}.mp3"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    prompt = NICHE_MUSIC_PROMPTS.get(
        niche, NICHE_MUSIC_PROMPTS["default"]
    )
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}

    for model in MUSICGEN_MODELS:
        try:
            url = f"https://api-inference.huggingface.co/models/{model}"
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": min(duration_hint * 50, 1500),
                    "do_sample": True,
                    "guidance_scale": 3.0,
                },
            }
            log.info(f"Generating music via {model} for niche: {niche}")
            resp = requests.post(url, headers=headers,
                                 json=payload, timeout=180)

            if resp.status_code == 503:
                log.warning(f"MusicGen model loading — waiting 15s...")
                time.sleep(15)
                resp = requests.post(url, headers=headers,
                                     json=payload, timeout=180)

            if resp.status_code == 200 and len(resp.content) > MIN_VALID_BYTES:
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                log.info(f"Music generated: {len(resp.content)} bytes "
                         f"via {model}")
                return output_path
            else:
                log.warning(f"MusicGen {model}: {resp.status_code}, "
                            f"{len(resp.content)} bytes")
        except Exception as e:
            log.warning(f"MusicGen {model} failed: {e}")
            continue

    log.warning("All MusicGen models failed — using silent track")
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