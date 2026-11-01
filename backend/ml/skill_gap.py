"""
Skill Gap Analysis.

Uses simple NLP normalization (lowercasing, lemmatization via NLTK when
available) plus fuzzy string similarity to match a student's existing
skills against a target career's required skills, even when phrasing
differs slightly (e.g. "ML" vs "Machine Learning").
"""
import re
from difflib import SequenceMatcher

try:
    import nltk
    from nltk.stem import WordNetLemmatizer

    try:
        nltk.data.find("corpora/wordnet")
    except LookupError:
        nltk.download("wordnet", quiet=True)
        nltk.download("omw-1.4", quiet=True)

    _lemmatizer = WordNetLemmatizer()
    _NLTK_AVAILABLE = True
except Exception:
    _NLTK_AVAILABLE = False

SYNONYMS = {
    "ml": "machine learning",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "js": "javascript",
    "db": "database",
    "cv": "computer vision",
}


def _normalize(skill: str) -> str:
    s = skill.lower().strip()
    s = SYNONYMS.get(s, s)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    if _NLTK_AVAILABLE:
        s = " ".join(_lemmatizer.lemmatize(w) for w in s.split())
    return s


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def analyze_skill_gap(user_skills: dict, required_skills: list, proficiency_threshold: int = 60):
    """
    user_skills: {"Python": 80, "SQL": 40, ...}
    required_skills: ["Python", "Statistics", "Machine Learning", ...]

    Returns dict with:
      matched: skills the student already has at/above threshold
      partial: skills the student has but below threshold
      missing: skills the student doesn't have at all
      overall_gap_percent: 0-100, how much of the required skillset is still missing
    """
    norm_user = {_normalize(k): (k, v) for k, v in user_skills.items()}

    matched, partial, missing = [], [], []

    for req_skill in required_skills:
        norm_req = _normalize(req_skill)

        best_match = None
        best_score = 0.0
        for norm_key, (orig_key, prof) in norm_user.items():
            score = _similar(norm_req, norm_key)
            if norm_req == norm_key:
                score = 1.0
            if score > best_score:
                best_score = score
                best_match = (orig_key, prof)

        if best_match and best_score >= 0.8:
            orig_key, prof = best_match
            level = (
                "Advanced" if prof >= 80 else
                "Intermediate" if prof >= 60 else
                "Beginner"
            )
            entry = {"skill": req_skill, "proficiency": prof, "level": level}
            if prof >= proficiency_threshold:
                matched.append(entry)
            else:
                partial.append(entry)
        else:
            missing.append({"skill": req_skill, "proficiency": 0, "level": "None"})

    total = len(required_skills) if required_skills else 1
    gap_weight = len(missing) + 0.5 * len(partial)
    overall_gap_percent = round((gap_weight / total) * 100)

    return {
        "matched": matched,
        "partial": partial,
        "missing": missing,
        "overall_gap_percent": overall_gap_percent,
        "overall_skill_percent": 100 - overall_gap_percent,
    }
