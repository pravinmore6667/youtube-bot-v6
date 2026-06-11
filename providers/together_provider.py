import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("TogetherProvider")

class TogetherProvider(BaseProvider):
    name = "together"
    tier = 2
    timeout = 30

    def is_configured(self) -> bool:
        return bool(getattr(config, "TOGETHER_API_KEY", None))

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        url = "https://api.together.xyz/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.TOGETHER_API_KEY}",
            "Content-Type": "application/json"
        }
        models = [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
            "meta-llama/Llama-3.1-8B-Instruct-Turbo",
        ]
        model = models[3] if is_fast else models[0]
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
                    raise RuntimeError(f"Together error {resp.status}: {text}")

manager.register(TogetherProvider())
