"""
Course-completion e-certificates.

  GET /api/certificates                     all of the student's certificates (newest first)
  GET /api/certificates/<course_id>         one certificate (404 until the assessment is passed)
  GET /api/certificates/verify/<code>       PUBLIC - confirms a certificate id is genuine
"""
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.db import get_db
from services.certificates import backfill_certificates, certificate_payload, _fetch

certificates_bp = Blueprint("certificates", __name__)


@certificates_bp.route("", methods=["GET"])
@jwt_required()
def list_certificates():
    user_id = get_jwt_identity()
    db = get_db()
    if backfill_certificates(db, user_id):
        db.commit()
    rows = db.execute(
        """SELECT cert.cert_code, cert.score_percent, cert.issued_at,
                  u.name AS student_name,
                  c.id AS course_id, c.title AS course_title, c.skill_tag, c.level, c.provider
           FROM certificates cert
           JOIN users u ON u.id = cert.user_id
           JOIN courses c ON c.id = cert.course_id
           WHERE cert.user_id = ?
           ORDER BY cert.issued_at DESC, cert.id DESC""",
        (user_id,),
    ).fetchall()
    db.close()
    return jsonify({"certificates": [certificate_payload(r) for r in rows]})


@certificates_bp.route("/<int:course_id>", methods=["GET"])
@jwt_required()
def get_certificate(course_id):
    user_id = get_jwt_identity()
    db = get_db()
    row = _fetch(db, user_id, course_id)
    if not row and backfill_certificates(db, user_id):
        db.commit()
        row = _fetch(db, user_id, course_id)
    db.close()
    if not row:
        return jsonify({"error": "No certificate yet. Pass this course's assessment to earn it."}), 404
    return jsonify({"certificate": certificate_payload(row)})


@certificates_bp.route("/verify/<code>", methods=["GET"])
def verify_certificate(code):
    db = get_db()
    row = db.execute(
        """SELECT cert.cert_code, cert.score_percent, cert.issued_at,
                  u.name AS student_name, c.title AS course_title, c.skill_tag
           FROM certificates cert
           JOIN users u ON u.id = cert.user_id
           JOIN courses c ON c.id = cert.course_id
           WHERE cert.cert_code = ?""",
        (code.strip().upper(),),
    ).fetchone()
    db.close()
    if not row:
        return jsonify({"valid": False}), 404
    return jsonify({"valid": True, "certificate": certificate_payload(row)})