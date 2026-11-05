"""
Live job openings matched to a user's PROFILE SKILLS (company names included).

Sources (all return the hiring company, title, location and an apply link):
  * Adzuna    - real openings in India (and other countries). Needs a free key:
                set ADZUNA_APP_ID and ADZUNA_APP_KEY in backend/.env
                (https://developer.adzuna.com). Optional.
  * Remotive  - remote jobs worldwide. No key. Public API asks for max ~2 requests/min,
                so ONE broad request is made and cached; matching is done locally.
  * Arbeitnow - international / remote job board. No key. Used when scope = "all".

If a source is down or has no key it is skipped; the others still work.
Remotive asks that its jobs link back to the listing and are not re-published to other
job boards - every result keeps its `url` and a `source` label for that reason.
"""
import os
import re
import time
import html
import threading

import requests

CACHE_TTL = 30 * 60          # seconds; keeps us well inside Remotive's rate limit
HTTP_TIMEOUT = 10
MAX_SKILLS_USED = 6          # skills used for matching / Adzuna queries
MAX_RESULTS = 60

# Profile "skills" that are too generic to find jobs with.
GENERIC_SKILLS = {
    "technology", "communication", "leadership", "teamwork", "problem solving",
    "management", "skills", "software", "computer skills", "english",
}

_cache = {}                  # key -> (timestamp, data)
_cache_lock = threading.Lock()


# --------------------------------------------------------------------------- helpers
def _cached(key, loader):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
    data = loader()
    with _cache_lock:
        _cache[key] = (now, data)
    return data


def _strip_html(text, limit=4000):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return text[:limit]


def _skill_regex(skill):
    """Whole-word, case-insensitive match; 'C++' / '.NET' style names handled by escaping."""
    s = re.escape(skill.strip())
    return re.compile(rf"(?<![A-Za-z0-9]){s}(?![A-Za-z0-9])", re.IGNORECASE)


def pick_profile_skills(rows):
    """
    rows: iterable of dicts {skill_name, proficiency, verified, category}.
    Returns [(skill_name, weight)] - technical, non-generic, strongest / verified first.
    """
    picked = []
    for r in rows:
        name = (r["skill_name"] or "").strip()
        if not name or name.lower() in GENERIC_SKILLS:
            continue
        if (r.get("category") or "technical") == "soft":
            continue
        weight = (r.get("proficiency") or 50) / 100.0
        if r.get("verified"):
            weight += 0.25          # verified skills count for more
        picked.append((name, round(weight, 3)))
    picked.sort(key=lambda p: p[1], reverse=True)
    return picked[:MAX_SKILLS_USED]


# --------------------------------------------------------------------------- sources
def _fetch_adzuna(skills, where, country):
    app_id, app_key = os.getenv("ADZUNA_APP_ID", ""), os.getenv("ADZUNA_APP_KEY", "")
    if not (app_id and app_key):
        return []
    jobs = []
    for name, _ in skills[:4]:
        def load(name=name):
            r = requests.get(
                f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
                params={
                    "app_id": app_id, "app_key": app_key, "what": name,
                    "where": where or "", "results_per_page": 20,
                    "sort_by": "date", "content-type": "application/json",
                },
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            return r.json().get("results", [])
        try:
            results = _cached(("adzuna", country, where, name.lower()), load)
        except Exception:
            continue
        for j in results:
            jobs.append({
                "id": f"adzuna-{j.get('id')}",
                "title": j.get("title", ""),
                "company": (j.get("company") or {}).get("display_name") or "Not disclosed",
                "location": (j.get("location") or {}).get("display_name", ""),
                "remote": False,
                "url": j.get("redirect_url", ""),
                "posted": (j.get("created") or "")[:10],
                "salary": _fmt_salary(j.get("salary_min"), j.get("salary_max"), "₹"),
                "tags": [],
                "description": _strip_html(j.get("description")),
                "source": "Adzuna",
            })
    return jobs


def _fmt_salary(lo, hi, symbol):
    if lo and hi:
        return f"{symbol}{int(lo):,} - {symbol}{int(hi):,} / yr"
    if lo or hi:
        return f"{symbol}{int(lo or hi):,} / yr"
    return ""


def _fetch_remotive():
    def load():
        r = requests.get("https://remotive.com/api/remote-jobs",
                         params={"limit": 400}, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json().get("jobs", [])
    try:
        results = _cached(("remotive",), load)
    except Exception:
        return []
    return [{
        "id": f"remotive-{j.get('id')}",
        "title": j.get("title", ""),
        "company": j.get("company_name") or "Not disclosed",
        "location": j.get("candidate_required_location") or "Remote",
        "remote": True,
        "url": j.get("url", ""),
        "posted": (j.get("publication_date") or "")[:10],
        "salary": j.get("salary") or "",
        "tags": j.get("tags") or [],
        "description": _strip_html(j.get("description")),
        "source": "Remotive",
    } for j in results]


def _fetch_arbeitnow():
    def load():
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json().get("data", [])
    try:
        results = _cached(("arbeitnow",), load)
    except Exception:
        return []
    return [{
        "id": f"arbeitnow-{j.get('slug')}",
        "title": j.get("title", ""),
        "company": j.get("company_name") or "Not disclosed",
        "location": j.get("location") or ("Remote" if j.get("remote") else ""),
        "remote": bool(j.get("remote")),
        "url": j.get("url", ""),
        "posted": time.strftime("%Y-%m-%d", time.gmtime(j["created_at"])) if j.get("created_at") else "",
        "salary": "",
        "tags": j.get("tags") or [],
        "description": _strip_html(j.get("description")),
        "source": "Arbeitnow",
    } for j in results]


# Remote postings restricted to another region are not useful to an applicant in India.
_OPEN_LOCATION = re.compile(
    r"worldwide|anywhere|global|remote|apac|asia|india|^\s*$", re.IGNORECASE)


def _location_ok(job, scope):
    if scope == "all":
        return True
    if job["source"] == "Adzuna":
        return True
    return bool(_OPEN_LOCATION.search(job["location"] or ""))


# --------------------------------------------------------------------------- matching
def match_jobs(jobs, skills):
    """Score every job against the profile skills; drop jobs that match none."""
    patterns = [(name, w, _skill_regex(name)) for name, w in skills]
    seen, out = set(), []
    for job in jobs:
        key = (job["company"].lower(), job["title"].lower())
        if key in seen:
            continue
        seen.add(key)

        title_blob = job["title"] + " " + " ".join(job["tags"])
        body = job["description"]
        matched, score = [], 0.0
        for name, w, pat in patterns:
            in_title = bool(pat.search(title_blob))
            in_body = bool(pat.search(body))
            if in_title or in_body:
                matched.append(name)
                score += w * (2.0 if in_title else 1.0)
        if not matched:
            continue
        total_weight = sum(w for _, w in skills) or 1.0
        out.append({
            **{k: v for k, v in job.items() if k != "description"},
            "summary": job["description"][:220].rstrip() + ("..." if len(job["description"]) > 220 else ""),
            "matched_skills": matched,
            "missing_skills": [n for n, _ in skills if n not in matched],
            "match_percent": min(100, round(100 * len(matched) / len(skills))),
            "_score": score / total_weight,
        })
    out.sort(key=lambda j: (j["_score"], j["posted"]), reverse=True)
    for j in out:
        j.pop("_score")
    return out[:MAX_RESULTS]


def find_jobs_for_skills(skills, where="", country="in", scope="india"):
    """
    skills: [(name, weight)] from pick_profile_skills().
    scope: "india" -> Adzuna(country) + remote roles open to India, "all" -> everything.
    """
    if not skills:
        return {"skills_used": [], "jobs": [], "sources": [], "note": "Add technical skills to your profile first."}

    pool = _fetch_adzuna(skills, where, country) + _fetch_remotive()
    if scope == "all":
        pool += _fetch_arbeitnow()
    pool = [j for j in pool if _location_ok(j, scope)]

    sources = sorted({j["source"] for j in pool})
    note = ""
    if not pool:
        note = "Could not reach the job boards right now. Check your internet connection and try again."

    return {
        "skills_used": [n for n, _ in skills],
        "jobs": match_jobs(pool, skills),
        "sources": sources,
        "note": note,
    }