from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db import get_db

progress_bp = Blueprint("progress", __name__)


@progress_bp.route("", methods=["GET"])
@jwt_required()
def get_progress():
    user_id = get_jwt_identity()
    db = get_db()

    courses_completed = db.execute(
        "SELECT COUNT(*) c FROM user_courses WHERE user_id = ? AND status = 'completed'",
        (user_id,),
    ).fetchone()["c"]

    skills_learned = db.execute(
        "SELECT COUNT(*) c FROM user_skills WHERE user_id = ? AND proficiency >= 50",
        (user_id,),
    ).fetchone()["c"]

    recent = db.execute(
        """SELECT c.title, uc.completed_at FROM user_courses uc
           JOIN courses c ON c.id = uc.course_id
           WHERE uc.user_id = ? AND uc.status = 'completed'
           ORDER BY uc.completed_at DESC LIMIT 5""",
        (user_id,),
    ).fetchall()

    db.close()

    career_readiness = min(round((skills_learned * 5 + courses_completed * 5) / 2), 100)

    return jsonify({
        "courses_completed": courses_completed,
        "skills_learned": skills_learned,
        "projects_completed": courses_completed,
        "career_readiness_percent": career_readiness,
        "recent_achievements": [dict(r) for r in recent],
    })
