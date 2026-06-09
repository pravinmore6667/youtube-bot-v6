"""
agents/script_agent.py
───────────────────────
Now delegates to UnifiedAgent.
If brainstorm already ran unified agent, reuses that result.
Zero additional AI calls.
"""
from utils.logger import get_logger

log = get_logger("ScriptAgent")


def write_script(topic: dict, brainstorm: dict = None) -> dict:
    """
    Backward-compatible function.
    Reuses unified result if available, else generates it.
    """
    # If unified result already exists in brainstorm, reuse it
    if brainstorm and "_unified_result" in brainstorm:
        log.info("Reusing unified agent result — 0 AI calls")
        return _reshape_to_script(brainstorm["_unified_result"])

    # Fallback: generate fresh (shouldn't normally happen)
    log.info("Generating via UnifiedAgent (fallback)")
    from agents.unified_agent import generate
    result = generate(topic)
    return _reshape_to_script(result)


def _reshape_to_script(unified: dict) -> dict:
    """Convert unified output to script-agent dict shape."""
    return {
        "title":                  unified.get("title", ""),
        "format":                 unified.get("format", "explainer"),
        "language":               unified.get("language", "en"),
        "hook":                   unified.get("hook", ""),
        "sections":               unified.get("sections", []),
        "outro":                  unified.get("outro", ""),
        "full_narration":         unified.get("full_narration", ""),
        "word_count":             unified.get("word_count", 0),
        "estimated_duration_min": unified.get("estimated_duration_min", 6),
        # Pass full unified for SEO reuse
        "_unified_result":        unified,
    }
