-- CareerAI Database Schema

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'student',       -- student | admin
    education TEXT,
    stream TEXT,                       -- e.g. MCA, MBA, MA, BSC, LAW, MEDICAL...
    year TEXT,
    location TEXT,
    bio TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skills_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT UNIQUE NOT NULL,
    category TEXT               -- technical | soft
);

CREATE TABLE IF NOT EXISTS user_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    skill_name TEXT NOT NULL,
    proficiency INTEGER NOT NULL,   -- 0-100
    source TEXT DEFAULT 'manual',   -- manual | course (earned by finishing a course)
    course_id INTEGER,              -- the course that awarded it, when source = 'course'
    verified INTEGER DEFAULT 0,     -- 1 = proven by a skill test or course assessment
    verified_score INTEGER,         -- score % of the test that verified it
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS careers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT UNIQUE NOT NULL,
    description TEXT,
    required_skills TEXT NOT NULL,     -- comma separated
    avg_salary_lpa TEXT,
    job_growth TEXT,                   -- Low | Medium | High
    category TEXT,
    automation_risk INTEGER             -- 0-100, estimated % chance AI/automation
                                         -- significantly displaces this role's tasks
                                         -- in the foreseeable future
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    provider TEXT,
    level TEXT,                 -- Beginner | Intermediate | Advanced
    skill_tag TEXT,
    rating REAL,
    url TEXT,
    video_id TEXT                -- legacy (unused): lessons are now self-hosted in course_lessons
);

CREATE TABLE IF NOT EXISTS user_courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    status TEXT DEFAULT 'in_progress',   -- in_progress | watched (assessment pending) | completed (assessment passed)
    watch_percent REAL DEFAULT 0,        -- highest % of the video the user has watched (0-100)
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS aptitude_test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    abilities_json TEXT NOT NULL,     -- {numerical, verbal, logical, spatial}: 0-100
    interests_json TEXT NOT NULL,     -- {R, I, A, S, E, C}: 0-100
    interest_code TEXT,               -- e.g. "ICE"
    top_matches TEXT,                 -- JSON list of recommended roles
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    sender TEXT NOT NULL,     -- user | bot
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- A course (= one skill topic) has 1+ lessons; each lesson is a YouTube video found by
-- searching YouTube for the topic (see services/youtube_lessons.py).
CREATE TABLE IF NOT EXISTS course_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 1,
    filename TEXT NOT NULL DEFAULT '',   -- legacy self-hosted file (unused for YouTube lessons)
    youtube_id TEXT,                     -- YouTube video id fetched for the course topic
    channel_title TEXT,
    duration_seconds REAL NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

-- How much of each lesson a learner has genuinely watched (validated on the server).
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

-- Assessment questions per skill topic (seeded from data/assessments.json).
CREATE TABLE IF NOT EXISTS assessment_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_tag TEXT NOT NULL,
    question TEXT NOT NULL,
    options_json TEXT NOT NULL,          -- ["A","B","C","D"]
    answer TEXT NOT NULL,                -- must equal one of the options
    explanation TEXT
);

-- Every assessment attempt a student makes after watching a course.
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

-- A started skill test: remembers exactly which questions were served and when it expires.
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

-- Every submitted skill test.
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