"""
Jamendo API — free royalty-free music.
Get free Client ID at: https://developer.jamendo.com
"""
import os, requests, random, tempfile

JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "")

NICHE_TO_TAGS = {
    "technology": "electronic+ambient",
    "gaming":     "electronic+energetic",
    "finance":    "corporate+instrumental",
    "default":    "background+instrumental",
}

def jamendo_music(niche: str = "technology", output_path: str = None) -> str:
    if not JAMENDO_CLIENT_ID:
        raise ValueError("JAMENDO_CLIENT_ID not set")
    tags = NICHE_TO_TAGS.get(niche.lower(), NICHE_TO_TAGS["default"])
    r = requests.get("https://api.jamendo.com/v3.0/tracks/",
                     params={"client_id": JAMENDO_CLIENT_ID, "format": "json",
                             "tags": tags, "limit": 10, "audioformat": "mp32",
                             "order": "popularity_total"},
                     timeout=15)
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        raise ValueError("No tracks found on Jamendo")
    track = random.choice(results[:5])
    audio_r = requests.get(track["audio"], timeout=45)
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mp3")
    with open(output_path, "wb") as f:
        f.write(audio_r.content)
    return output_path
