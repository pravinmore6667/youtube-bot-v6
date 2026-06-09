"""
agents/video_agent.py
──────────────────────
Professional video assembly — maximum retention editing.
"""

import os, uuid, requests, tempfile, subprocess, math, shutil, time, gc
from tenacity import retry, stop_after_attempt, wait_exponential

import numpy as np
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeVideoClip,
    TextClip, concatenate_videoclips, ColorClip, ImageClip
)
from moviepy.video.fx.all import fadein, fadeout, crop, resize
from pydub import AudioSegment
from config import config
from utils.logger import get_logger

log = get_logger("VideoAgent")
W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT


# ── Stock footage fetchers ────────────────────────────────────


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_music(mood: str = "ambient background") -> str | None:
    if not config.ENABLE_MUSIC:
        return None
    os.makedirs(config.OUTPUT_MUSIC, exist_ok=True)
    try:
        r = requests.get("https://pixabay.com/api/",
            params={"key": config.PIXABAY_API_KEY, "q": mood,
                    "media_type": "music", "per_page": 5}, timeout=15)
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            for hit in hits:
                audio_url = hit.get("audio", {}).get("url") or hit.get("previewURL")
                if audio_url:
                    mr = requests.get(audio_url, timeout=30)
                    if mr.status_code == 200:
                        path = os.path.join(config.OUTPUT_MUSIC, f"_music_{uuid.uuid4().hex[:8]}.mp3")
                        with open(path, "wb") as f: f.write(mr.content)
                        log.info(f"  Music downloaded: {path}")
                        return path
    except Exception as e:
        log.warning(f"Music fetch failed: {e}")
        raise
    return None


def _intelligent_clip_selector(query: str, dest: str) -> str | None:
    import asyncio
    from agents.video_quality_agent import generate_and_select_best_clip
    return asyncio.run(generate_and_select_best_clip(query, dest))

def _get_clip_for_query(query: str, dest: str) -> str | None:
    from utils.stock_router import get_stock_video
    import time

    start_time = time.time()
    path = get_stock_video(query, dest, 4)
    if not path:
        path = get_stock_video(config.CHANNEL_NICHE, dest, 3)
    if not path:
        path = get_stock_video("abstract background", dest, 2)

    elapsed = time.time() - start_time
    log.info(f"Footage download duration for '{query}': {elapsed:.1f}s")
    return path




    try:
        if not config.ENABLE_ZOOM_EFFECTS:
            return clip
        dur = clip.duration
        if zoom_direction == "in":
            return clip.fl(lambda gf, t: gf(t) if True else gf(t)).resize(
                lambda t: 1 + (zoom_amount - 1) * (t / dur)
            ).crop(x_center=W/2, y_center=H/2, width=W, height=H)
        else:
            return clip.resize(
                lambda t: zoom_amount - (zoom_amount - 1) * (t / dur)
            ).crop(x_center=W/2, y_center=H/2, width=W, height=H)
    except Exception:
        return clip


def _color_grade(clip):
    try:
        def grade(frame):
            arr  = frame.astype(np.float32)
            arr  = np.clip((arr - 128) * 1.15 + 128, 0, 255)
            grey = 0.299*arr[:,:,0] + 0.587*arr[:,:,1] + 0.114*arr[:,:,2]
            grey = grey[:,:,np.newaxis]
            arr  = np.clip(grey + (arr - grey) * 1.20, 0, 255)
            return arr.astype(np.uint8)
        return clip.fl_image(grade)
    except Exception:
        return clip


def _section_title_card(heading: str, duration: float) -> TextClip | None:
    try:
        tc = (TextClip(heading.upper(), fontsize=54, font="DejaVu-Sans-Bold",
                       color="#FFD700", stroke_color="black", stroke_width=2,
                       method="caption", size=(int(W*0.7), None), align="center")
              .set_duration(min(2.5, duration))
              .set_position(("center", 72))
              .crossfadein(0.3).crossfadeout(0.3))
        return tc
    except Exception:
        return None


def _progress_bar(progress: float, duration: float) -> ColorClip:
    bar_w = max(1, int(W * progress))
    return (ColorClip((bar_w, 7), color=(255, 200, 0))
            .set_duration(duration).set_position((0, 0)))


def _lower_third(text: str, duration: float) -> TextClip | None:
    try:
        bg  = (ColorClip((500, 50), color=(0, 0, 0))
               .set_opacity(0.55).set_duration(min(3.0, duration))
               .set_position((40, H - 90)))
        txt = (TextClip(text[:55], fontsize=28, font="DejaVu-Sans",
                        color="white", method="label")
               .set_duration(min(3.0, duration))
               .set_position((50, H - 82)))
        return [bg, txt]
    except Exception:
        return None


# ── Main builder ──────────────────────────────────────────────

def build_video(audio_path: str, script: dict, job_id: str) -> str:
    os.makedirs(config.OUTPUT_VIDEO, exist_ok=True)
    output_path = os.path.join(config.OUTPUT_VIDEO, f"{job_id}_video.mp4")

    audio      = AudioFileClip(audio_path)
    total_dur  = audio.duration
    sections   = script.get("sections", [])
    n_sections = max(len(sections), 1)
    seg_dur    = total_dur / n_sections

    log.info(f"🎬 Building {total_dur:.1f}s video — {n_sections} sections")

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        niche_mood = {"technology":"cinematic electronic","finance":"corporate background",
                      "history":"epic orchestral","science":"ambient space",
                      "motivation":"inspiring uplifting","gaming":"electronic gaming",
                      "documentary":"documentary background"}.get(config.CHANNEL_NICHE, "ambient background")
        music_future = ex.submit(_fetch_music, niche_mood)

        tmp = tempfile.mkdtemp()
        try:
            import concurrent.futures as cf2
            clip_futures = {}
            with cf2.ThreadPoolExecutor(max_workers=4) as clip_ex:
                for i, section in enumerate(sections):
                    query = (section.get("broll_cue") or section.get("heading") or config.CHANNEL_NICHE)
                    query = query[:60].split(",")[0].strip()
                    clip_futures[clip_ex.submit(_intelligent_clip_selector, query, tmp)] = i

            clip_paths = {}
            for future in cf2.as_completed(clip_futures):
                idx = clip_futures[future]
                try: clip_paths[idx] = future.result()
                except Exception as e:
                    log.warning(f"Clip {idx} failed: {e}")
                    clip_paths[idx] = None

            video_clips = []
            zoom_dirs   = ["in", "out", "in", "out", "in"]

            for i, section in enumerate(sections):
                clip_path = clip_paths.get(i)
                zoom_dir  = zoom_dirs[i % len(zoom_dirs)]
                progress  = (i + 1) / n_sections

                try:
                    if clip_path and os.path.exists(clip_path):
                        log.info(f"Video path: {clip_path}")
                        log.info(f"Video size: {os.path.getsize(clip_path)} bytes")

                        probe = subprocess.run(
                            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", clip_path],
                            capture_output=True, text=True
                        )

                        if os.path.getsize(clip_path) < 100000 or probe.returncode != 0:
                            raise ValueError(f"Invalid video: {clip_path}")

                        vc = VideoFileClip(clip_path, audio=False)
                        vc = vc.resize((W, H))
                        if vc.duration < seg_dur:
                            reps = math.ceil(seg_dur / vc.duration)
                            vc   = concatenate_videoclips([vc] * reps)
                        vc = vc.subclip(0, seg_dur)
                        vc = _ken_burns(vc, zoom_dir)
                        vc = _color_grade(vc)
                    else:
                        vc = ColorClip((W, H), color=(8, 12, 28), duration=seg_dur)

                    vc = fadein(vc, 0.5)
                    vc = fadeout(vc, 0.5)

                    overlays = [vc]

                    title_card = _section_title_card(section.get("heading",""), seg_dur)
                    if title_card: overlays.append(title_card)

                    bar = _progress_bar(progress, seg_dur)
                    overlays.append(bar)

                    lower = _lower_third(section.get("heading",""), seg_dur)
                    if lower: overlays.extend(lower)

                    vc = CompositeVideoClip(overlays, size=(W, H))
                    video_clips.append(vc)

                except Exception as e:
                    log.warning(f"Section rendering failed: {e}")

                    def create_fallback_slide():
                        return ColorClip((W, H), color=(10, 14, 30), duration=seg_dur)

                    fb = create_fallback_slide()
                    video_clips.append(fb)

            if video_clips:
                video = concatenate_videoclips(video_clips, method="compose")
                if video.duration > total_dur:
                    video = video.subclip(0, total_dur)
                elif video.duration < total_dur:
                    pad   = ColorClip((W, H), color=(0,0,0), duration=total_dur - video.duration)
                    video = concatenate_videoclips([video, pad])
            else:
                video = ColorClip((W, H), color=(0,0,0), duration=total_dur)

            try:
                music_path = music_future.result()
            except Exception as e:
                log.warning(f"Failed to fetch background music: {e}")
                music_path = None

            final_audio = AudioFileClip(audio_path)

            if music_path and os.path.exists(music_path) and config.ENABLE_MUSIC:
                try:
                    music_size = os.path.getsize(music_path)
                    log.info(f"Music path: {music_path}, size: {music_size} bytes")

                    if music_size < 1000:
                        log.warning("Music file is too small, likely invalid. Proceeding without music.")
                        raise ValueError("Invalid music file size")

                    voice_audio  = AudioSegment.from_mp3(audio_path)
                    music_audio  = AudioSegment.from_mp3(music_path)

                    music_duration_s = len(music_audio) / 1000.0
                    voice_duration_s = len(voice_audio) / 1000.0
                    log.info(f"Music duration: {music_duration_s:.1f}s, Voice duration: {voice_duration_s:.1f}s")

                    # If music is very short and would loop hundreds of times, might cause issues
                    if len(music_audio) == 0:
                        raise ValueError("Music audio has 0 duration.")

                    if len(music_audio) < len(voice_audio):
                        # Calculate needed loops to avoid massive concatenation loops and list index out of range internally
                        loops_needed = math.ceil(len(voice_audio) / len(music_audio))
                        music_audio = music_audio * loops_needed

                    music_audio  = music_audio[:len(voice_audio)]
                    music_audio  = music_audio.fade_in(3000).fade_out(5000)

                    # Ensure background music volume is 15-20%. Let's default to 0.15.
                    music_volume = config.MUSIC_VOLUME if config.MUSIC_VOLUME <= 0.20 else 0.15
                    duck_db      = 20 * math.log10(music_volume)
                    music_audio  = music_audio + duck_db

                    mixed        = voice_audio.overlay(music_audio)
                    mixed_path   = audio_path.replace(".mp3", "_mixed.mp3")
                    mixed.export(mixed_path, format="mp3", bitrate="192k")

                    # Close the original before replacing it to avoid locking
                    if final_audio and hasattr(final_audio, "close"): final_audio.close()
                    final_audio  = AudioFileClip(mixed_path)
                    log.info(f"  Background music mixed in at {int(music_volume * 100)}% volume")
                except Exception as e:
                    log.warning(f"  Music mix failed: {e} — using voice only")
            else:
                log.warning("No music available or ENABLE_MUSIC is false.")

            final = video.set_audio(final_audio)
            log.info(f"🖥️  Rendering to {output_path}...")
            final.write_videofile(output_path, fps=config.VIDEO_FPS,
                                  codec="libx264", audio_codec="aac",
                                  threads=4, preset="fast", logger=None)

            log.success(f"Video built: {output_path}")

        except Exception as e:
            log.warning(f"Video rendering failed: {e}")
            raise e
        except Exception as e:
            log.warning(f"Video rendering failed: {e}")
            raise e
        finally:
            log.info("Closing video clips")
            log.info("Closing audio clips")
            log.info("Running garbage collection")

            if 'final' in locals() and final and hasattr(final, "close"): final.close()
            if 'final_audio' in locals() and final_audio and hasattr(final_audio, "close"): final_audio.close()
            if 'video' in locals() and video and hasattr(video, "close"): video.close()
            if 'audio' in locals() and audio and hasattr(audio, "close"): audio.close()

            if 'video_clips' in locals():
                for c in video_clips:
                    if c and hasattr(c, "close"): c.close()

            gc.collect()

            for _ in range(10):
                try:
                    shutil.rmtree(tmp)
                    break
                except PermissionError:
                    gc.collect()
                    time.sleep(1)

    return output_path
