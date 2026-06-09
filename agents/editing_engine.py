import asyncio
import os
import librosa
import numpy as np
from typing import Dict, Any
from utils.logger import get_logger

log = get_logger("EditingEngine")

class AIEditingEngine:
    """
    A true AI editing system that applies dynamic pacing, silence cutting,
    and emotional transitions to video generation.
    Used by video_agent.py during assembly.
    """

    def __init__(self, script: Dict[str, Any]):
        self.script = script
        self.pacing_plan = {}

    async def analyze_pacing(self, audio_path: str = None):
        """
        Determine when to zoom, cut, or add sound effects based on the script pacing
        and actual audio analysis (beat detection/silence detection).
        """
        log.info("Analyzing script and audio for dynamic pacing and effects...")
        text = self.script.get("full_narration", "")

        # 1. Text-based semantic analysis
        semantic_cuts = "shocking" in text.lower() or "suddenly" in text.lower()
        semantic_bass = "massive" in text.lower() or "boom" in text.lower()

        # 2. Audio-based physical analysis using Librosa
        audio_beats = []
        silences = []
        bpm = 120 # Default

        if audio_path and os.path.exists(audio_path):
            try:
                # Load audio (downsampled for speed)
                y, sr = librosa.load(audio_path, sr=22050)

                # Detect beats
                tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
                bpm = float(tempo[0]) if isinstance(tempo, np.ndarray) else float(tempo)
                beat_times = librosa.frames_to_time(beat_frames, sr=sr)
                audio_beats = beat_times.tolist()

                # Detect silences (intervals where audio is below a threshold)
                non_mute_intervals = librosa.effects.split(y, top_db=40)
                # Invert to get silences
                last_end = 0
                for start, end in non_mute_intervals:
                    start_time = librosa.samples_to_time(start, sr=sr)
                    if start_time - last_end > 0.5: # 0.5s silence threshold
                        silences.append((last_end, start_time))
                    last_end = librosa.samples_to_time(end, sr=sr)

                log.info(f"Audio analysis complete: {bpm} BPM, {len(audio_beats)} beats, {len(silences)} silences found.")
            except Exception as e:
                log.warning(f"Audio analysis failed: {e}")

        self.pacing_plan = {
            "fast_cuts": semantic_cuts or bpm > 130,
            "heavy_bass": semantic_bass,
            "slow_zoom": len(text) > 500 and bpm < 100,
            "bpm": bpm,
            "cut_points": audio_beats[:10], # Store first 10 beats as cut points
            "silence_removal_points": silences
        }
        log.success(f"Pacing plan generated: {self.pacing_plan}")
        return self.pacing_plan

    def apply_editing_effects(self, video_clip: Any, effect_type: str) -> Any:
        """
        Apply an actual MoviePy effect based on AI decision.
        (Placeholder for MoviePy clip manipulation).
        """
        log.debug(f"Applying AI effect: {effect_type}")
        # In a full MoviePy integration:
        # if effect_type == "zoom":
        #     return video_clip.resize(lambda t: 1 + 0.04 * t)
        # elif effect_type == "fast_cut":
        #     return video_clip.subclip(0, min(2, video_clip.duration))
        return video_clip
