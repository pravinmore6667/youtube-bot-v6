import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("SambaNovaProvider")

class SambaNovaProvider(BaseProvider):
    name = "sambanova"
    tier = 2
    timeout = 45

    def is_configured(self) -> bool:
        return bool(getattr(config, "SAMBANOVA_API_KEY", None))

    async def generate(self, prompt: str,
                       is_fast: bool = False,
                       max_tokens: int = 4096) -> str:
        url = "https://api.sambanova.ai/v1/chat/completions"
        # Use 405B for quality, 70B for speed
        model = "Meta-Llama-3.1-70B-Instruct" if is_fast else \
                "Meta-Llama-3.1-405B-Instruct"
        self.current_model = model
        headers = {
            "Authorization": f"Bearer {config.SAMBANOVA_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload,
                headers=headers, timeout=self.timeout
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    text = await resp.text()
                    raise RuntimeError(
                        f"SambaNova error {resp.status}: {text}"
                    )

manager.register(SambaNovaProvider())