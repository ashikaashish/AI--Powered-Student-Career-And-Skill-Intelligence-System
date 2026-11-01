import json
import sqlite3
import traceback
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db import get_db
from ml.aptitude_test import (
    ABILITIES, ABILITY_LABELS, INTERESTS, INTEREST_LABELS, INTEREST_HINTS,
    get_questions, score_answers, holland_code, recommend_careers,
)

aptitude_bp = Blueprint("aptitude", __name__)

# Older databases (built before this table existed) don't have it. Create it on
# demand so a saved result never fails just because init_db.py wasn't re-run.
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS aptitude_test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    abilities_json TEXT NOT NULL,
    interests_json TEXT NOT NULL,
    interest_code TEXT,
    top_matches TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""


@aptitude_bp.route("/questions", methods=["GET"])
@jwt_required()
def questions():
    """Ability questions (no answer key) + interest statements."""
    data = get_questions()
    data["labels"] = {
        "ability": ABILITY_LABELS,
        "interest": INTEREST_LABELS,
        "interest_hints": INTEREST_HINTS,
    }
    return jsonify(data)


@aptitude_bp.route("/submit", methods=["POST"])
@jwt_required()
def submit():
    """
    Body: { "ability": {"n1": 1, "n2": 2, ...},      # chosen option index
            "interest": {"r1": 4, "i1": 5, ...} }    # rating 1-5
    Scores the test, recommends careers, saves the attempt.
    """
    user_id = get_jwt_identity()
    body = request.get_json(force=True) or {}

    try:
        abilities, interests, detail = score_answers(
            body.get("ability") or {}, body.get("interest") or {}
        )
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400

    db = get_db()
    try:
        careers = [dict(r) for r in db.execute("SELECT * FROM careers").fetchall()]
        matches, fields = recommend_careers(abilities, interests, careers)
        code = holland_code(interests)

        saved = True
        try:
            db.execute(_CREATE_TABLE)
            db.execute(
                """INSERT INTO aptitude_test_results
                   (user_id, abilities_json, interests_json, interest_code, top_matches)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, json.dumps(abilities), json.dumps(interests), code,
                 json.dumps([{"title": m["title"], "match_score": m["match_score"]} for m in matches])),
            )
            db.commit()
        except sqlite3.IntegrityError:
            # Token points at a user that no longer exists (e.g. the DB was rebuilt).
            db.close()
            return jsonify({"error": "Your session is out of date. Please log in again."}), 401
        except sqlite3.Error:
            traceback.print_exc()
            saved = False   # still show the result, just don't keep history
    except Exception as e:
        traceback.print_exc()
        db.close()
        return jsonify({"error": f"Couldn't calculate your results ({type(e).__name__}). Check the backend console."}), 500
    db.close()

    return jsonify({
        "abilities": abilities,
        "interests": interests,
        "interest_code": code,
        "correct": detail["correct"],
        "total": detail["total"],
        "careers": matches,
        "fields": fields,
        "saved": saved,
    })


@aptitude_bp.route("/history", methods=["GET"])
@jwt_required()
def history():
    user_id = get_jwt_identity()
    db = get_db()
    db.execute(_CREATE_TABLE)
    rows = db.execute(
        "SELECT * FROM aptitude_test_results WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user_id,),
    ).fetchall()
    db.close()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "created_at": r["created_at"],
            "interest_code": r["interest_code"],
            "abilities": json.loads(r["abilities_json"]),
            "interests": json.loads(r["interests_json"]),
            "top_matches": json.loads(r["top_matches"]) if r["top_matches"] else [],
        })
    return jsonify(out)
