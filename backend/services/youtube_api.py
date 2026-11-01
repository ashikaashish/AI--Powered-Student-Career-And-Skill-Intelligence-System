"""
Thin wrapper around the YouTube Data API v3.

Setup:
1. Go to https://console.cloud.google.com/apis/library/youtube.googleapis.com
   and enable "YouTube Data API v3" for a (free) project.
2. Create an API key: https://console.cloud.google.com/apis/credentials
3. Put it in backend/.env as YOUTUBE_API_KEY=your_key_here

Free quota is 10,000 units/day. A search.list call costs 100 units, a
videos.list call costs 1 unit, so ~90 searches/day is the practical ceiling
on the free tier -- cache/store results rather than searching on every page
load (see data_pipeline/fetch_youtube_courses.py for the batch/offline flow).
"""
import os
import re
import requests

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeAPIError(Exception):
    pass


def _api_key():
    key = os.environ.get("YOUTUBE_API_KEY", "").strip().strip("\"'").strip()
    if not key:
        raise YouTubeAPIError(
            "YOUTUBE_API_KEY is not set. Add it to backend/.env "
            "(see services/youtube_api.py docstring for how to get one)."
        )
    return key


def _explain(resp, what):
    """Turn a Google API error response into a message the student/developer can act on."""
    try:
        err = resp.json().get("error", {})
    except ValueError:
        err = {}
    message = err.get("message", "") or resp.text[:200]
    reasons = " ".join(
        [e.get("reason", "") for e in err.get("errors", [])]
        + [d.get("reason", "") for d in err.get("details", []) if isinstance(d, dict)]
    )
    blob = f"{reasons} {message}".lower()
    if "quotaexceeded" in blob or "quota" in blob and resp.status_code == 403:
        why = ("The daily YouTube quota (10,000 units) is used up. It resets at midnight Pacific time. "
               "Lessons that were already found keep working.")
    elif "api_key_invalid" in blob or "keyinvalid" in blob or "api key not valid" in blob:
        why = ("YouTube rejected the API key as invalid. Re-copy the key into backend/.env as "
               "YOUTUBE_API_KEY=yourkey (no quotes or spaces) and restart the backend.")
    elif "accessnotconfigured" in blob or "service_disabled" in blob or "has not been used" in blob or "is disabled" in blob:
        why = ("YouTube Data API v3 is not enabled for the Google Cloud project this key belongs to. "
               "Enable it at https://console.cloud.google.com/apis/library/youtube.googleapis.com and try again in a minute.")
    elif "referer" in blob or "referrer" in blob or "ip address" in blob or "ipRefererBlocked".lower() in blob:
        why = ("The API key has an application restriction (HTTP referrer / IP) that blocks the backend. "
               "In Google Cloud > Credentials set 'Application restrictions' to None (or your server IP) "
               "and 'API restrictions' to YouTube Data API v3.")
    elif "api_key_service_blocked" in blob or "blocked" in blob:
        why = ("The key's API restriction does not include YouTube Data API v3. "
               "Edit the key in Google Cloud > Credentials and allow that API.")
    else:
        why = message or "Unknown error."
    return f"{what} failed (HTTP {resp.status_code}): {why}"


def _get(url, params, what):
    try:
        resp = requests.get(url, params=params, timeout=10)
    except requests.exceptions.RequestException as e:
        raise YouTubeAPIError(
            f"Could not reach YouTube ({type(e).__name__}). Check the server's internet connection / firewall."
        )
    if resp.status_code != 200:
        raise YouTubeAPIError(_explain(resp, what))
    return resp


def _parse_iso8601_duration(duration):
    """'PT1H2M10S' -> seconds (int)."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def search_videos(query, max_results=10, min_duration_seconds=180):
    """
    Search YouTube for videos matching `query`.
    Returns a list of dicts: video_id, title, channel_title, thumbnail,
    published_at, duration_seconds. Videos shorter than
    `min_duration_seconds` (default 3 min, to filter out shorts/clips) are
    dropped.
    """
    key = _api_key()

    search_resp = _get(
        f"{YOUTUBE_API_BASE}/search",
        {
            "key": key,
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": min(max_results * 2, 25),  # over-fetch, we filter some out below
            "relevanceLanguage": "en",
            "safeSearch": "strict",
            "videoEmbeddable": "true",
        },
        "YouTube search",
    )

    items = search_resp.json().get("items", [])
    video_ids = [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]
    if not video_ids:
        return []

    details_resp = _get(
        f"{YOUTUBE_API_BASE}/videos",
        {"key": key, "id": ",".join(video_ids), "part": "snippet,contentDetails"},
        "YouTube video lookup",
    )

    results = []
    for item in details_resp.json().get("items", []):
        duration_seconds = _parse_iso8601_duration(item["contentDetails"]["duration"])
        if duration_seconds < min_duration_seconds:
            continue
        snippet = item["snippet"]
        results.append({
            "video_id": item["id"],
            "title": snippet["title"],
            "channel_title": snippet["channelTitle"],
            "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url"),
            "published_at": snippet.get("publishedAt"),
            "duration_seconds": duration_seconds,
        })
        if len(results) >= max_results:
            break
    return results
