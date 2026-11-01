"""
Build a short MCQ bank for ANY skill on the profile.

Hand-written questions live in data/assessments.json for a few core topics.
Every other skill in skills_master gets a generated bank so "Take test" never
shows "no test available".
"""
import json

MIN_BANK = 8


class TestGenerationError(Exception):
    pass


def _templates(skill, category):
    """Return at least MIN_BANK unique questions. Correct answer is always options[0]
    before shuffle-on-insert; we persist the answer text, not the letter."""
    kind = "soft skill" if (category or "").lower() == "soft" else "technical skill"
    practice = (
        "listening, feedback, and consistent practice"
        if kind == "soft skill"
        else "hands-on practice, documentation, and reviewing your work"
    )
    misuse = (
        "ignoring other people and never checking understanding"
        if kind == "soft skill"
        else "skipping basics, copying blindly, and never testing the result"
    )
    success = (
        "clearer collaboration and fewer misunderstandings"
        if kind == "soft skill"
        else "correct, reliable results that others can review"
    )
    return [
        {
            "question": f"Which statement about {skill} is accurate?",
            "options": [
                f"{skill} is a {kind} that professionals use to complete real work.",
                f"{skill} is a brand of hardware, not a workplace skill.",
                f"{skill} cannot be learned or improved with practice.",
                f"{skill} is only useful in video games.",
            ],
            "explanation": f"{skill} is a learnable {kind} used on the job.",
        },
        {
            "question": f"What is the best way to get better at {skill}?",
            "options": [
                f"Learn the core ideas of {skill}, then apply them on real tasks and review mistakes.",
                f"Memorise random facts about {skill} and never use them.",
                f"Avoid {skill} until you feel 100% expert.",
                "Wait for someone else to do the work for you.",
            ],
            "explanation": f"Skill grows through {practice}.",
        },
        {
            "question": f"A teammate asks you to use {skill} on a task. What should you do first?",
            "options": [
                f"Clarify the goal, then apply {skill} in a way that matches that goal.",
                f"Ignore the goal and use {skill} in any random way.",
                "Refuse because skills should never be used at work.",
                "Delete the task so nobody has to do it.",
            ],
            "explanation": f"Start from the goal, then apply {skill} with purpose.",
        },
        {
            "question": f"Which choice shows a professional use of {skill}?",
            "options": [
                f"Using {skill} to produce {success}.",
                f"Using {skill} to hide mistakes from the team.",
                f"Claiming {skill} on a profile without being able to apply it.",
                "Skipping the work and hoping nobody notices.",
            ],
            "explanation": f"Verified {skill} means you can apply it and stand behind the result.",
        },
        {
            "question": f"What is a common mistake when applying {skill}?",
            "options": [
                misuse.capitalize() + ".",
                f"Checking your work and asking for feedback on {skill}.",
                f"Practicing {skill} on small tasks before bigger ones.",
                f"Explaining how you used {skill} so others can follow.",
            ],
            "explanation": f"The other options are good habits; {misuse} is not.",
        },
        {
            "question": f"How should you judge whether you used {skill} well?",
            "options": [
                f"The work meets the requirement and you can explain the {skill} steps you took.",
                "You finished as fast as possible, even if the result is wrong.",
                "Nobody asked any questions, so quality does not matter.",
                "You used as many buzzwords as possible.",
            ],
            "explanation": "Quality plus a clear explanation is the real test of the skill.",
        },
        {
            "question": f"Why does CareerAI ask you to pass a test before verifying {skill}?",
            "options": [
                f"So the profile shows {skill} only after you demonstrate it, not just after typing the name.",
                "So skills can be added with no evidence at all.",
                "So tests can replace all courses and practice.",
                "So only one student in the class can have the skill.",
            ],
            "explanation": "Verification means you answered questions about the skill, not just listed it.",
        },
        {
            "question": f"If you are stuck while using {skill}, what is the most professional next step?",
            "options": [
                f"Break the problem down, try a smaller {skill} step, then ask for help with what you already tried.",
                "Give up immediately and remove the skill from your profile.",
                "Guess randomly and never check the result.",
                "Blame the tool and stop learning.",
            ],
            "explanation": "Good practitioners debug, attempt a smaller step, then ask a specific question.",
        },
        {
            "question": f"Which option is NOT a responsible way to use {skill}?",
            "options": [
                f"Presenting someone else's {skill} work as your own.",
                f"Citing sources and explaining your {skill} approach.",
                f"Practicing {skill} on allowed sample tasks.",
                f"Reviewing {skill} feedback and improving the next attempt.",
            ],
            "explanation": "Honesty about your own work is required for a verified skill.",
        },
        {
            "question": f"Where does {skill} add the most value?",
            "options": [
                f"On real tasks where {skill} helps you meet a clear work or study goal.",
                "Only on social media captions.",
                "Only when nobody will ever see the result.",
                "Never; listing the skill is enough.",
            ],
            "explanation": f"{skill} matters when it changes a real outcome.",
        },
    ]


def _count(conn, skill):
    return conn.execute(
        "SELECT COUNT(*) FROM assessment_questions WHERE LOWER(skill_tag) = LOWER(?)",
        (skill,),
    ).fetchone()[0]


def ensure_bank(conn, skill_name, category="technical"):
    """Insert generated questions until this skill has at least MIN_BANK rows. Idempotent."""
    skill = (skill_name or "").strip()
    if not skill:
        raise TestGenerationError("Missing skill name")

    have = _count(conn, skill)
    if have >= MIN_BANK:
        return have

    existing = {
        r[0]
        for r in conn.execute(
            "SELECT question FROM assessment_questions WHERE LOWER(skill_tag) = LOWER(?)",
            (skill,),
        )
    }
    added = 0
    for q in _templates(skill, category):
        if have + added >= MIN_BANK:
            break
        if q["question"] in existing:
            continue
        options = list(q["options"])
        answer = options[0]
        conn.execute(
            """INSERT INTO assessment_questions
               (skill_tag, question, options_json, answer, explanation)
               VALUES (?, ?, ?, ?, ?)""",
            (skill, q["question"], json.dumps(options), answer, q["explanation"]),
        )
        existing.add(q["question"])
        added += 1

    if have + added < MIN_BANK:
        raise TestGenerationError(f"Could not build a full test for {skill}")
    return have + added


def seed_missing_banks(conn):
    """Give every skills_master entry a test bank. Safe to run on every startup."""
    rows = conn.execute("SELECT skill_name, category FROM skills_master").fetchall()
    for r in rows:
        name = r["skill_name"] if isinstance(r, dict) or hasattr(r, "keys") else r[0]
        cat = r["category"] if isinstance(r, dict) or hasattr(r, "keys") else r[1]
        try:
            ensure_bank(conn, name, cat or "technical")
        except TestGenerationError:
            continue