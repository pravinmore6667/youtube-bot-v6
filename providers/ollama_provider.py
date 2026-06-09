import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("OllamaProvider")

class OllamaProvider(BaseProvider):
    name = "ollama"
    tier = 3 # Local fallback
    timeout = 120

    def is_configured(self) -> bool:
        return bool(getattr(config, 'OLLAMA_URL', None))

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        base_url = getattr(config, 'OLLAMA_URL', '').rstrip('/')
        if not base_url:
            raise RuntimeError("Ollama URL not configured.")

        url = f"{base_url}/api/generate"

        model = "llama3" if is_fast else "mistral"
        self.current_model = model

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    try:
                        return data["response"].strip()
                    except KeyError:
                        raise ValueError(f"Unexpected response format from Ollama: {data}")
                else:
                    text = await resp.text()
                    raise RuntimeError(f"Ollama error {resp.status}: {text}")

manager.register(OllamaProvider())
