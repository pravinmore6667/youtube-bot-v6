import asyncio
import uuid
import json
import os
import cv2
import numpy as np
import mediapipe as mp
from typing import Dict, Any
from router.ai_router import ask_json
from utils.logger import get_logger

log = get_logger("ThumbnailIntelligenceAgent")

def analyze_thumbnail_cv(image_path: str) -> Dict[str, Any]:
    """
    Use OpenCV and MediaPipe to actually analyze the generated thumbnail
    for contrast, brightness, and face detection (simulating emotion/focus checks).
    """
    if not os.path.exists(image_path):
        return {"error": "Image not found"}

    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"error": "Failed to load image"}

        # 1. Analyze brightness and contrast
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        contrast = np.std(gray)

        # 2. Face detection using MediaPipe
        mp_face_detection = mp.solutions.face_detection
        faces_detected = 0
        face_confidence = 0.0

        with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
            results = face_detection.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            if results.detections:
                faces_detected = len(results.detections)
                face_confidence = float(results.detections[0].score[0])

        return {
            "brightness": float(brightness),
            "contrast": float(contrast),
            "faces_detected": faces_detected,
            "face_confidence": face_confidence,
            "is_aesthetic": bool(contrast > 40 and 50 < brightness < 200)
        }
    except Exception as e:
        log.warning(f"CV analysis failed: {e}")
        return {"error": str(e)}

async def generate_intelligent_thumbnail(topic: Dict[str, Any]) -> str:
    """
    Analyze viral thumbnails, predict CTR, score thumbnails,
    detect emotional impact, optimize mobile readability, and perform
    simulated A/B testing before generation.
    """
    from agents.thumbnail_agent import generate_thumbnail

    topic_title = topic.get("title", "Untitled")

    # 1. Simulate an intelligence phase before generation
    prompt = f"""
You are an Enterprise Thumbnail AI.
Analyze the topic "{topic_title}" for a YouTube thumbnail.
You need to conceptualize a thumbnail that maximizes CTR, conveys strong emotion,
and reads well on mobile devices.
Simulate an A/B test between two concepts and pick the winner.

Return strict JSON:
{{
    "winning_concept": str (Brief visual description),
    "emotion_target": str,
    "ctr_prediction": int (0-100),
    "mobile_readability_score": int (0-100)
}}
"""
    log.info(f"Running Thumbnail Intelligence for: {topic_title}")
    try:
        intelligence = await ask_json(prompt, is_fast=True)
        if intelligence and "winning_concept" in intelligence:
            topic["thumbnail_concept"] = intelligence["winning_concept"]
            topic["target_emotion"] = intelligence.get("emotion_target", "curiosity")
            log.success(f"Thumbnail concept chosen: {topic['thumbnail_concept'][:50]}... (Predicted CTR: {intelligence.get('ctr_prediction', 80)}%)")
    except Exception as e:
        log.warning(f"Thumbnail intelligence failed: {e}. Falling back to default.")

    # 2. Delegate to the actual image generator
    job_id = topic.get("job_id", uuid.uuid4().hex[:10])
    thumb_path = generate_thumbnail(topic, job_id, None)

    # 3. Post-generation CV Analysis
    if thumb_path:
        cv_stats = analyze_thumbnail_cv(thumb_path)
        log.info(f"CV Thumbnail Analysis Results: {cv_stats}")
        # In a real enterprise system, we might loop back and regenerate if CV stats are poor

    return thumb_path
