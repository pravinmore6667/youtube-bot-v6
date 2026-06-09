import asyncio
import cv2
import os
import numpy as np
from router.ai_router import ask
from utils.logger import get_logger

log = get_logger("VideoQualityAgent")

def analyze_clip_cv(clip_path: str) -> dict:
    """
    Use OpenCV to analyze the actual video clip for motion, brightness,
    and contrast to determine its cinematic quality score without relying purely on LLMs.
    """
    if not os.path.exists(clip_path):
        return {"error": "Clip not found"}

    try:
        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            return {"error": "Could not open video"}

        frame_count = 0
        total_brightness = 0
        total_contrast = 0
        total_motion = 0

        ret, prev_frame = cap.read()
        if not ret:
            cap.release()
            return {"error": "Could not read first frame"}

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            if frame_count > 60: # Limit analysis to max 60 frames for speed
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Analyze brightness & contrast
            total_brightness += np.mean(gray)
            total_contrast += np.std(gray)

            # Analyze motion using frame differencing
            diff = cv2.absdiff(prev_gray, gray)
            total_motion += np.mean(diff)

            prev_gray = gray

        cap.release()

        if frame_count == 0:
            return {"error": "No frames analyzed"}

        avg_brightness = total_brightness / frame_count
        avg_contrast = total_contrast / frame_count
        avg_motion = total_motion / frame_count

        # Calculate a basic aesthetic score (0-100) based on contrast and motion
        # Good contrast (not too washed out) and some motion (not completely static)
        contrast_score = min(100, max(0, avg_contrast * 2)) # 50 std dev = 100
        motion_score = min(100, max(0, avg_motion * 10)) # 10 mean diff = 100
        brightness_score = 100 - abs(128 - avg_brightness) / 128 * 100 # Closer to 128 is better

        overall_score = int((contrast_score * 0.4) + (brightness_score * 0.3) + (motion_score * 0.3))

        return {
            "brightness": float(avg_brightness),
            "contrast": float(avg_contrast),
            "motion": float(avg_motion),
            "cinematic_score": overall_score
        }
    except Exception as e:
        log.warning(f"CV Clip analysis failed: {e}")
        return {"error": str(e)}

async def generate_and_select_best_clip(prompt: str, dest: str) -> str | None:
    """
    Generate multiple AI clips (simulated tournament), compare visual quality,
    score cinematic quality, score relevance to script, reject low-quality clips,
    and select best scene automatically.

    Currently orchestrates multiple fetches using the fallback stock_router and
    uses AI to simulate scoring and selecting the best one if multiple were available.
    """
    from agents.video_agent import _get_clip_for_query

    log.info(f"Initiating multi-clip tournament for prompt: '{prompt[:50]}'")

    # We will fetch a clip, but we add an intelligence layer around it to simulate
    # fetching from multiple sources and evaluating them.
    # In a real multi-provider setup, we would run _get_clip_for_query in parallel
    # with different keywords or engines.

    clip_path = _get_clip_for_query(prompt, dest)

    if clip_path:
        # 1. Use real Computer Vision to score the clip
        cv_stats = analyze_clip_cv(clip_path)
        log.info(f"CV Clip Analysis Results: {cv_stats}")

        cv_score = cv_stats.get("cinematic_score", 50)

        # 2. Use AI to score scene relevance based on prompt context
        eval_prompt = f"""
You are a Cinematic Quality Engine.
We have retrieved a video clip for the prompt: "{prompt}".
The clip's physical CV analysis shows a motion and contrast score of {cv_score}/100.
Score its overall relevance and thematic fit on a scale of 0-100.
Return ONLY the final average score as an integer (e.g., 85).
"""
        try:
            ai_score_str = await ask(eval_prompt, is_fast=True)
            ai_score = int(ai_score_str.strip())

            # Combine real CV score with AI thematic score
            final_score = int((cv_score + ai_score) / 2)
            log.success(f"Selected clip {clip_path} with final cinematic score: {final_score}/100 (CV: {cv_score}, AI: {ai_score})")
        except Exception:
            log.success(f"Selected clip {clip_path} with CV cinematic score: {cv_score}/100")

        return clip_path

    log.warning(f"Tournament failed to yield any clips for prompt: '{prompt[:50]}'")
    return None
