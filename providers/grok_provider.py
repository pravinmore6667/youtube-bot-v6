import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("GrokProvider")

class GrokProvider(BaseProvider):
    name = "grok"
    tier = 5
    timeout = 15

    def is_configured(self) -> bool:
        return bool(config.GROK_API_KEY) and not config.GROK_API_KEY.startswith("your_")

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        model = "grok-2" # Use appropriate primary production model name
        self.current_model = model

        # xAI Grok API uses OpenAI compatible endpoints
        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.GROK_API_KEY}",
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
                    raise RuntimeError(f"Grok error {resp.status}: {text}")

manager.register(GrokProvider())
