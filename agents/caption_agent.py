"""
agents/caption_agent.py
────────────────────────
Auto captions via faster-whisper (FREE, local CPU).
Supports English + Hindi transcription.
Burns captions into video with professional styling.
"""

import os, subprocess
from config import config
from utils.logger import get_logger

log = get_logger("CaptionAgent")

_model = None

def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        lang  = config.CHANNEL_LANGUAGE
        msize = "small" if lang == "hi" else "tiny"
        log.info(f"Loading Whisper '{msize}' model...")
        _model = WhisperModel(msize, device="cpu", compute_type="int8")
    return _model


def generate_srt(audio_path: str, job_id: str) -> str:
    os.makedirs(config.OUTPUT_CAPTIONS, exist_ok=True)
    srt_path = os.path.join(config.OUTPUT_CAPTIONS, f"{job_id}.srt")
    lang     = config.CHANNEL_LANGUAGE if config.CHANNEL_LANGUAGE in ["en","hi"] else "en"

    log.info(f"📝 Transcribing ({lang})...")
    model = _get_model()
    segments, _ = model.transcribe(audio_path, language=lang,
                                   beam_size=3, word_timestamps=False,
                                   vad_filter=True)

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n{_ts(seg.start)} --> {_ts(seg.end)}\n{seg.text.strip()}\n\n")

    log.success(f"SRT: {srt_path}")
    return srt_path


def burn_captions(video_path: str, srt_path: str) -> str:
    """Burn styled captions into video using FFmpeg."""
    log.info("🔥 Burning captions...")
    escaped = srt_path.replace("\\","/").replace(":","\\:")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", (
            f"subtitles='{escaped}':"
            "force_style='FontName=DejaVu Sans,FontSize=20,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "Outline=2,Shadow=1,Alignment=2,MarginV=45,"
            "Bold=1'"
        ),
        "-c:a", "copy", "-c:v", "libx264",
        "-preset", "fast", "-crf", "22",
        video_path + "_cap.mp4"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        os.replace(video_path + "_cap.mp4", video_path)
        log.success("Captions burned")
    else:
        log.warning(f"Caption burn failed: {res.stderr[:150]}")
    return video_path


def _ts(s: float) -> str:
    ms = int((s % 1)*1000); s = int(s)
    m = s // 60; s %= 60; h = m // 60; m %= 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
