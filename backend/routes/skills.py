from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db import get_db
from ml.skill_gap import analyze_skill_gap

skills_bp = Blueprint("skills", __name__)


@skills_bp.route("/gap", methods=["GET"])
@jwt_required()
def skill_gap():
    """
    Query param: career (career title). Defaults to the user's top recommended career.
    """
    user_id = get_jwt_identity()
    target_career = request.args.get("career")

    db = get_db()
    user_skills_rows = db.execute(
        "SELECT skill_name, proficiency FROM user_skills WHERE user_id = ?", (user_id,)
    ).fetchall()
    user_skills = {r["skill_name"]: r["proficiency"] for r in user_skills_rows}

    if not target_career:
        from ml.recommend import recommend_careers
        careers = [dict(r) for r in db.execute("SELECT * FROM careers").fetchall()]
        if not careers:
            db.close()
            return jsonify({"error": "No careers available"}), 400
        top = recommend_careers(user_skills, careers, top_n=1)
        target_career = top[0]["title"] if top else careers[0]["title"]

    career_row = db.execute(
        "SELECT * FROM careers WHERE title = ?", (target_career,)
    ).fetchone()
    db.close()

    if not career_row:
        return jsonify({"error": f"Career '{target_career}' not found"}), 404

    required_skills = [s.strip() for s in career_row["required_skills"].split(",")]
    result = analyze_skill_gap(user_skills, required_skills)
    result["target_career"] = target_career
    return jsonify(result)
