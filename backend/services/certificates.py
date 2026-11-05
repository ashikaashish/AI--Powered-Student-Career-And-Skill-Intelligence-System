"""
E-certificates: issued when a student passes a course assessment.

  issue_certificate(db, user_id, course_id, score)  -> row   (idempotent: one per student per course)
  certificate_payload(row)                          -> dict  (everything the frontend needs to draw it)
  backfill_certificates(db, user_id)                -> issues certificates for courses completed
                                                       before this feature existed
"""
import secrets
from datetime import datetime


def _new_code(db):
    year = datetime.utcnow().year
    while True:
        code = f"CAI-{year}-{secrets.token_hex(4).upper()}"
        if not db.execute("SELECT 1 FROM certificates WHERE cert_code = ?", (code,)).fetchone():
            return code


def _fetch(db, user_id, course_id):
    return db.execute(
        """SELECT cert.id, cert.cert_code, cert.score_percent, cert.issued_at,
                  u.name AS student_name,
                  c.id AS course_id, c.title AS course_title, c.skill_tag, c.level, c.provider
           FROM certificates cert
           JOIN users u ON u.id = cert.user_id
           JOIN courses c ON c.id = cert.course_id
           WHERE cert.user_id = ? AND cert.course_id = ?""",
        (user_id, course_id),
    ).fetchone()


def issue_certificate(db, user_id, course_id, score_percent=None):
    """Create the certificate if the student doesn't have one yet; never creates duplicates."""
    row = _fetch(db, user_id, course_id)
    if row:
        # keep the best score on the certificate if they pass again with a higher mark
        if score_percent is not None and (row["score_percent"] or 0) < score_percent:
            db.execute("UPDATE certificates SET score_percent = ? WHERE user_id = ? AND course_id = ?",
                       (score_percent, user_id, course_id))
            row = _fetch(db, user_id, course_id)
        return row
    db.execute(
        "INSERT INTO certificates (cert_code, user_id, course_id, score_percent) VALUES (?, ?, ?, ?)",
        (_new_code(db), user_id, course_id, score_percent),
    )
    return _fetch(db, user_id, course_id)


def certificate_payload(row):
    d = dict(row)
    d["issued_at"] = str(d["issued_at"]) if d.get("issued_at") else None
    return d


def backfill_certificates(db, user_id):
    """Courses finished before certificates existed get one too (dated from the completion time)."""
    missing = db.execute(
        """SELECT uc.course_id, uc.completed_at,
                  (SELECT MAX(score_percent) FROM assessment_attempts a
                    WHERE a.user_id = uc.user_id AND a.course_id = uc.course_id AND a.passed = 1) AS best
           FROM user_courses uc
           WHERE uc.user_id = ? AND uc.status = 'completed'
             AND NOT EXISTS (SELECT 1 FROM certificates x WHERE x.user_id = uc.user_id AND x.course_id = uc.course_id)""",
        (user_id,),
    ).fetchall()
    for m in missing:
        issue_certificate(db, user_id, m["course_id"], m["best"])
        if m["completed_at"]:
            db.execute("UPDATE certificates SET issued_at = ? WHERE user_id = ? AND course_id = ?",
                       (m["completed_at"], user_id, m["course_id"]))
    return len(missing)