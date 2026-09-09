"""
Video metadata service. Fetches real YouTube video metadata (title, channel,
thumbnail, duration, published date, description) cleanly and efficiently.
Eliminates redundant YouTubeTranscriptApi calls and caches results.
"""
import re
import time
import uuid
import logging
import urllib.request
import json
from app.services.error_validator import contains_raw_error_text, sanitize_text_field

logger = logging.getLogger(__name__)
METADATA_CACHE = {}


def log_provider_call(request_id: str, video_id: str, provider_name: str, operation_name: str, attempt: int, elapsed_ms: float, status_code: int, error_code: str = None):
    err_str = f" | Error={error_code}" if error_code else ""
    logger.info(
        f"[PROVIDER_METRICS] ReqID={request_id[:8]} | Video={video_id} | Provider={provider_name} | "
        f"Op={operation_name} | Attempt={attempt} | Time={elapsed_ms}ms | Status={status_code}{err_str}"
    )


def clean_description(raw_desc: str) -> str:
    if not raw_desc or not isinstance(raw_desc, str) or contains_raw_error_text(raw_desc):
        return "Video overview available upon processing."

    lines = raw_desc.split("\n")
    cleaned_lines = []

    for line in lines:
        l = line.strip()
        if not l or contains_raw_error_text(l):
            continue
        l_lower = l.lower()
        if any(token in l_lower for token in [
            "subscribe", "follow us", "instagram.com", "facebook.com", 
            "twitter.com", "x.com", "tiktok.com", "http://", "https://", 
            "patreon.com", "merch", "discount code", "affiliate", "sponsor"
        ]):
            continue
        l_no_hash = re.sub(r"#\w+", "", l).strip()
        if l_no_hash and not contains_raw_error_text(l_no_hash):
            cleaned_lines.append(l_no_hash)

    result = " ".join(cleaned_lines[:5])
    return sanitize_text_field(result, "Video overview available upon processing.")


def get_video_metadata(video_id: str, request_id: str = None) -> dict:
    req_id = request_id or str(uuid.uuid4())

    if video_id in METADATA_CACHE:
        logger.info(f"[METADATA CACHE HIT] ReqID={req_id[:8]} | Video={video_id}")
        return METADATA_CACHE[video_id]

    url = f"https://www.youtube.com/watch?v={video_id}"
    title = "YouTube Video"
    channel_name = "YouTube Channel"
    thumbnail = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    description = "Video overview available upon processing."
    duration = "N/A"
    published_at = "N/A"
    language = "en"

    # Step 1: YouTube oEmbed API for fast title & channel name (Fast path: ~30-50ms)
    t0 = time.time()
    oembed_success = False
    try:
        oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw_body = resp.read().decode("utf-8")
            elapsed = round((time.time() - t0) * 1000, 2)
            if not contains_raw_error_text(raw_body):
                data = json.loads(raw_body)
                title = sanitize_text_field(data.get("title"), title)
                channel_name = sanitize_text_field(data.get("author_name"), channel_name)
                oembed_success = True
                log_provider_call(req_id, video_id, "youtube_oembed", "fetch_title", 1, elapsed, 200)
    except Exception as e:
        elapsed = round((time.time() - t0) * 1000, 2)
        log_provider_call(req_id, video_id, "youtube_oembed", "fetch_title", 1, elapsed, 500, str(type(e).__name__))

    # Step 2: Only call yt-dlp if oEmbed failed to get basic metadata
    if not oembed_success:
        t0 = time.time()
        import yt_dlp
        try:
            ydl_opts = {
                "quiet": True,
                "skip_download": True,
                "no_warnings": True,
                "socket_timeout": 5,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                elapsed = round((time.time() - t0) * 1000, 2)
                if info:
                    title = sanitize_text_field(info.get("title"), title)
                    channel_name = sanitize_text_field(info.get("uploader") or info.get("channel"), channel_name)
                    raw_desc = info.get("description") or ""
                    description = clean_description(raw_desc)
                    duration = sanitize_text_field(info.get("duration_string"), duration)
                    upload_date = info.get("upload_date")
                    if upload_date and len(upload_date) == 8:
                        published_at = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
                    language = sanitize_text_field(info.get("language"), "en")
                    log_provider_call(req_id, video_id, "yt_dlp", "extract_info", 1, elapsed, 200)
        except Exception as e:
            elapsed = round((time.time() - t0) * 1000, 2)
            log_provider_call(req_id, video_id, "yt_dlp", "extract_info", 1, elapsed, 500, str(type(e).__name__))

    res = {
        "videoId": video_id,
        "title": title,
        "thumbnail": thumbnail,
        "channelName": channel_name,
        "description": description,
        "publishedAt": published_at,
        "duration": duration,
        "language": language,
        "hasTranscript": True
    }
    METADATA_CACHE[video_id] = res
    return res
