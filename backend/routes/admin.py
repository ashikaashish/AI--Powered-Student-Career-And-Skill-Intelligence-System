from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db import get_db
from services.youtube_lessons import ensure_lessons
from functools import wraps
from datetime import date, timedelta

admin_bp = Blueprint("admin", __name__)


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        db = get_db()
        user = db.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        db.close()
        if not user or user["role"] != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return fn(*args, **kwargs)
    return wrapper


@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def admin_dashboard():
    db = get_db()
    total_students = db.execute("SELECT COUNT(*) c FROM users WHERE role = 'student'").fetchone()["c"]
    total_skills = db.execute("SELECT COUNT(*) c FROM skills_master").fetchone()["c"]
    total_courses = db.execute("SELECT COUNT(*) c FROM courses").fetchone()["c"]
    total_careers = db.execute("SELECT COUNT(*) c FROM careers").fetchone()["c"]

    top_skills = db.execute(
        """SELECT skill_name, COUNT(*) as count FROM user_skills
           GROUP BY skill_name ORDER BY count DESC LIMIT 6"""
    ).fetchall()

    # Registrations per DAY for the last 14 days (days with 0 signups included)
    days = 14
    start = date.today() - timedelta(days=days - 1)
    rows = db.execute(
        """SELECT date(created_at) AS day, COUNT(*) AS count
           FROM users
           WHERE role = 'student' AND date(created_at) >= ?
           GROUP BY day""",
        (start.isoformat(),),
    ).fetchall()
    db.close()

    counts = {r["day"]: r["count"] for r in rows}
    registrations = [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "count": counts.get((start + timedelta(days=i)).isoformat(), 0),
        }
        for i in range(days)
    ]

    return jsonify({
        "total_students": total_students,
        "total_skills": total_skills,
        "total_courses": total_courses,
        "total_careers": total_careers,
        "top_skills": [dict(r) for r in top_skills],
        "registrations_over_time": registrations,
    })


@admin_bp.route("/students", methods=["GET"])
@admin_required
def manage_students():
    db = get_db()
    rows = db.execute(
        """SELECT id, name, email, education, stream, year, created_at FROM users
           WHERE role = 'student' ORDER BY created_at DESC"""
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@admin_bp.route("/students/<int:student_id>", methods=["DELETE"])
@admin_required
def delete_student(student_id):
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ? AND role = 'student'", (student_id,))
    db.commit()
    db.close()
    return jsonify({"message": "Student removed"})


@admin_bp.route("/courses", methods=["GET"])
@admin_required
def manage_courses():
    db = get_db()
    rows = db.execute(
        """SELECT c.*,
                  (SELECT COUNT(*) FROM course_lessons l WHERE l.course_id = c.id) AS lesson_count,
                  (SELECT COALESCE(SUM(l.duration_seconds), 0) FROM course_lessons l WHERE l.course_id = c.id) AS total_seconds,
                  (SELECT COUNT(*) FROM user_courses uc WHERE uc.course_id = c.id) AS enrolled_count,
                  (SELECT COUNT(*) FROM assessment_questions q WHERE LOWER(q.skill_tag) = LOWER(c.skill_tag)) AS question_count
           FROM courses c ORDER BY c.id DESC"""
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@admin_bp.route("/courses", methods=["POST"])
@admin_required
def add_course():
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "").strip()
    skill_tag = (data.get("skill_tag") or "").strip()
    if not title or not skill_tag:
        return jsonify({"error": "title and skill_tag are required"}), 400
    db = get_db()
    cur = db.execute(
        """INSERT INTO courses (title, provider, level, skill_tag, rating, url)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, data.get("provider") or "YouTube", data.get("level") or "Beginner",
         skill_tag, data.get("rating", 4.5), data.get("url", "")),
    )
    db.commit()
    new_id = cur.lastrowid
    db.close()
    return jsonify({"message": "Course added", "id": new_id}), 201


@admin_bp.route("/courses/<int:course_id>", methods=["DELETE"])
@admin_required
def delete_course(course_id):
    db = get_db()
    db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    db.commit()
    db.close()
    return jsonify({"message": "Course removed"})


# ------------------------------------------------------------------ lessons ---
# Lessons are YouTube videos found automatically for the course topic
# (services/youtube_lessons.py). Admins can inspect them or re-run the search.

@admin_bp.route("/courses/<int:course_id>/lessons", methods=["GET"])
@admin_required
def list_lessons(course_id):
    db = get_db()
    rows = db.execute(
        """SELECT id, title, position, duration_seconds, youtube_id, channel_title
           FROM course_lessons WHERE course_id = ? ORDER BY position, id""",
        (course_id,),
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@admin_bp.route("/courses/<int:course_id>/refresh-videos", methods=["POST"])
@admin_required
def refresh_videos(course_id):
    """Throw away the saved videos for this topic and search YouTube again."""
    db = get_db()
    if not db.execute("SELECT 1 FROM courses WHERE id = ?", (course_id,)).fetchone():
        db.close()
        return jsonify({"error": "Course not found"}), 404
    db.execute("DELETE FROM lesson_progress WHERE lesson_id IN (SELECT id FROM course_lessons WHERE course_id = ?)", (course_id,))
    db.execute("DELETE FROM course_lessons WHERE course_id = ?", (course_id,))
    db.execute("UPDATE user_courses SET watch_percent = 0, status = 'in_progress' WHERE course_id = ? AND status != 'completed'", (course_id,))
    db.commit()
    count, err = ensure_lessons(db, course_id)
    db.close()
    if not count:
        return jsonify({"error": err or "No videos found"}), 502
    return jsonify({"message": f"Found {count} video(s) on YouTube", "count": count})


@admin_bp.route("/lessons/<int:lesson_id>", methods=["DELETE"])
@admin_required
def delete_lesson(lesson_id):
    db = get_db()
    db.execute("DELETE FROM course_lessons WHERE id = ?", (lesson_id,))
    db.commit()
    db.close()
    return jsonify({"message": "Lesson removed"})


@admin_bp.route("/courses/youtube-search", methods=["GET"])
@admin_required
def youtube_search():
    """
    Live search against the real YouTube Data API.
    Query params: q (search text, required), max (optional, default 8)
    """
    from services.youtube_api import search_videos, YouTubeAPIError

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "q is required"}), 400
    max_results = min(int(request.args.get("max", 8)), 15)

    try:
        results = search_videos(query, max_results=max_results)
    except YouTubeAPIError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify(results)


@admin_bp.route("/courses/from-youtube", methods=["POST"])
@admin_required
def add_course_from_youtube():
    """
    Add a course row from a video the admin picked out of /youtube-search
    results. Body: { video_id, title, channel_title, skill_tag, level }
    """
    data = request.get_json(force=True) or {}
    video_id = (data.get("video_id") or "").strip()
    skill_tag = (data.get("skill_tag") or "").strip()
    if not video_id or not skill_tag:
        return jsonify({"error": "video_id and skill_tag are required"}), 400

    db = get_db()
    db.execute(
        """INSERT INTO courses (title, provider, level, skill_tag, rating, url, video_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data.get("title", "Untitled"),
            data.get("channel_title", "YouTube"),
            data.get("level", "Beginner"),
            skill_tag,
            4.5,
            f"https://www.youtube.com/watch?v={video_id}",
            video_id,
        ),
    )
    db.commit()
    db.close()
    return jsonify({"message": "Course added from YouTube"}), 201


@admin_bp.route("/skills", methods=["GET"])
@admin_required
def manage_skills():
    db = get_db()
    rows = db.execute("SELECT * FROM skills_master ORDER BY skill_name").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@admin_bp.route("/skills", methods=["POST"])
@admin_required
def add_skill():
    data = request.get_json(force=True)
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO skills_master (skill_name, category) VALUES (?, ?)",
        (data.get("skill_name"), data.get("category", "technical")),
    )
    db.commit()
    db.close()
    return jsonify({"message": "Skill added"}), 201