import os
import asyncio
import hashlib
import json
import time
from gtts import gTTS
from pydub import AudioSegment, effects
from config import config
from utils.logger import get_logger
from utils.provider_health import check_provider_health, record_success, record_failure
from agents.voice_agent import _tts_async, _split_text, _preprocess_text

log = get_logger("TTSRouter")

CACHE_DIR = "cache/tts"
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL = 7 * 24 * 60 * 60  # 7 days

def _get_cache_key(text: str, voice: str) -> str:
    key_str = f"{text}_{voice}"
    key_hash = hashlib.md5(key_str.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{key_hash}.mp3")

def _check_cache(text: str, voice: str) -> str | None:
    cache_path = _get_cache_key(text, voice)
    if os.path.exists(cache_path):
        if os.path.getmtime(cache_path) + CACHE_TTL > time.time():
            return cache_path
    return None

def _save_cache(source_path: str, text: str, voice: str):
    cache_path = _get_cache_key(text, voice)
    import shutil
    shutil.copy(source_path, cache_path)

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

def generate_voice(script_text: str, job_id: str) -> str:
    """
    Intelligently routes to TTS providers.
    Tries Edge-TTS first, then gTTS as a fallback.
    Returns path to processed MP3.
    """
    os.makedirs(config.OUTPUT_AUDIO, exist_ok=True)
    output_path = os.path.join(config.OUTPUT_AUDIO, f"{job_id}_voice.mp3")
    voice = config.get_tts_voice()
    lang = config.CHANNEL_LANGUAGE

    log.info(f"🎙️ Voice: {voice} | lang: {lang}")
    clean_text = _preprocess_text(script_text, lang)

    # Check Cache
    cached_path = _check_cache(clean_text, voice)
    if cached_path:
        log.info("[TTS Router] Cache hit")
        import shutil
        shutil.copy(cached_path, output_path)
        return output_path

    chunks = _split_text(clean_text)

    # Try Edge-TTS
    if check_provider_health("edge_tts"):
        try:
            tmp_files = []
            for i, chunk in enumerate(chunks):
                tmp = os.path.join(config.OUTPUT_AUDIO, f"_tmp_{job_id}_{i}.mp3")
                asyncio.run(_tts_async(chunk, tmp, voice,
                                       config.TTS_RATE, config.TTS_VOLUME, config.TTS_PITCH))

                # Check for empty audio
                if not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
                    raise RuntimeError("edge-tts generated empty audio")

                tmp_files.append(tmp)

            section_pause = AudioSegment.silent(duration=400)
            combined = AudioSegment.from_mp3(tmp_files[0])
            for f in tmp_files[1:]:
                combined = combined + section_pause + AudioSegment.from_mp3(f)

            combined = _post_process(combined)
            combined.export(output_path, format="mp3", bitrate="192k",
                            tags={"title": "AI Voice", "artist": config.CHANNEL_NAME})

            for f in tmp_files:
                try: os.remove(f)
                except: pass

            record_success("edge_tts")
            _save_cache(output_path, clean_text, voice)
            log.info("[TTS Router] Edge-TTS success")
            return output_path

        except Exception as e:
            record_failure("edge_tts")
            log.info(f"[TTS Router] Edge-TTS failed: {e}")
            log.info("[TTS Router] Switching to gTTS")
    else:
        log.info("[TTS Router] Edge-TTS degraded, Switching to gTTS")

    # Fallback to gTTS
    if check_provider_health("gtts"):
        try:
            tmp_files = []
            for i, chunk in enumerate(chunks):
                tmp = os.path.join(config.OUTPUT_AUDIO, f"_tmp_{job_id}_{i}_gtts.mp3")
                tts = gTTS(text=chunk, lang=lang, slow=False)
                tts.save(tmp)

                # Check for empty audio
                if not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
                    raise RuntimeError("gTTS generated empty audio")

                tmp_files.append(tmp)

            section_pause = AudioSegment.silent(duration=400)
            combined = AudioSegment.from_mp3(tmp_files[0])
            for f in tmp_files[1:]:
                combined = combined + section_pause + AudioSegment.from_mp3(f)

            combined = _post_process(combined)
            combined.export(output_path, format="mp3", bitrate="192k",
                            tags={"title": "AI Voice", "artist": config.CHANNEL_NAME})

            for f in tmp_files:
                try: os.remove(f)
                except: pass

            record_success("gtts")
            _save_cache(output_path, clean_text, voice)
            log.info("[TTS Router] gTTS success")
            return output_path

        except Exception as e:
            record_failure("gtts")
            log.warning(f"[TTS Router] gTTS failed: {e}")

    raise RuntimeError("Both TTS providers failed")
