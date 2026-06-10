import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("FluxProvider")

class FluxProvider(BaseProvider):
    name = "flux"
    tier = 2
    timeout = 60

    def is_configured(self) -> bool:
        return bool(getattr(config, 'HF_TOKEN', None))

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
        headers = {"Authorization": f"Bearer {config.HF_TOKEN}"}
        payload = {"inputs": prompt}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=self.timeout) as resp:
                if resp.status == 200:
                    import base64
                    data = await resp.read()
                    encoded = base64.b64encode(data).decode('utf-8')
                    return f"data:image/jpeg;base64,{encoded}"
                else:
                    text = await resp.text()
                    raise RuntimeError(f"FLUX failed: {resp.status} - {text}")

# manager.register(FluxProvider()) # Disabled from text-LLM manager since this generates images
