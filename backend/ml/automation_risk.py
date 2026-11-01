"""
AI Automation Risk estimation.

Every row in backend/data/careers.csv carries an `automation_risk` value
(0-100): a heuristic estimate of how much of that role's day-to-day tasks
are exposed to being automated by AI in the foreseeable future. Higher =
more exposed. These are illustrative estimates (routine/rule-based/
scripted work scores higher, people-leadership/strategic/judgment-heavy
work scores lower) rather than a precise economic forecast.

This module figures out the automation risk for a user's *current job*
(a free-text field, not one of our fixed career titles) by matching it
against the careers table, falling back to keyword heuristics when there's
no good match.
"""
import re

# Applied on top of a matched/base score depending on words present in the
# job title text itself - lets us give a reasonable estimate even for a
# free-text title that only loosely matches (or doesn't match at all) one
# of our known career records.
_HIGH_RISK_KEYWORDS = [
    "data entry", "telecaller", "telecalling", "cashier", "clerk", "clerical",
    "receptionist", "support specialist", "technician", "administrator",
    "representative", "assistant", "coordinator", "operator", "processor",
    "billing", "scheduling", "transcription", "bookkeeping", "telesales",
]
_LOW_RISK_KEYWORDS = [
    "manager", "director", "head", "lead", "leader", "founder", "strategist",
    "counselor", "therapist", "surgeon", "doctor", "teacher", "professor",
    "creative director", "designer", "artist", "negotiator", "business partner",
    "architect", "researcher", "scientist",
]

DEFAULT_RISK = 50  # used when nothing else gives us a signal


def _keyword_adjustment(title: str) -> int:
    t = title.lower()
    adj = 0
    if any(k in t for k in _HIGH_RISK_KEYWORDS):
        adj += 10
    if any(k in t for k in _LOW_RISK_KEYWORDS):
        adj -= 10
    return adj


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def estimate_automation_risk(job_title: str, careers: list):
    """
    job_title: free-text current-job string from the user's profile.
    careers: list of dicts (from the `careers` table), each with at least
        'title' and 'automation_risk'.

    Returns: (risk_percent: int, matched_title: str | None)
        matched_title is the careers.csv title we matched against, or None
        if we fell back to a pure keyword estimate.
    """
    if not job_title or not job_title.strip():
        return None, None

    norm_input = _normalize(job_title)
    if not norm_input:
        return None, None

    careers_with_risk = [c for c in careers if c.get("automation_risk") is not None]

    # 1) Exact (normalized) match
    for c in careers_with_risk:
        if _normalize(c["title"]) == norm_input:
            return int(c["automation_risk"]), c["title"]

    # 2) Substring match either direction (e.g. "IT Support" vs
    #    "Information Technology Support Specialist" won't hit this, but
    #    "Sales Manager" vs "Territory Sales Manager" style overlaps will)
    best, best_len = None, 0
    for c in careers_with_risk:
        norm_title = _normalize(c["title"])
        if norm_input in norm_title or norm_title in norm_input:
            if len(norm_title) > best_len:
                best, best_len = c, len(norm_title)
    if best:
        return int(best["automation_risk"]), best["title"]

    # 3) Word-overlap match: most shared significant words wins
    input_words = set(norm_input.split())
    best, best_overlap = None, 0
    for c in careers_with_risk:
        title_words = set(_normalize(c["title"]).split())
        overlap = len(input_words & title_words)
        if overlap > best_overlap:
            best_overlap, best = overlap, c
    if best and best_overlap > 0:
        return int(best["automation_risk"]), best["title"]

    # 4) No match at all - pure keyword heuristic on the free-text title
    risk = DEFAULT_RISK + _keyword_adjustment(job_title)
    risk = max(5, min(95, risk))
    return risk, None


def risk_label(risk_percent):
    """Small human-readable bucket for UI badges."""
    if risk_percent is None:
        return None
    if risk_percent >= 65:
        return "High"
    if risk_percent >= 40:
        return "Moderate"
    return "Low"
