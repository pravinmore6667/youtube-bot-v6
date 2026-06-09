import os
import time
import threading
from typing import Optional, List
from utils.logger import get_logger

log = get_logger("GeminiPool")

class GeminiKey:
    def __init__(self, key: str, index: int):
        self.key = key
        self.index = index
        self.failure_count = 0
        self.last_success = 0.0
        self.cooldown_until = 0.0

    @property
    def is_active(self) -> bool:
        return time.time() >= self.cooldown_until

    def mark_success(self):
        self.failure_count = 0
        self.last_success = time.time()
        self.cooldown_until = 0.0

    def mark_exhausted(self, cooldown_minutes: int = 30):
        self.failure_count += 1
        # Set cooldown slightly in the future to mark it exhausted,
        # but don't block the pool from moving to the next key.
        self.cooldown_until = time.time() + (cooldown_minutes * 60)
        log.warning(f"Gemini Key #{self.index} exhausted. Marked unavailable for {cooldown_minutes} min.")

class GeminiPool:
    def __init__(self):
        self._lock = threading.Lock()
        self.keys: List[GeminiKey] = []
        self._load_keys()
        self._current_idx = 0

    def _load_keys(self):
        # Always check base key first
        base_key = os.getenv("GEMINI_API_KEY", "")
        if base_key and not base_key.startswith("your_"):
            self.keys.append(GeminiKey(base_key, 0))

        # Auto-discover GEMINI_API_KEY_*
        for env_var, value in os.environ.items():
            if env_var.startswith("GEMINI_API_KEY_") and value and not value.startswith("your_"):
                # Avoid adding base key again if it was set as GEMINI_API_KEY_1
                if not any(k.key == value for k in self.keys):
                    self.keys.append(GeminiKey(value, len(self.keys)))

        log.info(f"Loaded {len(self.keys)} Gemini keys into pool.")

    def get_active_key(self) -> Optional[GeminiKey]:
        with self._lock:
            if not self.keys:
                return None

            # Always check all keys
            for _ in range(len(self.keys)):
                k = self.keys[self._current_idx]
                if k.is_active:
                    # Found an active key. Return it and increment index for next time (round-robin)
                    self._current_idx = (self._current_idx + 1) % len(self.keys)
                    return k
                # If exhausted, immediately try next key
                self._current_idx = (self._current_idx + 1) % len(self.keys)

            return None # All keys exhausted/in cooldown

    def get_all_keys(self) -> List[GeminiKey]:
        return self.keys

pool = GeminiPool()
