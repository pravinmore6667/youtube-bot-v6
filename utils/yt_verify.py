"""
utils/yt_verify.py
───────────────────
YouTube Upload Verification
After uploading, fetch actual video data from YouTube API
to confirm the video is live, public, and accessible.
Returns rich metadata for the dashboard.
"""

import time
from utils.logger import get_logger

log = get_logger("YTVerify")


def verify_upload(video_id: str, max_wait_sec: int = 300) -> dict:
    """
    Poll YouTube until video is fully processed and public.
    Returns verification data dict.
    """
    try:
        from agents.upload_agent import _yt_client
        yt = _yt_client()
    except Exception as e:
        return {"verified": False, "error": str(e)}

    log.info(f"Verifying upload: {video_id}")
    deadline = time.time() + max_wait_sec

    while time.time() < deadline:
        try:
            resp = yt.videos().list(
                part="snippet,status,statistics,contentDetails",
                id=video_id
            ).execute()

            if not resp.get("items"):
                log.info("  Video not found yet — waiting 15s")
                time.sleep(15)
                continue

            item    = resp["items"][0]
            snip    = item["snippet"]
            status  = item["status"]
            stats   = item.get("statistics", {})
            details = item.get("contentDetails", {})

            privacy  = status.get("privacyStatus","unknown")
            upload_s = status.get("uploadStatus","unknown")

            if upload_s == "processed" and privacy == "public":
                result = {
                    "verified":      True,
                    "video_id":      video_id,
                    "url":           f"https://www.youtube.com/watch?v={video_id}",
                    "studio_url":    f"https://studio.youtube.com/video/{video_id}/edit",
                    "title":         snip.get("title",""),
                    "description":   snip.get("description","")[:200],
                    "channel":       snip.get("channelTitle",""),
                    "published_at":  snip.get("publishedAt",""),
                    "thumbnail_url": snip.get("thumbnails",{}).get("maxres",{}).get("url","") or
                                     snip.get("thumbnails",{}).get("high",{}).get("url",""),
                    "privacy":       privacy,
                    "upload_status": upload_s,
                    "duration":      details.get("duration",""),
                    "views":         int(stats.get("viewCount", 0)),
                    "likes":         int(stats.get("likeCount", 0)),
                    "comments":      int(stats.get("commentCount", 0)),
                    "tags":          snip.get("tags", []),
                }
                log.success(f"✅ Verified LIVE: {result['url']}")
                return result

            elif upload_s in ["failed","rejected","deleted"]:
                return {
                    "verified": False,
                    "error":    f"YouTube upload status: {upload_s}",
                    "privacy":  privacy,
                }
            else:
                log.info(f"  Processing... upload_status={upload_s}, privacy={privacy}")
                time.sleep(20)

        except Exception as e:
            log.warning(f"  Verification error: {e}")
            time.sleep(15)

    return {
        "verified": False,
        "error":    "Timed out waiting for YouTube to process video",
        "url":      f"https://www.youtube.com/watch?v={video_id}",
    }


def fetch_video_stats(video_id: str) -> dict:
    """Fetch current stats for an already-uploaded video."""
    try:
        from agents.upload_agent import _yt_client
        yt   = _yt_client()
        resp = yt.videos().list(
            part="snippet,statistics,status", id=video_id
        ).execute()
        if not resp.get("items"):
            return {}
        item  = resp["items"][0]
        stats = item.get("statistics", {})
        snip  = item["snippet"]
        return {
            "title":       snip.get("title",""),
            "views":       int(stats.get("viewCount",  0)),
            "likes":       int(stats.get("likeCount",  0)),
            "comments":    int(stats.get("commentCount",0)),
            "privacy":     item["status"].get("privacyStatus",""),
            "thumbnail":   snip.get("thumbnails",{}).get("high",{}).get("url",""),
            "published_at":snip.get("publishedAt",""),
        }
    except Exception as e:
        log.warning(f"Stats fetch failed: {e}")
        return {}
