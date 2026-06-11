"""gTTS — Free Google TTS. Excellent Hindi support. pip install gTTS"""
import tempfile
from gtts import gTTS
from utils.text_utils import sanitize_for_tts

def gtts_tts(text: str, lang: str = "hi", output_path: str = None) -> str:
    text = sanitize_for_tts(text)
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mp3")
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(output_path)
    return output_path
