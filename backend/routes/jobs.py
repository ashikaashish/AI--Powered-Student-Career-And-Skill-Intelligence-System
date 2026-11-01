from flask import Blueprint, jsonify, request
from database.db import get_db

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
