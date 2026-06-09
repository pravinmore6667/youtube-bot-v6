import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("SDXLProvider")

class SDXLProvider(BaseProvider):
    name = "sdxl"
    tier = 2
    timeout = 60

    def is_configured(self) -> bool:
        return bool(getattr(config, 'SDXL_API_KEY', None))

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        return "SDXL image placeholder"

# manager.register(SDXLProvider()) # Disabled from text-LLM manager since this generates images
