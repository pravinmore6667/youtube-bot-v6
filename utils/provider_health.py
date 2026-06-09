import os
import json
import time

HEALTH_FILE = "provider_health.json"
SKIP_TIME = 15 * 60  # 15 minutes

def load_health():
    if os.path.exists(HEALTH_FILE):
        try:
            with open(HEALTH_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "pixabay": {"fails": 0, "degraded_until": 0},
        "pexels": {"fails": 0, "degraded_until": 0},
        "edge_tts": {"fails": 0, "degraded_until": 0},
        "gtts": {"fails": 0, "degraded_until": 0},
    }

def save_health(data):
    with open(HEALTH_FILE, "w") as f:
        json.dump(data, f, indent=4)

def check_provider_health(provider: str) -> bool:
    """Returns True if provider is healthy (or if skip time has passed)."""
    data = load_health()
    if provider not in data:
        return True

    p_data = data[provider]
    if p_data.get("degraded_until", 0) > time.time():
        return False

    # Reset fails if time passed
    if p_data.get("degraded_until", 0) > 0 and p_data.get("degraded_until", 0) < time.time():
        p_data["fails"] = 0
        p_data["degraded_until"] = 0
        save_health(data)
        return True

    return True

def record_success(provider: str):
    data = load_health()
    if provider in data:
        data[provider]["fails"] = 0
        data[provider]["degraded_until"] = 0
        save_health(data)

def record_failure(provider: str):
    data = load_health()
    if provider not in data:
        data[provider] = {"fails": 0, "degraded_until": 0}

    data[provider]["fails"] = data[provider].get("fails", 0) + 1

    if data[provider]["fails"] >= 3:
        data[provider]["degraded_until"] = time.time() + SKIP_TIME

    save_health(data)
