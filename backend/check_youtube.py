"""
Checks that the YouTube API key works, and (optionally) pre-loads videos for every topic.

    python check_youtube.py              # tests the key with one search
    python check_youtube.py --prefetch   # also finds videos for all 25 course topics now

Run it from the backend folder. Restart `python app.py` after changing backend/.env.
"""
import os
import sys
import sqlite3

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"), override=True)
sys.path.insert(0, HERE)

from services.youtube_api import search_videos, YouTubeAPIError  # noqa: E402
from services.youtube_lessons import ensure_lessons  # noqa: E402

key = os.environ.get("YOUTUBE_API_KEY", "").strip()
print(f"Key found in backend/.env: {'yes (' + key[:6] + '...' + key[-3:] + ')' if key else 'NO - YOUTUBE_API_KEY is empty'}")
if not key:
    sys.exit(1)

try:
    vids = search_videos("Python full course tutorial", max_results=3, min_duration_seconds=600)
except YouTubeAPIError as e:
    print("FAILED:", e)
    sys.exit(1)
print(f"OK - the key works. Example result: {vids[0]['title']!r} ({vids[0]['channel_title']})" if vids else "Key works but no videos matched.")

if "--prefetch" in sys.argv:
    conn = sqlite3.connect(os.path.join(HERE, "database", "career_ai.db"))
    conn.row_factory = sqlite3.Row
    topics = conn.execute("SELECT skill_tag, MIN(id) AS id FROM courses GROUP BY skill_tag ORDER BY skill_tag").fetchall()
    for t in topics:
        n, err = ensure_lessons(conn, t["id"])
        print(f"  {t['skill_tag']:<28} {n} video(s) {('- ' + err) if err else ''}")
        if err and "quota" in err.lower():
            break
    conn.close()
