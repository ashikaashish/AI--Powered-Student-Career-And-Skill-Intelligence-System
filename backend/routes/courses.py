from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db import get_db
from services.youtube_lessons import ensure_lessons

courses_bp = Blueprint("courses", __name__)

# Each course is a skill topic; its lessons are real YouTube videos found for that topic
# (services/youtube_lessons.py). Watching unlocks the assessment; the skill is added to the
# profile only after the student passes it (routes/assessment.py).

_LESSON_STATS = """
    SELECT c.*,
           (SELECT COUNT(*) FROM course_lessons l WHERE l.course_id = c.id) AS lesson_count,
           (SELECT COALESCE(SUM(l.duration_seconds), 0) FROM course_lessons l WHERE l.course_id = c.id) AS total_seconds,
           (SELECT COUNT(*) FROM assessment_questions q WHERE LOWER(q.skill_tag) = LOWER(c.skill_tag)) AS question_count
    FROM courses c
"""


@courses_bp.route("", methods=["GET"])
def list_courses():
    level = request.args.get("level")  # Beginner | Intermediate | Advanced
    skill = request.args.get("skill")

    query = _LESSON_STATS + " WHERE 1=1"
    params = []
    if level and level.lower() != "all":
        query += " AND c.level = ?"
        params.append(level)
    if skill:
        query += " AND c.skill_tag = ?"
        params.append(skill)
    # courses that already have videos first, then best rated
    query += " ORDER BY (question_count > 0) DESC, c.rating DESC, c.id"

    db = get_db()
    rows = db.execute(query, params).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@courses_bp.route("/recommended", methods=["GET"])
@jwt_required()
def recommended_courses():
    """Recommend courses that target the user's current skill gaps for their top career."""
    user_id = get_jwt_identity()
    db = get_db()
    user_skills_rows = db.execute(
        "SELECT skill_name, proficiency FROM user_skills WHERE user_id = ?", (user_id,)
    ).fetchall()
    user_skills = {r["skill_name"]: r["proficiency"] for r in user_skills_rows}
    careers = [dict(r) for r in db.execute("SELECT * FROM careers").fetchall()]

    from ml.recommend import recommend_careers
    from ml.skill_gap import analyze_skill_gap

    if not user_skills or not careers:
        db.close()
        return jsonify([])

    top = recommend_careers(user_skills, careers, top_n=1)[0]
    required_skills = [s.strip() for s in top["required_skills"].split(",")]
    gap = analyze_skill_gap(user_skills, required_skills)
    weak_skill_names = [s["skill"] for s in gap["missing"]] + [s["skill"] for s in gap["partial"]]

    if not weak_skill_names:
        rows = db.execute(_LESSON_STATS + " ORDER BY c.rating DESC LIMIT 5").fetchall()
    else:
        placeholders = ",".join("?" for _ in weak_skill_names)
        rows = db.execute(
            _LESSON_STATS + f" WHERE c.skill_tag IN ({placeholders}) ORDER BY c.rating DESC",
            weak_skill_names,
        ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@courses_bp.route("/enrolled", methods=["GET"])
@jwt_required()
def enrolled_courses():
    """Returns this user's course_id -> {status, watch_percent} map, so the
    frontend can show correct progress bars/checkmarks on page load."""
    user_id = get_jwt_identity()
    db = get_db()
    rows = db.execute(
        "SELECT course_id, status, watch_percent FROM user_courses WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    db.close()
    return jsonify({str(r["course_id"]): {"status": r["status"], "watch_percent": r["watch_percent"]} for r in rows})


@courses_bp.route("/<int:course_id>/enroll", methods=["POST"])
@jwt_required()
def enroll_course(course_id):
    user_id = get_jwt_identity()
    db = get_db()
    course = db.execute("SELECT id FROM courses WHERE id = ?", (course_id,)).fetchone()
    if not course:
        db.close()
        return jsonify({"error": "Course not found"}), 404
    has_quiz = db.execute(
        "SELECT 1 FROM assessment_questions q JOIN courses c ON LOWER(c.skill_tag) = LOWER(q.skill_tag) "
        "WHERE c.id = ? LIMIT 1", (course_id,)).fetchone()
    if not has_quiz:
        db.close()
        return jsonify({"error": "The assessment for this topic isn't ready yet."}), 409
    count, err = ensure_lessons(db, course_id)     # search YouTube for this topic (cached after 1st time)
    if not count:
        db.close()
        return jsonify({"error": err or "Couldn't find videos for this topic."}), 409
    existing = db.execute(
        "SELECT id FROM user_courses WHERE user_id = ? AND course_id = ?",
        (user_id, course_id),
    ).fetchone()
    if not existing:
        db.execute(
            "INSERT INTO user_courses (user_id, course_id, status) VALUES (?, ?, 'in_progress')",
            (user_id, course_id),
        )
        db.commit()
    db.close()
    return jsonify({"message": "Enrolled successfully"})
