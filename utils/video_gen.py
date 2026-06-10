import os, requests, time
from utils.logger import get_logger

log = get_logger("VideoGen")
KLING_API_KEY = os.getenv("KLING_API_KEY", "")

def generate_broll_kling(prompt: str, duration: int = 5,
                          output_path: str = None) -> str | None:
    """
    Generate a short B-roll clip via Kling AI.
    Falls back gracefully if no API key or credits exhausted.
    """
    if not KLING_API_KEY:
        return None
    try:
        headers = {"Authorization": f"Bearer {KLING_API_KEY}",
                   "Content-Type": "application/json"}
        payload = {
            "model": "kling-v1",
            "prompt": prompt,
            "negative_prompt": "text, watermark, blurry, low quality",
            "duration": str(duration),
            "aspect_ratio": "16:9",
            "cfg_scale": 0.5,
            "mode": "std"
        }
        resp = requests.post(
            "https://api.klingai.com/v1/videos/text2video",
            headers=headers, json=payload, timeout=30
        )
        if resp.status_code != 200:
            log.warning(f"Kling API error: {resp.status_code}")
            return None

        task_id = resp.json()["data"]["task_id"]
        # Poll for completion
        for _ in range(30):
            time.sleep(5)
            poll = requests.get(
                f"https://api.klingai.com/v1/videos/text2video/{task_id}",
                headers=headers, timeout=15
            ).json()
            status = poll["data"]["task_status"]
            if status == "succeed":
                video_url = poll["data"]["task_result"]["videos"][0]["url"]
                content = requests.get(video_url, timeout=60).content
                if output_path:
                    with open(output_path, "wb") as f:
                        f.write(content)
                    return output_path
            elif status == "failed":
                log.warning("Kling task failed")
                return None
    except Exception as e:
        log.warning(f"Kling B-roll generation failed: {e}")
    return None

def generate_music_stable_audio(prompt: str, duration: int,
                                 output_path: str) -> str | None:
    """Stable Audio Open via HuggingFace — free, higher quality than MusicGen."""
    HF_TOKEN = os.getenv("HF_TOKEN", "")
    if not HF_TOKEN:
        return None
    url = "https://api-inference.huggingface.co/models/stabilityai/stable-audio-open-1.0"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {"duration": min(duration, 47)}  # max 47s
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    if resp.status_code == 200 and len(resp.content) > 50_000:
        with open(output_path, "wb") as f:
            f.write(resp.content)
        return output_path
    return None

def generate_broll_svd(prompt: str, output_path: str) -> str | None:
    """Stable Video Diffusion via HuggingFace. 2-4 second clip."""
    HF_TOKEN = os.getenv("HF_TOKEN", "")
    if not HF_TOKEN:
        return None
    # First generate an image, then animate it
    img_url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    vid_url = "https://api-inference.huggingface.co/models/stabilityai/stable-video-diffusion-img2vid-xt"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    try:
        img_resp = requests.post(img_url, headers=headers,
                                  json={"inputs": prompt}, timeout=60)
        if img_resp.status_code != 200:
            return None
        vid_resp = requests.post(vid_url, headers=headers,
                                  data=img_resp.content, timeout=120)
        if vid_resp.status_code == 200 and len(vid_resp.content) > 50_000:
            with open(output_path, "wb") as f:
                f.write(vid_resp.content)
            return output_path
    except Exception as e:
        log.warning(f"SVD generation failed: {e}")
    return None
