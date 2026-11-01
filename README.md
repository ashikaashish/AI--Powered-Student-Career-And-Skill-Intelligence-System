## UI refresh (this version)

The frontend has been re-skinned to match the look and feel of the
`ai-career-intelligence-system` reference build: a dark-navy branded sidebar,
brand-blue accent colors, rounded-3xl cards, a gradient "Recommended Next
Step" banner on the dashboard, a recharts donut for the skill-gap overview,
and a two-panel branded Login/Signup screen. This is a **visual-only**
change — the Flask backend, database schema, ML pipeline, API routes, and
all real datasets (job postings, aptitude professions, skills taxonomy) are
untouched. The old build's "Download Project ZIP" / "Export ZIP" links have
intentionally **not** been carried over, since they aren't something an
end user needs — this project doesn't have (or need) one.

---

## Learning with in-platform videos (new)

Courses are now watched **inside CareerAI** - nothing is embedded from or sent to YouTube.

**Learner flow**
1. *Learning* page -> **Enroll** on a course that has videos -> the lesson player opens.
2. The video streams from the Flask server (`GET /api/learn/lessons/<id>/stream`, HTTP Range/seek supported).
3. The player reports its position every few seconds; the **server** keeps the watched-% per lesson and for the whole course (time-weighted). Closing the tab and coming back resumes where you left off.
4. At **90%** of the course (`COMPLETION_THRESHOLD` in `services/learning.py`) the course is marked **Completed** automatically and its skill is **added to the profile** (shown with an "Earned from course" badge; it can't be deleted by a later profile save).
5. **AI Career Recommendations** are computed from the profile skills, so the new skill immediately changes the matches. The completion card shows which careers moved up, and the recommendations page lists "skills you have" / "still to learn" per career.

Skipping ahead is blocked in the player, and the server only credits as much watch time as real time allows, so jumping to the end (or calling the API directly) doesn't complete a course.

**Admin flow** - log in as admin -> *Courses & Skills* -> add a course (pick the skill it teaches) -> **Manage videos** -> upload `.mp4` lessons. Upload only videos you own or are licensed to host.

**Sample videos** - the project ships two short placeholder clips (`backend/uploads/videos/sample_lesson_*.mp4`). On first start they are attached to every course that has no lessons, so all courses are playable immediately (set `AUTO_SEED_DEMO_VIDEOS=0` in `backend/.env` to turn this off, or run `python seed_demo_videos.py` manually). Replace them with real lessons via the admin page.

Existing databases are upgraded automatically on startup (`database/migrate.py`); re-running `init_db.py` is not required.

---

# CareerAI — AI-Powered Career Guidance Platform

A full-stack web application that gives students AI-driven career recommendations,
skill-gap analysis, personalized course suggestions, and more — plus an admin panel to manage the platform.

This matches the 13-page product design (Login/Signup, Student Profile, Dashboard,
AI Career Recommendations, Skill Gap Analysis, Learning/Course Recommendations,
Job Role Explorer, AI Career Assistant chatbot, Progress Tracking,
and the Admin Dashboard / Manage Students / Manage Courses pages).

## Tech Stack

| Part                      | Technology                                  |
| -------------------------- | -------------------------------------------- |
| Frontend / UI              | React.js (Vite) + Tailwind CSS               |
| Backend                    | Python + Flask                               |
| Machine Learning           | Python, Scikit-learn                         |
| Recommendation System      | Cosine Similarity / Content-Based Filtering  |
| Career Prediction          | Random Forest Classifier                     |
| Skill Gap Analysis         | NLP + fuzzy similarity matching              |
| NLP                        | NLTK                                         |
| Database                   | SQLite                                       |
| Data Processing            | Pandas, NumPy                                |
| Model Storage              | Joblib                                       |
| Auth                       | Flask-JWT-Extended, Werkzeug password hashing|

## Project Structure

```
career-ai-project/
├── backend/
│   ├── app.py                  # Flask app entry point
│   ├── requirements.txt
│   ├── database/
│   │   ├── schema.sql          # DB schema
│   │   ├── init_db.py          # Creates + seeds the SQLite DB
│   │   └── db.py                # DB connection helper
│   ├── data/                   # Seed datasets (careers, skills, courses)
│   ├── ml/
│   │   ├── train_model.py      # Trains the Random Forest career predictor
│   │   ├── recommend.py        # Cosine similarity + model-based recommender
│   │   ├── skill_gap.py        # NLP-based skill gap analysis
│   │   └── models/             # Saved .pkl models (generated)
│   └── routes/                 # Flask blueprints (auth, profile, recommend, ...)
└── frontend/
    ├── src/
    │   ├── pages/               # One component per page in the product design
    │   ├── components/          # Sidebar, Layout, ProtectedRoute
    │   ├── context/AuthContext.jsx
    │   └── api/client.js        # Axios instance with JWT auth
    └── ...vite/tailwind config
```

## Getting Started

### 1. Backend setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Initialize the database (creates career_ai.db with seed data + demo accounts)
python database/init_db.py

# Train the ML career-prediction model
python ml/train_model.py

# Run the API server
python app.py
```

The API will be running at `http://localhost:5000`.

**Demo accounts** (created by `init_db.py`):
- Student: `ananya@gmail.com` / `password123`
- Admin: `admin@careerai.com` / `admin123`

### 2. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The app will be running at `http://localhost:5173`.

The frontend reads the API URL from `frontend/.env` (`VITE_API_URL`), which
defaults to `http://localhost:5000/api`.

### 3. Build for production

```bash
cd frontend
npm run build   # outputs static files to frontend/dist
```

Serve `frontend/dist` with any static file host, and run the Flask backend
behind a production WSGI server (e.g. gunicorn) for deployment.

## How the ML pieces work

- **Career Prediction (Random Forest)**: `ml/train_model.py` builds a synthetic
  training set from each career's required-skills profile (high proficiency in
  required skills + noise, low proficiency elsewhere), trains a
  `RandomForestClassifier`, and saves it with `joblib`. At inference time the
  model outputs a probability for each career given a student's skill vector.
- **Recommendation Engine (Cosine Similarity)**: `ml/recommend.py` builds a
  skill-proficiency vector for the student and for each career's required
  skills, then computes cosine similarity between them. The final match score
  blends this similarity score with the Random Forest's predicted probability.
- **Skill Gap Analysis (NLP)**: `ml/skill_gap.py` normalizes skill names
  (lowercasing, synonym expansion like "ML" → "Machine Learning", and NLTK
  lemmatization), then uses fuzzy string similarity to match a student's
  existing skills against a career's required skills — even when the phrasing
  differs slightly. It reports matched / partially-matched / missing skills
  and an overall readiness percentage.

## API Overview

All endpoints are prefixed with `/api`. Authenticated endpoints require an
`Authorization: Bearer <token>` header (token returned by login/signup).

| Endpoint                          | Method | Description                          |
| ---------------------------------- | ------ | ------------------------------------- |
| `/auth/signup`, `/auth/login`      | POST   | Create account / log in               |
| `/profile/me`                      | GET/PUT| View / update profile                 |
| `/profile/skills`                  | PUT    | Replace student's skill list          |
| `/recommend`                       | GET    | Top career recommendations            |
| `/recommend/dashboard-summary`     | GET    | Stats for the Dashboard page          |
| `/skills/gap?career=...`           | GET    | Skill gap analysis for a career       |
| `/courses`, `/courses/recommended` | GET    | Browse / get recommended courses      |
| `/chatbot/message`                 | POST   | Send a message to the AI assistant    |
| `/jobs`, `/jobs/<title>`           | GET    | Explore job roles                     |
| `/progress`                        | GET    | Learning/career progress stats        |
| `/admin/*`                         | GET/POST/DELETE | Admin-only management routes |

## Notes

- The database (`career_ai.db`) and trained model (`.pkl` files) are **not**
  included in this zip — run `init_db.py` and `train_model.py` once to
  generate them locally.
- This is a learning/demo project: the JWT secret, CORS policy, and Flask
  dev server are configured for local development. Harden these before any
  production deployment (proper secret management, restricted CORS origins,
  a production WSGI server, HTTPS, etc).

## Real-data update (real job postings, resumes, aptitude quiz)

This version replaces the original toy CSVs with real datasets and adds two
new features. What changed:

**Data pipeline** (`backend/data_pipeline/`) — run once, or re-run any time
you want to regenerate the derived data from the raw sources:
- `load_jobs.py` — turns `backend/data/raw/all_job_post.csv` (1,167 real
  postings across IT/Finance/Sales/HR/Business-Dev) into `careers.csv`
  (40 career families) and `skills.csv` (~1,400-skill taxonomy), by
  collapsing near-duplicate titles and ranking each family's most common
  required skills.
- There's no `load_resumes.py` step — resume parsing happens live per-upload
  via `ml/resume_parser.py`, matched against the skill taxonomy above.

**New ML modules** (`backend/ml/`):
- `train_model.py` now trains the Random Forest on **real posting skill
  combinations** (521 rows) blended with lighter synthetic augmentation,
  instead of purely synthetic data — accuracy on held-out data: ~90%.
- `resume_parser.py` — extracts skills from resume text (.pdf/.docx/.txt or
  pasted text) via taxonomy-matching, with mention-frequency-based
  proficiency scoring.
- `aptitude_test.py` — the Aptitude & Interest test: 20 scored ability
  questions (numerical, verbal, logical, spatial) + 24 Holland/RIASEC
  interest ratings. Scores are matched against a requirement profile for
  every career in the `careers` table and returned as ranked career
  recommendations with reasons.

**New API routes**:
- `POST /api/profile/resume-upload` — parses a resume and returns
  extracted skills for review (does not save automatically; follow up with
  `PUT /api/profile/skills` to persist the ones the user confirms).
- `GET /api/aptitude/questions`, `POST /api/aptitude/submit`,
  `GET /api/aptitude/history` — the aptitude & interest test (answer key stays
  on the server) and its saved attempts.

**New frontend**:
- A "Import skills from resume" panel on the Profile page (upload or paste,
  review extracted skills, add selected ones).
- A new **Aptitude Test** page (sidebar → Aptitude Test) — a one-question-at-a-time
  test (ability + interests) that ends with ability scores, an interest radar,
  best-fit fields and recommended careers, each linking to its
  Skill Gap. Useful for someone who isn't sure what to put on their skill profile yet.
- Job Explorer now filters by the 5 real categories and hides the salary
  figure where the source data doesn't provide one (rather than showing a
  fabricated number).

**Setup, in order:**
```bash
cd backend
pip install -r requirements.txt
python data_pipeline/load_jobs.py        # regenerate careers.csv / skills.csv (already generated in this zip)
python database/init_db.py               # build career_ai.db, seeds real data + demo users
python ml/train_model.py                 # trains career_predictor.pkl on real + synthetic data
python app.py                            # http://localhost:5000
```
```bash
cd frontend
npm install
npm run dev                              # http://localhost:5173
```

**One thing left out of this zip:** the raw resume dataset
(`Resume_dataset.csv`, ~100MB, 9,000 resumes) was too large to bundle and
isn't needed at runtime — the resume parser matches live uploads against the
skill taxonomy, it doesn't need the training resumes themselves. If you want
to use it to build a stronger resume→role classifier later, drop it into
`backend/data/raw/Resume_dataset.csv` and extend the pipeline.


---

## Learning: self-hosted course videos (new)

Videos now play **inside CareerAI** from your own server — no YouTube player, no redirect.

**Student flow**
1. *Learning* → **Enroll** → opens the course page (`/courses/:id`) with the player and lesson list.
2. Progress is saved every ~5 s and on pause/leave; coming back **resumes** where you stopped.
3. Learners can rewind freely but **cannot skip ahead** of what they've actually watched.
4. At **90 %** of the course's total video time the course is marked **Completed** automatically, the course's skill is **added to the user's profile** (tagged "Course"), and a card shows which careers moved up.
5. **AI Careers** is ranked from the skills on the profile, and each card shows *your matching skills* and *learn next* (links to courses for that skill).

**Admin flow** — *Courses & Skills* → create a course (set the **skill it teaches**) → **Videos** → upload `.mp4` (H.264 + AAC recommended), `.webm`, `.m4v` or `.mov`. A course can have many videos; they play in upload order. Files are stored in `backend/uploads/videos/`.

**Try it without uploading anything** (needs `ffmpeg`): `python seed_demo_videos.py` adds short placeholder clips to 3 courses.

**How it's built**

| Piece | Where |
|---|---|
| Lesson + per-user watch tables | `database/schema.sql` (auto-applied to existing DBs by `database/migrate.py` on startup) |
| Progress maths, anti-skip, completion, skill award, career impact | `backend/services/learning.py` |
| Player API (`/api/learn/...`) incl. Range streaming | `backend/routes/learning.py` |
| Admin upload/delete | `backend/routes/admin.py` |
| Player page / course list / admin UI | `frontend/src/pages/CourseLearn.jsx`, `Courses.jsx`, `AdminCourses.jsx` |

**Technical careers added.** The original 40 careers (sales, HR, finance, IT support) required none of the skills the courses teach (Python, SQL, Java, ML…), so finishing a course could never change the AI Careers list. `data/careers_tech.csv` adds 12 technical careers (Data Analyst, Data Scientist, ML Engineer, Python/Java Developer, DevOps, Cloud, …) and `data/skills_extra.csv` adds the missing skills. They are in separate files so `load_jobs.py` can't overwrite them. If you edit careers, retrain with `python ml/train_model.py`. The `automation_risk` and `job_growth` values on these careers are estimates; salary is left blank — please review.

**Security notes**
- Streaming uses `?jwt=<token>` (a `<video>` tag can't send headers); only that one endpoint accepts it, and it checks enrolment.
- Anti-skip is deterrence, not DRM: the server only credits watch time as fast as real time allows (≤ 2.2×), so seeking to the end or scripting the API earns nothing. Anyone who can stream a file can still save it.
- The old `/courses/<id>/complete` and `/courses/<id>/progress` endpoints were **removed**: they let any logged-in student mark a course complete (and get the skill) without watching.
- Set a real `JWT_SECRET_KEY` in `backend/.env` for production. For many concurrent viewers, serve `uploads/videos` via nginx/S3/CDN instead of Flask.


## Learning flow (YouTube + assessment)

1. Each course is a **skill topic** (Python, SQL, Excel, Leadership, ...).
2. When a student enrolls, the backend searches YouTube for that topic and saves the best
   full-length tutorial(s) as the course lessons (`services/youtube_lessons.py`). No dummy videos.
3. Videos play inside CareerAI through the YouTube player. Progress is validated on the
   server; skipping ahead is blocked. Watching 90% unlocks the assessment.
4. The **assessment** (6 multiple-choice questions on the same topic, `data/assessments.json`)
   is graded on the server. Pass mark: 65% (4 of 6). Only then is the skill added to the
   student's profile. Failed attempts can be retaken.
5. Profile skills are shown as plain names (no rating sliders / percentages).

**Setup:** put a YouTube Data API v3 key in `backend/.env` as `YOUTUBE_API_KEY=...`
(free; see `backend/services/youtube_api.py`). Without a key, only courses that already have a
`video_id` in `data/courses.csv` can play.

To add a new topic: add a course (admin panel or `data/courses.csv`) and add its questions to
`data/assessments.json` under the same skill name, then restart the backend.
