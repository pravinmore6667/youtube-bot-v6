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
import requests

log = get_logger("TTSRouter")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_IDS = {
    "narrator":    "VR6AewLTigWG4xSOukaG",  # Arnold — deep cinematic
    "male_deep":   "pNInz6obpgDQGcFmaJgB",  # Adam — warm authority
    "male_young":  "ErXwobaYiN019PkySvjV",  # Antoni — energetic
    "female_warm": "21m00Tcm4TlvDq8ikWAM",  # Rachel — clear and warm
}
ELEVENLABS_DEFAULT_VOICE = "narrator"

KOKORO_VOICES = {
    "en_female_warm":  "af_heart",
    "en_female_clear": "af_sky",
    "en_male_deep":    "am_echo",
    "en_male_casual":  "am_michael",
}
KOKORO_DEFAULT_VOICE = "af_heart"
HF_TOKEN = os.getenv("HF_TOKEN", "")

PLAYHT_API_KEY   = os.getenv("PLAYHT_API_KEY", "")
PLAYHT_USER_ID   = os.getenv("PLAYHT_USER_ID", "")
PLAYHT_VOICE_IDS = {
    "male_narrator":   "s3://voice-cloning-zero-shot/"
                       "d9ff78ba-d016-47f6-b0ef-dd630f59414e/"
                       "female-cs/manifest.json",
    "male_energetic":  "larry",
    "female_narrator": "nova",
}

def _tts_playht(text: str, output_path: str, voice_key: str = "female_narrator") -> bool:
    if not PLAYHT_API_KEY or not PLAYHT_USER_ID:
        return False

    voice = PLAYHT_VOICE_IDS.get(voice_key, PLAYHT_VOICE_IDS["female_narrator"])
    url = "https://api.play.ht/api/v2/tts/stream"
    headers = {
        "AUTHORIZATION": PLAYHT_API_KEY,
        "X-USER-ID": PLAYHT_USER_ID,
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }
    payload = {
        "text": text,
        "voice": voice,
        "output_format": "mp3",
        "voice_engine": "PlayDialog"
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=60)
        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            if os.path.getsize(output_path) > 1000:
                record_success("playht")
                log.info("[TTS Router] PlayHT TTS success")
                return True
        log.warning(f"[TTS Router] PlayHT failed: {resp.status_code}")
        record_failure("playht")
        return False
    except Exception as e:
        log.warning(f"[TTS Router] PlayHT exception: {e}")
        record_failure("playht")
        return False

def _tts_kokoro(text: str, output_path: str,
                voice: str = KOKORO_DEFAULT_VOICE) -> bool:
    """
    Generate speech via HuggingFace Kokoro-82M.
    Free with HF_TOKEN. Best open-source TTS quality available.
    Returns True on success, False on failure.
    """
    if not HF_TOKEN:
        return False
    try:
        url = ("https://api-inference.huggingface.co"
               "/models/hexgrad/Kokoro-82M")
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        payload = {
            "inputs": text,
            "parameters": {"voice": voice, "speed": 1.0},
        }
        resp = requests.post(url, headers=headers,
                             json=payload, timeout=90)
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            record_success("kokoro")
            log.info("[TTS Router] Kokoro TTS success")
            return True
        elif resp.status_code == 503:
            # Model loading — wait and skip for now
            log.warning("[TTS Router] Kokoro model loading (503) — skipping")
            return False
        else:
            log.warning(f"[TTS Router] Kokoro: {resp.status_code}")
            return False
    except Exception as e:
        log.warning(f"[TTS Router] Kokoro exception: {e}")
        return False

def _tts_elevenlabs(text: str, output_path: str,
                    voice_key: str = ELEVENLABS_DEFAULT_VOICE) -> bool:
    """
    Generate speech using ElevenLabs API.
    Returns True on success, False on any failure.
    Silently skips if API key is not configured.
    """
    if not ELEVENLABS_API_KEY:
        return False

    voice_id = ELEVENLABS_VOICE_IDS.get(voice_key,
                                         ELEVENLABS_VOICE_IDS["narrator"])
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.80,
            "style": 0.25,
            "use_speaker_boost": True,
        },
    }
    try:
        resp = requests.post(url, headers=headers,
                             json=payload, timeout=60)
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            record_success("elevenlabs")
            log.info("[TTS Router] ElevenLabs success")
            return True
        elif resp.status_code == 401:
            log.warning("[TTS Router] ElevenLabs: invalid API key")
            return False
        elif resp.status_code == 429:
            log.warning("[TTS Router] ElevenLabs: quota exceeded")
            record_failure("elevenlabs")
            return False
        else:
            log.warning(f"[TTS Router] ElevenLabs: {resp.status_code}")
            return False
    except Exception as e:
        log.warning(f"[TTS Router] ElevenLabs exception: {e}")
        record_failure("elevenlabs")
        return False

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

    # ── ElevenLabs (most human, free 10K chars/month) ────────
    if ELEVENLABS_API_KEY and check_provider_health("elevenlabs"):
        try:
            tmp_files = []
            all_ok = True
            for i, chunk in enumerate(chunks):
                tmp = os.path.join(config.OUTPUT_AUDIO,
                                   f"_tmp_{job_id}_{i}_el.mp3")
                if not _tts_elevenlabs(chunk, tmp, voice):
                    all_ok = False
                    break
                tmp_files.append(tmp)

            if all_ok and tmp_files:
                section_pause = AudioSegment.silent(duration=400)
                combined = AudioSegment.from_mp3(tmp_files[0])
                for f in tmp_files[1:]:
                    combined = combined + section_pause + \
                                AudioSegment.from_mp3(f)
                combined = _post_process(combined)
                combined.export(output_path, format="mp3", bitrate="192k",
                                tags={"title": "AI Voice", "artist": config.CHANNEL_NAME})
                for f in tmp_files:
                    try: os.remove(f)
                    except: pass
                _save_cache(output_path, clean_text, voice)
                return output_path
        except Exception as e:
            log.warning(f"[TTS Router] ElevenLabs pipeline failed: {e}")

    # ── Kokoro TTS (free, HF_TOKEN, best open-source quality)
    if HF_TOKEN and check_provider_health("kokoro"):
        try:
            tmp_files = []
            all_ok = True
            for i, chunk in enumerate(chunks):
                tmp = os.path.join(config.OUTPUT_AUDIO,
                                   f"_tmp_{job_id}_{i}_kokoro.mp3")
                if not _tts_kokoro(chunk, tmp, voice):
                    all_ok = False
                    break
                tmp_files.append(tmp)

            if all_ok and tmp_files:
                section_pause = AudioSegment.silent(duration=400)
                combined = AudioSegment.from_mp3(tmp_files[0])
                for f in tmp_files[1:]:
                    combined = combined + section_pause + \
                                AudioSegment.from_mp3(f)
                combined = _post_process(combined)
                combined.export(output_path, format="mp3", bitrate="192k",
                                tags={"title": "AI Voice", "artist": config.CHANNEL_NAME})
                for f in tmp_files:
                    try: os.remove(f)
                    except: pass
                _save_cache(output_path, clean_text, voice)
                return output_path
        except Exception as e:
            log.warning(f"[TTS Router] Kokoro pipeline failed: {e}")

    # ── PlayHT (ultra realistic, 12.5k words free)
    if PLAYHT_API_KEY and check_provider_health("playht"):
        try:
            tmp_files = []
            all_ok = True
            for i, chunk in enumerate(chunks):
                tmp = os.path.join(config.OUTPUT_AUDIO,
                                   f"_tmp_{job_id}_{i}_playht.mp3")
                if not _tts_playht(chunk, tmp, voice):
                    all_ok = False
                    break
                tmp_files.append(tmp)

            if all_ok and tmp_files:
                section_pause = AudioSegment.silent(duration=400)
                combined = AudioSegment.from_mp3(tmp_files[0])
                for f in tmp_files[1:]:
                    combined = combined + section_pause + \
                                AudioSegment.from_mp3(f)
                combined = _post_process(combined)
                combined.export(output_path, format="mp3", bitrate="192k",
                                tags={"title": "AI Voice", "artist": config.CHANNEL_NAME})
                for f in tmp_files:
                    try: os.remove(f)
                    except: pass
                _save_cache(output_path, clean_text, voice)
                return output_path
        except Exception as e:
            log.warning(f"[TTS Router] PlayHT pipeline failed: {e}")

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
