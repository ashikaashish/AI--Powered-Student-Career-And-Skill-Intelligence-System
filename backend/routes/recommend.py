from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db import get_db
from ml.recommend import recommend_careers, stream_only_suggestions
from streams import categories_for_stream

recommend_bp = Blueprint("recommend", __name__)


def _get_user_skills(db, user_id):
    rows = db.execute(
        "SELECT skill_name, proficiency FROM user_skills WHERE user_id = ?", (user_id,)
    ).fetchall()
    return {r["skill_name"]: r["proficiency"] for r in rows}


def _get_user_stream_categories(db, user_id):
    row = db.execute("SELECT stream FROM users WHERE id = ?", (user_id,)).fetchone()
    return categories_for_stream(row["stream"] if row else None)


def _get_all_careers(db):
    rows = db.execute("SELECT * FROM careers").fetchall()
    return [dict(r) for r in rows]


@recommend_bp.route("", methods=["GET"])
@jwt_required()
def get_recommendations():
    user_id = get_jwt_identity()
    top_n = int(request.args.get("top_n", 5))

    db = get_db()
    user_skills = _get_user_skills(db, user_id)
    stream_categories = _get_user_stream_categories(db, user_id)
    careers = _get_all_careers(db)
    db.close()

    if not user_skills:
        if stream_categories:
            suggestions = stream_only_suggestions(careers, stream_categories, top_n=top_n)
            return jsonify({
                "recommendations": suggestions,
                "message": "These are starting suggestions based on your stream. "
                           "Add your skills to your profile for a personalized match.",
            })
        return jsonify({"error": "Add your skills to your profile first to get recommendations"}), 400

    recommendations = recommend_careers(user_skills, careers, top_n=top_n, stream_categories=stream_categories)
    have = {k.lower() for k, v in user_skills.items() if v > 0}
    for r in recommendations:
        req = [x.strip() for x in r["required_skills"].split(",") if x.strip()]
        r["matched_skills"] = [x for x in req if x.lower() in have]
        r["missing_skills"] = [x for x in req if x.lower() not in have]

    db = get_db()
    earned = [dict(r) for r in db.execute(
        """SELECT us.skill_name, c.title AS course_title FROM user_skills us
           LEFT JOIN courses c ON c.id = us.course_id
           WHERE us.user_id = ? AND us.source = 'course' ORDER BY us.id DESC""", (user_id,))]
    db.close()
    return jsonify({
        "recommendations": recommendations,
        "skills_summary": {"total": len(user_skills), "from_courses": earned},
    })


@recommend_bp.route("/dashboard-summary", methods=["GET"])
@jwt_required()
def dashboard_summary():
    """Powers the Dashboard page: career match score, skills acquired, skill gap count, career options."""
    user_id = get_jwt_identity()
    db = get_db()
    user_skills = _get_user_skills(db, user_id)
    stream_categories = _get_user_stream_categories(db, user_id)
    careers = _get_all_careers(db)
    db.close()

    if not user_skills:
        if stream_categories:
            suggestions = stream_only_suggestions(careers, stream_categories, top_n=3)
            return jsonify({
                "career_match_score": suggestions[0]["match_score"] if suggestions else 0,
                "skills_acquired": 0,
                "skills_gap": 0,
                "career_options": len(careers),
                "top_suggestions": [{"title": r["title"], "match_score": r["match_score"]} for r in suggestions],
            })
        return jsonify({
            "career_match_score": 0, "skills_acquired": 0,
            "skills_gap": 0, "career_options": 0, "top_suggestions": [],
        })

    recs = recommend_careers(user_skills, careers, top_n=3, stream_categories=stream_categories)
    top_required_skills = {s.strip() for s in recs[0]["required_skills"].split(",")} if recs else set()
    skills_acquired = len([k for k, v in user_skills.items() if v >= 50])
    skills_gap = len(top_required_skills - set(user_skills.keys()))

    return jsonify({
        "career_match_score": recs[0]["match_score"] if recs else 0,
        "skills_acquired": skills_acquired,
        "skills_gap": skills_gap,
        "career_options": len(careers),
        "top_suggestions": [{"title": r["title"], "match_score": r["match_score"]} for r in recs],
    })
