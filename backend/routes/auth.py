from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from database.db import get_db
from streams import STREAMS

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    stream = (data.get("stream") or "").strip().upper() or None

    if not name or not email or not password:
        return jsonify({"error": "name, email and password are required"}), 400

    if stream and stream not in STREAMS:
        return jsonify({"error": "Unrecognized stream"}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        db.close()
        return jsonify({"error": "An account with this email already exists"}), 409

    password_hash = generate_password_hash(password)
    cur = db.execute(
        "INSERT INTO users (name, email, password_hash, role, stream) VALUES (?, ?, ?, 'student', ?)",
        (name, email, password_hash, stream),
    )
    db.commit()
    user_id = cur.lastrowid
    db.close()

    token = create_access_token(identity=str(user_id))
    return jsonify({
        "token": token,
        "user": {"id": user_id, "name": name, "email": email, "role": "student", "stream": stream},
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    db.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_access_token(identity=str(user["id"]))
    return jsonify({
        "token": token,
        "user": {
            "id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"],
            "stream": user["stream"] if "stream" in user.keys() else None,
        },
    }), 200
