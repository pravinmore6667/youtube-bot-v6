"""
utils/continuation.py
──────────────────────
Smart Generation Continuation System

Problem: Provider hits token/rate limit mid-generation.
Solution: Detect the cutoff, save state, continue from exact point.

Supports:
  - JSON continuation (partial JSON objects/arrays)
  - Text continuation (incomplete sentences)
  - Section-level continuation (for multi-section scripts)
  - Cross-provider continuation (Groq → Gemini mid-script)

Goal: Reduce token waste by 50%+ on provider failures.
"""
import json, re
from typing import Optional, Any
from utils.logger import get_logger

log = get_logger("Continuation")


# ─────────────────────────────────────────────────────────────
# Cutoff Detection
# ─────────────────────────────────────────────────────────────

def detect_cutoff(text: str) -> dict:
    """
    Analyse text to detect if it was cut off mid-generation.
    Returns:
      is_complete: bool
      cutoff_type: 'json' | 'text' | 'section' | None
      completed_portions: dict | str  — what was successfully generated
      resume_context: str             — what to send as context for continuation
      missing_parts: list[str]        — descriptions of what's still needed
    """
    text = text.strip()
    result = {
        "is_complete":         True,
        "cutoff_type":         None,
        "completed_portions":  None,
        "resume_context":      "",
        "missing_parts":       [],
    }

    # ── JSON detection ─────────────────────────────────────────
    if text.startswith("{") or text.startswith("["):
        try:
            data = json.loads(text)
            result["completed_portions"] = data
            return result           # valid JSON = complete
        except json.JSONDecodeError:
            result["is_complete"] = False
            result["cutoff_type"] = "json"
            partial               = _extract_partial_json(text)
            result["completed_portions"] = partial
            result["missing_parts"]      = _find_missing_json_keys(partial, text)
            result["resume_context"]     = _build_json_resume_context(partial, text)
            return result

    # ── Text/script detection ──────────────────────────────────
    # Check for abrupt endings (no trailing period/question/exclamation)
    last_sentence_end = max(
        text.rfind("."), text.rfind("!"), text.rfind("?"),
        text.rfind("।"),    # Hindi Devanagari danda
    )

    # If last punctuation is > 80 chars from end, likely cut off
    if last_sentence_end >= 0 and (len(text) - last_sentence_end) > 80:
        result["is_complete"]        = False
        result["cutoff_type"]        = "text"
        result["completed_portions"] = text[:last_sentence_end + 1].strip()
        result["resume_context"]     = text[max(0, last_sentence_end - 300):last_sentence_end + 1]
        return result

    # ── Script section detection ───────────────────────────────
    # Check if we have a clear incomplete section pattern
    sections_found = len(re.findall(r'"narration"\s*:', text))
    sections_expected = text.count('"heading"')
    if sections_found > 0 and sections_expected > sections_found:
        result["is_complete"]    = False
        result["cutoff_type"]    = "section"
        result["missing_parts"]  = [f"sections {sections_found+1}+"]

    return result


def _extract_partial_json(text: str) -> dict:
    """Extract all complete top-level key-value pairs from partial JSON."""
    partial = {}
    # Try progressively shorter substrings until valid JSON
    for end in range(len(text), 0, -1):
        candidate = text[:end].rstrip(",\n\r ")
        if not candidate.endswith("}"):
            candidate += "}"
        try:
            parsed = json.loads(candidate)
            return parsed
        except Exception:
            pass

    # Fallback: extract individual string values with regex
    for match in re.finditer(r'"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*)"', text):
        partial[match.group(1)] = match.group(2)
    for match in re.finditer(r'"(\w+)"\s*:\s*(\d+(?:\.\d+)?)', text):
        try:
            partial[match.group(1)] = json.loads(match.group(2))
        except Exception:
            pass
    # Extract arrays
    for match in re.finditer(r'"(\w+)"\s*:\s*(\[(?:[^\[\]]|\[(?:[^\[\]])*\])*\])', text):
        try:
            partial[match.group(1)] = json.loads(match.group(2))
        except Exception:
            pass
    return partial


def _find_missing_json_keys(partial: dict, original_text: str) -> list[str]:
    """Identify keys that appear in the prompt template but not in partial."""
    # Look for key patterns that were defined but not yet produced
    all_keys = re.findall(r'"(\w+)"\s*:', original_text)
    seen = set()
    missing = []
    for key in all_keys:
        if key not in partial and key not in seen:
            missing.append(key)
        seen.add(key)
    return missing


def _build_json_resume_context(partial: dict, original_text: str) -> str:
    """Build a context string for resuming JSON generation."""
    if not partial:
        return "The previous generation was cut off before any fields were completed."
    done = ", ".join(f'"{k}"' for k in list(partial.keys())[:8])
    return f"Previously completed fields: {done}. Continue from where you left off."


# ─────────────────────────────────────────────────────────────
# Continuation Prompt Builder
# ─────────────────────────────────────────────────────────────

def build_continuation_prompt(
    original_prompt: str,
    cutoff_info: dict,
    expected_format: str = "json",
) -> str:
    """
    Build a prompt that asks the AI to continue from the cutoff point.
    The AI should only generate the MISSING portions.
    """
    completed  = cutoff_info.get("completed_portions")
    context    = cutoff_info.get("resume_context", "")
    missing    = cutoff_info.get("missing_parts", [])
    ctype      = cutoff_info.get("cutoff_type")

    if ctype == "json":
        completed_str = json.dumps(completed, ensure_ascii=False, indent=2) \
                        if completed else "{}"
        missing_str   = ", ".join(missing) if missing else "remaining fields"
        prompt = (
            f"CONTINUATION TASK\n"
            f"─────────────────\n"
            f"The previous AI generation was cut off. "
            f"Here is what was successfully generated:\n\n"
            f"```json\n{completed_str}\n```\n\n"
            f"Original task: {original_prompt[:500]}...\n\n"
            f"Please generate ONLY the missing parts: {missing_str}\n"
            f"Output ONLY the missing JSON fields — no explanations, "
            f"no repetition of completed fields."
        )

    elif ctype in ("text", "section"):
        prompt = (
            f"CONTINUATION TASK\n"
            f"─────────────────\n"
            f"The previous generation was cut off mid-way.\n"
            f"Here is where it stopped:\n\n"
            f"...{context[-400:]}\n\n"
            f"Continue EXACTLY from where it left off. "
            f"Do NOT repeat any text already generated. "
            f"Continue in the same style and language."
        )

    else:
        prompt = (
            f"The previous generation may be incomplete.\n"
            f"Original task: {original_prompt[:500]}\n"
            f"Please complete the task fully."
        )

    return prompt


# ─────────────────────────────────────────────────────────────
# Output Merger
# ─────────────────────────────────────────────────────────────

def merge_outputs(first: Any, second: Any) -> Any:
    """
    Merge two partial outputs from different providers.
    Handles JSON dicts, JSON arrays, and plain text.
    """
    # Dict merge (JSON objects)
    if isinstance(first, dict) and isinstance(second, dict):
        merged = dict(first)
        for key, val in second.items():
            if key not in merged or not merged[key]:
                merged[key] = val
            elif isinstance(merged[key], list) and isinstance(val, list):
                # Deduplicate list merge
                seen = {json.dumps(i, sort_keys=True) for i in merged[key]}
                for item in val:
                    k = json.dumps(item, sort_keys=True)
                    if k not in seen:
                        merged[key].append(item)
                        seen.add(k)
            elif isinstance(merged[key], str) and isinstance(val, str):
                # String: keep the longer one (likely more complete)
                if len(val) > len(merged[key]):
                    merged[key] = val
        return merged

    # List merge
    if isinstance(first, list) and isinstance(second, list):
        seen = {json.dumps(i, sort_keys=True) for i in first}
        merged = list(first)
        for item in second:
            k = json.dumps(item, sort_keys=True)
            if k not in seen:
                merged.append(item)
                seen.add(k)
        return merged

    # Text merge — concatenate, remove duplicates at junction
    if isinstance(first, str) and isinstance(second, str):
        return _merge_text(first, second)

    # Fallback: prefer second (likely more complete)
    return second


def _merge_text(first: str, second: str) -> str:
    """Concatenate text while avoiding duplicate sentences at the junction."""
    if not first:
        return second
    if not second:
        return first

    # Find the overlap — last sentence of `first` should not be in `second`
    last_sentences = re.split(r'(?<=[.!?])\s+', first.strip())[-3:]
    for sent in last_sentences:
        if len(sent) > 20 and sent.strip() in second:
            # Remove the duplicate from second
            idx = second.find(sent.strip())
            second = second[idx + len(sent):].lstrip()
            break

    return first.rstrip() + "\n\n" + second.lstrip()


# ─────────────────────────────────────────────────────────────
# High-level generate_with_continuation()
# ─────────────────────────────────────────────────────────────

from typing import Any, Callable

async def generate_with_continuation(
    prompt: str,
    call_fn: Callable[[str], Any],
    parse_fn: Callable[[str], Any] = None,
    max_attempts: int = 3,
    expected_format: str = "json",
) -> Any:
    """
    Call AI and automatically continue if output is cut off.

    Args:
        prompt:    The original prompt
        call_fn:   Function(prompt) → raw string response
        parse_fn:  Function(raw_string) → parsed object (default: json.loads)
        max_attempts: Max continuation attempts
    """
    parse_fn = parse_fn or json.loads
    accumulated = None
    last_raw    = ""

    import asyncio

    for attempt in range(max_attempts):
        if attempt == 0:
            current_prompt = prompt
        else:
            cutoff = detect_cutoff(last_raw)
            if cutoff["is_complete"]:
                break
            log.warning(f"Output cutoff detected ({cutoff['cutoff_type']}) — "
                        f"continuing (attempt {attempt+1})")
            current_prompt = build_continuation_prompt(
                prompt, cutoff, expected_format)

        raw = call_fn(current_prompt)

        if asyncio.iscoroutine(raw):
            raw = await raw

        if not isinstance(raw, str):
            raise TypeError(f"Expected string, got {type(raw).__name__}")

        last_raw = raw

        try:
            parsed = parse_fn(raw)
        except Exception:
            # Try to parse what we have
            cutoff = detect_cutoff(raw)
            parsed = cutoff.get("completed_portions") or {}

        if accumulated is None:
            accumulated = parsed
        else:
            accumulated = merge_outputs(accumulated, parsed)

        # Check if we're now complete
        if attempt > 0:
            check_raw = json.dumps(accumulated) if isinstance(accumulated, (dict, list)) \
                        else str(accumulated)
            if detect_cutoff(check_raw)["is_complete"]:
                break

    return accumulated
