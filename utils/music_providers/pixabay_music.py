"""
Pixabay Music API — free royalty-free music.
Get free API key at: https://pixabay.com/api/docs/
"""
import os, requests, random, tempfile

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

NICHE_TO_QUERY = {
    "technology": "electronic technology",
    "gaming":     "epic gaming electronic",
    "finance":    "corporate background",
    "lifestyle":  "upbeat positive",
    "education":  "calm focus study",
    "default":    "background music",
}

def pixabay_music(niche: str = "technology", output_path: str = None) -> str:
    if not PIXABAY_API_KEY:
        raise ValueError("PIXABAY_API_KEY not set")
    query = NICHE_TO_QUERY.get(niche.lower(), NICHE_TO_QUERY["default"])
    r = requests.get("https://pixabay.com/api/videos/music/",
                     params={"key": PIXABAY_API_KEY, "q": query,
                             "per_page": 10, "order": "popular"},
                     timeout=15)
    r.raise_for_status()
    hits = r.json().get("hits", [])
    if not hits:
        raise ValueError("No music found on Pixabay")
    track = random.choice(hits[:5])
    audio_r = requests.get(track["audio"], timeout=45)
    audio_r.raise_for_status()
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mp3")
    with open(output_path, "wb") as f:
        f.write(audio_r.content)
    return output_path
