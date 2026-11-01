"""
Shared learning logic: watch-progress maths, assessment unlock, skill award,
and "how did earning this skill change my career matches?".

Flow:  in_progress --(watch >= 90%)--> watched --(pass the assessment)--> completed
The skill is added to the student's profile ONLY when the assessment is passed.
All decisions are made on the SERVER; the browser only reports where the video is.
"""
import time

# % of the course's total video time that must be watched to auto-complete it
COMPLETION_THRESHOLD = 90

# Proficiency given the first time a skill is earned from a course. If the user
# already has a higher value we never lower it.
LEVEL_PROFICIENCY = {"Beginner": 60, "Intermediate": 70, "Advanced": 80}
DEFAULT_PROFICIENCY = 60

# Anti-skip. Credit for "watched" time is limited by how much real time has passed since
# the previous report, so jumping to the end (or hammering the API) earns nothing.
MAX_PLAYBACK_RATE = 2.2          # nobody legitimately watches faster than ~2x
FIRST_REPORT_ALLOWANCE = 15      # seconds of credit on a lesson's very first report
MAX_GAP_CREDIT_SECONDS = 90      # backgrounded tabs throttle timers to ~1/min; cap the credit


# ---------------------------------------------------------------- progress ---

def lesson_percent(watched, duration):
    if not duration or duration <= 0:
        return 0.0
    return round(min(100.0, (watched / duration) * 100.0), 1)


def course_percent(db, user_id, course_id):
    """Overall % watched across every lesson of the course (time-weighted)."""
    rows = db.execute(
        """SELECT l.duration_seconds AS dur, COALESCE(p.watched_seconds, 0) AS watched
           FROM course_lessons l
           LEFT JOIN lesson_progress p ON p.lesson_id = l.id AND p.user_id = ?
           WHERE l.course_id = ?""",
        (user_id, course_id),
    ).fetchall()
    total = sum(r["dur"] for r in rows if r["dur"] and r["dur"] > 0)
    if total <= 0:
        return 0.0
    got = sum(min(r["watched"], r["dur"]) for r in rows if r["dur"] and r["dur"] > 0)
    return round(min(100.0, got / total * 100.0), 1)


def record_lesson_progress(db, user_id, lesson, position, duration=None, ended=False):
    """
    Store progress for one lesson and return (watched_seconds, last_position).
    `position` is where the player currently is. The furthest-watched mark only
    advances as fast as real time allows, so seeking to the end or replaying API
    calls can't fake a completion.
    """
    dur = float(lesson["duration_seconds"] or 0)
    if dur <= 0 and duration and duration > 0:
        dur = float(duration)
        db.execute("UPDATE course_lessons SET duration_seconds = ? WHERE id = ?", (dur, lesson["id"]))
    if dur <= 0:
        return 0.0, 0.0

    pos = dur if ended else max(0.0, min(float(position), dur))
    now = time.time()
    row = db.execute(
        "SELECT watched_seconds, updated_ts FROM lesson_progress WHERE user_id = ? AND lesson_id = ?",
        (user_id, lesson["id"]),
    ).fetchone()

    prev = row["watched_seconds"] if row else 0.0
    if row and row["updated_ts"]:
        elapsed = min(max(0.0, now - row["updated_ts"]), MAX_GAP_CREDIT_SECONDS)
        allowed = prev + elapsed * MAX_PLAYBACK_RATE
    else:
        allowed = prev + FIRST_REPORT_ALLOWANCE

    watched = max(prev, min(pos, allowed, dur))
    last_pos = min(pos, watched)
    if watched >= dur * 0.995:        # finished: next visit starts from the top
        last_pos = 0.0

    if row:
        db.execute(
            """UPDATE lesson_progress SET watched_seconds = ?, last_position = ?, updated_ts = ?
               WHERE user_id = ? AND lesson_id = ?""",
            (watched, last_pos, now, user_id, lesson["id"]),
        )
    else:
        db.execute(
            """INSERT INTO lesson_progress (user_id, lesson_id, watched_seconds, last_position, updated_ts)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, lesson["id"], watched, last_pos, now),
        )
    return watched, last_pos


# ------------------------------------------------------------ career impact ---

def _career_scores(db, user_id):
    """{career title: match_score} for the user's *current* skills, plus the full rows."""
    from ml.recommend import recommend_careers
    from streams import categories_for_stream

    skills = {
        r["skill_name"]: r["proficiency"]
        for r in db.execute("SELECT skill_name, proficiency FROM user_skills WHERE user_id = ?", (user_id,))
    }
    careers = [dict(r) for r in db.execute("SELECT * FROM careers").fetchall()]
    stream_row = db.execute("SELECT stream FROM users WHERE id = ?", (user_id,)).fetchone()
    cats = categories_for_stream(stream_row["stream"] if stream_row else None)
    if not skills or not careers:
        return {}
    ranked = recommend_careers(skills, careers, top_n=len(careers), stream_categories=cats)
    return {c["title"]: c["match_score"] for c in ranked}


def career_snapshot(db, user_id):
    try:
        return _career_scores(db, user_id)
    except Exception:
        return {}


def career_impact(before, after, top_n=3):
    """Careers whose match score went UP because of the newly earned skill (biggest gain first)."""
    moved = [
        {"title": t, "match_score": s, "change": s - before.get(t, 0)}
        for t, s in after.items()
        if s - before.get(t, 0) > 0
    ]
    moved.sort(key=lambda x: (x["change"], x["match_score"]), reverse=True)
    return moved[:top_n]


# ---------------------------------------------------------------- completion ---

def award_skill(db, user_id, course_id):
    """Add (or raise) the course's skill on the user's profile. Returns its name."""
    course = db.execute("SELECT skill_tag, level FROM courses WHERE id = ?", (course_id,)).fetchone()
    if not course or not (course["skill_tag"] or "").strip():
        return None
    skill = course["skill_tag"].strip()
    # use the master list's spelling ("Machine Learning" -> "Machine learning") so the
    # skill matches careers' required_skills exactly
    canon = db.execute("SELECT skill_name FROM skills_master WHERE LOWER(skill_name) = LOWER(?)", (skill,)).fetchone()
    if canon:
        skill = canon["skill_name"]
    target = LEVEL_PROFICIENCY.get(course["level"], DEFAULT_PROFICIENCY)

    # make sure the skill exists in the master list so the Profile page categorises it
    db.execute("INSERT OR IGNORE INTO skills_master (skill_name, category) VALUES (?, 'technical')", (skill,))

    existing = db.execute(
        "SELECT id, proficiency FROM user_skills WHERE user_id = ? AND skill_name = ?",
        (user_id, skill),
    ).fetchone()
    if existing:
        if existing["proficiency"] < target:
            db.execute(
                "UPDATE user_skills SET proficiency = ?, source = 'course', course_id = ?, verified = 1 WHERE id = ?",
                (target, course_id, existing["id"]),
            )
    else:
        db.execute(
            "INSERT INTO user_skills (user_id, skill_name, proficiency, source, course_id, verified) VALUES (?, ?, ?, 'course', ?, 1)",
            (user_id, skill, target, course_id),
        )
    return skill


def sync_course(db, user_id, course_id):
    """
    Recompute overall % for the course and store it on user_courses. The first time it
    crosses the threshold the course becomes 'watched', which unlocks the assessment.
    (The skill is NOT awarded here - see award_after_assessment.)
    """
    percent = course_percent(db, user_id, course_id)
    row = db.execute(
        "SELECT status, watch_percent FROM user_courses WHERE user_id = ? AND course_id = ?",
        (user_id, course_id),
    ).fetchone()
    if not row:
        db.execute(
            "INSERT INTO user_courses (user_id, course_id, status, watch_percent) VALUES (?, ?, 'in_progress', 0)",
            (user_id, course_id),
        )
        status, best = "in_progress", 0.0
    else:
        status, best = row["status"], row["watch_percent"] or 0.0

    best = max(best, percent)
    result = {"watch_percent": round(best, 1), "status": status, "newly_watched": False}

    if status == "in_progress" and best >= COMPLETION_THRESHOLD:
        status = "watched"
        result.update(status="watched", newly_watched=True)
    db.execute(
        "UPDATE user_courses SET watch_percent = ?, status = ? WHERE user_id = ? AND course_id = ?",
        (best, status, user_id, course_id),
    )
    return result


def award_after_assessment(db, user_id, course_id):
    """Called when the student passes the assessment: complete the course, add the skill."""
    before = career_snapshot(db, user_id)
    skill = award_skill(db, user_id, course_id)
    db.execute(
        """UPDATE user_courses SET status = 'completed', completed_at = CURRENT_TIMESTAMP
           WHERE user_id = ? AND course_id = ?""",
        (user_id, course_id),
    )
    after = career_snapshot(db, user_id)
    return skill, (career_impact(before, after) if after else [])