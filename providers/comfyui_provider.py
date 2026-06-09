import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("ComfyUIProvider")

class ComfyUIProvider(BaseProvider):
    name = "comfyui"
    tier = 3
    timeout = 180

    def is_configured(self) -> bool:
        return bool(getattr(config, 'COMFYUI_URL', None))

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        return "ComfyUI generation placeholder"

# manager.register(ComfyUIProvider()) # Disabled from text-LLM manager since this generates images
