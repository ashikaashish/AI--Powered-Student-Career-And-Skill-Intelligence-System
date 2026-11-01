"""
Course player API (YouTube videos).

  GET  /api/learn/courses/<id>           course + YouTube lessons + this user's progress
  POST /api/learn/lessons/<id>/progress  player reports its position (server validates it)
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db import get_db
from services.learning import (
    COMPLETION_THRESHOLD, lesson_percent, record_lesson_progress, sync_course,
)
from services.youtube_lessons import ensure_lessons

learning_bp = Blueprint("learning", __name__)


def _is_enrolled(db, user_id, course_id):
    return db.execute(
        "SELECT 1 FROM user_courses WHERE user_id = ? AND course_id = ?", (user_id, course_id)
    ).fetchone() is not None


@learning_bp.route("/courses/<int:course_id>", methods=["GET"])
@jwt_required()
def course_detail(course_id):
    user_id = get_jwt_identity()
    db = get_db()
    course = db.execute("SELECT id, title, provider, level, skill_tag, rating FROM courses WHERE id = ?",
                        (course_id,)).fetchone()
    if not course:
        db.close()
        return jsonify({"error": "Course not found"}), 404

    # Find the topic's videos on YouTube the first time the course is opened.
    _, fetch_error = ensure_lessons(db, course_id)
    course = db.execute("SELECT id, title, provider, level, skill_tag, rating FROM courses WHERE id = ?",
                        (course_id,)).fetchone()

    enrollment = db.execute(
        "SELECT status, watch_percent FROM user_courses WHERE user_id = ? AND course_id = ?",
        (user_id, course_id),
    ).fetchone()

    rows = db.execute(
        """SELECT l.id, l.title, l.position, l.duration_seconds, l.youtube_id, l.channel_title,
                  COALESCE(p.watched_seconds, 0) AS watched_seconds,
                  COALESCE(p.last_position, 0)   AS last_position
           FROM course_lessons l
           LEFT JOIN lesson_progress p ON p.lesson_id = l.id AND p.user_id = ?
           WHERE l.course_id = ? AND l.youtube_id IS NOT NULL AND l.youtube_id != ''
           ORDER BY l.position, l.id""",
        (user_id, course_id),
    ).fetchall()
    last_attempt = db.execute(
        """SELECT score_percent, passed, created_at FROM assessment_attempts
           WHERE user_id = ? AND course_id = ? ORDER BY id DESC LIMIT 1""",
        (user_id, course_id),
    ).fetchone()
    db.close()

    lessons = []
    resume_id = None
    for r in rows:
        pct = lesson_percent(r["watched_seconds"], r["duration_seconds"])
        done = pct >= COMPLETION_THRESHOLD
        lessons.append({
            "id": r["id"], "title": r["title"], "position": r["position"],
            "youtube_id": r["youtube_id"], "channel_title": r["channel_title"],
            "duration_seconds": r["duration_seconds"],
            "watched_seconds": r["watched_seconds"], "last_position": r["last_position"],
            "percent": pct, "completed": done,
        })
        if resume_id is None and not done:
            resume_id = r["id"]
    if resume_id is None and lessons:
        resume_id = lessons[0]["id"]

    return jsonify({
        "course": dict(course),
        "lessons": lessons,
        "total_seconds": sum(l["duration_seconds"] for l in lessons),
        "enrolled": enrollment is not None,
        "status": enrollment["status"] if enrollment else None,   # in_progress | watched | completed
        "watch_percent": enrollment["watch_percent"] if enrollment else 0,
        "resume_lesson_id": resume_id,
        "completion_threshold": COMPLETION_THRESHOLD,
        "last_attempt": dict(last_attempt) if last_attempt else None,
        "video_error": fetch_error if not lessons else None,
    })


@learning_bp.route("/lessons/<int:lesson_id>/progress", methods=["POST"])
@jwt_required()
def report_progress(lesson_id):
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    try:
        position = float(data.get("position", 0))
        duration = float(data.get("duration") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "position and duration must be numbers"}), 400
    ended = bool(data.get("ended"))

    db = get_db()
    lesson = db.execute("SELECT * FROM course_lessons WHERE id = ?", (lesson_id,)).fetchone()
    if not lesson:
        db.close()
        return jsonify({"error": "Lesson not found"}), 404
    if not _is_enrolled(db, user_id, lesson["course_id"]):
        db.close()
        return jsonify({"error": "Enroll in this course first"}), 403

    watched, last_pos = record_lesson_progress(db, user_id, lesson, position, duration, ended)
    course_state = sync_course(db, user_id, lesson["course_id"])
    db.commit()

    dur = db.execute("SELECT duration_seconds FROM course_lessons WHERE id = ?", (lesson_id,)).fetchone()[0]
    db.close()

    return jsonify({
        **course_state,
        "lesson": {
            "id": lesson_id,
            "watched_seconds": watched,
            "last_position": last_pos,
            "duration_seconds": dur,
            "percent": lesson_percent(watched, dur),
            "completed": lesson_percent(watched, dur) >= COMPLETION_THRESHOLD,
        },
    })
