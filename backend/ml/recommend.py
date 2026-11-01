"""
Career recommendation engine.

Combines two techniques:
 1. Content-based filtering (cosine similarity) between the student's
    skill vector and each career's required-skill vector.
 2. The trained Random Forest classifier's predicted probabilities
    (share of trees voting for the career family), which acts as a secondary "model confidence" signal.

The final match score is a weighted blend of both, expressed as a percentage.
"""
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from ml.families import career_family

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "ml", "models")

_model = None
_skill_columns = None


def _load_model():
    global _model, _skill_columns
    if _model is None:
        model_path = os.path.join(MODEL_DIR, "career_predictor.pkl")
        cols_path = os.path.join(MODEL_DIR, "skill_columns.pkl")
        if os.path.exists(model_path) and os.path.exists(cols_path):
            try:
                _model = joblib.load(model_path)
                _skill_columns = joblib.load(cols_path)
            except Exception as e:  # e.g. model saved with a different scikit-learn version
                print(f"[recommend] Could not load model ({e}). Run: python ml/train_model.py")
                _model = False
                _skill_columns = []
        else:
            _model = False  # mark as "not available" so we degrade gracefully
            _skill_columns = []
    return _model, _skill_columns


def _career_vector(required_skills, all_skills):
    req = set(s.strip() for s in required_skills.split(","))
    return np.array([100 if s in req else 0 for s in all_skills])


def _student_vector(user_skills: dict, all_skills):
    return np.array([user_skills.get(s, 0) for s in all_skills])


STREAM_BOOST = 8  # points added to careers in the student's stream categories


def recommend_careers(user_skills: dict, careers: list, top_n: int = 5, stream_categories=None):
    """
    user_skills: {"Python": 80, "SQL": 60, ...}
    careers: list of dicts with keys title, description, required_skills, avg_salary_lpa, job_growth, category
    stream_categories: optional list of `category` values matching the student's stream
        (e.g. MA/BA -> ["Arts & Humanities", "Education"]). Careers in these categories
        get a modest score boost, so a student's own field surfaces even when their
        skill list is thin or overlaps a lot of soft skills across categories.
    Returns list of careers sorted by match_score desc, each augmented with 'match_score' (0-100 int)
    """
    all_skills = sorted({s.strip() for c in careers for s in c["required_skills"].split(",")}
                         | set(user_skills.keys()))

    model, model_skill_cols = _load_model()

    student_vec = _student_vector(user_skills, all_skills).reshape(1, -1)
    stream_categories = set(stream_categories or [])

    family_prob = {}
    if model:
        feat = np.array([[user_skills.get(s, 0) for s in model_skill_cols]])
        try:
            family_prob = dict(zip(model.classes_, model.predict_proba(feat)[0]))
        except Exception:
            family_prob = {}

    results = []
    for career in careers:
        career_vec = _career_vector(career["required_skills"], all_skills).reshape(1, -1)
        sim = cosine_similarity(student_vec, career_vec)[0][0]  # 0..1
        cosine_score = sim * 100

        model_score = None
        if model:
            try:
                # the model predicts the career FAMILY (see ml/families.py);
                # every title in a family shares that family's probability
                family = career_family(career["title"])
                if family in family_prob:
                    model_score = family_prob[family] * 100
            except Exception:
                model_score = None

        if model_score is not None:
            final_score = 0.6 * cosine_score + 0.4 * model_score
        else:
            final_score = cosine_score

        if career.get("category") in stream_categories:
            final_score += STREAM_BOOST

        c = dict(career)
        c["match_score"] = round(float(np.clip(final_score, 0, 99)))
        results.append(c)

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:top_n]


_GROWTH_SCORE = {"High": 82, "Medium": 68, "Low": 55}


def stream_only_suggestions(careers: list, stream_categories, top_n: int = 5):
    """
    Fallback for a brand-new student who has picked a stream but hasn't added
    any skills yet: filter careers to the stream's categories and rank by
    job-growth, so the app has something relevant to show immediately.
    Scores here reflect stream fit + market demand, not a personalized skill
    match - callers should treat this as a starting point, not a final result.
    """
    stream_categories = set(stream_categories or [])
    matches = [c for c in careers if c.get("category") in stream_categories]
    for c in matches:
        c["match_score"] = _GROWTH_SCORE.get(c.get("job_growth"), 60)
        c["stream_based"] = True
    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return matches[:top_n]
