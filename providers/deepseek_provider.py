import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("DeepSeekProvider")

class DeepSeekProvider(BaseProvider):
    name = "deepseek"
    tier = 2
    timeout = 30

    def is_configured(self) -> bool:
        return bool(getattr(config, "DEEPSEEK_API_KEY", None))

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        models = ["deepseek-chat", "deepseek-reasoner"]
        model = models[0] if is_fast else models[1]
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
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    text = await resp.text()
                    raise RuntimeError(f"DeepSeek error {resp.status}: {text}")

manager.register(DeepSeekProvider())
