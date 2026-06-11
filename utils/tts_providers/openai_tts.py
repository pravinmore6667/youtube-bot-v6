import os, tempfile
from openai import OpenAI
from utils.text_utils import sanitize_for_tts

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

def openai_tts(text: str, voice: str = "nova", output_path: str = None) -> str:
    """Voices: alloy, echo, fable, onyx, nova, shimmer"""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set")
    text = sanitize_for_tts(text)
    client = OpenAI(api_key=OPENAI_API_KEY)
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mp3")
    response = client.audio.speech.create(model="tts-1", voice=voice, input=text)
    response.stream_to_file(output_path)
    return output_path
