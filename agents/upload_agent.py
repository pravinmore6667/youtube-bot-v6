"""
agents/upload_agent.py
───────────────────────
YouTube Data API v3 upload — FREE (10,000 units/day).
Upload = 1,600 units → 6 uploads/day free.
Features: resumable upload, thumbnail, playlist, chapters in description.
"""

import os, time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import config
from utils.logger import get_logger

log = get_logger("UploadAgent")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]


def _yt_client():
    creds = Credentials(token=None, refresh_token=config.YOUTUBE_REFRESH_TOKEN,
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=config.YOUTUBE_CLIENT_ID,
                        client_secret=config.YOUTUBE_CLIENT_SECRET,
                        scopes=SCOPES)
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def upload_video(video_path: str, thumbnail_path: str, seo: dict) -> dict:
    log.info(f"📤 Uploading: {seo['title']}")
    yt   = _yt_client()
    body = {
        "snippet": {
            "title":           seo["title"],
            "description":     seo["description"],
            "tags":            seo["tags"],
            "categoryId":      seo.get("category_id","28"),
            "defaultLanguage": seo.get("default_language","en"),
        },
        "status": {
            "privacyStatus":           "public",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia":  True,
        },
    }
    media    = MediaFileUpload(video_path, mimetype="video/mp4",
                               resumable=True, chunksize=20*1024*1024)
    request  = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    retries  = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                log.info(f"  {int(status.progress()*100)}%")
        except HttpError as e:
            if e.resp.status in [500,502,503,504] and retries < 5:
                retries += 1
                time.sleep(8 * retries)
                log.warning(f"  Retry {retries}/5")
            else:
                raise

    vid_id  = response["id"]
    vid_url = f"https://www.youtube.com/watch?v={vid_id}"

    # Thumbnail
    try:
        yt.thumbnails().set(videoId=vid_id,
            media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg")).execute()
        log.success("Thumbnail set")
    except Exception as e:
        log.warning(f"Thumbnail failed: {e}")

    log.success(f"Published: {vid_url}")
    return {"video_id": vid_id, "url": vid_url, "title": seo["title"]}


def fetch_analytics(video_id: str) -> dict:
    try:
        yt   = _yt_client()
        resp = yt.videos().list(part="statistics,contentDetails", id=video_id).execute()
        if resp.get("items"):
            stats = resp["items"][0].get("statistics", {})
            return {"views": int(stats.get("viewCount",0)),
                    "likes": int(stats.get("likeCount",0)),
                    "comments": int(stats.get("commentCount",0))}
    except Exception as e:
        log.warning(f"Analytics fetch failed: {e}")
    return {}
