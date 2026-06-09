"""
agents/unified_agent.py
────────────────────────
UNIFIED AI AGENT — Single call generates everything.

Replaces:
  ✗ BrainstormAgent (6 parallel calls + 1 synthesis = 7 calls)
  ✗ ScriptAgent     (1 call)
  ✗ SEOAgent        (1 call)

New:
  ✓ UnifiedAgent    (1-2 calls total)

Generates in ONE call:
  • Script (800-1200 words, 5-7 min retention-optimised)
  • Title (SEO-optimised, <70 chars)
  • Description (1500-2000 chars, keyword-rich)
  • Tags (30+ YouTube-optimised tags)
  • Hashtags (5 trending hashtags)
  • Primary keyword
  • SEO score
  • Thumbnail concept + text overlay
  • Chapter timestamps

Cache-first: checks cache before making any AI call.
Continuation-aware: resumes if provider cuts off mid-generation.

AI call reduction: 9+ → 1-2 (85% fewer calls)
Token reduction:   50% shorter scripts
"""

import json
from datetime import datetime
from utils.logger import get_logger
from router.ai_router import ask, ask_json, get_status
from utils.cache import get as cache_get, put as cache_put, find_similar
from utils.content_library import store_unified, get_reuse_recommendations
from utils.continuation import generate_with_continuation, detect_cutoff
from config import config

log = get_logger("UnifiedAgent")

# ── Format structures ─────────────────────────────────────────

FORMAT_SECTIONS = {
    "explainer":   ["Hook & Context", "The Core Problem", "Deep Dive — The Truth",
                    "Real Examples & Proof", "Key Takeaways"],
    "list":        ["Hook & Tease", "Items 5-3 (build up)", "Items 2-1 (most shocking)",
                    "Bonus Insight", "Takeaways & CTA"],
    "story":       ["Hook — Drop into Drama", "Background", "The Turning Point",
                    "The Outcome", "Lesson & CTA"],
    "documentary": ["Cold Open", "Historical Context", "The Evidence",
                    "Modern Relevance", "Closing Reflection"],
    "tutorial":    ["Hook — Show End Result", "What You'll Need",
                    "Steps 1-3", "Steps 4+", "Summary & Pro Tips"],
}

YOUTUBE_CATEGORIES = {
    "technology": "28", "finance": "25", "science": "28",
    "history": "27", "health": "26", "gaming": "20",
    "news": "25", "education": "27", "motivation": "22",
    "business": "25", "documentary": "27",
}

HINDI_NOTE = """
Write in Hindi (Devanagari script). Use conversational Hindi like a
YouTube creator — mix English technical terms naturally where Indians
expect them (AI, technology, startup, app). Use: "दोस्तों", "सोचो",
"क्या आप जानते हैं", "यकीन नहीं होगा".
"""

RETENTION_RULES = """
RETENTION RULES (strict):
• Hook must create an open loop in 0-15s — DON'T answer yet
• Pattern interrupt every 60-90s: "But wait...", "Here's the crazy part..."
• Short sentences: max 15 words for spoken delivery
• Rhetorical questions every 2-3 minutes
• Every section must end with a teaser for the next
• Final 30s must feel rewarding — viewer must feel it was worth it
• Target 800-1200 spoken words (5-7 min) — quality over quantity
"""


def _build_prompt(topic: dict, niche: str, lang: str, tone: str,
                  audience: str, channel: str, fmt: str) -> str:
    sections  = FORMAT_SECTIONS.get(fmt, FORMAT_SECTIONS["explainer"])
    sec_str   = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(sections))
    lang_note = HINDI_NOTE if lang == "hi" else "Write in clear, natural English."
    cat_id    = YOUTUBE_CATEGORIES.get(niche, "28")
    title     = topic.get("title", "")
    hook      = topic.get("hook", "")
    angle     = topic.get("angle", "")
    keywords  = topic.get("keywords", [])
    kw_str    = ", ".join(keywords[:8]) if keywords else niche

    return f"""You are a world-class YouTube content creator for channel "{channel}".

TASK: Generate complete video content for ONE YouTube video.

Video Topic: "{title}"
Unique Angle: "{angle}"
Niche: {niche} | Language: {lang} | Format: {fmt.upper()}
Tone: {tone} | Audience: {audience}
Seed Keywords: {kw_str}
Opening Hook to build on: "{hook}"

LANGUAGE: {lang_note}

SCRIPT SECTIONS:
{sec_str}

{RETENTION_RULES}

SCRIPT TARGET: 800-1200 spoken words (5-7 minutes). Tight and punchy.
Write ONLY the spoken narration. No stage directions. No asterisks.

Return a SINGLE valid JSON object with ALL these fields:

{{
  "title": "SEO-optimised title under 70 chars",
  "title_variants": ["variant 1", "variant 2"],
  "hook": "The exact first 15-20 seconds of narration (open loop, no answer yet)",
  "sections": [
    {{
      "heading": "Section name",
      "narration": "Spoken narration (150-250 words). Natural rhythm. Short sentences.",
      "broll_cue": "Footage description for editor (3-8 words)"
    }}
  ],
  "outro": "Final 30-40s. Reward viewer. Strong CTA to like/subscribe/comment.",
  "full_narration": "Complete script: hook + all section narrations + outro joined with double newlines",
  "word_count": 950,
  "estimated_duration_min": 6,
  "primary_keyword": "main search term",
  "seo_keywords": ["kw1","kw2","kw3","kw4","kw5"],
  "description": "YouTube description 1500-2000 chars. First 150 chars must hook. Include chapters. Keyword-rich.",
  "tags": ["tag1","tag2","tag3"],
  "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"],
  "category_id": "{cat_id}",
  "default_language": "{lang}",
  "chapters": ["00:00 - Intro","01:30 - Section 1","03:00 - Section 2","05:00 - Outro"],
  "seo_score": "8",
  "thumbnail_concept": "Visual scene description for AI image generation (max 20 words)",
  "thumbnail_text": "Max 4 bold words for thumbnail overlay",
  "thumbnail_emotion": "shock|curiosity|awe|excitement|fear",
  "target_emotion": "primary viewer emotion to trigger",
  "unique_angle": "What makes this video different from all others on this topic"
}}

CRITICAL: full_narration must be the complete, ready-to-speak script.
No placeholders. No [brackets]. Real content only."""


async def generate(topic: dict, job_id: str = "") -> dict:
    """
    Main entry point. Returns complete video content dict.
    Cache-first → AI generation → library storage.
    """
    niche    = config.CHANNEL_NICHE
    lang     = config.CHANNEL_LANGUAGE
    tone     = config.CHANNEL_TONE
    audience = config.TARGET_AUDIENCE
    channel  = config.CHANNEL_NAME
    title    = topic.get("title", "")
    fmt      = topic.get("format", "explainer").lower()

    log.info(f"🎬 Unified generation: '{title[:50]}' [{niche}/{lang}]")

    # ── 1. Cache check ─────────────────────────────────────────
    cached = cache_get(title, "unified", niche=niche, lang=lang)
    if cached:
        log.success(f"Cache hit! Skipping AI call for '{title[:40]}'")
        _ensure_full_narration(cached)
        return cached

    # ── 2. Library similarity check ────────────────────────────
    recs = get_reuse_recommendations(title, niche)
    if recs["can_reuse"] and recs["score"] > 0.8:
        log.info(f"Similar content found in library (score {recs['score']:.0%}) — "
                 f"checking partial reuse")
        sim = find_similar(title, "unified", niche=niche, lang=lang, threshold=0.65)
        if sim:
            log.success("Partial cache reuse from content library")
            _ensure_full_narration(sim)
            return sim

    # ── 3. AI Generation with continuation ────────────────────
    from router.ai_router import ask
    prompt = _build_prompt(topic, niche, lang, tone, audience, channel, fmt)

    log.info("🤖 Calling AI (single unified call)...")

    def _call(p: str):
        return ask(p, max_tokens=4096) # will return coroutine

    result = await generate_with_continuation(
        prompt=prompt,
        call_fn=_call,
        parse_fn=lambda raw: _parse_result(raw, topic, niche, lang),
        max_attempts=3,
        expected_format="json",
    )

    if not result:
        raise RuntimeError("UnifiedAgent: AI returned empty result after all retries")

    # ── 4. Post-process ────────────────────────────────────────
    result = _post_process(result, topic, niche, lang, fmt)
    _ensure_full_narration(result)

    # ── 5. Cache result ────────────────────────────────────────
    cache_put(title, "unified", result, niche=niche, lang=lang)

    # ── 6. Store in content library ────────────────────────────
    try:
        store_unified(job_id or "manual", title, result,
                      niche=niche, language=lang)
    except Exception as e:
        log.warning(f"Library storage failed (non-fatal): {e}")

    log.success(
        f"✓ Unified: {result.get('word_count',0)} words, "
        f"~{result.get('estimated_duration_min',0)} min, "
        f"title: {result.get('title','')[:50]}"
    )
    return result


# ── Helpers ───────────────────────────────────────────────────

def _parse_result(raw: str, topic: dict, niche: str, lang: str) -> dict:
    """Parse AI response, with graceful fallback for partial JSON."""
    import re
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    s, e = raw.find("{"), raw.rfind("}")
    if s >= 0 and e > s:
        raw = raw[s:e+1]
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    raw = raw.replace("\ufeff", "")
    return json.loads(raw)


def _post_process(result: dict, topic: dict, niche: str,
                  lang: str, fmt: str) -> dict:
    """Validate and fill defaults in the unified result."""
    title_fallback = topic.get("title", "Untitled Video")

    result.setdefault("title",            title_fallback)
    result.setdefault("title_variants",   [])
    result.setdefault("hook",             "")
    result.setdefault("sections",         [])
    result.setdefault("outro",            "")
    result.setdefault("full_narration",   "")
    result.setdefault("word_count",       0)
    result.setdefault("estimated_duration_min", 6)
    result.setdefault("primary_keyword",  niche)
    result.setdefault("seo_keywords",     topic.get("keywords", []))
    result.setdefault("description",      f"Video about {title_fallback}")
    result.setdefault("tags",             [])
    result.setdefault("hashtags",         [])
    result.setdefault("category_id",      YOUTUBE_CATEGORIES.get(niche, "28"))
    result.setdefault("default_language", lang)
    result.setdefault("chapters",         ["00:00 - Intro"])
    result.setdefault("seo_score",        "7")
    result.setdefault("thumbnail_concept", title_fallback)
    result.setdefault("thumbnail_text",    title_fallback[:20])
    result.setdefault("thumbnail_emotion", "curiosity")
    result.setdefault("format",           fmt)
    result.setdefault("language",         lang)

    # Enforce YouTube tag length limit (500 chars total)
    tags, total = [], 0
    for tag in result.get("tags", []):
        if total + len(str(tag)) + 1 <= 500:
            tags.append(str(tag))
            total += len(str(tag)) + 1
    result["tags"] = tags

    # Chapters: generate from sections if missing/minimal
    if len(result.get("chapters", [])) < 2 and result.get("sections"):
        secs = result["sections"]
        dur  = result.get("estimated_duration_min", 6)
        seg  = dur / max(len(secs), 1)
        chapters = ["00:00 - Intro"]
        for i, s in enumerate(secs):
            m   = int((i + 1) * seg)
            sec = int(((i + 1) * seg - m) * 60)
            chapters.append(f"{m:02d}:{sec:02d} - {s.get('heading', f'Section {i+1}')}")
        result["chapters"] = chapters

    return result


def _ensure_full_narration(result: dict):
    """Make sure full_narration is populated (assembles from sections if needed)."""
    if result.get("full_narration"):
        wc = len(result["full_narration"].split())
        result["word_count"] = wc
        result["estimated_duration_min"] = round(
            wc / (130 if result.get("language") == "hi" else 150))
        return

    parts = []
    if result.get("hook"):
        parts.append(result["hook"])
    for s in result.get("sections", []):
        if s.get("narration"):
            parts.append(s["narration"])
    if result.get("outro"):
        parts.append(result["outro"])

    narration = "\n\n".join(p for p in parts if p)
    result["full_narration"]         = narration
    result["word_count"]              = len(narration.split())
    result["estimated_duration_min"]  = round(
        len(narration.split()) / (130 if result.get("language") == "hi" else 150))
