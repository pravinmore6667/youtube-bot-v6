import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager

class PuterProvider(BaseProvider):
    name = "puter"
    tier = 3
    timeout = 30

    def is_configured(self) -> bool:
        return True

    _is_disabled = False

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        if self._is_disabled:
            raise RuntimeError("Puter provider is currently disabled due to previous 404 errors.")

        url = "https://api.puter.com/v1/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.35,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    text = await resp.text()
                    if resp.status == 404:
                        self._is_disabled = True
                        raise RuntimeError(f"Puter endpoint returned 404 and is now disabled. Error: {text}")
                    raise RuntimeError(f"Puter error {resp.status}: {text}")

manager.register(PuterProvider())
