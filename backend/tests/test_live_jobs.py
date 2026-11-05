"""Live-jobs tests. Network calls are replaced with sample payloads."""
import pytest
from services import live_jobs as lj

SAMPLE = [
    {"id": "r-1", "title": "Senior Python Engineer", "company": "Acme Cloud", "location": "Worldwide",
     "remote": True, "url": "https://x/1", "posted": "2026-11-03", "salary": "", "tags": ["python", "aws"],
     "description": "Build data pipelines with Python, SQL and AWS.", "source": "Remotive"},
    {"id": "r-2", "title": "Sales Executive", "company": "Shopify Corp", "location": "Worldwide",
     "remote": True, "url": "https://x/2", "posted": "2026-11-02", "salary": "", "tags": [],
     "description": "Close deals.", "source": "Remotive"},
    {"id": "r-3", "title": "Data Engineer", "company": "US Only Inc", "location": "USA Only",
     "remote": True, "url": "https://x/3", "posted": "2026-11-04", "salary": "", "tags": ["sql"],
     "description": "SQL and Python.", "source": "Remotive"},
    {"id": "r-4", "title": "Data Engineer", "company": "Infosys", "location": "Mangaluru",
     "remote": False, "url": "https://x/4", "posted": "2026-11-04", "salary": "", "tags": [],
     "description": "Data Engineering with SQL on AWS.", "source": "Adzuna"},
    {"id": "r-5", "title": "Senior Python Engineer", "company": "acme cloud", "location": "Worldwide",
     "remote": True, "url": "https://x/5", "posted": "2026-11-01", "salary": "", "tags": ["python"],
     "description": "duplicate company+title test", "source": "Remotive"},
]
SKILLS = [("Python", 1.0), ("SQL", 0.8), ("AWS", 0.6)]


def test_pick_profile_skills_drops_soft_and_generic():
    rows = [
        {"skill_name": "Python", "proficiency": 80, "verified": 1, "category": "technical"},
        {"skill_name": "Leadership", "proficiency": 100, "verified": 1, "category": "soft"},
        {"skill_name": "Technology", "proficiency": 88, "verified": 1, "category": "technical"},
        {"skill_name": "SQL", "proficiency": 70, "verified": 0, "category": "technical"},
    ]
    assert [n for n, _ in lj.pick_profile_skills(rows)] == ["Python", "SQL"]


def test_match_ranks_by_skills_and_hides_unrelated():
    out = lj.match_jobs(SAMPLE, SKILLS)
    titles = [(j["company"], j["title"]) for j in out]
    assert ("Shopify Corp", "Sales Executive") not in titles          # no skill overlap
    assert out[0]["company"] in ("Acme Cloud", "Infosys")              # strongest matches first
    assert set(out[0]["matched_skills"]) >= {"Python", "SQL"} or set(out[0]["matched_skills"]) >= {"SQL", "AWS"}
    assert all("company" in j and j["url"] for j in out)
    assert len([j for j in out if j["company"].lower() == "acme cloud"]) == 1   # de-duplicated


def test_whole_word_matching():
    jobs = [dict(SAMPLE[0], id="x", title="Frontend Developer", tags=[], description="javascript only")]
    assert lj.match_jobs(jobs, [("Java", 1.0)]) == []                  # 'javascript' must not match 'Java'


def test_location_scope():
    us = SAMPLE[2]
    assert not lj._location_ok(us, "india")
    assert lj._location_ok(us, "all")
    assert lj._location_ok(SAMPLE[3], "india")                          # Adzuna on-site always ok


def test_endpoint_uses_profile_skills(monkeypatch):
    from app import app
    monkeypatch.setattr(lj, "_fetch_adzuna", lambda *a, **k: [SAMPLE[3]])
    monkeypatch.setattr(lj, "_fetch_remotive", lambda: [SAMPLE[0], SAMPLE[1], SAMPLE[2]])
    monkeypatch.setattr(lj, "_fetch_arbeitnow", lambda: [])
    c = app.test_client()
    tok = c.post("/api/auth/login", json={"email": "ananya@gmail.com", "password": "password123"}).get_json()["token"]
    r = c.get("/api/jobs/for-me", headers={"Authorization": "Bearer " + tok})
    assert r.status_code == 200
    data = r.get_json()
    assert "jobs" in data and "skills_used" in data
    assert "Leadership" not in data["skills_used"] and "Technology" not in data["skills_used"]
    assert c.get("/api/jobs/for-me").status_code in (401, 422)          # login required