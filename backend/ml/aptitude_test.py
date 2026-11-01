"""
Aptitude + Interest test.

Two parts:
  1. ABILITY  - 20 multiple-choice questions with right/wrong answers
                (numerical, verbal, logical, spatial; 5 each).
  2. INTEREST - 24 statements rated 1-5 (Holland / RIASEC model, 4 each):
                Realistic, Investigative, Artistic, Social, Enterprising,
                Conventional.

The result (4 ability scores + 6 interest scores, all 0-100) is matched against a
requirement profile for every career in the `careers` table, so the output is
a ranked list of real careers from the rest of the app (roadmap, skill gap and
courses all work for them).
"""

ABILITIES = ["numerical", "verbal", "logical", "spatial"]
ABILITY_LABELS = {
    "numerical": "Numerical reasoning",
    "verbal": "Verbal reasoning",
    "logical": "Logical reasoning",
    "spatial": "Spatial reasoning",
}

INTERESTS = ["R", "I", "A", "S", "E", "C"]
INTEREST_LABELS = {
    "R": "Realistic",
    "I": "Investigative",
    "A": "Artistic",
    "S": "Social",
    "E": "Enterprising",
    "C": "Conventional",
}
INTEREST_HINTS = {
    "R": "hands-on, technical, practical work",
    "I": "analysing, researching, solving problems",
    "A": "creative, original, expressive work",
    "S": "helping, teaching, working with people",
    "E": "leading, persuading, selling",
    "C": "organised, detail-focused, structured work",
}

# (id, ability, question, options, correct_index)
_ABILITY_BANK = [
    # ---- numerical ----
    ("n1", "numerical", "A laptop costs 40,000 after a 20% discount. What was the original price?",
     ["48,000", "50,000", "52,000", "56,000"], 1),
    ("n2", "numerical", "Two numbers are in the ratio 3:5 and their sum is 160. What is the larger number?",
     ["60", "80", "100", "120"], 2),
    ("n3", "numerical", "A train covers 240 km in 3 hours. At the same speed, how long will it take to cover 400 km?",
     ["4 hours", "5 hours", "6 hours", "6.5 hours"], 1),
    ("n4", "numerical", "Monthly sales rose from 120 units in January to 150 units in February. What is the percentage increase?",
     ["20%", "25%", "30%", "15%"], 1),
    ("n5", "numerical", "8 workers finish a job in 12 days. At the same rate, how many days will 6 workers need?",
     ["9", "14", "16", "18"], 2),
    # ---- verbal ----
    ("v1", "verbal", "Choose the word closest in meaning to METICULOUS.",
     ["Careless", "Precise", "Hurried", "Generous"], 1),
    ("v2", "verbal", "Choose the word opposite in meaning to SCARCE.",
     ["Rare", "Abundant", "Tiny", "Costly"], 1),
    ("v3", "verbal", "Doctor is to Patient as Teacher is to ...",
     ["School", "Student", "Book", "Lesson"], 1),
    ("v4", "verbal", "\"Profits rose 10% even though sales fell, because the company cut its costs sharply.\" What was the main reason profits rose?",
     ["Higher sales", "Lower costs", "New customers", "Higher prices"], 1),
    ("v5", "verbal", "Choose the best word to complete the sentence: Despite the heavy rain, the match ___ as scheduled.",
     ["was abandoned", "was cancelled", "proceeded", "stopped"], 2),
    # ---- logical ----
    ("l1", "logical", "What comes next?  2, 6, 12, 20, 30, ...",
     ["40", "42", "44", "36"], 1),
    ("l2", "logical", "No file is empty. Some files are PDFs. Which statement must be true?",
     ["All PDFs are empty", "Some PDFs are not empty", "No PDF is a file", "All files are PDFs"], 1),
    ("l3", "logical", "What comes next?  A, C, F, J, O, ...",
     ["S", "T", "U", "V"], 2),
    ("l4", "logical", "If CAT is coded as 24 (3 + 1 + 20), what is DOG coded as?",
     ["24", "26", "27", "28"], 1),
    ("l5", "logical", "Amit is taller than Raj. Raj is taller than Sam. Kiran is shorter than Sam. Who is the second shortest?",
     ["Amit", "Raj", "Sam", "Kiran"], 2),
    # ---- spatial ----
    ("s1", "spatial", "A 3x3x3 cube is painted on all faces and cut into 27 small cubes. How many small cubes have exactly 2 painted faces?",
     ["8", "12", "6", "24"], 1),
    ("s2", "spatial", "How many faces does a triangular prism have?",
     ["4", "5", "6", "8"], 1),
    ("s3", "spatial", "You face north, turn right 90 degrees, then turn left 180 degrees. Which direction do you face now?",
     ["North", "South", "East", "West"], 3),
    ("s4", "spatial", "A wall clock shows exactly 3:00. What time would its mirror image appear to show?",
     ["3:00", "6:00", "9:00", "12:00"], 2),
    ("s5", "spatial", "Looking straight down from directly above, what shape does a cylinder standing upright appear to be?",
     ["Rectangle", "Circle", "Triangle", "Oval"], 1),
]

# (id, dimension, statement)
_INTEREST_BANK = [
    ("int_r1", "R", "Fixing or setting up equipment, devices, or machines"),
    ("int_r2", "R", "Doing hands-on tasks with tools, in a workshop or outdoors"),
    ("int_r3", "R", "Figuring out why a device, system, or network isn't working"),
    ("int_r4", "R", "Building or assembling something step by step"),
    ("int_i1", "I", "Analysing data to find patterns or answers"),
    ("int_i2", "I", "Researching how things work"),
    ("int_i3", "I", "Working through complex problems that need deep thinking"),
    ("int_i4", "I", "Learning about science, technology, or new methods"),
    ("int_a1", "A", "Writing, designing, or creating original content"),
    ("int_a2", "A", "Coming up with new ideas and unconventional approaches"),
    ("int_a3", "A", "Expressing ideas through visuals, stories, or presentations"),
    ("int_a4", "A", "Working in a place with freedom and few rigid rules"),
    ("int_s1", "S", "Helping people solve personal or work problems"),
    ("int_s2", "S", "Teaching, training, or mentoring others"),
    ("int_s3", "S", "Listening to and supporting colleagues or customers"),
    ("int_s4", "S", "Working in a team towards a shared goal"),
    ("int_e1", "E", "Persuading or convincing other people"),
    ("int_e2", "E", "Leading a team or taking charge of a project"),
    ("int_e3", "E", "Negotiating deals and closing sales"),
    ("int_e4", "E", "Taking business risks to hit ambitious targets"),
    ("int_c1", "C", "Keeping records, files, and data accurate and organised"),
    ("int_c2", "C", "Following clear procedures and checklists"),
    ("int_c3", "C", "Working with budgets, numbers, and reports"),
    ("int_c4", "C", "Keeping schedules, documents, and details in order"),
]


def get_questions():
    """Questions for the frontend - the answer key is NOT included."""
    return {
        "ability": [
            {"id": q[0], "ability": q[1], "ability_label": ABILITY_LABELS[q[1]],
             "question": q[2], "options": q[3]}
            for q in _ABILITY_BANK
        ],
        "interest": [
            {"id": q[0], "dimension": q[1], "statement": q[2]} for q in _INTEREST_BANK
        ],
    }


# --------------------------------------------------------------------------- scoring

def score_answers(ability_answers: dict, interest_answers: dict):
    """
    ability_answers:  {question_id: chosen_option_index}
    interest_answers: {question_id: 1..5}
    Returns (abilities, interests, correct_counts), each score 0-100.
    Raises ValueError if anything is missing or out of range.
    """
    correct = {a: 0 for a in ABILITIES}
    total = {a: 0 for a in ABILITIES}
    for qid, ability, _q, options, answer in _ABILITY_BANK:
        if qid not in ability_answers:
            raise ValueError(f"Missing answer for question {qid}")
        chosen = int(ability_answers[qid])
        if not 0 <= chosen < len(options):
            raise ValueError(f"Invalid option for question {qid}")
        total[ability] += 1
        if chosen == answer:
            correct[ability] += 1
    abilities = {a: round(100 * correct[a] / total[a]) for a in ABILITIES}

    sums = {d: 0 for d in INTERESTS}
    counts = {d: 0 for d in INTERESTS}
    for qid, dim, _s in _INTEREST_BANK:
        if qid not in interest_answers:
            raise ValueError(f"Missing rating for statement {qid}")
        rating = int(interest_answers[qid])
        if not 1 <= rating <= 5:
            raise ValueError(f"Rating out of range for statement {qid}")
        sums[dim] += rating
        counts[dim] += 1
    # 1..5 average -> 0..100
    interests = {d: round((sums[d] / counts[d] - 1) / 4 * 100) for d in INTERESTS}
    return abilities, interests, {"correct": correct, "total": total}


def holland_code(interests: dict, n: int = 3) -> str:
    ranked = sorted(INTERESTS, key=lambda d: interests[d], reverse=True)
    return "".join(ranked[:n])


# --------------------------------------------------------------------------- career profiles
# Requirement profile per career category: minimum ability level wanted (0-100)
# and the typical interest profile (0-100) of people who enjoy that work.
CATEGORY_PROFILES = {
    "Information Technology": {
        "ability": {"numerical": 65, "verbal": 50, "logical": 80, "spatial": 55},
        "interest": {"R": 60, "I": 80, "A": 30, "S": 30, "E": 30, "C": 55},
    },
    "Finance": {
        "ability": {"numerical": 85, "verbal": 60, "logical": 70, "spatial": 30},
        "interest": {"R": 15, "I": 65, "A": 15, "S": 25, "E": 45, "C": 85},
    },
    "HR": {
        "ability": {"numerical": 45, "verbal": 80, "logical": 55, "spatial": 25},
        "interest": {"R": 10, "I": 30, "A": 30, "S": 90, "E": 55, "C": 60},
    },
    "Sales": {
        "ability": {"numerical": 55, "verbal": 75, "logical": 50, "spatial": 25},
        "interest": {"R": 15, "I": 20, "A": 30, "S": 60, "E": 90, "C": 35},
    },
    "Business Development": {
        "ability": {"numerical": 60, "verbal": 80, "logical": 65, "spatial": 30},
        "interest": {"R": 10, "I": 40, "A": 35, "S": 60, "E": 85, "C": 40},
    },
}
DEFAULT_PROFILE = {
    "ability": {"numerical": 55, "verbal": 60, "logical": 60, "spatial": 40},
    "interest": {"R": 30, "I": 40, "A": 30, "S": 50, "E": 50, "C": 50},
}

# Title keywords nudge the category profile (e.g. a Manager role leans more Enterprising).
_TITLE_ADJUSTMENTS = [
    (("manager", "director", "lead", "head", "partner", "vice president"),
     {"interest": {"E": 10, "S": 5}, "ability": {"verbal": 5}}),
    (("analyst", "analysis", "financial"),
     {"interest": {"I": 15, "C": 5}, "ability": {"numerical": 10, "logical": 5}}),
    (("coordinator", "administrator", "assistant", "accounting"),
     {"interest": {"C": 15}, "ability": {}}),
    (("technician", "support", "system administrator"),
     {"interest": {"R": 20, "C": 5}, "ability": {"logical": 5}}),
    (("project",),
     {"interest": {"C": 10, "E": 5}, "ability": {"logical": 5}}),
    (("representative", "retail", "seasonal", "salesperson", "center"),
     {"interest": {"S": 10, "E": 5}, "ability": {"verbal": 5}}),
    (("intern",),
     {"interest": {}, "ability": {"numerical": -10, "logical": -10, "verbal": -10}}),
]


def career_profile(title: str, category: str):
    base = CATEGORY_PROFILES.get(category, DEFAULT_PROFILE)
    ability = dict(base["ability"])
    interest = dict(base["interest"])
    t = (title or "").lower()
    for keywords, adj in _TITLE_ADJUSTMENTS:
        if any(k in t for k in keywords):
            for k, v in adj["ability"].items():
                ability[k] = max(0, min(100, ability[k] + v))
            for k, v in adj["interest"].items():
                interest[k] = max(0, min(100, interest[k] + v))
    return {"ability": ability, "interest": interest}


def _ability_fit(user: dict, req: dict) -> float:
    """1.0 when the user meets every requirement; drops with each shortfall."""
    weights = {a: req[a] for a in ABILITIES}
    wsum = sum(weights.values()) or 1
    shortfall = sum(max(0, req[a] - user[a]) * weights[a] for a in ABILITIES) / wsum
    return max(0.0, 1 - shortfall / 100 * 2.2)


def _interest_fit(user: dict, prof: dict) -> float:
    diff = sum(abs(user[d] - prof[d]) for d in INTERESTS) / (len(INTERESTS) * 100)
    return max(0.0, 1 - diff * 2.4)


def _reasons(abilities, interests, prof):
    reasons = []
    top_interest = sorted(
        INTERESTS, key=lambda d: (min(interests[d], prof["interest"][d]) if prof["interest"][d] >= 50 else -1),
        reverse=True,
    )
    for d in top_interest[:2]:
        if prof["interest"][d] >= 50 and interests[d] >= 50:
            reasons.append(f"Your {INTEREST_LABELS[d].lower()} interest ({interests[d]}) fits this role ({INTEREST_HINTS[d]})")
    strong = [a for a in ABILITIES if prof["ability"][a] >= 55 and abilities[a] >= prof["ability"][a]]
    strong.sort(key=lambda a: prof["ability"][a], reverse=True)
    for a in strong[:2]:
        reasons.append(f"{ABILITY_LABELS[a]} score {abilities[a]} meets the level this role needs")
    gaps = [a for a in ABILITIES if abilities[a] < prof["ability"][a] - 10]
    gaps.sort(key=lambda a: prof["ability"][a] - abilities[a], reverse=True)
    return reasons[:3], [ABILITY_LABELS[a] for a in gaps[:2]]


def recommend_careers(abilities: dict, interests: dict, careers: list, top_n: int = 8, per_field: int = 4):
    """
    careers: list of dicts with title, category, job_growth, automation_risk, ...
    Score = 50% ability fit + 50% interest fit, returned 0-100.
    Returns (careers, fields): the best `top_n` roles (at most `per_field` from one
    field so the list isn't one category), and a ranking of the fields themselves.
    """
    scored = []
    for c in careers:
        title = c.get("title") or ""
        if title.lower().startswith("of "):      # malformed source titles, e.g. "Of Finance"
            continue
        prof = career_profile(title, c.get("category"))
        a_fit = _ability_fit(abilities, prof["ability"])
        i_fit = _interest_fit(interests, prof["interest"])
        reasons, gaps = _reasons(abilities, interests, prof)
        scored.append({
            "title": title,
            "category": c.get("category"),
            "job_growth": c.get("job_growth"),
            "automation_risk": c.get("automation_risk"),
            "match_score": round((0.5 * a_fit + 0.5 * i_fit) * 100),
            "ability_fit": round(a_fit * 100),
            "interest_fit": round(i_fit * 100),
            "reasons": reasons,
            "grow_areas": gaps,
        })
    scored.sort(key=lambda r: r["match_score"], reverse=True)

    picked, per = [], {}
    for r in scored:
        if per.get(r["category"], 0) >= per_field:
            continue
        per[r["category"]] = per.get(r["category"], 0) + 1
        picked.append(r)
        if len(picked) >= top_n:
            break

    by_field = {}
    for r in scored:
        by_field.setdefault(r["category"], []).append(r["match_score"])
    fields = sorted(
        ({"field": f, "match_score": round(sum(sorted(v, reverse=True)[:3]) / len(v[:3]))}
         for f, v in by_field.items()),
        key=lambda x: x["match_score"], reverse=True,
    )
    return picked, fields
