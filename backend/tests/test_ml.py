"""Unit tests for the ML / logic modules (no server needed)."""
import sqlite3, os
import pytest
from ml.skill_gap import analyze_skill_gap
from ml.recommend import recommend_careers, stream_only_suggestions
from ml.resume_parser import extract_skills
from ml.aptitude_test import get_questions, score_answers, holland_code
from ml.automation_risk import estimate_automation_risk
from ml.families import career_family
from services.learning import lesson_percent

DB = os.path.join(os.path.dirname(__file__), "..", "database", "career_ai.db")


@pytest.fixture(scope="module")
def careers():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute("SELECT * FROM careers")]
    c.close()
    return rows


# ---------------- skill gap ----------------
def test_gap_synonym_ml_matches_machine_learning():
    r = analyze_skill_gap({"ML": 70}, ["Machine Learning"])
    assert len(r["matched"]) == 1

def test_gap_missing_skill_is_100_percent():
    r = analyze_skill_gap({}, ["Python", "SQL"])
    assert r["overall_gap_percent"] == 100 and len(r["missing"]) == 2

def test_gap_low_proficiency_is_partial():
    r = analyze_skill_gap({"Python": 40}, ["Python"])
    assert len(r["partial"]) == 1 and len(r["matched"]) == 0

def test_gap_full_match_is_zero_percent():
    r = analyze_skill_gap({"Python": 90, "SQL": 80}, ["Python", "SQL"])
    assert r["overall_gap_percent"] == 0

def test_gap_threshold_boundary_60_is_matched():
    r = analyze_skill_gap({"Python": 60}, ["Python"])
    assert len(r["matched"]) == 1

# ---------------- recommender ----------------
def test_recommend_returns_five_sorted_scores(careers):
    r = recommend_careers({"Python": 80, "SQL": 70, "Statistics": 60}, careers, top_n=5)
    scores = [x["match_score"] for x in r]
    assert len(r) == 5 and scores == sorted(scores, reverse=True)

def test_recommend_scores_within_0_99(careers):
    r = recommend_careers({"Python": 100, "SQL": 100, "Excel": 100}, careers, top_n=10)
    assert all(0 <= x["match_score"] <= 99 for x in r)

def test_data_profile_gets_data_role(careers):
    r = recommend_careers({"Python": 80, "SQL": 70, "Statistics": 60, "Excel": 60,
                           "Machine Learning": 60}, careers, top_n=5)
    assert any("data" in x["title"].lower() for x in r)

def test_sales_profile_gets_sales_role(careers):
    r = recommend_careers({"Communication": 80, "Negotiation": 70, "Sales": 80}, careers, top_n=5)
    assert any("sales" in x["title"].lower() or "business development" in x["title"].lower() for x in r)

def test_stream_only_fallback(careers):
    cats = {c["category"] for c in careers}
    r = stream_only_suggestions(careers, [sorted(cats)[0]], top_n=5)
    assert 0 < len(r) <= 5 and all(x.get("stream_based") for x in r)

def test_career_family_merges_variants():
    assert career_family("Senior Data Scientist") == career_family("Intern Data Scientist")

# ---------------- resume parser ----------------
def test_resume_extracts_known_skills():
    text = "Skills: Python, SQL and Excel. Built dashboards in Python for sales analysis."
    names = [s["skill_name"].lower() for s in extract_skills(text)]
    assert "python" in names and "sql" in names

def test_resume_empty_text_returns_empty_list():
    assert extract_skills("") == [] and extract_skills("   ") == []

def test_resume_proficiency_capped_at_90():
    s = extract_skills("Python " * 30)
    assert all(x["proficiency"] <= 90 for x in s)

# ---------------- aptitude test ----------------
def _all_answers(correct=True):
    from ml.aptitude_test import _ABILITY_BANK, _INTEREST_BANK
    ab = {q[0]: (q[4] if correct else (q[4] + 1) % len(q[3])) for q in _ABILITY_BANK}
    it = {q[0]: 3 for q in _INTEREST_BANK}
    return ab, it

def test_aptitude_question_counts():
    q = get_questions()
    assert len(q["ability"]) == 20 and len(q["interest"]) == 24

def test_aptitude_answer_key_not_exposed():
    q = get_questions()
    assert all("answer" not in x for x in q["ability"])

def test_aptitude_all_correct_scores_100():
    ab, it = _all_answers(True)
    abilities, _, _ = score_answers(ab, it)
    assert all(v == 100 for v in abilities.values())

def test_aptitude_all_wrong_scores_0():
    ab, it = _all_answers(False)
    abilities, _, _ = score_answers(ab, it)
    assert all(v == 0 for v in abilities.values())

def test_aptitude_missing_answer_raises():
    with pytest.raises(ValueError):
        score_answers({}, {})

def test_holland_code_has_three_letters():
    assert len(holland_code({"R": 10, "I": 90, "A": 20, "S": 30, "E": 80, "C": 70})) == 3

# ---------------- automation risk ----------------
def test_automation_risk_clerk_higher_than_director(careers):
    clerk, _ = estimate_automation_risk("Data entry clerk xyz", [])
    director, _ = estimate_automation_risk("Director of strategy xyz", [])
    assert clerk > director

def test_automation_risk_blank_title():
    assert estimate_automation_risk("", [])[0] is None

# ---------------- learning rules ----------------
def test_lesson_percent_basic():
    assert lesson_percent(50, 100) == 50.0

def test_lesson_percent_capped_at_100():
    assert lesson_percent(500, 100) == 100.0

def test_lesson_percent_zero_duration_safe():
    assert lesson_percent(10, 0) == 0.0

def test_course_completion_gate_is_90_percent():
    from services import learning
    assert getattr(learning, "COMPLETION_THRESHOLD", 90) == 90
