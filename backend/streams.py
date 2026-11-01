"""
Educational stream definitions.

Lets a student pick their stream (MCA, MBA, MA, BSc, LLB, ...) on signup/
profile. This is used to:
 1. Give brand-new users (no skills entered yet) a relevant starting point -
    career suggestions filtered to categories that fit their stream.
 2. Give a small relevance boost to careers in matching categories once the
    skill-based recommender runs, so a Fine Arts MA student doesn't see
    "Business Development Manager" out-rank "Content Writer" just because
    of overlapping soft skills.

This is intentionally a light-touch signal, not a hard filter: the
skill-based match score always remains the primary driver. A student can
always add skills outside their stream's usual categories and see careers
in any category.
"""

STREAMS = {
    "MCA":         ("MCA (Computer Applications)",    ["Information Technology"]),
    "BCA":         ("BCA (Computer Applications)",    ["Information Technology"]),
    "BTECH_CS_IT": ("B.Tech / B.E. (CS / IT)",        ["Information Technology"]),
    "MBA":         ("MBA",                            ["Business Development", "Sales", "HR", "Finance"]),
    "BBA":         ("BBA",                            ["Business Development", "Sales"]),
    "BCOM_MCOM":   ("B.Com / M.Com",                  ["Finance"]),
    "CA_CS":       ("CA / CS / CMA",                  ["Finance"]),
    "OTHER":       ("Other / Diploma / Not listed",   []),
}
 

def stream_options():
    """List of {value, label} for the frontend dropdown."""
    return [{"value": key, "label": label} for key, (label, _) in STREAMS.items()]


def categories_for_stream(stream_key):
    """Career `category` values relevant to a given stream key. [] if unknown/none."""
    entry = STREAMS.get((stream_key or "").strip().upper())
    return entry[1] if entry else []
