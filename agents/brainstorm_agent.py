"""
agents/brainstorm_agent.py
───────────────────────────
Now delegates to UnifiedAgent (single call = everything).
Original 7-call parallel brainstorm → 1 unified call.
AI call reduction: 7 → 0 (brainstorm merged into unified_agent).

Preserved for backward compatibility with pipeline imports.
"""
from agents.unified_agent import generate as _unified_generate
from utils.logger import get_logger
from config import config

log = get_logger("BrainstormAgent")


def run_brainstorm(topic: dict, performance_insights: str = "") -> dict:
    """
    Backward-compatible function.
    Returns a brainstorm-shaped dict from the unified agent.
    """
    log.info(f"Delegating brainstorm → UnifiedAgent for '{topic.get('title','')[:50]}'")
    # The unified agent generates everything in one shot.
    # We return a brainstorm-compatible dict so pipeline.py doesn't break.
    result = _unified_generate(topic)
    return _reshape_to_brainstorm(result, topic)


def _reshape_to_brainstorm(unified: dict, topic: dict) -> dict:
    """Convert unified output to the brainstorm dict shape expected by pipeline."""
    return {
        "final_title":      unified.get("title", topic.get("title", "")),
        "hook_line":        unified.get("hook", ""),
        "story_structure":  unified.get("format", "explainer"),
        "emotional_journey":unified.get("target_emotion", "curiosity → insight"),
        "thumbnail_concept":unified.get("thumbnail_concept", ""),
        "thumbnail_text":   unified.get("thumbnail_text", ""),
        "key_sections":     [s.get("heading","") for s in unified.get("sections",[])],
        "pattern_interrupts":[],
        "voice_style":      "conversational",
        "target_emotion":   unified.get("target_emotion", "curiosity"),
        "seo_keywords":     unified.get("seo_keywords", []),
        "unique_angle":     unified.get("unique_angle", topic.get("angle","")),
        "cta_line":         "Like this video, subscribe, and hit the bell!",
        # Carry the full unified result so script/seo agents don't call AI again
        "_unified_result":  unified,
        "agent_contributions": {
            "UnifiedAgent": {"note": "Single call replaced 7 parallel agents"}
        },
    }
