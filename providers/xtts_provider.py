import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("XTTSProvider")

class XTTSProvider(BaseProvider):
    name = "xtts"
    tier = 3
    timeout = 60

    def is_configured(self) -> bool:
        return bool(getattr(config, 'XTTS_URL', None))

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        return "XTTS audio path placeholder"

# manager.register(XTTSProvider()) # Disabled from text-LLM manager since this generates audio
