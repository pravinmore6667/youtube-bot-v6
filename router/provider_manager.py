from typing import List, Dict, Any

class BaseProvider:
    name = "base"
    tier = 1
    timeout = 30

    async def generate(self, prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
        raise NotImplementedError()

    def is_configured(self) -> bool:
        return False

class ProviderManager:
    def __init__(self):
        self.providers: Dict[str, BaseProvider] = {}

    def register(self, provider: BaseProvider):
        self.providers[provider.name] = provider

manager = ProviderManager()


# Auto-load all providers from the providers directory
import importlib
import pkgutil
import providers

def _load_all_providers():
    for _, module_name, _ in pkgutil.iter_modules(providers.__path__):
        importlib.import_module(f"providers.{module_name}")

_load_all_providers()
