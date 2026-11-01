"""
AI Career Assistant.

A rule-based assistant that answers from the student's own data (skills, stream,
courses, aptitude result) and from the careers / courses tables. It understands
~25 kinds of questions and can also pick up a career title or a skill name
inside the message ("salary of a Data Scientist", "courses for Python").

Each reply comes back with follow-up suggestions so the chat always has a
natural next question to click.
"""
import json
import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from database.db import get_db
from ml.recommend import recommend_careers, stream_only_suggestions
from ml.skill_gap import analyze_skill_gap
from ml.automation_risk import risk_label, estimate_automation_risk, _keyword_adjustment
from ml.families import career_family
from streams import STREAMS, categories_for_stream

chatbot_bp = Blueprint("chatbot", __name__)

DEFAULT_SUGGESTIONS = [
    "What career is best for me?",
    "What should I learn next?",
    "Show me a roadmap",
    "Which courses should I take?",
    "How am I doing?",
    "What are the highest paying careers?",
]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#. ]", " ", (text or "").lower())).strip()


def _salary(value):
    try:
        return f"{float(value):g} LPA"
    except (TypeError, ValueError):
        return f"{value} LPA" if value else "not available"


def _salary_num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _skills_of(career):
    return [s.strip() for s in (career.get("required_skills") or "").split(",") if s.strip()]


def _a(title):
    """'a Data Scientist' / 'an Analyst' (cosmetic, for follow-up chips)."""
    return ("an " if (title or "").strip()[:1].lower() in "aeiou" else "a ") + title


_GENERIC = {"", "me", "my job", "this job", "that job", "the job", "it", "my career", "jobs", "my work",
            "automation", "ai", "robots", "technology", "machines", "chatgpt"}


def _phrase_after(msg, pattern):
    """Free text the user typed after e.g. 'tell me about' / 'replace' (normalised), or ''."""
    m = re.search(pattern, msg)
    if not m:
        return ""
    phrase = re.sub(r"\b(job|jobs|role|career|profession|work|in future|soon|someday)\b", " ", m.group(1))
    phrase = re.sub(r"^(from|by|to|with|for|become|be)\s+", "", phrase.strip())
    phrase = re.sub(r"^(an?|the|my)\s+", "", phrase)
    phrase = re.sub(r"\s+", " ", phrase).strip()
    return "" if phrase in _GENERIC else phrase


def _bullets(items):
    return "\n".join(f"• {i}" for i in items)


class Ctx:
    """Everything a handler may need, loaded lazily so cheap questions stay cheap."""

    def __init__(self, db, user_id, message):
        self.db = db
        self.user_id = user_id
        self.message = message
        self.msg = _norm(message)
        self._cache = {}

    def _memo(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    @property
    def user(self):
        return self._memo("user", lambda: self.db.execute(
            "SELECT * FROM users WHERE id = ?", (self.user_id,)).fetchone())

    @property
    def first_name(self):
        name = (self.user["name"] if self.user else "") or ""
        return name.split()[0] if name.strip() else "there"

    @property
    def skill_rows(self):
        return self._memo("skill_rows", lambda: [dict(r) for r in self.db.execute(
            "SELECT skill_name, proficiency, verified FROM user_skills WHERE user_id = ?",
            (self.user_id,)).fetchall()])

    @property
    def skills(self):
        return {r["skill_name"]: r["proficiency"] for r in self.skill_rows}

    @property
    def careers(self):
        return self._memo("careers", lambda: [dict(r) for r in self.db.execute(
            "SELECT * FROM careers").fetchall()])

    @property
    def stream_categories(self):
        return categories_for_stream(self.user["stream"] if self.user else None)

    @property
    def recs(self):
        def build():
            if self.skills:
                return recommend_careers(self.skills, self.careers, top_n=5,
                                         stream_categories=self.stream_categories)
            if self.stream_categories:
                return stream_only_suggestions(self.careers, self.stream_categories, top_n=5)
            return []
        return self._memo("recs", build)

    @property
    def top(self):
        return self.recs[0] if self.recs else None

    # ---- mention detection ------------------------------------------------ #
    def mentioned_careers(self, limit=2):
        """Careers whose title appears in the message, longest title first, no overlaps."""
        padded = f" {self.msg} "
        hits = []
        for c in self.careers:
            t = _norm(c["title"])
            if t and f" {t} " in padded:
                hits.append((len(t), t, c))
        hits.sort(key=lambda h: -h[0])
        chosen = []
        for _, t, c in hits:
            if any(t in other for other, _c in chosen):
                continue
            chosen.append((t, c))
            if len(chosen) == limit:
                break
        return [c for _, c in chosen]

    def similar_careers(self, phrase, limit=3):
        """Distinct careers sharing a word with a free-text role the user typed."""
        words = {w for w in phrase.split() if len(w) > 2}
        scored = []
        for c in self.careers:
            overlap = len(words & set(_norm(c["title"]).split()))
            if overlap:
                scored.append((overlap, -len(c["title"]), c))
        scored.sort(key=lambda x: (-x[0], x[1]))
        out, seen = [], set()
        for _, _, c in scored:
            fam = career_family(c["title"])
            if fam not in seen:
                seen.add(fam)
                out.append(c)
            if len(out) == limit:
                break
        return out

    def mentioned_skill(self):
        """A skill/topic from the courses table or the user's own skills named in the message."""
        padded = f" {self.msg} "
        tags = {r[0] for r in self.db.execute(
            "SELECT DISTINCT skill_tag FROM courses WHERE skill_tag IS NOT NULL").fetchall()}
        tags |= set(self.skills.keys())
        best = None
        for tag in tags:
            t = _norm(tag)
            if len(t) >= 2 and f" {t} " in padded and (best is None or len(t) > len(_norm(best))):
                best = tag
        return best

    def target_career(self):
        """The career the question is about: one named in the message, otherwise the top match."""
        named = self.mentioned_careers(limit=1)
        if named:
            return named[0], True
        return self.top, False

    def gap_for(self, career):
        return analyze_skill_gap(self.skills, _skills_of(career))


def _need_profile(ctx):
    return ("I don't have any skills or stream on your profile yet, so I can't personalise this. "
            "Add a few skills on your Profile page (or pick your stream) and ask me again!")


# --------------------------------------------------------------------------- #
# handlers: each returns (reply, follow_up_suggestions)
# --------------------------------------------------------------------------- #
def _unknown_role_reply(ctx, phrase):
    """Honest answer when the user names a role that isn't in the careers table."""
    close = ctx.similar_careers(phrase)
    if close:
        return (f"I couldn't find a career called \"{phrase}\". Closest matches: "
                + ", ".join(c["title"] for c in close) + ".",
                [f"Tell me about {c['title']}" for c in close[:3]])
    return (f"I couldn't find a career called \"{phrase}\" in my data. Try \"Show my top careers\" "
            "or ask about a specific role like Data Scientist."), ["Show my top careers", "Highest paying careers"]


def h_greeting(ctx):
    return (f"Hi {ctx.first_name}! 👋 I'm your career assistant. I can suggest careers, find your "
            "skill gaps, build a roadmap, recommend courses and more. What would you like to know?",
            DEFAULT_SUGGESTIONS[:4])


def h_thanks(ctx):
    return ("You're welcome! Keep going - small, steady progress adds up. "
            "Anything else you'd like to know?", DEFAULT_SUGGESTIONS[:3])


def h_help(ctx):
    return ("Here's what you can ask me:\n" + _bullets([
        "Career advice - \"What career is best for me?\", \"Show my top careers\"",
        "Skills - \"What should I learn next?\", \"What are my skills?\", \"What are my weak skills?\"",
        "Careers by name - \"Tell me about Data Scientist\", \"Compare Data Analyst vs Data Scientist\"",
        "Money & demand - \"Salary of a Software Engineer\", \"Highest paying careers\", \"Is it in demand?\"",
        "Plans - \"Roadmap to become a Data Scientist\", \"Which courses should I take?\"",
        "Progress - \"How am I doing?\", \"Verify my skills\", \"Aptitude test results\"",
        "Job hunt - resume tips, interview tips, portfolio ideas, internships",
        "AI & the future - \"Will AI replace this job?\"",
    ]), ["What career is best for me?", "What should I learn next?", "Resume tips"])


def h_best_career(ctx):
    if not ctx.recs:
        return _need_profile(ctx), ["What can you do?"]
    top = ctx.top
    others = [r["title"] for r in ctx.recs[1:3]]
    note = "" if ctx.skills else (" (based on your stream - add skills for a personalised match)")
    match = f" ({top['match_score']}% match)" if ctx.skills else ""
    reply = f"{top['title']} looks like your best fit right now{match}{note}."
    if others:
        reply += " Other strong options: " + ", ".join(others) + "."
    reply += f" It typically pays around {_salary(top.get('avg_salary_lpa'))} with {str(top.get('job_growth') or 'steady').lower()} job growth."
    return reply, [f"Roadmap to become {_a(top['title'])}", "What should I learn next?", "Show my top careers"]


def h_top_careers(ctx):
    if not ctx.recs:
        return _need_profile(ctx), ["What can you do?"]
    pct = (lambda r: f"{r['match_score']}% - ") if ctx.skills else (lambda r: "")
    lines = [f"{i}. {r['title']} - {pct(r)}{_salary(r.get('avg_salary_lpa'))}, "
             f"{str(r.get('job_growth') or 'n/a').lower()} growth" for i, r in enumerate(ctx.recs, 1)]
    head = ("Your top career matches:" if ctx.skills
            else "Careers that fit your stream (add skills for a personalised match):")
    return (head + "\n" + "\n".join(lines),
            [f"Tell me about {ctx.recs[0]['title']}", "Compare my top two careers", "What should I learn next?"])


def h_compare(ctx):
    found = ctx.mentioned_careers(limit=2)
    if len(found) < 2 and re.search(r"top two|top 2|my top|my careers", ctx.msg) and len(ctx.recs) >= 2:
        found = ctx.recs[:2]
    if len(found) < 2:
        return ("Tell me the two careers to compare, e.g. \"Compare Data Analyst vs Data Scientist\".",
                ["Show my top careers"])
    a, b = found
    rows = []
    for c in (a, b):
        req = _skills_of(c)
        extra = ""
        if ctx.skills:
            g = ctx.gap_for(c)
            extra = f", you already cover {g['overall_skill_percent']}% of its skills"
        rows.append(f"{c['title']}: {_salary(c.get('avg_salary_lpa'))}, "
                    f"{str(c.get('job_growth') or 'n/a').lower()} growth, "
                    f"{c.get('automation_risk', 'n/a')}% automation risk{extra}. "
                    f"Key skills: {', '.join(req[:4])}.")
    return ("\n\n".join(rows),
            [f"Roadmap to become {_a(a['title'])}", f"Roadmap to become {_a(b['title'])}"])


def h_gap(ctx):
    career, named = ctx.target_career()
    if not career:
        return _need_profile(ctx), ["What can you do?"]
    if not ctx.skills:
        req = _skills_of(career)
        return (f"For {career['title']} the key skills are: {', '.join(req[:6])}. "
                "Add the ones you already know to your profile and I'll show your exact gap."), ["Which courses should I take?"]
    g = ctx.gap_for(career)
    missing = [s["skill"] for s in g["missing"]]
    partial = [s["skill"] for s in g["partial"]]
    if not missing and not partial:
        return (f"You already cover every key skill for {career['title']}! "
                "Focus on real projects and a portfolio now."), ["Portfolio ideas", "Interview tips"]
    parts = [f"For {career['title']} you cover about {g['overall_skill_percent']}% of the required skills."]
    if missing:
        parts.append("Learn next: " + ", ".join(missing[:4]) + ".")
    if partial:
        parts.append("Strengthen: " + ", ".join(partial[:3]) + ".")
    return " ".join(parts), ["Which courses should I take?", f"Roadmap to become {_a(career['title'])}", "Verify my skills"]


def h_my_skills(ctx):
    if not ctx.skill_rows:
        return ("You haven't added any skills yet. Add them on your Profile page and I can analyse your strengths.",
                ["What should I learn next?"])
    rows = sorted(ctx.skill_rows, key=lambda r: -r["proficiency"])
    top = [f"{r['skill_name']} ({r['proficiency']}%{', verified' if r.get('verified') else ''})" for r in rows[:6]]
    verified = sum(1 for r in rows if r.get("verified"))
    return (f"You have {len(rows)} skill{'s' if len(rows) != 1 else ''} on your profile, {verified} verified. "
            "Strongest: " + ", ".join(top) + ".",
            ["What are my weak skills?", "Verify my skills", "What should I learn next?"])


def h_improve(ctx):
    weak = sorted([r for r in ctx.skill_rows if r["proficiency"] < 60], key=lambda r: r["proficiency"])
    career = ctx.top
    if not ctx.skill_rows:
        return ("Add a few skills first and I'll point out which ones to level up.", ["What can you do?"])
    out = []
    if weak:
        out.append("Skills under 60%: " + ", ".join(f"{r['skill_name']} ({r['proficiency']}%)" for r in weak[:4]) + ".")
    if career:
        g = ctx.gap_for(career)
        if g["partial"]:
            out.append(f"For {career['title']}, level up: " + ", ".join(s["skill"] for s in g["partial"][:3]) + ".")
    if not out:
        out.append("All your skills are at 60% or above - great! Go deeper with projects, then verify them with a skill test.")
    out.append("Tip: practise on a small real task, then take the skill test to prove it.")
    return " ".join(out), ["Which courses should I take?", "Verify my skills"]


def h_salary(ctx):
    career, named = ctx.target_career()
    if not career:
        return _need_profile(ctx), ["What are the highest paying careers?"]
    reply = (f"{career['title']} roles typically pay around {_salary(career.get('avg_salary_lpa'))} in India, "
             "depending on experience, city and company.")
    if not named and not ctx.skills:
        reply += " (Based on your stream - add skills for a closer match.)"
    return reply, ["What are the highest paying careers?", f"Is {career['title']} in demand?", f"Roadmap to become {_a(career['title'])}"]


def h_top_paying(ctx):
    best = {}
    for c in ctx.careers:
        fam = career_family(c["title"])
        if fam not in best or _salary_num(c.get("avg_salary_lpa")) > _salary_num(best[fam].get("avg_salary_lpa")):
            best[fam] = c
    pool = list(best.values())
    if ctx.stream_categories and re.search(r"my stream|my field|for me", ctx.msg):
        pool = [c for c in pool if c.get("category") in ctx.stream_categories] or pool
    pool.sort(key=lambda c: -_salary_num(c.get("avg_salary_lpa")))
    lines = [f"{i}. {c['title']} - {_salary(c.get('avg_salary_lpa'))} ({c.get('category', 'General')})"
             for i, c in enumerate(pool[:5], 1)]
    return ("Highest paying careers in our data:\n" + "\n".join(lines),
            [f"Roadmap to become {_a(pool[0]['title'])}", "What career is best for me?"] if pool else DEFAULT_SUGGESTIONS[:2])


def h_growth(ctx):
    career, named = ctx.target_career()
    if career:
        growth = str(career.get("job_growth") or "steady")
        meaning = {"high": "demand is rising quickly, so hiring should stay strong",
                   "medium": "demand is steady with healthy openings",
                   "low": "openings are limited, so standout skills and projects matter more"}.get(growth.lower(), "demand is steady")
        return (f"{career['title']} has {growth.lower()} job growth - {meaning}.",
                [f"Salary of {_a(career['title'])}", f"Roadmap to become {_a(career['title'])}", "Will AI replace this job?"])
    high = [c["title"] for c in ctx.careers if str(c.get("job_growth")).lower() == "high"]
    seen, uniq = set(), []
    for t in high:
        fam = career_family(t)
        if fam not in seen:
            seen.add(fam)
            uniq.append(t)
    return ("Fast-growing careers include: " + ", ".join(uniq[:5]) + ".", ["What career is best for me?"])


def h_roadmap(ctx):
    career, named = ctx.target_career()
    if not named:
        phrase = _phrase_after(ctx.msg, r"(?:become|path to|roadmap (?:to|for))\s+(?:an?\s+|the\s+)?(.+)$")
        if phrase and phrase not in {"best", "roadmap"}:
            return _unknown_role_reply(ctx, phrase)
    if not career:
        return _need_profile(ctx), ["What can you do?"]
    req = _skills_of(career)
    if ctx.skills:
        g = ctx.gap_for(career)
        missing = [s["skill"] for s in g["missing"]] or req[:2]
        partial = [s["skill"] for s in g["partial"]]
    else:
        missing, partial = req[:4], []
    stage1 = ", ".join(missing[:2]) or "the core fundamentals"
    stage2 = ", ".join((missing[2:4] + partial[:2]) or req[2:4])
    reply = (f"Roadmap to {career['title']}:\n"
             f"1. Months 0-3 - build foundations: {stage1}.\n"
             f"2. Months 3-6 - go deeper: {stage2 or 'practise what you learned on small exercises'}.\n"
             "3. Months 6-12 - apply it: 2-3 real projects, then verify your skills with skill tests.\n"
             "4. 12+ months - polish your portfolio and resume, then apply for internships and jobs.")
    return reply, ["Which courses should I take?", "Portfolio ideas", "Resume tips"]


def h_courses(ctx):
    skill = ctx.mentioned_skill()
    names, label = [], ""
    if skill:
        names, label = [skill], f"for {skill}"
    else:
        career, _ = ctx.target_career()
        if career and ctx.skills:
            g = ctx.gap_for(career)
            names = [s["skill"] for s in g["missing"] + g["partial"]]
            label = f"to close your gap for {career['title']}"
        elif career:
            names = _skills_of(career)[:6]
            label = f"for {career['title']}"
    rows = []
    if names:
        ph = ",".join("?" for _ in names)
        rows = ctx.db.execute(
            f"SELECT title, level, rating, skill_tag FROM courses WHERE LOWER(skill_tag) IN ({ph}) "
            "ORDER BY rating DESC LIMIT 4", [n.lower() for n in names]).fetchall()
    if not rows:
        rows = ctx.db.execute("SELECT title, level, rating, skill_tag FROM courses ORDER BY rating DESC LIMIT 4").fetchall()
        label = "(top rated overall)"
    lines = [f"{r['title']} - {r['level']}, rated {r['rating']}" for r in rows]
    return (f"Courses {label}:\n" + _bullets(lines) + "\nOpen the Courses page to start - passing the assessment adds the skill to your profile.",
            ["What should I learn next?", "How am I doing?"])


def h_progress(ctx):
    done = ctx.db.execute("SELECT COUNT(*) c FROM user_courses WHERE user_id=? AND status='completed'", (ctx.user_id,)).fetchone()["c"]
    learned = sum(1 for r in ctx.skill_rows if r["proficiency"] >= 50)
    ready = min(round((learned * 5 + done * 5) / 2), 100)
    active = ctx.db.execute(
        "SELECT c.title, uc.watch_percent FROM user_courses uc JOIN courses c ON c.id = uc.course_id "
        "WHERE uc.user_id=? AND uc.status='in_progress' ORDER BY uc.started_at DESC LIMIT 2", (ctx.user_id,)).fetchall()
    reply = (f"You've completed {done} course{'s' if done != 1 else ''} and have {learned} skill"
             f"{'s' if learned != 1 else ''} at 50%+. Career readiness: {ready}%.")
    if active:
        reply += " In progress: " + ", ".join(f"{a['title']} ({round(a['watch_percent'] or 0)}% watched)" for a in active) + "."
    elif not done:
        reply += " You haven't started a course yet - pick one to get going!"
    return reply, ["Which courses should I take?", "What should I learn next?"]


def h_automation(ctx):
    career, named = ctx.target_career()
    if not named:
        phrase = _phrase_after(ctx.msg, r"(?:replace|replaced|replacing|automate|automated|automating|safe)\s+(?:an?\s+|the\s+|my\s+)?(.+)$")
        if phrase:
            risk, matched = estimate_automation_risk(phrase, ctx.careers)
            if matched and not (_norm(matched) in phrase or phrase in _norm(matched)):
                risk, matched = max(5, min(95, 50 + _keyword_adjustment(phrase))), None   # weak match: use title keywords
            if risk is not None:
                label = risk_label(risk)
                basis = f" (closest match: {matched})" if matched else " (estimated from the job title)"
                return (f"A \"{phrase}\" role has roughly {risk}% automation risk - {label}{basis}. "
                        "Routine, rule-based tasks are most exposed; judgment, creativity and people skills are safest.",
                        ["What should I learn next?", "What career is best for me?"])
    if not career or career.get("automation_risk") is None:
        return ("I need a career to check - ask e.g. \"Will AI replace a Data Entry Clerk?\" "
                "or add skills so I can use your top match."), ["What career is best for me?"]
    risk = int(career["automation_risk"])
    label = risk_label(risk)
    advice = {"High": "Routine tasks are exposed, so build skills that need judgment, creativity or people skills.",
              "Moderate": "Parts of the job may be automated; learning to work alongside AI tools will keep you ahead.",
              "Low": "This role relies on judgment and people skills, which are hard to automate."}[label]
    return (f"{career['title']} has about {risk}% automation risk ({label}). {advice}",
            ["What should I learn next?", "What career is best for me?"])


def h_career_info(ctx):
    career, named = ctx.target_career()
    if not named:
        phrase = _phrase_after(ctx.msg, r"(?:tell me about|what is|what does|describe|about)\s+(?:an?\s+|the\s+)?(.+)$")
        if phrase:
            return _unknown_role_reply(ctx, phrase)
    if not career:
        return _need_profile(ctx), ["What can you do?"]
    req = _skills_of(career)
    desc = (career.get("description") or "").split(". (")[0]
    reply = (f"{career['title']} ({career.get('category', 'General')}): {desc}\n"
             f"• Salary: about {_salary(career.get('avg_salary_lpa'))}\n"
             f"• Job growth: {career.get('job_growth', 'n/a')}\n"
             f"• Key skills: {', '.join(req[:6])}")
    if ctx.skills:
        reply += f"\n• You already cover about {ctx.gap_for(career)['overall_skill_percent']}% of these skills"
    return reply, [f"Roadmap to become {_a(career['title'])}", f"Salary of {_a(career['title'])}", f"Will AI replace {_a(career['title'])}?"]


def h_aptitude(ctx):
    row = ctx.db.execute(
        "SELECT interest_code, top_matches, created_at FROM aptitude_test_results WHERE user_id=? "
        "ORDER BY created_at DESC LIMIT 1", (ctx.user_id,)).fetchone()
    if not row:
        return ("You haven't taken the aptitude test yet. It measures your abilities and interests and suggests "
                "roles that suit you - find it in the sidebar."), ["What career is best for me?"]
    titles = []
    try:
        for m in json.loads(row["top_matches"] or "[]")[:3]:
            titles.append(m if isinstance(m, str) else m.get("title") or m.get("career") or "")
    except (ValueError, AttributeError, TypeError):
        pass
    titles = [t for t in titles if t]
    reply = f"Your aptitude interest code is {row['interest_code'] or 'n/a'}."
    if titles:
        reply += " It points to: " + ", ".join(titles) + "."
    return reply, ["What career is best for me?", "What should I learn next?"]


def h_verify(ctx):
    if not ctx.skill_rows:
        return ("Add skills to your profile first - then you can take a short test to verify each one.", ["What can you do?"])
    verified = [r["skill_name"] for r in ctx.skill_rows if r.get("verified")]
    pending = [r["skill_name"] for r in ctx.skill_rows if not r.get("verified")]
    reply = f"{len(verified)} of your {len(ctx.skill_rows)} skills are verified."
    if pending:
        reply += (" Not yet verified: " + ", ".join(pending[:5]) + ". Use \"Take test\" next to a skill on your Profile page - "
                  "pass it and the skill shows as verified to employers.")
    else:
        reply += " Nice - everything on your profile is proven!"
    return reply, ["What are my skills?", "What should I learn next?"]


def h_resume(ctx):
    career = ctx.top
    tips = ["Keep it to one page with a 2-line summary aimed at the role",
            "Lead with projects and results (numbers!) rather than duties",
            "Put verified skills near the top and mirror keywords from the job post",
            "Use a clean format, no photo or long paragraphs, and proofread twice"]
    reply = "Resume tips:\n" + _bullets(tips)
    if career:
        reply += f"\nFor {career['title']}, highlight: " + ", ".join(_skills_of(career)[:4]) + "."
    return reply, ["Interview tips", "Portfolio ideas"]


def h_interview(ctx):
    career = ctx.top
    tips = ["Research the company and the role the day before",
            "Prepare 2-3 stories using Situation - Task - Action - Result",
            "Practise explaining your projects in 2 minutes, simply",
            "Ask 2 thoughtful questions at the end"]
    reply = "Interview tips:\n" + _bullets(tips)
    if career:
        reply += f"\nFor {career['title']}, revise: " + ", ".join(_skills_of(career)[:4]) + "."
    return reply, ["Resume tips", "Portfolio ideas"]


def h_portfolio(ctx):
    career = ctx.top
    skills = _skills_of(career)[:3] if career else []
    ideas = ["Build one small project end-to-end and write a short README on what you learned",
             "Publish your work on GitHub (or a simple site) with screenshots",
             "Recreate a real-world problem you care about instead of copying a tutorial"]
    if len(skills) >= 2:
        ideas.insert(0, f"A project combining {skills[0]} and {skills[1]}"
                        + (f" for a {career['title']} role" if career else ""))
    return "Portfolio ideas:\n" + _bullets(ideas), ["Resume tips", "Interview tips"]


def h_soft(ctx):
    soft = [s for s in (_skills_of(ctx.top) if ctx.top else [])
            if re.search(r"communicat|team|leader|problem|adapt|negotiat|present|relationship|time", s.lower())]
    reply = ("Soft skills employers value: communication, teamwork, problem solving, adaptability and time management. "
             "Practise by presenting your projects, working in a group, and asking for feedback.")
    if soft:
        reply += f" Important for {ctx.top['title']}: " + ", ".join(soft[:4]) + "."
    return reply, ["Verify my skills", "What should I learn next?"]


def h_internship(ctx):
    career = ctx.top
    reply = ("For a first job or internship: build 2-3 projects, verify your skills, keep your profile and resume current, "
             "and apply widely (campus drives, LinkedIn, company career pages). Cold-message people for referrals - it works.")
    if career:
        reply += f" Target entry-level {career['title']} roles first."
    return reply, ["Resume tips", "Portfolio ideas", "Interview tips"]


def h_stream(ctx):
    key = (ctx.user["stream"] if ctx.user else None) or ""
    label = STREAMS.get(key.upper(), (None,))[0]
    if not label:
        return ("You haven't set your stream yet. Choose it on your Profile page so I can tailor suggestions.", ["What can you do?"])
    cats = ", ".join(ctx.stream_categories) or "all categories"
    return f"Your stream is {label}. Careers I weigh most for you: {cats}.", ["What career is best for me?", "Show my top careers"]


def h_confused(ctx):
    return ("It's completely normal to feel unsure - most people do. Try this: (1) take the aptitude test, "
            "(2) add your skills to your profile, (3) look at your top 3 matches and read about each. "
            "Then pick one and start a small course to test the waters.",
            ["What career is best for me?", "Aptitude test results", "Which courses should I take?"])


def h_fallback(ctx):
    named = ctx.mentioned_careers(limit=1)
    if named:
        return h_career_info(ctx)
    skill = ctx.mentioned_skill()
    if skill:
        return h_courses(ctx)
    return ("I'm not sure I got that. I can help with careers, skills, courses, salary, roadmaps, resumes and more - "
            "try one of these:", DEFAULT_SUGGESTIONS[:5])


# Order matters: the first matching pattern wins, so specific intents come first.
INTENTS = [
    (r"^\s*(hi+|hello+|hey+|good (morning|afternoon|evening)|namaste)\b", h_greeting),
    (r"\b(thanks|thank you|thx)\b", h_thanks),
    (r"what can you (do|help)|how can you help|your features|^\s*help\s*[!?.]*\s*$", h_help),
    (r"\b(compare|versus|difference between)\b|\bvs\b", h_compare),
    (r"automat|replace|will ai|ai take|job (safe|security)|future proof", h_automation),
    (r"(highest|best|top|most)[ -]?(paying|paid|salary|salaries)|high(est)? salary", h_top_paying),
    (r"salary|salaries|\bpay\b|\bearn|package|\bctc\b|\blpa\b|income", h_salary),
    (r"demand|growth|scope|job market|hiring|opportunit|trending|future of", h_growth),
    (r"roadmap|how (do|can|to) i become|how to become|\bsteps\b|path to|become an? |timeline|how long", h_roadmap),
    (r"\bcourses?\b|tutorial|resources?|where (can|do) i learn|study material|certification", h_courses),
    (r"progress|how am i doing|readiness|achievement|my stats|completed", h_progress),
    (r"aptitude|personality|riasec|interest code", h_aptitude),
    (r"verif|skill test|take (a )?test|prove my skill", h_verify),
    (r"my skills|skills do i have|what do i know|strengths?|strongest", h_my_skills),
    (r"improve|weak|partial|level up|get better|upskill", h_improve),
    (r"skill gap|missing skills?|skills? (do i|should i|to) (need|learn|have)|learn next|what should i learn|what to learn", h_gap),
    (r"resume|\bcv\b", h_resume),
    (r"interview", h_interview),
    (r"portfolio|projects?\b|github", h_portfolio),
    (r"soft skills?|communication skills?|teamwork", h_soft),
    (r"intern(ship)?|first job|fresher|no experience|entry[ -]level", h_internship),
    (r"my stream|my degree|my course of study|my field", h_stream),
    (r"confus|don.?t know|not sure|lost|stuck|which path|can.?t decide", h_confused),
    (r"top (\d+ )?careers?|my careers|other (options|careers)|alternatives|list careers|show (me )?careers", h_top_careers),
    (r"best career|career for me|which career|career is best|best for me|suggest|recommend|what should i (do|become)|which job", h_best_career),
    (r"tell me about|what is an? |what does|describe|about the role|job description", h_career_info),
]
_COMPILED = [(re.compile(p), fn) for p, fn in INTENTS]


def build_reply(message, user_id, db):
    ctx = Ctx(db, user_id, message)
    for pattern, handler in _COMPILED:
        if pattern.search(ctx.msg):
            return handler(ctx)
    return h_fallback(ctx)


# --------------------------------------------------------------------------- #
# routes
# --------------------------------------------------------------------------- #
@chatbot_bp.route("/message", methods=["POST"])
@jwt_required()
def send_message():
    user_id = get_jwt_identity()
    data = request.get_json(force=True)
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "message is required"}), 400
    message = message[:500]

    db = get_db()
    reply, suggestions = build_reply(message, user_id, db)

    db.execute("INSERT INTO chat_history (user_id, sender, message) VALUES (?, 'user', ?)", (user_id, message))
    db.execute("INSERT INTO chat_history (user_id, sender, message) VALUES (?, 'bot', ?)", (user_id, reply))
    db.commit()
    db.close()

    return jsonify({"reply": reply, "suggestions": suggestions[:4]})


@chatbot_bp.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    user_id = get_jwt_identity()
    db = get_db()
    rows = db.execute(
        "SELECT sender, message, created_at FROM chat_history WHERE user_id = ? ORDER BY created_at ASC, id ASC",
        (user_id,),
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@chatbot_bp.route("/clear", methods=["POST"])
@jwt_required()
def clear_history():
    user_id = get_jwt_identity()
    db = get_db()
    db.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    db.commit()
    db.close()
    return jsonify({"cleared": True})