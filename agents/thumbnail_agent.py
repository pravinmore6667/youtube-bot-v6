"""
agents/thumbnail_agent.py
──────────────────────────
CTR-maximised thumbnail generation.
Uses Pollinations.ai (FREE, no key) for cinematic base image.
Uses brainstorm output for exact concept + text.
PIL overlay: bold title, emotion badge, channel branding, accent bar.
Output: 1280×720 JPG optimised for YouTube.
"""

import os, io, uuid, re, requests, urllib.parse
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps
from config import config
from utils.logger import get_logger

log = get_logger("ThumbnailAgent")

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?width=1280&height=720&nologo=true&enhance=true&seed={seed}"

NICHE_PALETTES = {
    "technology":  {"accent": (0,212,255),   "glow": (0,80,160),  "dark": (5,10,28)},
    "finance":     {"accent": (0,255,136),   "glow": (0,100,50),  "dark": (5,18,10)},
    "history":     {"accent": (255,184,0),   "glow": (120,60,0),  "dark": (28,15,5)},
    "science":     {"accent": (187,0,255),   "glow": (80,0,120),  "dark": (10,5,28)},
    "gaming":      {"accent": (255,60,60),   "glow": (140,0,0),   "dark": (20,5,5)},
    "health":      {"accent": (68,255,136),  "glow": (0,120,60),  "dark": (5,20,12)},
    "motivation":  {"accent": (255,140,0),   "glow": (160,60,0),  "dark": (24,10,2)},
    "business":    {"accent": (255,220,50),  "glow": (140,100,0), "dark": (18,14,2)},
    "documentary": {"accent": (200,200,200), "glow": (60,60,60),  "dark": (10,10,10)},
    "news":        {"accent": (255,80,80),   "glow": (140,0,0),   "dark": (18,5,5)},
}

EMOTION_BADGES = {
    "shock":       ("😱", "#FF4444"),
    "curiosity":   ("🤔", "#FFB800"),
    "inspiration": ("🚀", "#00FF88"),
    "fear":        ("⚠️",  "#FF6600"),
    "nostalgia":   ("📜", "#C8A870"),
    "awe":         ("✨", "#AA44FF"),
    "excitement":  ("🔥", "#FF4400"),
}


def get_resample_filter():
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.LANCZOS


def _fetch_image(prompt: str, seed: int = 42) -> Image.Image | None:
    try:
        encoded = urllib.parse.quote(prompt)
        url     = POLLINATIONS_URL.format(prompt=encoded, seed=seed)
        log.info("  Fetching image from Pollinations.ai...")
        r = requests.get(url, timeout=90)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img = img.resize((1280, 720), get_resample_filter())
        return img
    except Exception as e:
        log.warning(f"  Pollinations failed: {e}")
        return None


def _gradient_bg(palette: dict) -> Image.Image:
    img  = Image.new("RGB", (1280, 720), palette["dark"])
    draw = ImageDraw.Draw(img)
    glow = palette["glow"]
    for r in range(500, 0, -8):
        alpha = int(90 * (1 - r / 500))
        color = tuple(min(255, c + alpha) for c in palette["dark"])
        draw.ellipse([640-r, 360-r, 640+r, 360+r], fill=color)
    return img


def _dark_gradient_overlay(img: Image.Image) -> Image.Image:
    """Strong bottom gradient for text legibility."""
    overlay = Image.new("RGBA", (1280, 720), (0,0,0,0))
    draw    = ImageDraw.Draw(overlay)
    # Bottom 55% gets progressively darker
    for y in range(315, 720):
        alpha = int(210 * ((y - 315) / 405) ** 1.3)
        draw.line([(0,y),(1280,y)], fill=(0,0,0,alpha))
    # Thin top vignette
    for y in range(0, 60):
        alpha = int(100 * (1 - y/60))
        draw.line([(0,y),(1280,y)], fill=(0,0,0,alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]
    for path in candidates:
        try: return ImageFont.truetype(path, size)
        except: pass
    return ImageFont.load_default()


def _wrap_title(title: str, max_chars: int = 20) -> list[str]:
    words, lines, cur = title.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars:
            if cur: lines.append(cur.strip())
            cur = w + " "
        else:
            cur += w + " "
    if cur.strip(): lines.append(cur.strip())
    return lines[:3]  # max 3 lines


def _draw_text_shadow(draw, pos, text, font, fill, shadow_offset=4, shadow_color=(0,0,0)):
    x, y = pos
    for dx in range(-shadow_offset, shadow_offset+1, 2):
        for dy in range(-shadow_offset, shadow_offset+1, 2):
            draw.text((x+dx, y+dy), text, font=font, fill=shadow_color)
    draw.text(pos, text, font=font, fill=fill)


def generate_thumbnail(topic: dict, job_id: str, brainstorm: dict = None) -> str:
    os.makedirs(config.OUTPUT_THUMBNAIL, exist_ok=True)
    output_path = os.path.join(config.OUTPUT_THUMBNAIL, f"{job_id}_thumb.jpg")

    niche   = config.CHANNEL_NICHE
    palette = NICHE_PALETTES.get(niche, NICHE_PALETTES["technology"])
    accent  = palette["accent"]

    # Use brainstorm data if available
    if brainstorm:
        title_text    = brainstorm.get("thumbnail_text") or topic["title"]
        concept       = brainstorm.get("thumbnail_concept") or topic.get("thumbnail_concept","")
        emotion_key   = brainstorm.get("target_emotion", "curiosity")
    else:
        title_text    = topic["title"]
        concept       = topic.get("thumbnail_concept","")
        emotion_key   = topic.get("target_emotion","curiosity")

    # Trim thumbnail text to 4 words max
    title_words = title_text.split()
    thumb_text  = " ".join(title_words[:4]).upper()

    # Full title for multi-line display
    full_title  = topic["title"]

    # Build image gen prompt
    lang   = config.CHANNEL_LANGUAGE
    style  = "Bollywood dramatic style, vibrant Indian colors," if lang == "hi" else "Hollywood cinematic,"
    prompt = (f"{concept}, {style} dramatic lighting, high contrast, "
              f"YouTube thumbnail background, no text, photorealistic, 8K quality, "
              f"vivid {niche} themed imagery, dark vignette edges, "
              f"professional composition with rule of thirds")

    # Try 2 seeds for variety
    img = _fetch_image(prompt, seed=hash(topic["title"]) % 9999) or \
          _fetch_image(prompt, seed=42) or \
          _gradient_bg(palette)

    # Post-process
    img = ImageEnhance.Contrast(img).enhance(1.35)
    img = ImageEnhance.Color(img).enhance(1.45)
    img = ImageEnhance.Sharpness(img).enhance(1.2)
    img = _dark_gradient_overlay(img)

    draw       = ImageDraw.Draw(img)
    font_xl    = _load_font(88)
    font_lg    = _load_font(64)
    font_md    = _load_font(42)
    font_sm    = _load_font(28, bold=False)
    font_badge = _load_font(26)

    # Left accent bar
    draw.rectangle([0, 0, 10, 720], fill=accent)

    # Section: full title in multiple lines at bottom
    lines = _wrap_title(full_title, max_chars=22)
    y_start = 720 - 115 - (len(lines) * 78)

    for i, line in enumerate(lines):
        font_use = font_xl if i == 0 else font_lg
        _draw_text_shadow(draw, (52, y_start), line, font_use,
                          fill=(255,255,255), shadow_offset=4)
        y_start += 78

    # Large accent keyword (top-left highlight word)
    highlight = full_title.split()[0].upper()
    _draw_text_shadow(draw, (18, 22), highlight, font_md, fill=accent, shadow_offset=3)

    # Emotion badge (top-right pill)
    badge_emoji, badge_color = EMOTION_BADGES.get(emotion_key, ("⚡","#FFB800"))
    badge_text = f"{badge_emoji}  {emotion_key.upper()}"
    bx, by     = 1160, 18
    bbox       = draw.textbbox((0,0), badge_text, font=font_badge)
    bw, bh     = bbox[2]-bbox[0]+24, bbox[3]-bbox[1]+12
    draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=8, fill=badge_color)
    draw.text((bx+12, by+6), badge_text, font=font_badge, fill=(0,0,0))

    # Channel name bottom-right
    ch   = config.CHANNEL_NAME
    bbox = draw.textbbox((0,0), ch, font=font_sm)
    tw   = bbox[2]-bbox[0]
    draw.text((1268-tw, 692), ch, font=font_sm, fill=(180,180,180,200))

    # Niche bottom-left tag
    draw.text((20, 692), f"#{niche}", font=font_sm, fill=(160,160,160,180))

    img.save(output_path, "JPEG", quality=96)
    log.success(f"Thumbnail: {output_path}")
    return output_path
