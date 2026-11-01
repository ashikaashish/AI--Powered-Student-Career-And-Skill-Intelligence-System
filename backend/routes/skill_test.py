"""
Skill verification tests.

A student can no longer just "add" a skill to the profile. They must pass a short test for it.

  GET  /api/skill-test/available   skills that have a test + the student's status for each
  POST /api/skill-test/start       {skill_name} -> questions (NO answers) + session_id + time limit
  POST /api/skill-test/submit      {session_id, answers: {question_id: chosen option text}}

Grading happens only on the server. Passing adds the skill to user_skills with verified = 1.
Questions come from the same `assessment_questions` table the course assessments use.
"""
import json
import random
import time

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db import get_db
from services.test_generator import TestGenerationError, ensure_bank

skill_test_bp = Blueprint("skill_test", __name__)

# ---- tweak these ----
QUESTIONS_PER_TEST = 8          # uses fewer if the bank for that skill is smaller
PASS_PERCENT = 65
TIME_LIMIT_SECONDS = 10 * 60
GRACE_SECONDS = 30              # network slack when submitting
MAX_STARTS_PER_DAY = 3          # per skill
COOLDOWN_MINUTES_AFTER_FAIL = 30


def _bank(db, skill):
    return db.execute(
        "SELECT * FROM assessment_questions WHERE LOWER(skill_tag) = LOWER(?) ORDER BY id", (skill,)
    ).fetchall()


def _canonical_skill(db, skill):
    """Return (canonical_name, category) for a master-list skill, else None."""
    raw = (skill or "").strip()
    if not raw:
        return None
    row = db.execute(
        "SELECT skill_name, category FROM skills_master WHERE LOWER(skill_name) = LOWER(?)",
        (raw,),
    ).fetchone()
    if row:
        return row["skill_name"], row["category"] or "technical"
    tagged = db.execute(
        "SELECT skill_tag FROM assessment_questions WHERE LOWER(skill_tag) = LOWER(?) LIMIT 1",
        (raw,),
    ).fetchone()
    if tagged:
        return tagged["skill_tag"], "technical"
    return None


def _cooldown_left(db, user_id, skill):
    """Seconds left of the cooldown after the most recent FAILED attempt (0 if none)."""
    row = db.execute(
        """SELECT CAST((julianday('now') - julianday(created_at)) * 86400 AS INTEGER) AS age
           FROM skill_test_attempts
           WHERE user_id = ? AND skill_name = ? AND passed = 0
           ORDER BY id DESC LIMIT 1""",
        (user_id, skill),
    ).fetchone()
    if not row:
        return 0
    return max(0, COOLDOWN_MINUTES_AFTER_FAIL * 60 - row["age"])


def _starts_today(db, user_id, skill):
    return db.execute(
        """SELECT COUNT(*) FROM skill_test_sessions
           WHERE user_id = ? AND skill_name = ? AND created_at >= datetime('now', '-1 day')""",
        (user_id, skill),
    ).fetchone()[0]


@skill_test_bp.route("/available", methods=["GET"])
@jwt_required()
def available():
    user_id = get_jwt_identity()
    db = get_db()
    counts = {
        r["skill_tag"].lower(): r["n"]
        for r in db.execute(
            "SELECT skill_tag, COUNT(*) AS n FROM assessment_questions GROUP BY skill_tag"
        )
    }
    masters = db.execute(
        "SELECT skill_name, category FROM skills_master ORDER BY skill_name"
    ).fetchall()
    owned = {
        r["skill_name"].lower(): r
        for r in db.execute(
            "SELECT skill_name, COALESCE(verified, 0) AS verified, verified_score FROM user_skills WHERE user_id = ?",
            (user_id,),
        )
    }
    out = []
    for m in masters:
        name = m["skill_name"]
        mine = owned.get(name.lower())
        n = counts.get(name.lower(), 0)
        out.append({
            "skill_name": name,
            "category": m["category"] or "technical",
            "question_count": n,
            "has_test": True,
            "verified": bool(mine and mine["verified"]),
            "verified_score": mine["verified_score"] if mine else None,
            "cooldown_seconds": _cooldown_left(db, user_id, name),
        })
    db.close()
    return jsonify({"skills": out, "pass_percent": PASS_PERCENT, "time_limit_seconds": TIME_LIMIT_SECONDS})


@skill_test_bp.route("/start", methods=["POST"])
@jwt_required()
def start():
    user_id = get_jwt_identity()
    body = request.get_json(silent=True) or {}

    db = get_db()
    found = _canonical_skill(db, body.get("skill_name"))
    if not found:
        db.close()
        return jsonify({"error": "This skill is not on the skill list, so it cannot be tested."}), 404
    skill, category = found
    try:
        ensure_bank(db, skill, category)
        db.commit()
    except TestGenerationError as exc:
        db.close()
        return jsonify({"error": str(exc)}), 500

    already = db.execute(
        "SELECT 1 FROM user_skills WHERE user_id = ? AND LOWER(skill_name) = LOWER(?) AND COALESCE(verified, 0) = 1",
        (user_id, skill),
    ).fetchone()
    if already:
        db.close()
        return jsonify({"error": f"{skill} is already verified on your profile."}), 409

    wait = _cooldown_left(db, user_id, skill)
    if wait > 0:
        db.close()
        return jsonify({
            "error": f"Review {skill} and try again in {-(-wait // 60)} min.",
            "cooldown_seconds": wait,
        }), 429
    if _starts_today(db, user_id, skill) >= MAX_STARTS_PER_DAY:
        db.close()
        return jsonify({"error": f"You've used all {MAX_STARTS_PER_DAY} attempts for {skill} today. Try again tomorrow."}), 429

    rows = list(_bank(db, skill))
    if not rows:
        db.close()
        return jsonify({"error": f"Could not load test questions for {skill}."}), 500
    random.shuffle(rows)
    rows = rows[:QUESTIONS_PER_TEST]

    # abandon any earlier unfinished session for this skill, then open a new one
    db.execute("UPDATE skill_test_sessions SET used = 1 WHERE user_id = ? AND skill_name = ?", (user_id, skill))
    cur = db.execute(
        "INSERT INTO skill_test_sessions (user_id, skill_name, question_ids_json, expires_at) VALUES (?, ?, ?, ?)",
        (user_id, skill, json.dumps([r["id"] for r in rows]), time.time() + TIME_LIMIT_SECONDS),
    )
    session_id = cur.lastrowid
    db.commit()

    questions = []
    for r in rows:
        opts = json.loads(r["options_json"])
        random.shuffle(opts)
        questions.append({"id": r["id"], "question": r["question"], "options": opts})
    db.close()

    return jsonify({
        "session_id": session_id,
        "skill_name": skill,
        "pass_percent": PASS_PERCENT,
        "time_limit_seconds": TIME_LIMIT_SECONDS,
        "questions": questions,
    })


@skill_test_bp.route("/submit", methods=["POST"])
@jwt_required()
def submit():
    user_id = get_jwt_identity()
    body = request.get_json(silent=True) or {}
    answers = body.get("answers") or {}

    db = get_db()
    sess = db.execute(
        "SELECT * FROM skill_test_sessions WHERE id = ? AND user_id = ?",
        (body.get("session_id"), user_id),
    ).fetchone()
    if not sess or sess["used"]:
        db.close()
        return jsonify({"error": "This test session is not valid any more. Start the test again."}), 400
    # a session can be graded only once
    db.execute("UPDATE skill_test_sessions SET used = 1 WHERE id = ?", (sess["id"],))

    if time.time() > sess["expires_at"] + GRACE_SECONDS:
        db.commit()
        db.close()
        return jsonify({"error": "Time ran out before the test was submitted."}), 400

    skill = sess["skill_name"]
    ids = json.loads(sess["question_ids_json"])
    marks = ",".join("?" * len(ids))
    rows = db.execute(f"SELECT * FROM assessment_questions WHERE id IN ({marks})", ids).fetchall()

    correct, results = 0, []
    for r in rows:
        chosen = answers.get(str(r["id"]))
        ok = chosen is not None and chosen == r["answer"]
        correct += 1 if ok else 0
        results.append({
            "id": r["id"], "question": r["question"], "chosen": chosen,
            "correct_answer": r["answer"], "is_correct": ok, "explanation": r["explanation"],
        })
    total = len(rows)
    score = round(correct / total * 100) if total else 0
    passed = score >= PASS_PERCENT

    db.execute(
        """INSERT INTO skill_test_attempts (user_id, skill_name, score_percent, correct, total, passed)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, skill, score, correct, total, 1 if passed else 0),
    )

    if passed:
        db.execute("INSERT OR IGNORE INTO skills_master (skill_name, category) VALUES (?, 'technical')", (skill,))
        existing = db.execute(
            "SELECT id, source, proficiency FROM user_skills WHERE user_id = ? AND LOWER(skill_name) = LOWER(?)",
            (user_id, skill),
        ).fetchone()
        if existing:
            # keep a course-earned skill's source; otherwise mark it as test-verified
            new_source = existing["source"] if existing["source"] == "course" else "test"
            db.execute(
                """UPDATE user_skills SET proficiency = MAX(proficiency, ?), source = ?,
                          verified = 1, verified_score = ? WHERE id = ?""",
                (score, new_source, score, existing["id"]),
            )
        else:
            db.execute(
                """INSERT INTO user_skills (user_id, skill_name, proficiency, source, verified, verified_score)
                   VALUES (?, ?, ?, 'test', 1, ?)""",
                (user_id, skill, score, score),
            )
    db.commit()
    db.close()

    resp = {
        "skill_name": skill, "score_percent": score, "correct": correct, "total": total,
        "passed": passed, "pass_percent": PASS_PERCENT,
    }
    if passed:
        resp["results"] = results   # answers + explanations are shown only after passing
    return jsonify(resp)