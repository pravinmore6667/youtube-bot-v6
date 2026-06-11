"""
Sarvam AI TTS — Best Hindi/Indian language TTS.
Register FREE at https://console.sarvam.ai (500 API calls/day on free tier).
Supports: Hindi, Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati, Marathi.
"""
import os, requests, base64, tempfile
from utils.text_utils import sanitize_for_tts

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

SARVAM_VOICES = {
    "hi": {"female": "meera",   "male": "arvind"},
    "ta": {"female": "pavithra","male": "amol"},
    "te": {"female": "maitreyi","male": "amartya"},
    "bn": {"female": "meera",   "male": "arvind"},
}

def sarvam_tts(text: str, language: str = "hi-IN",
               voice: str = "meera", output_path: str = None) -> str:
    if not SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY not configured")

    text = sanitize_for_tts(text)
    # Sarvam max input: 500 chars per call — chunk if needed
    chunks = [text[i:i+450] for i in range(0, len(text), 450)]
    raw_audio = b""

    for chunk in chunks:
        r = requests.post(
            "https://api.sarvam.ai/text-to-speech",
            headers={"api-subscription-key": SARVAM_API_KEY,
                     "Content-Type": "application/json"},
            json={
                "inputs": [chunk],
                "target_language_code": language,
                "speaker": voice,
                "pitch": 0,
                "pace": 1.0,
                "loudness": 1.5,
                "speech_sample_rate": 22050,
                "enable_preprocessing": True,
                "model": "bulbul:v1",
            },
            timeout=30,
        )
        r.raise_for_status()
        raw_audio += base64.b64decode(r.json()["audios"][0])

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".wav")
    with open(output_path, "wb") as f:
        f.write(raw_audio)
    return output_path
