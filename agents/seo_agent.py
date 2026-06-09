"""
agents/seo_agent.py
────────────────────
Now delegates to UnifiedAgent.
SEO was already generated in the single unified call — zero extra calls.
"""
import json
from utils.logger import get_logger

log = get_logger("SEOAgent")

CATEGORIES = {
    "technology": "28", "finance": "25", "science": "28",
    "history": "27", "health": "26", "gaming": "20",
    "news": "25", "education": "27", "motivation": "22",
    "business": "25", "documentary": "27",
}


def generate_seo(topic: dict, script: dict, brainstorm: dict = None) -> dict:
    """
    Backward-compatible function.
    Extracts SEO from already-generated unified result.
    Zero additional AI calls.
    """
    # Check script for embedded unified result
    unified = (script or {}).get("_unified_result", {})
    if not unified and brainstorm:
        unified = brainstorm.get("_unified_result", {})

    if unified:
        log.info("Reusing unified agent SEO result — 0 AI calls")
        return _extract_seo(unified, topic)

    # Fallback: generate fresh (shouldn't normally happen)
    log.warning("No unified result found — generating SEO separately")
    from agents.unified_agent import generate
    result = generate(topic)
    return _extract_seo(result, topic)


def _extract_seo(unified: dict, topic: dict) -> dict:
    """Extract SEO fields from the unified result dict."""
    from config import config
    niche = config.CHANNEL_NICHE
    return {
        "title":            unified.get("title", topic.get("title", "Untitled")),
        "title_variants":   unified.get("title_variants", []),
        "description":      unified.get("description", ""),
        "tags":             unified.get("tags", []),
        "hashtags":         unified.get("hashtags", []),
        "category_id":      unified.get("category_id", CATEGORIES.get(niche, "28")),
        "default_language": unified.get("default_language", "en"),
        "chapters":         unified.get("chapters", ["00:00 - Intro"]),
        "seo_score":        unified.get("seo_score", "7"),
        "primary_keyword":  unified.get("primary_keyword", niche),
    }
