"""API tests using Flask's test client (no server needed)."""
import io, os, sqlite3, uuid
import pytest
from app import app

DB = os.path.join(os.path.dirname(__file__), "..", "database", "career_ai.db")


@pytest.fixture(scope="module")
def client():
    app.config["TESTING"] = True
    return app.test_client()

def _login(client, email, pw):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    return r

def _hdr(client, email="ananya@gmail.com", pw="password123"):
    return {"Authorization": "Bearer " + _login(client, email, pw).get_json()["token"]}

# ---------------- auth ----------------
def test_health(client):
    assert client.get("/api/health").status_code == 200

def test_login_success(client):
    r = _login(client, "ananya@gmail.com", "password123")
    assert r.status_code == 200 and "token" in r.get_json()

def test_login_wrong_password(client):
    assert _login(client, "ananya@gmail.com", "wrong").status_code == 401

def test_login_unknown_user(client):
    assert _login(client, "nobody@x.com", "x").status_code == 401

def test_signup_missing_fields(client):
    r = client.post("/api/auth/signup", json={"email": "a@b.com"})
    assert r.status_code == 400

def test_signup_duplicate_email(client):
    r = client.post("/api/auth/signup", json={"name": "A", "email": "ananya@gmail.com", "password": "abcdef"})
    assert r.status_code == 409

def test_signup_new_user_then_cleanup(client):
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/auth/signup", json={"name": "Test", "email": email, "password": "abcdef"})
    assert r.status_code == 201
    c = sqlite3.connect(DB); c.execute("DELETE FROM users WHERE email=?", (email,)); c.commit(); c.close()

# ---------------- protected routes ----------------
@pytest.mark.parametrize("path", ["/api/recommend", "/api/profile/me", "/api/progress",
                                  "/api/skills/gap?career=Data Analyst"])
def test_protected_routes_need_token(client, path):
    assert client.get(path).status_code == 401

def test_invalid_token_rejected(client):
    r = client.get("/api/recommend", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code in (401, 422)

# ---------------- profile & recommendations ----------------
def test_profile_me(client):
    r = client.get("/api/profile/me", headers=_hdr(client))
    assert r.status_code == 200

def test_recommend_returns_list(client):
    r = client.get("/api/recommend", headers=_hdr(client))
    assert r.status_code == 200 and "recommendations" in r.get_json()

def test_recommend_top_n_respected(client):
    r = client.get("/api/recommend?top_n=3", headers=_hdr(client))
    assert len(r.get_json()["recommendations"]) <= 3

def test_dashboard_summary(client):
    assert client.get("/api/recommend/dashboard-summary", headers=_hdr(client)).status_code == 200

def test_jobs_list(client):
    r = client.get("/api/jobs", headers=_hdr(client))
    assert r.status_code in (200,)

def test_courses_list(client):
    assert client.get("/api/courses", headers=_hdr(client)).status_code == 200

def test_chatbot_replies(client):
    r = client.post("/api/chatbot/message", json={"message": "hello"}, headers=_hdr(client))
    assert r.status_code == 200

# ---------------- aptitude ----------------
def test_aptitude_questions_hide_answers(client):
    r = client.get("/api/aptitude/questions", headers=_hdr(client))
    assert r.status_code == 200
    assert "answer" not in str(r.get_json()["ability"][0])

# ---------------- assessment integrity ----------------
def test_assessment_locked_until_course_watched(client):
    r = client.post("/api/assessment/1/start", headers=_hdr(client))
    assert r.status_code in (403, 404)

# ---------------- roles ----------------
def test_student_cannot_open_admin_dashboard(client):
    assert client.get("/api/admin/dashboard", headers=_hdr(client)).status_code == 403

def test_admin_can_open_admin_dashboard(client):
    h = _hdr(client, "admin@careerai.com", "admin123")
    assert client.get("/api/admin/dashboard", headers=h).status_code == 200

def test_admin_lists_students(client):
    h = _hdr(client, "admin@careerai.com", "admin123")
    assert client.get("/api/admin/students", headers=h).status_code == 200

# ---------------- input limits / errors ----------------
def test_unknown_route_returns_json_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.get_json()["error"]

def test_recommend_response_time_under_2s(client):
    import time
    h = _hdr(client); t = time.time()
    client.get("/api/recommend", headers=h)
    assert time.time() - t < 2.0
