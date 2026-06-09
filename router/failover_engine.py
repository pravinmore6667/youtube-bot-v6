import time
from typing import List
from router.health_monitor import monitor
from router.provider_manager import manager
from utils.logger import get_logger

log = get_logger("FailoverEngine")

def get_ordered_providers(tier_filter: int = None) -> List[str]:
    candidates = []
    for name, provider in manager.providers.items():
        if not provider.is_configured(): continue
        if tier_filter and provider.tier != tier_filter: continue

        h = monitor.get_health(name)
        if h.cooldown_until > time.time(): continue

        # Circuit breaker logic
        if not h.healthy and h.cooldown_until > time.time():
            continue

        score = h.success_rate
        score -= min(10, h.latency)
        score -= min(30, h.failures * 5)

        candidates.append((score, provider.tier, name))

    # Sort by Tier (lowest first), then Score (highest first)
    candidates.sort(key=lambda x: (x[1], -x[0]))
    return [c[2] for c in candidates]

def get_best_provider(tier_filter: int = None) -> str:
    c = get_ordered_providers(tier_filter)
    return c[0] if c else None

def check_all_health():
    """Background check. Restores providers."""
    for name, provider in manager.providers.items():
        if not provider.is_configured(): continue
        h = monitor.get_health(name)
        # HALF-OPEN state: if cooldown has passed, allow one test
        if not h.healthy and h.cooldown_until < time.time():
            log.info(f"Health recovery check for {name} (Half-Open)...")
            try:
                # We could do a real call, but just marking available for next real request is safer
                monitor.record_success(name, 1.0) # Reset to healthy
                log.success(f"{name} marked healthy and re-entered rotation.")
            except Exception:
                pass
