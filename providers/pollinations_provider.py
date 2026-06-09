import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager

class PollinationsProvider(BaseProvider):
    name = "pollinations"
    tier = 3
    timeout = 30

    def is_configured(self) -> bool:
        return True

    _cached_model = None
    _cached_time = 0

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        url = "https://text.pollinations.ai/openai"

        models = ["openai-large", "openai", "llama", "mistral"]

        import time
        # Use cached model if valid
        if not is_fast and self._cached_model and time.time() - self._cached_time < 3600:
            models = [self._cached_model] + [m for m in models if m != self._cached_model]

        if is_fast:
            models = ["mistral"]

        async with aiohttp.ClientSession() as session:
            last_err = None
            for model in models:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.35,
                }

                try:
                    async with session.post(url, json=payload, timeout=self.timeout) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if not is_fast:
                                self._cached_model = model
                                self._cached_time = time.time()
                            return data["choices"][0]["message"]["content"].strip()
                        else:
                            text = await resp.text()
                            err_msg = f"Pollinations error {resp.status} with model {model}: {text}"
                            if resp.status == 404 or "not found" in text.lower() or "invalid" in text.lower():
                                last_err = err_msg
                                continue
                            else:
                                raise RuntimeError(err_msg)
                except Exception as e:
                    last_err = str(e)
                    continue

            raise RuntimeError(f"All Pollinations models failed. Last error: {last_err}")

manager.register(PollinationsProvider())
