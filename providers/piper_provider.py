import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("PiperProvider")

class PiperProvider(BaseProvider):
    name = "piper"
    tier = 3
    timeout = 30

    def is_configured(self) -> bool:
        return bool(getattr(config, 'PIPER_URL', None))

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        return "Piper audio path placeholder"

# manager.register(PiperProvider()) # Disabled from text-LLM manager since this generates audio
