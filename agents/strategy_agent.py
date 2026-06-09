"""
agents/strategy_agent.py
─────────────────────────
Trend Research — NO Reddit needed.
Free sources (zero extra API keys):
  1. Google Trends        (pytrends — free, no key)
  2. Hacker News API      (free, no key, JSON API)
  3. Google News RSS      (free, no key, XML feed)
  4. Wikipedia Trending   (Wikimedia API — free, no key)
  5. YouTube Trending     (YouTube Data API — already have key)
  6. Gemini Web Insight   (Gemini — already have key)
"""

import random, requests, feedparser
from xml.etree import ElementTree as ET
from pytrends.request import TrendReq
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from config import config
from database import db
from agents.niche_profiles import get_profile
from utils.gemini import ask_json
from utils.logger import get_logger

log = get_logger("StrategyAgent")


# ─── 1. Google Trends ────────────────────────────────────────

def _google_trends(profile: dict) -> list[str]:
    """Fetch live trend velocity and keywords from Google Trends."""
    try:
        kw   = profile["keywords_seed"][0]
        geo  = "IN" if config.CHANNEL_LANGUAGE == "hi" else "US"
        hl   = "hi-IN" if config.CHANNEL_LANGUAGE == "hi" else "en-US"
        pt   = TrendReq(hl=hl, tz=330 if geo == "IN" else 360, timeout=(10, 30))

        # 1. Related queries for the niche seed keyword
        pt.build_payload([kw], timeframe="now 7-d", geo=geo)
        related = pt.related_queries()
        topics  = []
        if related and kw in related and related[kw]:
            for kind in ["top", "rising"]:
                if related[kw].get(kind) is not None:
                    topics += related[kw][kind]["query"].head(8).tolist()

        # 2. Trending searches right now (Daily Trends)
        try:
            trending_df = pt.trending_searches(pn='india' if geo == 'IN' else 'united_states')
            if not trending_df.empty:
                # Filter daily trends by our niche keywords to ensure relevance
                daily_trends = trending_df[0].tolist()
                kws = [k.lower() for k in profile.get("keywords_seed", [])]
                for dt in daily_trends:
                    if any(k in dt.lower() for k in kws):
                        topics.append(dt)
        except Exception as e:
            log.warning(f"  Google Daily Trends fetch failed: {e}")

        log.info(f"  Google Trends: {len(topics)} topics found before saturation")
        return list(set(topics))
    except Exception as e:
        log.warning(f"  Google Trends: {e}")
        return []

# ─── 1.5. Reddit Trend Scraping (Free JSON API) ───────────────
def _reddit_trends(profile: dict) -> list[str]:
    """Scrape Reddit for hot/rising topics in niche subreddits."""
    import requests
    topics = []
    # Map niches to subreddits (could be in niche profile, hardcoded for now)
    subreddits = {
        "technology": "technology+gadgets+futurology",
        "finance": "personalfinance+investing+CryptoCurrency",
        "history": "AskHistorians+HistoryMemes",
        "science": "science+space+Physics",
        "health": "Health+Fitness+nutrition",
        "gaming": "gaming+Games",
        "documentary": "Documentaries"
    }

    niche = config.CHANNEL_NICHE
    subs = subreddits.get(niche, "all")

    try:
        url = f"https://www.reddit.com/r/{subs}/hot.json?limit=15"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Bot/1.0"}
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code == 200:
            data = r.json()
            for post in data.get("data", {}).get("children", []):
                title = post.get("data", {}).get("title", "")
                score = post.get("data", {}).get("score", 0)
                if title and score > 50: # Filter low-engagement
                    topics.append(title)

        log.info(f"  Reddit Trends: {len(topics)} topics")
        return topics
    except Exception as e:
        log.warning(f"  Reddit Trends failed: {e}")
        return []



# ─── 2. Hacker News (no key, completely free) ────────────────

def _hacker_news(profile: dict) -> list[str]:
    """Fetch top HN stories and filter by niche keywords."""
    try:
        kws     = [k.lower() for k in profile.get("hn_keywords", [])]
        r       = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json",
                               timeout=10)
        ids     = r.json()[:80]
        titles  = []
        for sid in ids[:60]:
            try:
                item = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    timeout=6).json()
                title = item.get("title", "")
                if title and (not kws or any(k in title.lower() for k in kws)):
                    titles.append(title)
            except Exception:
                pass
        log.info(f"  Hacker News: {len(titles)} relevant stories")
        return titles
    except Exception as e:
        log.warning(f"  Hacker News: {e}")
        return []


# ─── 3. Google News RSS (no key, completely free) ────────────

def _google_news_rss(profile: dict) -> list[str]:
    """Parse Google News RSS for niche-relevant headlines."""
    titles = []
    queries = profile.get("news_queries", [profile["keywords_seed"][0]])[:4]
    for q in queries:
        try:
            url  = (f"https://news.google.com/rss/search?q={q.replace(' ','+')}"
                    f"&hl=en-US&gl=US&ceid=US:en")
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                t = entry.get("title","").split(" - ")[0].strip()
                if t and len(t) > 10:
                    titles.append(t)
        except Exception as e:
            log.warning(f"  Google News RSS ({q}): {e}")
    log.info(f"  Google News RSS: {len(titles)} headlines")
    return titles


# ─── 4. Wikipedia Trending (no key, completely free) ─────────

def _wikipedia_trending() -> list[str]:
    """Fetch Wikipedia's most viewed articles today."""
    try:
        from datetime import datetime, timedelta
        d    = datetime.utcnow() - timedelta(days=1)
        url  = (f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
                f"en.wikipedia.org/all-access/{d.year}/{d.month:02d}/{d.day:02d}")
        r    = requests.get(url, timeout=10,
                            headers={"User-Agent": "YouTubeBot/3.0"})
        articles = r.json()["items"][0]["articles"][:30]
        titles   = [a["article"].replace("_"," ")
                    for a in articles
                    if a["article"] not in ["Main_Page","Special:Search",
                                            "Wikipedia","Special:","Portal:"]]
        log.info(f"  Wikipedia trending: {len(titles)} articles")
        return titles
    except Exception as e:
        log.warning(f"  Wikipedia trending: {e}")
        return []


# ─── 5. YouTube Trending (uses existing YouTube key) ─────────

def _youtube_trending(profile: dict) -> list[str]:
    try:
        creds = Credentials(token=None,
                            refresh_token=config.YOUTUBE_REFRESH_TOKEN,
                            token_uri="https://oauth2.googleapis.com/token",
                            client_id=config.YOUTUBE_CLIENT_ID,
                            client_secret=config.YOUTUBE_CLIENT_SECRET)
        creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)

        geo = "IN" if config.CHANNEL_LANGUAGE == "hi" else "US"
        trending = yt.videos().list(
            part="snippet", chart="mostPopular",
            maxResults=30, regionCode=geo,
            videoCategoryId=profile.get("yt_category","28")
        ).execute()
        searched = yt.search().list(
            part="snippet", q=profile["keywords_seed"][0],
            type="video", order="viewCount", maxResults=15,
            relevanceLanguage=config.CHANNEL_LANGUAGE
        ).execute()

        titles = [i["snippet"]["title"] for i in trending.get("items",[])]
        titles += [i["snippet"]["title"] for i in searched.get("items",[])]
        log.info(f"  YouTube: {len(titles)} videos")
        return titles
    except Exception as e:
        log.warning(f"  YouTube trending: {e}")
        return []


# ─── 6. Gemini Web Insight ───────────────────────────────────

async def _gemini_insight(profile: dict) -> list[str]:
    try:
        lang_note = "Focus on India/Hindi market trends." if config.CHANNEL_LANGUAGE == "hi" else ""
        result = await ask_json(
            f"""What topics in the "{profile['label']}" category are going viral on YouTube
right now in the past 2 weeks? Include both evergreen AND trending.
{lang_note}
Return JSON: {{"topics": ["topic1","topic2","topic3","topic4","topic5","topic6","topic7","topic8"]}}"""
        )
        topics = result.get("topics", [])
        log.info(f"  Gemini insight: {len(topics)} topics")
        return topics
    except Exception as e:
        log.warning(f"  Gemini insight: {e}")
        return []


# ─── Main topic picker ────────────────────────────────────────

async def pick_todays_topic(niche_id: str = None) -> dict:
    niche_id = niche_id or config.CHANNEL_NICHE
    profile  = get_profile(niche_id)
    log.info(f"🔍 Researching: {profile['label']} | lang: {config.CHANNEL_LANGUAGE}")

    import concurrent.futures
    import asyncio

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        f1 = ex.submit(_google_trends,     profile)
        f2 = ex.submit(_hacker_news,       profile)
        f3 = ex.submit(_google_news_rss,   profile)
        f4 = ex.submit(_wikipedia_trending)
        f5 = ex.submit(_youtube_trending,  profile)
        f6 = ex.submit(_reddit_trends,     profile)

    all_topics = []
    for f in [f1, f2, f3, f4, f5, f6]:
        try: all_topics.extend(f.result())
        except Exception: pass

    # Run async function
    try:
        gemini_topics = await _gemini_insight(profile)
        all_topics.extend(gemini_topics)
    except Exception: pass

    # Add profile's seed keywords as evergreen fallback
    all_topics += profile["keywords_seed"]
    all_topics  = list(dict.fromkeys(all_topics))   # deduplicate, keep order
    random.shuffle(all_topics)

    recent   = db.get_recent_titles(30)
    strategy = db.get_current_strategy()
    perf     = db.get_performance_data()

    strategy_ctx = ""
    if strategy:
        strategy_ctx = f"This week — best format: {strategy.get('best_format','explainer')}, avoid: {', '.join(strategy.get('avoid_topics',[]))}"

    perf_ctx = ""
    if perf:
        top      = sorted(perf, key=lambda x: x["views"], reverse=True)[:2]
        perf_ctx = "Top performers: " + " | ".join(f'"{v["title"]}" ({v["views"]} views)' for v in top)

    candidates = "\n".join(f"- {t}" for t in all_topics[:45])
    avoid_str  = "\n".join(f"- {t}" for t in recent[:20])

    result = await ask_json(f"""YouTube growth strategist for a {profile['label']} channel.
Audience: {profile['audience']} | Language: {config.CHANNEL_LANGUAGE}
Tone: {profile['tone']}
{strategy_ctx}
{perf_ctx}

Trending candidates today:
{candidates}

ALREADY published — do NOT repeat:
{avoid_str}

Pick the SINGLE BEST video topic. Must have:
1. High search demand RIGHT NOW
2. Strong thumbnail/hook potential
3. Fills a gap competitors haven't covered
4. {"Works for Hindi-speaking Indian audience" if config.CHANNEL_LANGUAGE == "hi" else "Broad appeal for the niche"}

Return JSON:
{{
  "title": "Click-worthy title under 70 chars",
  "angle": "Unique creative angle nobody else uses",
  "format": "{random.choice(profile['video_formats'])}",
  "keywords": ["kw1","kw2","kw3","kw4","kw5"],
  "hook": "Exact opening line — grabs attention in 3 seconds",
  "reason": "Why this will perform well this week",
  "thumbnail_concept": "What image/scene to generate (be very specific)",
  "target_emotion": "curiosity|shock|inspiration|fear|nostalgia",
  "competition_level": "low|medium|high"
}}""")

    log.success(f"Topic: {result['title']}")
    return result


async def generate_weekly_strategy(niche_id: str = None) -> dict:
    niche_id = niche_id or config.CHANNEL_NICHE
    profile  = get_profile(niche_id)
    perf     = db.get_performance_data()
    recent   = db.get_recent_titles(20)

    top_str = "\n".join(
        f"  • \"{v['title']}\" — {v['views']} views, {v['avg_view_duration_pct']:.0f}% retention"
        for v in sorted(perf, key=lambda x: x["views"], reverse=True)[:5]
    ) if perf else "  No data yet"

    result = await ask_json(f"""YouTube strategist for {profile['label']} channel.
Language: {config.CHANNEL_LANGUAGE}
Recent videos: {recent[:8]}
Top performers:\n{top_str}

Generate weekly content strategy JSON:
{{
  "niche": "{niche_id}",
  "top_topics": ["topic1","topic2","topic3","topic4","topic5","topic6","topic7"],
  "avoid_topics": ["what to avoid this week based on overexposure"],
  "best_format": "{profile['video_formats'][0]}",
  "best_hook_style": "{profile['best_hooks'][0]}",
  "focus_keyword": "single keyword to dominate this week",
  "notes": "2-sentence strategic focus"
}}""")

    db.save_strategy(result)
    log.success("Weekly strategy saved")
    return result
