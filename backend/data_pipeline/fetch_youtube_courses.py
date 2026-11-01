"""
Auto-populate data/courses.csv with real YouTube videos, one search per skill,
using the actual YouTube Data API (not a static/guessed dataset).

Setup:
1. Enable "YouTube Data API v3" and create a key:
   https://console.cloud.google.com/apis/credentials
2. Put it in backend/.env as YOUTUBE_API_KEY=your_key_here
3. Run this from inside backend/ (with your virtualenv active):

     python data_pipeline/fetch_youtube_courses.py
     python data_pipeline/fetch_youtube_courses.py --skills Python,SQL,"Data Structures"
     python data_pipeline/fetch_youtube_courses.py --per-skill 2

4. Then reload the DB:  python database/init_db.py

Quota note: each skill costs 100 units (1 search call). The free daily quota
is 10,000 units, so you can run this for ~100 skills/day. Rows for a skill
that already has a course with a video_id are skipped by default so re-runs
don't waste quota re-searching the same thing (use --force to override).
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from services.youtube_api import search_videos, YouTubeAPIError  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COURSES_CSV = os.path.join(BASE_DIR, "data", "courses.csv")
SKILLS_CSV = os.path.join(BASE_DIR, "data", "skills.csv")

FIELDNAMES = ["title", "provider", "level", "skill_tag", "rating", "url", "video_id"]


def load_existing_rows():
    if not os.path.exists(COURSES_CSV):
        return []
    with open(COURSES_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def skills_from_master():
    with open(SKILLS_CSV, newline="", encoding="utf-8") as f:
        return [row["skill_name"] for row in csv.DictReader(f)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills", help="Comma-separated skill names to fetch for. Defaults to all of data/skills.csv.")
    parser.add_argument("--per-skill", type=int, default=1, help="How many videos to add per skill (default 1).")
    parser.add_argument("--level", default="Beginner", choices=["Beginner", "Intermediate", "Advanced"])
    parser.add_argument("--force", action="store_true", help="Re-search skills that already have a video course.")
    args = parser.parse_args()

    skills = [s.strip() for s in args.skills.split(",")] if args.skills else skills_from_master()

    existing_rows = load_existing_rows()
    skills_with_video = {r["skill_tag"] for r in existing_rows if r.get("video_id")}

    new_rows = []
    for skill in skills:
        if not args.force and skill in skills_with_video:
            print(f"Skipping '{skill}' (already has a video course; use --force to re-fetch).")
            continue

        query = f"{skill} full course tutorial for beginners"
        print(f"Searching YouTube for: {query!r}")
        try:
            videos = search_videos(query, max_results=args.per_skill)
        except YouTubeAPIError as e:
            print(f"  ! {e}")
            continue

        if not videos:
            print(f"  ! No suitable videos found for '{skill}'.")
            continue

        for video in videos:
            new_rows.append({
                "title": video["title"],
                "provider": video["channel_title"],
                "level": args.level,
                "skill_tag": skill,
                "rating": 4.5,
                "url": f"https://www.youtube.com/watch?v={video['video_id']}",
                "video_id": video["video_id"],
            })
            print(f"  + {video['title']}  ({video['channel_title']})")

    if not new_rows:
        print("Nothing new to add.")
        return

    file_exists = os.path.exists(COURSES_CSV)
    with open(COURSES_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_rows)

    print(f"\nAppended {len(new_rows)} course(s) to {COURSES_CSV}.")
    print("Now run: python database/init_db.py")


if __name__ == "__main__":
    main()
