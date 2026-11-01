import pandas as pd

from ml.aptitude_test import _ABILITY_BANK, _INTEREST_BANK, CATEGORY_PROFILES


def verify_cleaned_data():
    careers = pd.read_csv("data/careers.csv")
    skills = pd.read_csv("data/skills.csv")

    print("=== DATA QUALITY & CLEANLINESS REPORT ===")

    # Check 1: Missing values
    assert careers.isnull().sum()["title"] == 0, "Null values found in career titles!"
    assert skills.isnull().sum()["skill_name"] == 0, "Null values found in skills!"
    print("✔ Check 1 Passed: no missing career titles or skill names.")

    # Check 2: Uniqueness
    assert careers["title"].is_unique, "Duplicate career titles exist!"
    assert skills["skill_name"].is_unique, "Duplicate skill names exist!"
    print(f"✔ Check 2 Passed: unique titles ({len(careers)} careers, {len(skills)} skills).")

    # Check 3: Aptitude test integrity
    ids = [q[0] for q in _ABILITY_BANK] + [q[0] for q in _INTEREST_BANK]
    assert len(ids) == len(set(ids)), "Duplicate question ids!"
    assert all(0 <= q[4] < len(q[3]) for q in _ABILITY_BANK), "Answer index out of range!"
    missing = set(careers["category"]) - set(CATEGORY_PROFILES)
    assert not missing, f"Careers in categories with no aptitude profile: {missing}"
    print(f"✔ Check 3 Passed: {len(_ABILITY_BANK)} ability + {len(_INTEREST_BANK)} interest questions; "
          f"every career category has an aptitude profile.")

    print("\n🎉 ALL CHECKS PASSED: DATASET IS CLEAN AND VERIFIED!")


if __name__ == "__main__":
    verify_cleaned_data()
