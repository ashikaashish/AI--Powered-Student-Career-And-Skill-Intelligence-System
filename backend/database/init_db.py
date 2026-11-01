"""
Initializes the SQLite database for CareerAI.
Run with:  python database/init_db.py
"""
import sqlite3
import os
import csv
import sys

# allow `python database/init_db.py` to import the `database` package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "career_ai.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")
DATA_DIR = os.path.join(BASE_DIR, "data")


def init_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Removed existing database.")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        cur.executescript(f.read())
    print("Schema created.")

    # Seed skills_master
    with open(os.path.join(DATA_DIR, "skills.csv"), encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cur.execute(
                "INSERT OR IGNORE INTO skills_master (skill_name, category) VALUES (?, ?)",
                (row["skill_name"], row["category"]),
            )
    print("Skills seeded.")

    # Seed careers
    #
    # careers.csv comes in one of two shapes depending on which version of
    # data_pipeline/load_jobs.py generated it:
    #   - older shape: a single "avg_salary_lpa" column
    #   - current shape (real job-postings pipeline): "avg_salary_min_lpa",
    #     "avg_salary_max_lpa", "salary_data_available" (blank/False when the
    #     source postings didn't include a salary figure)
    # We normalize either shape down to the single avg_salary_lpa value the
    # rest of the app (routes, ML, frontend) expects, without touching the
    # CSV file itself.
    with open(os.path.join(DATA_DIR, "careers.csv"), encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "avg_salary_lpa" in row:
                avg_salary_lpa = row["avg_salary_lpa"] or None
            else:
                available = (row.get("salary_data_available", "") or "").strip().lower() == "true"
                salary_min = (row.get("avg_salary_min_lpa", "") or "").strip()
                salary_max = (row.get("avg_salary_max_lpa", "") or "").strip()
                if available and salary_min and salary_max:
                    avg_salary_lpa = salary_min if salary_min == salary_max else f"{salary_min}-{salary_max}"
                else:
                    avg_salary_lpa = None
            automation_risk = (row.get("automation_risk", "") or "").strip()
            cur.execute(
                """INSERT OR IGNORE INTO careers
                (title, description, required_skills, avg_salary_lpa, job_growth, category, automation_risk)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["title"],
                    row["description"],
                    row["required_skills"],
                    avg_salary_lpa,
                    row["job_growth"],
                    row["category"],
                    int(automation_risk) if automation_risk else None,
                ),
            )
    print("Careers seeded.")

    # Seed courses
    with open(os.path.join(DATA_DIR, "courses.csv"), encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cur.execute(
                """INSERT OR IGNORE INTO courses
                (title, provider, level, skill_tag, rating, url, video_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["title"],
                    row["provider"],
                    row["level"],
                    row["skill_tag"],
                    float(row["rating"]),
                    row["url"],
                    (row.get("video_id") or "").strip() or None,
                ),
            )
    print("Courses seeded.")

    # Technical careers + skills that match what the course catalog teaches
    from database.migrate import seed_extra_data, seed_assessments, VIDEO_DIR
    seed_extra_data(conn)
    seed_assessments(conn)
    print("Assessment questions seeded.")
    os.makedirs(VIDEO_DIR, exist_ok=True)
    print("Technical careers/skills seeded.")
    conn.commit()
    conn.close()
    # (YouTube lessons are fetched per course topic the first time it is opened)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Seed a demo admin + demo student so the app is usable immediately
    from werkzeug.security import generate_password_hash

    cur.execute(
        """INSERT OR IGNORE INTO users (name, email, password_hash, role, education, stream, year, location, bio)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "Admin User",
            "admin@careerai.com",
            generate_password_hash("admin123"),
            "admin",
            "N/A",
            None,
            "N/A",
            "N/A",
            "System administrator",
        ),
    )

    cur.execute(
        """INSERT OR IGNORE INTO users (name, email, password_hash, role, education, stream, year, location, bio)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "Ananya Sharma",
            "ananya@gmail.com",
            generate_password_hash("password123"),
            "student",
            "B.Tech Computer Science",
            "BTECH_CS_IT",
            "3rd Year",
            "Bangalore, India",
            "Aspiring IT professional building skills toward a support/ops role.",
        ),
    )
    conn.commit()

    demo_user_id = cur.execute(
        "SELECT id FROM users WHERE email = ?", ("ananya@gmail.com",)
    ).fetchone()[0]

    # Skills chosen to realistically overlap with the real job-posting-derived
    # career profiles (see backend/data/careers.csv), so the recommender/skill-gap
    # demo produces meaningful, non-flat scores out of the box.
    demo_skills = [
        ("Communication", 80),
        ("Problem Solving", 75),
        ("Teamwork", 80),
        ("Adaptability", 70),
        ("Troubleshooting", 60),
        ("Customer service", 55),
        ("Technical Support", 50),
        ("Time Management", 65),
        ("Collaboration", 70),
        ("Leadership", 45),
    ]
    for skill, prof in demo_skills:
        cur.execute(
            "INSERT INTO user_skills (user_id, skill_name, proficiency) VALUES (?, ?, ?)",
            (demo_user_id, skill, prof),
        )
    print("Demo users seeded (admin@careerai.com / admin123, ananya@gmail.com / password123).")

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_database()
