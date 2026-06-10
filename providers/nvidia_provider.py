import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager

class NvidiaProvider(BaseProvider):
    name = "nvidia"
    tier = 2
    timeout = 45

    def is_configured(self) -> bool:
        return bool(getattr(config, "NVIDIA_API_KEY", None))

    async def generate(self, prompt: str, is_fast: bool = False,
                       max_tokens: int = 4096) -> str:
        model = "meta/llama-3.1-8b-instruct" if is_fast else \
                "meta/llama-3.1-70b-instruct"
        self.current_model = model
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {config.NVIDIA_API_KEY}",
                   "Content-Type": "application/json"}
        payload = {"model": model,
                   "messages": [{"role": "user", "content": prompt}],
                   "max_tokens": max_tokens, "temperature": 0.7}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    text = await resp.text()
                    raise RuntimeError(f"NVIDIA error {resp.status}: {text[:100]}")

manager.register(NvidiaProvider())
