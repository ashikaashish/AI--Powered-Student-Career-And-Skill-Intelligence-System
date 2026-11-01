"""
Finds real YouTube videos for a course topic and stores them as the course's lessons.

A course is one skill topic (e.g. "Python"). The first time anyone opens/enrolls in the
course we search YouTube for that topic, keep the best 1-3 full-length tutorials, and
save them in course_lessons (so later visits cost no API quota).

Needs YOUTUBE_API_KEY in backend/.env. Without it, a course can still be played if the
courses table already has a video_id for it (data/courses.csv ships a few).
"""
import re
from services.youtube_api import search_videos, YouTubeAPIError

MAX_LESSONS = 3
# One long "full course" video is enough; extra videos are only added when the best
# hit is short, so students aren't sent through hours of unrelated material.
ENOUGH_SECONDS = 45 * 60


def _clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def _topic_queries(skill_tag, level):
    level_word = {"Beginner": "for beginners", "Intermediate": "intermediate", "Advanced": "advanced"}.get(level, "")
    return [
        f"{skill_tag} full course tutorial {level_word}".strip(),
        f"{skill_tag} complete tutorial",
    ]


def _copy_from_same_topic(db, course, need_duration):
    """
    The catalog has many courses per topic (e.g. 70 'Customer service' courses). Searching
    YouTube once per course would burn the free daily quota after ~100 courses, so a course
    reuses the videos already found for another course with the same topic (same level first).
    """
    donor = db.execute(
        """SELECT c.id FROM courses c
           JOIN course_lessons l ON l.course_id = c.id
           WHERE LOWER(c.skill_tag) = LOWER(?) AND c.id != ?
             AND l.youtube_id IS NOT NULL AND l.youtube_id != ''
             AND (? = 0 OR l.duration_seconds > 0)
           GROUP BY c.id
           ORDER BY (c.level = ?) DESC, c.id LIMIT 1""",
        (course["skill_tag"], course["id"], 1 if need_duration else 0, course["level"]),
    ).fetchone()
    if not donor:
        return 0
    lessons = db.execute(
        """SELECT title, position, youtube_id, channel_title, duration_seconds FROM course_lessons
           WHERE course_id = ? AND youtube_id IS NOT NULL AND youtube_id != '' ORDER BY position, id""",
        (donor["id"],),
    ).fetchall()
    for l in lessons:
        db.execute(
            """INSERT INTO course_lessons
               (course_id, title, position, filename, youtube_id, channel_title, duration_seconds)
               VALUES (?, ?, ?, '', ?, ?, ?)""",
            (course["id"], l["title"], l["position"], l["youtube_id"], l["channel_title"], l["duration_seconds"]),
        )
    db.execute(
        "UPDATE courses SET video_id = ?, url = ? WHERE id = ?",
        (lessons[0]["youtube_id"], f"https://www.youtube.com/watch?v={lessons[0]['youtube_id']}", course["id"]),
    )
    db.commit()
    return len(lessons)


def ensure_lessons(db, course_id):
    """
    Make sure the course has YouTube lessons. Returns (lesson_count, error_message|None).
    Never raises: callers show the error text to the user.
    """
    have = db.execute(
        "SELECT COUNT(*) FROM course_lessons WHERE course_id = ? AND youtube_id IS NOT NULL AND youtube_id != ''",
        (course_id,),
    ).fetchone()[0]
    if have:
        return have, None

    course = db.execute("SELECT id, title, skill_tag, level, video_id FROM courses WHERE id = ?", (course_id,)).fetchone()
    if not course:
        return 0, "Course not found"

    # Reuse videos already found for this topic (saves YouTube quota; see helper).
    copied = _copy_from_same_topic(db, course, need_duration=True)
    if copied:
        return copied, None

    videos = []
    error = None
    try:
        seen = set()
        for q in _topic_queries(course["skill_tag"], course["level"]):
            for v in search_videos(q, max_results=5, min_duration_seconds=600):
                if v["video_id"] not in seen:
                    seen.add(v["video_id"])
                    videos.append(v)
            if videos:
                break
    except YouTubeAPIError as e:
        error = str(e)

    chosen, total = [], 0
    for v in videos:
        chosen.append(v)
        total += v["duration_seconds"]
        if total >= ENOUGH_SECONDS or len(chosen) >= MAX_LESSONS:
            break

    # No API key / quota problem: fall back to the video id stored on the course row, if any.
    if not chosen and course["video_id"]:
        db.execute(
            """INSERT INTO course_lessons (course_id, title, position, filename, youtube_id, duration_seconds)
               VALUES (?, ?, 1, '', ?, 0)""",
            (course_id, course["title"], course["video_id"]),
        )
        db.commit()
        return 1, None

    if not chosen:
        # last resort: any video already stored for this topic, even without a known length
        copied = _copy_from_same_topic(db, course, need_duration=False)
        if copied:
            return copied, None
        return 0, error or f"No suitable YouTube videos were found for '{course['skill_tag']}'."

    for i, v in enumerate(chosen, 1):
        db.execute(
            """INSERT INTO course_lessons
               (course_id, title, position, filename, youtube_id, channel_title, duration_seconds)
               VALUES (?, ?, ?, '', ?, ?, ?)""",
            (course_id, _clean(v["title"]), i, v["video_id"], v["channel_title"], v["duration_seconds"]),
        )
    db.execute(
        "UPDATE courses SET provider = ?, video_id = ?, url = ? WHERE id = ?",
        (chosen[0]["channel_title"], chosen[0]["video_id"],
         f"https://www.youtube.com/watch?v={chosen[0]['video_id']}", course_id),
    )
    db.commit()
    return len(chosen), None
