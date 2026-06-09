import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("GroqProvider")

class GroqProvider(BaseProvider):
    name = "groq"
    tier = 3
    timeout = 10

    def is_configured(self) -> bool:
        return bool(config.GROQ_API_KEY) and not config.GROQ_API_KEY.startswith("your_")

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        model = "llama-3.1-8b-instant" if is_fast else "llama-3.3-70b-versatile"
        self.current_model = model

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.35
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    text = await resp.text()
                    raise RuntimeError(f"Groq error {resp.status}: {text}")

manager.register(GroqProvider())
