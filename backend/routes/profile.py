import io
import os
import threading
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db import get_db
from ml.resume_parser import (
    ALLOWED_RESUME_EXTENSIONS,
    assess_ats_friendliness,
    extract_skills,
    guess_job_title,
)
from streams import STREAMS, stream_options
from services.test_generator import MIN_BANK, TestGenerationError, ensure_bank

profile_bp = Blueprint("profile", __name__)


def _master_skills(db):
    """lower-case name -> canonical name. Only skills in skills_master can be on a profile,
    because every one of them has a test (see routes/skill_test.py)."""
    return {r["skill_name"].lower(): r["skill_name"]
            for r in db.execute("SELECT skill_name FROM skills_master")}


def _question_counts(db):
    """lower-case skill name -> number of test questions stored for it."""
    return {r["skill_tag"].lower(): r["n"]
            for r in db.execute(
                "SELECT skill_tag, COUNT(*) AS n FROM assessment_questions GROUP BY skill_tag")}


_preparing = set()                 # skills whose test questions are being generated right now
_preparing_lock = threading.Lock()


def _prepare_tests_async(app, skills):
    """
    Make sure every skill on a profile has its test questions. Skills that already have a bank
    are skipped; the rest are generated in a background thread (one API call each), so saving a
    profile never waits on the API. Safe to call repeatedly.
    """
    with _preparing_lock:
        todo = [s for s in skills if s.lower() not in _preparing]
        _preparing.update(s.lower() for s in todo)
    if not todo:
        return

    def work():
        for name in todo:
            conn = get_db()
            try:
                cat = conn.execute(
                    "SELECT category FROM skills_master WHERE LOWER(skill_name) = LOWER(?)", (name,)
                ).fetchone()
                ensure_bank(conn, name, (cat["category"] if cat else None) or "technical")
            except TestGenerationError as exc:
                app.logger.warning("Could not prepare test for %r: %s", name, exc)
            except Exception:
                app.logger.exception("Unexpected error preparing test for %r", name)
            finally:
                conn.close()
                with _preparing_lock:
                    _preparing.discard(name.lower())

    threading.Thread(target=work, daemon=True).start()


def _count_pdf_images(page):
    count = 0
    try:
        resources = page.get("/Resources")
        if not resources:
            return 0
        resources = resources.get_object()
        xobject = resources.get("/XObject")
        if not xobject:
            return 0
        xobject = xobject.get_object()
        for name in xobject:
            obj = xobject[name]
            if hasattr(obj, "get_object"):
                obj = obj.get_object()
            if obj.get("/Subtype") == "/Image":
                count += 1
    except Exception:
        return 0
    return count


def _docx_layout_meta(document):
    from docx.oxml.ns import qn

    table_count = len(document.tables)
    body = document.element.body
    textbox_count = len(body.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}txbxContent"))
    column_count = 1
    sect_pr = body.find(qn("w:sectPr"))
    if sect_pr is not None:
        cols = sect_pr.find(qn("w:cols"))
        if cols is not None:
            try:
                column_count = int(cols.get(qn("w:num")) or 1)
            except (TypeError, ValueError):
                column_count = 1
    return table_count, textbox_count, column_count


def _extract_text_from_upload(file_storage):
    filename = (file_storage.filename or "").lower()
    raw = file_storage.read()
    ext = os.path.splitext(filename)[1]
    meta = {
        "filename": filename,
        "file_type": ext,
        "page_count": 1,
        "image_count": 0,
        "table_count": 0,
        "textbox_count": 0,
        "column_count": 1,
        "unsupported": ext not in ALLOWED_RESUME_EXTENSIONS,
    }

    if meta["unsupported"]:
        return "", meta

    if filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            meta["page_count"] = max(len(reader.pages), 1)
            meta["image_count"] = sum(_count_pdf_images(page) for page in reader.pages)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text, meta
        except Exception:
            return raw.decode("utf-8", errors="ignore"), meta

    if filename.endswith(".docx"):
        try:
            import docx
            document = docx.Document(io.BytesIO(raw))
            tables, textboxes, columns = _docx_layout_meta(document)
            meta["table_count"] = tables
            meta["textbox_count"] = textboxes
            meta["column_count"] = columns
            return "\n".join(p.text for p in document.paragraphs), meta
        except Exception:
            return raw.decode("utf-8", errors="ignore"), meta

    return raw.decode("utf-8", errors="ignore"), meta


@profile_bp.route("/me", methods=["GET"])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    db = get_db()
    user = db.execute(
        "SELECT id, name, email, education, stream, year, location, bio, avatar_url, role "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not user:
        db.close()
        return jsonify({"error": "User not found"}), 404

    skills = db.execute(
        """SELECT us.skill_name, us.proficiency, COALESCE(us.source, 'manual') AS source,
                  us.course_id, c.title AS course_title,
                  COALESCE(us.verified, 0) AS verified, us.verified_score
           FROM user_skills us LEFT JOIN courses c ON c.id = us.course_id
           WHERE us.user_id = ?""",
        (user_id,),
    ).fetchall()
    counts = _question_counts(db)
    db.close()

    out = []
    for s in skills:
        d = dict(s)
        # every profile skill is a master-list skill, so it always has a test; question_count is
        # how many questions are already stored (0 = the bank is generated on the first attempt)
        d["has_test"] = True
        d["question_count"] = counts.get(d["skill_name"].lower(), 0)
        d["test_ready"] = d["question_count"] >= MIN_BANK
        out.append(d)

    # any skill on this profile without questions gets them prepared in the background
    _prepare_tests_async(current_app._get_current_object(),
                         [d["skill_name"] for d in out if not d["test_ready"]])

    return jsonify({
        "user": dict(user),
        "skills": out,
    })


@profile_bp.route("/me", methods=["PUT"])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    data = request.get_json(force=True)

    fields = ["name", "education", "stream", "year", "location", "bio", "avatar_url"]
    updates = {k: data[k] for k in fields if k in data}

    if "stream" in updates:
        stream = (updates["stream"] or "").strip().upper() or None
        if stream and stream not in STREAMS:
            return jsonify({"error": "Unrecognized stream"}), 400
        updates["stream"] = stream

    if updates:
        db = get_db()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        db.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?",
            (*updates.values(), user_id),
        )
        db.commit()
        db.close()

    return jsonify({"message": "Profile updated successfully"})


@profile_bp.route("/skills", methods=["PUT"])
@jwt_required()
def update_skills():
    """
    Body: { "skills": [{"skill_name": "Python", "proficiency": 60}, ...] }

    Every skill must be in skills_master, because that is what guarantees it has a test. Names are
    normalised to the master list's spelling; anything else is skipped and listed in "rejected".

    Students can add and remove skills freely. A skill added this way is saved as
    "manual" and NOT verified. It becomes verified (badge + score) only after the student
    passes its test via POST /api/skill-test/submit.

    What this endpoint will never do:
      - un-verify a skill that was proven by a test (source/verified/verified_score are kept)
      - remove a skill earned by passing a course assessment (source = 'course')
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    skills_in = data.get("skills")
    if not isinstance(skills_in, list):
        return jsonify({"error": "'skills' must be a list"}), 400

    db = get_db()
    master = _master_skills(db)

    incoming = {}   # lower-case name -> (canonical name, proficiency)
    rejected = []
    for s in skills_in:
        if not isinstance(s, dict):
            continue
        raw_name = (s.get("skill_name") or "").strip()
        if not raw_name:
            continue
        name = master.get(raw_name.lower())
        if not name:
            rejected.append(raw_name)       # not in the skill list -> no test -> not allowed
            continue
        if name.lower() in incoming:
            continue
        raw_prof = s.get("proficiency")
        try:
            prof = max(0, min(100, int(raw_prof))) if raw_prof is not None else 60
        except (TypeError, ValueError):
            prof = 60
        incoming[name.lower()] = (name, prof)

    rows = db.execute(
        "SELECT id, skill_name, source, COALESCE(verified, 0) AS verified "
        "FROM user_skills WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    existing = {r["skill_name"].lower(): r for r in rows}

    # 1) remove skills the student dropped (course-earned skills are protected)
    for key, r in existing.items():
        if key not in incoming and r["source"] != "course":
            db.execute("DELETE FROM user_skills WHERE id = ?", (r["id"],))

    # 2) add new skills (unverified) / update proficiency of unverified manual ones
    for key, (name, prof) in incoming.items():
        r = existing.get(key)
        if r is None:
            db.execute(
                "INSERT INTO user_skills (user_id, skill_name, proficiency, source, verified) "
                "VALUES (?, ?, ?, 'manual', 0)",
                (user_id, name, prof),
            )
        elif not r["verified"] and r["source"] != "course":
            db.execute("UPDATE user_skills SET proficiency = ? WHERE id = ?", (prof, r["id"]))
        # verified / course skills keep their earned score untouched

    db.commit()
    counts = _question_counts(db)
    db.close()

    # newly added skills get their test questions prepared right away (in the background)
    _prepare_tests_async(current_app._get_current_object(),
                         [name for key, (name, _p) in incoming.items() if counts.get(key, 0) < MIN_BANK])

    resp = {"message": "Skills updated successfully"}
    if rejected:
        resp["rejected"] = rejected
        resp["rejected_reason"] = "Not in the skill list, so they have no test and were not added."
    return jsonify(resp)


@profile_bp.route("/streams", methods=["GET"])
def get_streams():
    """List of {value, label} educational streams for the signup/profile dropdown."""
    return jsonify(stream_options())


@profile_bp.route("/skills/master", methods=["GET"])
def get_master_skills():
    db = get_db()
    rows = db.execute("SELECT skill_name, category FROM skills_master ORDER BY skill_name").fetchall()
    counts = _question_counts(db)
    db.close()
    out = []
    for r in rows:
        d = dict(r)
        d["has_test"] = True
        d["question_count"] = counts.get(d["skill_name"].lower(), 0)
        out.append(d)
    return jsonify(out)


@profile_bp.route("/resume-upload", methods=["POST"])
@jwt_required()
def resume_upload():
    """
    Accepts either a file upload (multipart form field "resume", .pdf/.docx/.txt)
    or raw pasted text (JSON body {"text": "..."}).

    Only ATS-friendly resumes are parsed. Designed, scanned, or graphic
    resumes are rejected with issues/tips. Extracted skills are returned for
    review and are not saved automatically.
    """
    meta = {}
    if "resume" in request.files:
        uploaded = request.files["resume"]
        filename = (uploaded.filename or "").lower()
        ext = os.path.splitext(filename)[1]
        if ext not in ALLOWED_RESUME_EXTENSIONS:
            return jsonify({
                "error": "Only ATS-friendly resumes are accepted (.pdf, .docx, or .txt). Image files and designed templates cannot be parsed.",
                "ats_friendly": False,
                "ats_score": 0,
                "issues": ["Unsupported file type."],
                "tips": ["Export a simple single-column resume as .pdf or .docx from Word or Google Docs."],
            }), 400
        text, meta = _extract_text_from_upload(uploaded)
    else:
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        meta = {"file_type": ".txt"}

    if not text or not text.strip():
        return jsonify({
            "error": "No selectable text found. Upload an ATS-friendly .pdf, .docx, or .txt resume, not a scanned or image CV.",
            "ats_friendly": False,
            "ats_score": 0,
            "issues": ["The file had no extractable text."],
            "tips": ["Make sure you can highlight the text in the PDF. If you cannot, it is an image resume and ATS cannot read it."],
        }), 400

    ats = assess_ats_friendliness(text, meta)
    if not ats["ats_friendly"]:
        return jsonify({
            "error": "This resume is not ATS-friendly, so skills were not extracted. Upload a plain text-based resume with standard headings.",
            "ats_friendly": False,
            "ats_score": ats["score"],
            "issues": ats["issues"],
            "tips": ats["tips"],
            "sections_found": ats["sections_found"],
            "word_count": ats["word_count"],
        }), 400

    db = get_db()
    master = _master_skills(db)
    counts = _question_counts(db)
    careers = db.execute("SELECT title, required_skills FROM careers").fetchall()
    db.close()

    # keep only skills that have a test, using the master list's spelling
    extracted = []
    for sk in extract_skills(text):
        name = master.get((sk.get("skill_name") or "").lower())
        if name:
            extracted.append({**sk, "skill_name": name,
                              "has_test": True, "question_count": counts.get(name.lower(), 0)})

    career_skill_map = {
        r["title"]: [x.strip() for x in (r["required_skills"] or "").split(",") if x.strip()]
        for r in careers
    }
    suggested_title = guess_job_title(text, career_skill_map)

    return jsonify({
        "extracted_skills": extracted,
        "suggested_career_family": suggested_title,
        "characters_parsed": len(text),
        "ats_friendly": True,
        "ats_score": ats["score"],
        "sections_found": ats["sections_found"],
    })