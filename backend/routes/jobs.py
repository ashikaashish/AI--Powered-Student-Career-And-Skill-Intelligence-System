from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db import get_db
from services.live_jobs import find_jobs_for_skills, pick_profile_skills

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.route("", methods=["GET"])
def list_jobs():
    search = request.args.get("q", "").strip()
    db = get_db()
    if search:
        rows = db.execute(
            "SELECT * FROM careers WHERE title LIKE ? OR category LIKE ?",
            (f"%{search}%", f"%{search}%"),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM careers ORDER BY title").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@jobs_bp.route("/for-me", methods=["GET"])
@jwt_required()
def jobs_for_me():
    """Current openings (with hiring company) that match the skills on the user's profile.
    Query: location (city, optional), scope = india | all (default india)."""
    user_id = get_jwt_identity()
    db = get_db()
    rows = db.execute(
        """SELECT us.skill_name, us.proficiency, us.verified, sm.category
           FROM user_skills us
           LEFT JOIN skills_master sm ON LOWER(sm.skill_name) = LOWER(us.skill_name)
           WHERE us.user_id = ?""", (user_id,)).fetchall()
    user = db.execute("SELECT location FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()

    skills = pick_profile_skills([dict(r) for r in rows])
    scope = "all" if request.args.get("scope") == "all" else "india"
    where = request.args.get("location")
    if where is None:                       # default to the city on the profile
        where = (user["location"] if user and user["location"] not in (None, "N/A") else "") or ""
    result = find_jobs_for_skills(skills, where=where.strip(), country="in", scope=scope)
    result["location"] = where.strip()
    return jsonify(result)


@jobs_bp.route("/<string:title>", methods=["GET"])
def job_detail(title):
    db = get_db()
    row = db.execute("SELECT * FROM careers WHERE title = ?", (title,)).fetchone()
    db.close()
    if not row:
        return jsonify({"error": "Career not found"}), 404
    career = dict(row)
    career["required_skills"] = [s.strip() for s in career["required_skills"].split(",")]
    return jsonify(career)