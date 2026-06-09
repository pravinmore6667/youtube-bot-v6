import time, json, asyncio
from typing import Dict, Any, Optional
from utils.logger import get_logger
from router.provider_manager import manager
from router.health_monitor import monitor
from router.failover_engine import get_best_provider
import utils.check_setup

log = get_logger("AIRouter")

def _is_rate_limit(err: str) -> bool:
    kws = ["429", "rate_limit", "rate limit", "quota", "resource_exhausted", "too many requests"]
    return any(k in err.lower() for k in kws)

from router.token_optimizer import optimize_prompt
from router.response_cache import get_cached_response, set_cached_response

async def ask(prompt: str, is_fast: bool = False, max_tokens: int = 4096) -> str:
    """Intelligent routing with failover. Fast execution mode."""

    prompt = optimize_prompt(prompt)
    cached = get_cached_response(prompt)
    if cached:
        log.info("Returning cached response.")
        return cached

    last_err = None

    # Prioritize providers: Gemini -> Mistral -> Groq -> Grok
    # We will query failover_engine to get sorted candidates
    candidates = []

    # Fast Execution Mode:
    # Provider -> Retry Once -> Next Provider

    provider_names = []

    # Get all configured and non-cooldown providers from failover engine (we'll update failover_engine to return list)
    from router.failover_engine import get_ordered_providers
    available_providers = get_ordered_providers()

    if not available_providers:
        # Check if all are in cooldown
        wait = 10
        for name in manager.providers.keys():
            h = monitor.get_health(name)
            if h.cooldown_until > time.time():
                w = h.cooldown_until - time.time()
                if w < wait: wait = w
        log.warning(f"All providers exhausted/cooldown. Waiting {wait:.1f}s...")
        await asyncio.sleep(max(1, wait))
        available_providers = get_ordered_providers()

    if not available_providers:
        raise RuntimeError("All AI providers failed or are unconfigured.")

    for provider_name in available_providers:
        provider = manager.providers[provider_name]

        # Retry once per provider
        for attempt in range(2):
            t0 = time.time()
            try:
                log.debug(f"Routing to {provider_name} (attempt {attempt+1})...")
                result = await provider.generate(prompt, is_fast=is_fast, max_tokens=max_tokens)
                latency = time.time() - t0
                log.info(f"[{provider_name}] Model={getattr(provider, 'current_model', 'unknown')} Latency={latency:.2f}s Tokens={len(result.split())} Status=Success")
                monitor.record_success(provider_name, latency)
                set_cached_response(prompt, result)
                return result
            except Exception as e:
                err_str = str(e)
                is_rl = _is_rate_limit(err_str)
                monitor.record_failure(provider_name, err_str, is_rate_limit=is_rl)
                last_err = e
                log.warning(f"[{provider_name}] Model={getattr(provider, 'current_model', 'unknown')} Latency={time.time() - t0:.2f}s Status=Error Error=\"{err_str[:60]}\"")

                if is_rl:
                    # Rate limit hit, skip second attempt for this provider
                    log.warning(f"Rate limit exceeded on {provider_name}. Immediately falling back to next provider.")
                    # If Gemini fails and Groq is available, we ensure we fallback immediately.
                    break

    raise RuntimeError(f"All AI providers failed. Last error: {last_err}")

import json, re

def _parse_json(raw: str) -> dict:
    if not raw: return {}
    s = raw.find('{')
    e = raw.rfind('}')
    if s != -1 and e != -1:
        raw = raw[s:e+1]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    try:
        return json.loads(raw)
    except:
        return {}

async def ask_json(prompt: str, is_fast: bool = False, max_tokens: int = 4096, retries: int = 2) -> dict:
    full_prompt = prompt + "\n\nIMPORTANT: Return STRICT JSON only. No markdown. No code blocks. Must be valid json.loads() input."
    last_err = None
    for attempt in range(retries + 1):
        try:
            raw = await ask(full_prompt, is_fast=is_fast, max_tokens=max_tokens)
            res = _parse_json(raw)
            if res: return res
            raise ValueError("Parsed JSON is empty.")
        except Exception as e:
            last_err = e
            log.warning(f"JSON parse failed (attempt {attempt+1}): {e}")
    raise ValueError(f"AI returned invalid JSON: {last_err}")

def get_status() -> dict:
    from router.failover_engine import get_best_provider
    active = get_best_provider() or "none"
    healthy = sum(1 for p in manager.providers.keys() if monitor.get_health(p).healthy)
    failed = sum(1 for p in manager.providers.keys() if not monitor.get_health(p).healthy)

    total_calls = sum(monitor.get_health(p).total_calls for p in manager.providers.keys())
    total_success = sum(monitor.get_health(p).total_success for p in manager.providers.keys())
    sr = (total_success / total_calls * 100.0) if total_calls > 0 else 100.0

    return {
        "active_provider": active,
        "healthy_providers": healthy,
        "failed_providers": failed,
        "success_rate": round(sr, 1)
    }
