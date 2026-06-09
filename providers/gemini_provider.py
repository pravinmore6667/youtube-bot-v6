import aiohttp
import json
from config import config
from router.provider_manager import BaseProvider, manager
from router.gemini_pool import pool
from utils.logger import get_logger

log = get_logger("GeminiProvider")

class GeminiProvider(BaseProvider):
    name = "gemini"
    tier = 1
    timeout = 20

    def is_configured(self) -> bool:
        return len(pool.get_all_keys()) > 0

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        key_obj = pool.get_active_key()
        if not key_obj:
            raise RuntimeError("All Gemini keys are exhausted or in cooldown.")

        model = "gemini-2.5-flash" if is_fast else "gemini-2.0-flash"
        self.current_model = model

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key_obj.key}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": max_tokens
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    key_obj.mark_success()
                    try:
                        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    except (KeyError, IndexError):
                        raise ValueError(f"Unexpected response format from Gemini: {data}")
                elif resp.status == 429:
                    # 429 Too Many Requests
                    key_obj.mark_exhausted()
                    raise RuntimeError("Gemini rate limit exceeded.")
                else:
                    text = await resp.text()
                    if "RESOURCE_EXHAUSTED" in text or "quota exceeded" in text.lower():
                        key_obj.mark_exhausted()
                    raise RuntimeError(f"Gemini error {resp.status}: {text}")

manager.register(GeminiProvider())
