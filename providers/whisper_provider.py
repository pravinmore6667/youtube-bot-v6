import aiohttp
from config import config
from router.provider_manager import BaseProvider, manager
from utils.logger import get_logger

log = get_logger("WhisperProvider")

class WhisperProvider(BaseProvider):
    name = "whisper"
    tier = 3
    timeout = 120

    def is_configured(self) -> bool:
        return bool(getattr(config, 'WHISPER_URL', None))

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        return "Whisper transcript placeholder"

# manager.register(WhisperProvider()) # Disabled from text-LLM manager since this parses audio
