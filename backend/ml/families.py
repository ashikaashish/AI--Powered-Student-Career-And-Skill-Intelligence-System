"""
Career-family grouping shared by training (ml/train_model.py) and scoring (ml/recommend.py).

The career files contain many near-identical titles ("Intern Data Scientist",
"Regional Inside Sales Representative", "Senior Data Scientist (Fintech)") that
need the same skills as the base role. The classifier predicts the career
FAMILY, so those variants are not counted as different answers.
"""
import os
import re
import sys

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_BASE, "data_pipeline"))
from load_jobs import base_title  # noqa: E402

_EXTRA_MODIFIERS = [
    r"\bintern(ship)?\b", r"\btrainee\b", r"\bregional\b", r"\bglobal\b",
    r"\bnational\b", r"\bgraduate\b", r"\bapprentice\b", r"\bsenior\b",
    r"\bsr\b", r"\bjr\b", r"\bmid level\b", r"\bentry level\b", r"\bnew\b",
]


# Phrases where a "modifier" word is really part of the role name.
_PROTECTED = {"lead generation": "leadgeneration", "account executive": "accountexecutive"}


def career_family(title: str) -> str:
    low = title.lower()
    for phrase, token in _PROTECTED.items():
        low = low.replace(phrase, token)
    t = base_title(low).lower()
    for phrase, token in _PROTECTED.items():
        t = t.replace(token, phrase)
    for pat in _EXTRA_MODIFIERS:
        t = re.sub(pat, " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.title() if t else title.strip()
