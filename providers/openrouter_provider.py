import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("OpenRouterProvider")

class OpenRouterProvider(BaseProvider):
    name = "openrouter"
    tier = 2
    timeout = 30

    def is_configured(self) -> bool:
        return bool(config.OPENROUTER_API_KEY)

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        # Select model based on speed requirement
        model = "google/gemini-2.5-flash" if is_fast else "anthropic/claude-3.5-sonnet"
        self.current_model = model

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    try:
                        return data["choices"][0]["message"]["content"].strip()
                    except (KeyError, IndexError):
                        raise ValueError(f"Unexpected response format from OpenRouter: {data}")
                else:
                    text = await resp.text()
                    raise RuntimeError(f"OpenRouter error {resp.status}: {text}")

manager.register(OpenRouterProvider())
