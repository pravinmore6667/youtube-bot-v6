import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("CerebrasProvider")

class CerebrasProvider(BaseProvider):
    name = "cerebras"
    tier = 2
    timeout = 20

    def is_configured(self) -> bool:
        return bool(config.CEREBRAS_API_KEY)

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        url = "https://api.cerebras.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.CEREBRAS_API_KEY}",
            "Content-Type": "application/json"
        }

        models = ["llama-3.1-8b", "llama-3.3-70b", "qwen-3-32b"]
        if not hasattr(self, "failed_models"):
            self.failed_models = set()

        models_to_try = [m for m in models if m not in self.failed_models]
        if not models_to_try:
            # reset if all failed
            self.failed_models = set()
            models_to_try = models

        for model in models_to_try:
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
                            raise ValueError(f"Unexpected response format from Cerebras: {data}")
                    elif resp.status == 404:
                        log.warning(f"Cerebras model {model} returned 404, marking as failed.")
                        self.failed_models.add(model)
                        continue
                    else:
                        text = await resp.text()
                        raise RuntimeError(f"Cerebras error {resp.status}: {text}")

        raise RuntimeError("All Cerebras models failed (404)")

manager.register(CerebrasProvider())
