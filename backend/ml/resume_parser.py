"""
Resume Skill Extraction.

Matches raw resume text against the app's skill taxonomy (backend/data/skills.csv,
built from real job postings) using whole-word/phrase regex matching. This is a
lightweight, dependency-free approach (no transformer model) chosen because the
taxonomy is already domain-specific - a term either appears in real job postings
as a skill or it doesn't, so keyword matching against that fixed vocabulary is a
solid, fast baseline. Mention frequency in the resume is used as a rough proxy
for proficiency.

Skill extraction only runs on ATS-friendly resumes (plain, text-based
.pdf / .docx / .txt with standard section headings). Designed, image-based,
or multi-column graphic resumes are rejected.
"""
import csv
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_PATH = os.path.join(BASE_DIR, "data", "skills.csv")

_skill_patterns = None  # list of (skill_name, compiled_regex)


def _load_skill_patterns():
    global _skill_patterns
    if _skill_patterns is not None:
        return _skill_patterns

    skills = []
    with open(SKILLS_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["skill_name"].strip()
            if len(name) >= 2:
                skills.append(name)

    # Longer phrases first, so "Machine Learning" matches before "Machine"-style
    # partial overlaps could occur with shorter skill names.
    skills.sort(key=len, reverse=True)

    patterns = []
    for skill in skills:
        escaped = re.escape(skill)
        # \b works fine for alphanumeric skill names; skills with punctuation
        # (e.g. ".NET", "C++") get looser boundaries.
        if re.match(r"^[A-Za-z0-9 ]+$", skill):
            pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
        else:
            pattern = re.compile(escaped, re.IGNORECASE)
        patterns.append((skill, pattern))

    _skill_patterns = patterns
    return _skill_patterns


ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx", ".txt"}

# Headings applicant-tracking systems expect in a parseable resume.
_ATS_SECTIONS = [
    ("summary", re.compile(r"\b(summary|objective|profile|about me)\b", re.I)),
    ("education", re.compile(r"\b(education|academic|academics|qualifications)\b", re.I)),
    ("experience", re.compile(
        r"\b(experience|employment|work history|professional experience|work experience|internship)\b",
        re.I,
    )),
    ("skills", re.compile(r"\b(skills|technical skills|core competencies|expertise|technologies)\b", re.I)),
    ("projects", re.compile(r"\b(projects|personal projects|academic projects)\b", re.I)),
    ("certifications", re.compile(r"\b(certifications?|certificates|licenses)\b", re.I)),
]

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s().]{7,}\d)")

ATS_MIN_SCORE = 60
ATS_MIN_WORDS = 50
ATS_MIN_SECTIONS = 2


def assess_ats_friendliness(resume_text: str, meta=None):
    """
    Decide whether a resume is ATS-friendly enough to extract skills from.

    ATS-friendly means: selectable text, standard section headings, contact
    details in the body, and a simple layout (not a scanned image, Canva
    graphic, or multi-column designed CV).

    Returns:
        {
          "ats_friendly": bool,
          "score": int,
          "issues": [str],
          "tips": [str],
          "sections_found": [str],
          "word_count": int,
        }
    """
    meta = meta or {}
    issues = []
    tips = []
    text = resume_text or ""
    words = re.findall(r"[A-Za-z]{2,}", text)
    word_count = len(words)
    sections_found = [name for name, pattern in _ATS_SECTIONS if pattern.search(text)]

    score = 0
    if word_count >= ATS_MIN_WORDS:
        score += 25
    if word_count >= 120:
        score += 10
    if _EMAIL_RE.search(text):
        score += 15
    else:
        issues.append("No email address found in the document text.")
        tips.append("Put your email in the resume body as plain text, not inside a header image.")
    if _PHONE_RE.search(text):
        score += 5

    score += min(30, len(sections_found) * 10)
    if "skills" in sections_found:
        score += 10

    file_type = (meta.get("file_type") or "").lower()
    if meta.get("unsupported"):
        issues.append("This file type is not ATS-friendly. Use a text-based .pdf, .docx, or .txt resume.")
        tips.append("Export your resume from Word or Google Docs as a simple .pdf or .docx, not PNG/JPG or a designed template.")
        return {
            "ats_friendly": False,
            "score": 0,
            "issues": issues,
            "tips": tips,
            "sections_found": sections_found,
            "word_count": word_count,
        }

    image_count = int(meta.get("image_count") or 0)
    table_count = int(meta.get("table_count") or 0)
    textbox_count = int(meta.get("textbox_count") or 0)
    column_count = int(meta.get("column_count") or 1)
    page_count = max(int(meta.get("page_count") or 1), 1)

    if image_count > 3:
        penalty = min(30, (image_count - 3) * 5)
        score -= penalty
        issues.append(f"Resume contains {image_count} images, which ATS software often cannot read.")
        tips.append("Remove photos, icons, logos, and skill bars. Use plain text and simple bullet points.")
    if table_count > 2:
        score -= min(20, (table_count - 2) * 5)
        issues.append("Layout relies on tables, which most ATS parsers scramble.")
        tips.append("Replace tables with a single-column list of sections.")
    if textbox_count > 0:
        score -= 15
        issues.append("Text boxes were detected. ATS tools often skip text inside boxes.")
        tips.append("Move all content out of text boxes into the normal document body.")
    if column_count > 1:
        score -= 20
        issues.append("Multi-column layout detected. ATS parsers read columns out of order.")
        tips.append("Use a single-column resume with clear headings like Experience, Education, and Skills.")

    # Scanned / image-only PDFs: almost no extractable text relative to pages.
    text_density = word_count / page_count
    if file_type == ".pdf" and image_count > 0 and text_density < 50:
        issues.append("This looks like a scanned or image-based PDF, not a text-based ATS resume.")
        tips.append("Create the resume in Word/Google Docs and export as PDF so the text is selectable.")
        score = min(score, 20)

    if word_count < ATS_MIN_WORDS:
        issues.append(
            f"Only {word_count} words of selectable text were found (need at least {ATS_MIN_WORDS})."
        )
        tips.append("ATS-friendly resumes are text-based. Designed/Canva/image CVs usually extract as empty.")

    if len(sections_found) < ATS_MIN_SECTIONS:
        issues.append(
            "Missing standard ATS section headings (need at least two of: Summary, Experience, Education, Skills, Projects, Certifications)."
        )
        tips.append("Add clear headings such as EXPERIENCE, EDUCATION, and SKILLS on their own lines.")

    hard_fail = (
        word_count < ATS_MIN_WORDS
        or len(sections_found) < ATS_MIN_SECTIONS
        or (file_type == ".pdf" and image_count > 0 and text_density < 50)
    )
    score = max(0, min(100, score))
    ats_friendly = (not hard_fail) and score >= ATS_MIN_SCORE

    if not ats_friendly and not tips:
        tips.append("Upload a simple, single-column .pdf or .docx with selectable text and standard headings.")

    return {
        "ats_friendly": ats_friendly,
        "score": score,
        "issues": issues,
        "tips": tips,
        "sections_found": sections_found,
        "word_count": word_count,
    }


def extract_skills(resume_text: str, max_skills: int = 25):
    """
    Returns a list of {"skill_name": str, "proficiency": int, "mentions": int}
    sorted by mention count desc, capped at max_skills.

    Proficiency is a heuristic: 1 mention -> 55, scaling up to 90 for skills
    mentioned frequently (e.g. in both a summary and multiple job entries).
    This is meant as a starting point for the user to review/adjust, not a
    precise measurement.
    """
    if not resume_text or not resume_text.strip():
        return []

    patterns = _load_skill_patterns()
    found = []
    seen_lower = set()

    for skill, pattern in patterns:
        key = skill.lower()
        if key in seen_lower:
            continue
        matches = pattern.findall(resume_text)
        if matches:
            seen_lower.add(key)
            mentions = len(matches)
            proficiency = min(90, 50 + mentions * 10)
            found.append({"skill_name": skill, "proficiency": proficiency, "mentions": mentions})

    found.sort(key=lambda x: x["mentions"], reverse=True)
    return found[:max_skills]


def guess_job_title(resume_text: str, career_titles):
    """
    Very lightweight best-effort guess of which career family a resume best
    matches, by counting how many of the resume's extracted skills overlap
    with each career's typical top skills. Used only as a starting suggestion,
    not shown as a confident classification.
    """
    extracted = {s["skill_name"].lower() for s in extract_skills(resume_text, max_skills=50)}
    if not extracted:
        return None

    best_title, best_overlap = None, 0
    for title, required_skills in career_titles.items():
        required_lower = {s.strip().lower() for s in required_skills}
        overlap = len(extracted & required_lower)
        if overlap > best_overlap:
            best_overlap = overlap
            best_title = title
    return best_title