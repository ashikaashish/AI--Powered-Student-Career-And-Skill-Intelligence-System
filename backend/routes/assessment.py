"""
Topic assessment taken after a course's videos are watched (with light proctoring).

  GET  /api/assessment/<course_id>                  questions (answers NOT included, order shuffled)
  POST /api/assessment/<course_id>/start            begins a sitting -> {session_id, time_limit_seconds, ...}
  POST /api/assessment/<course_id>/proctor-event    {session_id, event_type, detail}  (activity log)
  POST /api/assessment/<course_id>/submit           {session_id, answers: {question_id: option text}}

Passing marks the course completed and adds the course's skill to the student's profile.
Grading, the timer and the violation count all live on the server - the browser only reports events.
"""
import json
import random
import time
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db import get_db
from services.learning import award_after_assessment

assessment_bp = Blueprint("assessment", __name__)

PASS_PERCENT = 65             # 4 of 6 questions

# ---- proctoring settings (change these freely) ----
TIME_LIMIT_SECONDS = 10 * 60  # 10 minutes for the quiz
GRACE_SECONDS = 30            # allowance for network delay on the final submit
MAX_VIOLATIONS = 3            # the quiz is auto-submitted at this many warnings
FAIL_IF_FLAGGED = True        # True: reaching MAX_VIOLATIONS cannot pass. False: just record it.

# Counted as warnings:
VIOLATION_TYPES = {"tab_switch", "fullscreen_exit", "no_face", "multiple_faces"}
# Logged only (never counted):
INFO_TYPES = {
    "session_start", "camera_on", "camera_denied", "face_model_unavailable",
    "copy_blocked", "paste_blocked", "menu_blocked", "auto_submit",
}
ALLOWED_EVENTS = VIOLATION_TYPES | INFO_TYPES


def _course_and_status(db, user_id, course_id):
    course = db.execute("SELECT id, title, skill_tag FROM courses WHERE id = ?", (course_id,)).fetchone()
    enr = db.execute(
        "SELECT status FROM user_courses WHERE user_id = ? AND course_id = ?", (user_id, course_id)
    ).fetchone()
    return course, (enr["status"] if enr else None)


def _questions(db, skill_tag):
    return db.execute(
        "SELECT * FROM assessment_questions WHERE LOWER(skill_tag) = LOWER(?) ORDER BY id", (skill_tag,)
    ).fetchall()


def _open_session(db, user_id, course_id, session_id):
    """The student's own, not-yet-submitted sitting for this course (or None)."""
    try:
        session_id = int(session_id)
    except (TypeError, ValueError):
        return None
    return db.execute(
        "SELECT * FROM proctor_sessions WHERE id = ? AND user_id = ? AND course_id = ? AND submitted = 0",
        (session_id, user_id, course_id),
    ).fetchone()


@assessment_bp.route("/<int:course_id>", methods=["GET"])
@jwt_required()
def get_assessment(course_id):
    user_id = get_jwt_identity()
    db = get_db()
    course, status = _course_and_status(db, user_id, course_id)
    if not course:
        db.close()
        return jsonify({"error": "Course not found"}), 404
    if status not in ("watched", "completed"):
        db.close()
        return jsonify({"error": "Finish watching the course videos to unlock the assessment."}), 403

    rows = _questions(db, course["skill_tag"])
    attempts = db.execute(
        """SELECT score_percent, passed, created_at FROM assessment_attempts
           WHERE user_id = ? AND course_id = ? ORDER BY id DESC LIMIT 5""",
        (user_id, course_id),
    ).fetchall()
    db.close()
    if not rows:
        return jsonify({"error": "No assessment is available for this topic yet."}), 404

    rows = list(rows)
    random.shuffle(rows)
    questions = []
    for r in rows:
        opts = json.loads(r["options_json"])
        random.shuffle(opts)
        questions.append({"id": r["id"], "question": r["question"], "options": opts})

    return jsonify({
        "course": {"id": course["id"], "title": course["title"], "skill_tag": course["skill_tag"]},
        "status": status,
        "pass_percent": PASS_PERCENT,
        "time_limit_seconds": TIME_LIMIT_SECONDS,
        "max_violations": MAX_VIOLATIONS,
        "questions": questions,
        "attempts": [dict(a) for a in attempts],
    })


@assessment_bp.route("/<int:course_id>/start", methods=["POST"])
@jwt_required()
def start_assessment(course_id):
    """Called when the student clicks 'Start'. The server clock starts here."""
    user_id = get_jwt_identity()
    db = get_db()
    course, status = _course_and_status(db, user_id, course_id)
    if not course:
        db.close()
        return jsonify({"error": "Course not found"}), 404
    if status not in ("watched", "completed"):
        db.close()
        return jsonify({"error": "Finish watching the course videos to unlock the assessment."}), 403

    cur = db.execute(
        "INSERT INTO proctor_sessions (user_id, course_id, started_at) VALUES (?, ?, ?)",
        (user_id, course_id, time.time()),
    )
    session_id = cur.lastrowid
    db.execute(
        "INSERT INTO proctor_events (session_id, user_id, course_id, event_type) VALUES (?, ?, ?, 'session_start')",
        (session_id, user_id, course_id),
    )
    db.commit()
    db.close()
    return jsonify({
        "session_id": session_id,
        "time_limit_seconds": TIME_LIMIT_SECONDS,
        "max_violations": MAX_VIOLATIONS,
    })


@assessment_bp.route("/<int:course_id>/proctor-event", methods=["POST"])
@jwt_required()
def proctor_event(course_id):
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    event_type = str(data.get("event_type", ""))[:40]
    if event_type not in ALLOWED_EVENTS:
        return jsonify({"error": "Unknown event type"}), 400
    detail = str(data.get("detail") or "")[:200]

    db = get_db()
    session = _open_session(db, user_id, course_id, data.get("session_id"))
    if not session:
        db.close()
        return jsonify({"error": "No active assessment session"}), 404

    if event_type in VIOLATION_TYPES:
        db.execute("UPDATE proctor_sessions SET violation_count = violation_count + 1 WHERE id = ?", (session["id"],))
    db.execute(
        "INSERT INTO proctor_events (session_id, user_id, course_id, event_type, detail) VALUES (?, ?, ?, ?, ?)",
        (session["id"], user_id, course_id, event_type, detail),
    )
    db.commit()
    violations = db.execute(
        "SELECT violation_count FROM proctor_sessions WHERE id = ?", (session["id"],)
    ).fetchone()["violation_count"]
    db.close()
    return jsonify({"violations": violations, "max_violations": MAX_VIOLATIONS})


@assessment_bp.route("/<int:course_id>/submit", methods=["POST"])
@jwt_required()
def submit_assessment(course_id):
    user_id = get_jwt_identity()
    body = request.get_json(silent=True) or {}
    answers = body.get("answers") or {}

    db = get_db()
    course, status = _course_and_status(db, user_id, course_id)
    if not course:
        db.close()
        return jsonify({"error": "Course not found"}), 404
    if status not in ("watched", "completed"):
        db.close()
        return jsonify({"error": "Finish watching the course videos to unlock the assessment."}), 403

    session = _open_session(db, user_id, course_id, body.get("session_id"))
    if not session:
        db.close()
        return jsonify({"error": "Your assessment session was not found. Please start the assessment again."}), 400

    # Server-side timer: a refresh or a paused browser cannot buy extra time.
    if time.time() - session["started_at"] > TIME_LIMIT_SECONDS + GRACE_SECONDS:
        db.execute("UPDATE proctor_sessions SET submitted = 1 WHERE id = ?", (session["id"],))
        db.commit()
        db.close()
        return jsonify({"error": "The time limit for this attempt has passed. Please start a new attempt."}), 403

    rows = _questions(db, course["skill_tag"])
    if not rows:
        db.close()
        return jsonify({"error": "No assessment is available for this topic yet."}), 404

    # Only questions the student actually received count; unanswered = wrong.
    results, correct = [], 0
    for r in rows:
        chosen = answers.get(str(r["id"]))
        ok = chosen is not None and chosen == r["answer"]
        correct += 1 if ok else 0
        results.append({
            "id": r["id"], "question": r["question"], "chosen": chosen,
            "correct_answer": r["answer"], "is_correct": ok, "explanation": r["explanation"],
        })
    total = len(rows)
    score = round(correct / total * 100)

    violations = session["violation_count"]
    flagged = violations >= MAX_VIOLATIONS
    passed = score >= PASS_PERCENT and not (flagged and FAIL_IF_FLAGGED)

    db.execute("UPDATE proctor_sessions SET submitted = 1, flagged = ? WHERE id = ?",
               (1 if flagged else 0, session["id"]))
    db.execute(
        """INSERT INTO assessment_attempts (user_id, course_id, score_percent, correct, total, passed)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, course_id, score, correct, total, 1 if passed else 0),
    )

    skill, impact, newly = None, [], False
    if passed and status != "completed":
        skill, impact = award_after_assessment(db, user_id, course_id)
        newly = True
    db.commit()
    db.close()

    return jsonify({
        "score_percent": score, "correct": correct, "total": total,
        "passed": passed, "pass_percent": PASS_PERCENT,
        "newly_completed": newly,
        "skill_awarded": skill if newly else (course["skill_tag"] if passed else None),
        "career_impact": impact,
        "results": results,
        "proctor": {"violations": violations, "max_violations": MAX_VIOLATIONS, "flagged": flagged},
    })