import os
from datetime import timedelta
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

load_dotenv()

from routes.auth import auth_bp
from routes.profile import profile_bp
from routes.recommend import recommend_bp
from routes.skills import skills_bp
from routes.courses import courses_bp
from routes.chatbot import chatbot_bp
from routes.admin import admin_bp
from routes.jobs import jobs_bp
from routes.progress import progress_bp
from routes.aptitude import aptitude_bp
from routes.learning import learning_bp
from routes.assessment import assessment_bp
from routes.skill_test import skill_test_bp
from database.migrate import ensure_video_schema


def create_app():
    ensure_video_schema()   # adds video tables/columns to an existing DB (safe to repeat)
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "change_this_secret_key_in_production")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=7)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024   # resumes etc.
    JWTManager(app)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(recommend_bp, url_prefix="/api/recommend")
    app.register_blueprint(skills_bp, url_prefix="/api/skills")
    app.register_blueprint(courses_bp, url_prefix="/api/courses")
    app.register_blueprint(chatbot_bp, url_prefix="/api/chatbot")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(jobs_bp, url_prefix="/api/jobs")
    app.register_blueprint(progress_bp, url_prefix="/api/progress")
    app.register_blueprint(aptitude_bp, url_prefix="/api/aptitude")
    app.register_blueprint(learning_bp, url_prefix="/api/learn")
    app.register_blueprint(assessment_bp, url_prefix="/api/assessment")
    app.register_blueprint(skill_test_bp, url_prefix="/api/skill-test")

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "CareerAI backend"})

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app


app = create_app()

# Load the Random Forest once at startup so the first recommendation is fast (SRS: < 2 s).
try:
    from ml.recommend import _load_model
    _load_model()
except Exception as _e:  # the app still works with cosine similarity alone
    print(f"[startup] Model preload skipped: {_e}")

if __name__ == "__main__":
    # use_reloader=False: the reloader's file-watcher was picking up writes to
    # database/career_ai.db (which lives inside this directory) and restarting
    # mid-request. debug stays on for error pages/tracebacks.
    app.run(debug=True, port=5000, use_reloader=False)