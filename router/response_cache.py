import json
import os
import time
import hashlib
from typing import Optional

CACHE_DIR = "logs/response_cache"
TTL_SECONDS = 24 * 3600  # 24 hours

os.makedirs(CACHE_DIR, exist_ok=True)

def _get_cache_path(prompt: str) -> str:
    key = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{key}.json")

def get_cached_response(prompt: str) -> Optional[str]:
    path = _get_cache_path(prompt)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                if time.time() - data.get("timestamp", 0) < TTL_SECONDS:
                    return data.get("result")
        except Exception:
            pass
    return None

def set_cached_response(prompt: str, result: str):
    path = _get_cache_path(prompt)
    try:
        with open(path, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "result": result
            }, f)
    except Exception:
        pass
