"""
Lightweight, idempotent migrations so an EXISTING career_ai.db picks up the
YouTube-lesson + assessment tables without having to re-run init_db.py (which wipes data).
Called once at app start-up.
"""
import csv
import json
import os
import sqlite3
from database.db import DB_PATH, BASE_DIR

VIDEO_DIR = os.path.join(BASE_DIR, "uploads", "videos")
DATA_DIR = os.path.join(BASE_DIR, "data")


def seed_extra_data(conn):
    """
    Add the technical careers + skills that match what the course catalog teaches
    (data/careers_tech.csv, data/skills_extra.csv). They live in their own files so
    regenerating careers.csv/skills.csv with data_pipeline/load_jobs.py can't wipe them.
    Safe to call repeatedly (INSERT OR IGNORE).
    """
    skills_path = os.path.join(DATA_DIR, "skills_extra.csv")
    if os.path.exists(skills_path):
        with open(skills_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                conn.execute(
                    "INSERT OR IGNORE INTO skills_master (skill_name, category) VALUES (?, ?)",
                    (row["skill_name"], row["category"]),
                )
    careers_path = os.path.join(DATA_DIR, "careers_tech.csv")
    if os.path.exists(careers_path):
        with open(careers_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                conn.execute(
                    """INSERT OR IGNORE INTO careers
                       (title, description, required_skills, avg_salary_lpa, job_growth, category, automation_risk)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (row["title"], row["description"], row["required_skills"],
                     row["avg_salary_lpa"] or None, row["job_growth"], row["category"],
                     int(row["automation_risk"]) if row["automation_risk"] else None),
                )


def _columns(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def seed_assessments(conn):
    """Load data/assessments.json into assessment_questions (only topics not loaded yet)."""
    path = os.path.join(DATA_DIR, "assessments.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        bank = json.load(f)
    for skill, qs in bank.items():
        if conn.execute("SELECT 1 FROM assessment_questions WHERE skill_tag = ? LIMIT 1", (skill,)).fetchone():
            continue
        for q in qs:
            conn.execute(
                "INSERT INTO assessment_questions (skill_tag, question, options_json, answer, explanation) VALUES (?,?,?,?,?)",
                (skill, q["question"], json.dumps(q["options"]), q["answer"], q.get("explanation")),
            )


def ensure_video_schema():
    os.makedirs(VIDEO_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH):
        return  # fresh install: init_db.py will create everything from schema.sql

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS course_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 1,
                filename TEXT NOT NULL DEFAULT '',
                youtube_id TEXT,
                channel_title TEXT,
                duration_seconds REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS lesson_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                lesson_id INTEGER NOT NULL,
                watched_seconds REAL NOT NULL DEFAULT 0,
                last_position REAL NOT NULL DEFAULT 0,
                updated_ts REAL NOT NULL DEFAULT 0,
                UNIQUE (user_id, lesson_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (lesson_id) REFERENCES course_lessons(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS assessment_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_tag TEXT NOT NULL,
                question TEXT NOT NULL,
                options_json TEXT NOT NULL,
                answer TEXT NOT NULL,
                explanation TEXT
            );
            CREATE TABLE IF NOT EXISTS skill_test_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                skill_name TEXT NOT NULL,
                question_ids_json TEXT NOT NULL,
                expires_at REAL NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS skill_test_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                skill_name TEXT NOT NULL,
                score_percent INTEGER NOT NULL,
                correct INTEGER NOT NULL,
                total INTEGER NOT NULL,
                passed INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS assessment_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                score_percent INTEGER NOT NULL,
                correct INTEGER NOT NULL,
                total INTEGER NOT NULL,
                passed INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
            );
            """
        )
        cols = _columns(conn, "user_skills")
        if "source" not in cols:
            conn.execute("ALTER TABLE user_skills ADD COLUMN source TEXT DEFAULT 'manual'")
        if "course_id" not in cols:
            conn.execute("ALTER TABLE user_skills ADD COLUMN course_id INTEGER")
        if "verified" not in cols:
            conn.execute("ALTER TABLE user_skills ADD COLUMN verified INTEGER DEFAULT 0")
        if "verified_score" not in cols:
            conn.execute("ALTER TABLE user_skills ADD COLUMN verified_score INTEGER")
        # skills earned through a course assessment were already proven by a test
        conn.execute("UPDATE user_skills SET verified = 1 WHERE source = 'course' AND COALESCE(verified, 0) = 0")
        lcols = _columns(conn, "course_lessons")
        if "youtube_id" not in lcols:
            conn.execute("ALTER TABLE course_lessons ADD COLUMN youtube_id TEXT")
        if "channel_title" not in lcols:
            conn.execute("ALTER TABLE course_lessons ADD COLUMN channel_title TEXT")

        # One-time cleanup of the old placeholder / self-hosted lessons (and the watch progress
        # made on them). Real YouTube lessons are fetched per topic when a course is opened.
        old = conn.execute("SELECT COUNT(*) FROM course_lessons WHERE youtube_id IS NULL OR youtube_id = ''").fetchone()[0]
        if old:
            conn.execute("DELETE FROM lesson_progress WHERE lesson_id IN "
                         "(SELECT id FROM course_lessons WHERE youtube_id IS NULL OR youtube_id = '')")
            conn.execute("DELETE FROM course_lessons WHERE youtube_id IS NULL OR youtube_id = ''")
            conn.execute("UPDATE user_courses SET watch_percent = 0 WHERE status = 'in_progress'")
        conn.execute("UPDATE courses SET provider = 'YouTube' "
                     "WHERE provider IN ('Coursera','Udemy','edX','DeepLearning.AI','CareerAI')")

        seed_extra_data(conn)
        seed_assessments(conn)
        conn.commit()
    finally:
        conn.close()