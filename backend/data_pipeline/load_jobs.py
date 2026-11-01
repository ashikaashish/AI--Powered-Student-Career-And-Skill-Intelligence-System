"""
ETL: turns the raw job-postings dataset (backend/data/raw/all_job_post.csv)
into the app's careers.csv + skills.csv.

Why this exists: the raw data has 1,167 individual job postings across 723
distinct (mostly near-duplicate) titles - too granular to browse as "careers".
This script:
  1. Parses each posting's stringified skill list into a real Python list.
  2. Normalizes skill names (casing, whitespace) and builds a skill taxonomy.
  3. Collapses near-duplicate titles into "career families" per category
     (e.g. "Sr Human Resource Generalist" / "HR Generalist (Hybrid)" ->
     "Human Resource Generalist") by stripping seniority/format modifiers.
  4. Picks the most frequent skills within each family as required_skills.
  5. Keeps the top N families per category (by posting count) as careers.

Run with: python data_pipeline/load_jobs.py
Outputs: backend/data/careers.csv, backend/data/skills.csv
"""
import ast
import os
import re
from collections import Counter, defaultdict

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(BASE_DIR, "data", "raw", "all_job_post.csv")
CAREERS_OUT = os.path.join(BASE_DIR, "data", "careers.csv")
SKILLS_OUT = os.path.join(BASE_DIR, "data", "skills.csv")

CAREERS_PER_CATEGORY = 8
SKILLS_PER_CAREER = 10

# Category -> rough job-growth label (qualitative, since the dataset has no
# growth/salary figures; kept deliberately coarse rather than inventing numbers)
GROWTH_BY_CATEGORY = {
    "INFORMATION-TECHNOLOGY": "High",
    "FINANCE": "Medium",
    "BUSINESS-DEVELOPMENT": "Medium",
    "SALES": "Medium",
    "HR": "Medium",
}

SENIORITY_WORDS = [
    r"\bsr\.?\b", r"\bjr\.?\b", r"\bsenior\b", r"\bjunior\b", r"\blead\b",
    r"\bchief\b", r"\bhead of\b", r"\bdirector of\b", r"\bdirector\b",
    r"\bvp\b", r"\bvice president\b", r"\bassociate\b", r"\bassistant\b",
    r"\bexecutive\b", r"\bprincipal\b", r"\bstaff\b", r"\bentry level\b",
    r"\bi{1,3}\b", r"\biv\b",
]


def parse_skill_list(raw):
    """The job_skill_set column is a stringified Python list, e.g. "['a', 'b']"."""
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return [str(s).strip() for s in parsed if str(s).strip()]
    except (ValueError, SyntaxError):
        pass
    return [s.strip(" '\"[]") for s in raw.split(",") if s.strip(" '\"[]")]


_SKILL_CANONICAL = {}  # lowercase key -> first-seen display form, for case-insensitive dedup


def normalize_skill(skill):
    s = re.sub(r"\s+", " ", skill.strip())
    if not s:
        return s
    # Title-case looks best for display, but preserve common all-caps acronyms
    if not (s.isupper() and len(s) <= 6):
        s = s[:1].upper() + s[1:]
    key = s.lower()
    if key not in _SKILL_CANONICAL:
        _SKILL_CANONICAL[key] = s
    return _SKILL_CANONICAL[key]


def base_title(title):
    """Strip seniority/format modifiers so near-duplicate titles collapse together."""
    t = title.lower()
    t = re.sub(r"\(.*?\)", "", t)  # drop "(Hybrid Role)" etc.
    for pat in SENIORITY_WORDS:
        t = re.sub(pat, "", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.title() if t else title.strip()


def main():
    df = pd.read_csv(RAW_PATH)
    df["skills_list"] = df["job_skill_set"].apply(parse_skill_list)
    df["skills_list"] = df["skills_list"].apply(lambda lst: [normalize_skill(s) for s in lst])
    df["family"] = df["job_title"].apply(base_title)

    all_skill_counter = Counter()
    for lst in df["skills_list"]:
        all_skill_counter.update(lst)

    career_rows = []
    for category, cat_df in df.groupby("category"):
        family_groups = defaultdict(list)
        for _, row in cat_df.iterrows():
            family_groups[row["family"]].append(row)

        # Rank families by number of postings (proxy for how common that role is)
        ranked = sorted(family_groups.items(), key=lambda kv: len(kv[1]), reverse=True)

        for family, rows in ranked[:CAREERS_PER_CATEGORY]:
            skill_counter = Counter()
            titles = []
            for r in rows:
                skill_counter.update(r["skills_list"])
                titles.append(r["job_title"])
            top_skills = [s for s, _ in skill_counter.most_common(SKILLS_PER_CAREER)]
            if not top_skills:
                continue

            example_title = min(titles, key=len)  # shortest real title reads cleanest
            description = (
                f"{family} roles focus on {', '.join(top_skills[:3]).lower()}, "
                f"drawn from {len(rows)} real {category.replace('-', ' ').title()} "
                f"job postings (e.g. \"{example_title}\")."
            )

            career_rows.append({
                "title": family,
                "description": description,
                "required_skills": ",".join(top_skills),
                "avg_salary_lpa": "",  # not present in source data - left blank, not invented
                "job_growth": GROWTH_BY_CATEGORY.get(category, "Medium"),
                "category": category.replace("-", " ").title(),
            })

    careers_df = pd.DataFrame(career_rows).drop_duplicates(subset=["title"])
    careers_df.to_csv(CAREERS_OUT, index=False)
    print(f"Wrote {len(careers_df)} careers -> {CAREERS_OUT}")

    # Skills taxonomy: keep skills that appear at least twice (filters one-off noise)
    skills_df = pd.DataFrame(
        [{"skill_name": s, "category": "technical"} for s, c in all_skill_counter.items() if c >= 2]
    ).sort_values("skill_name")
    skills_df.to_csv(SKILLS_OUT, index=False)
    print(f"Wrote {len(skills_df)} skills -> {SKILLS_OUT}")


if __name__ == "__main__":
    main()
