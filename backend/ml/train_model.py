"""
Trains the career-prediction model and reports its accuracy.

Model formulation
-----------------
  Input  : a student's skill-proficiency vector (0-100 per skill)
  Output : the predicted career FAMILY (e.g. "Data Scientist"), with a
           probability for every family
  Model  : Random Forest classifier (ensemble of decision trees; the
           predicted probability is the share of trees voting for a family)

How the model is used (ml/recommend.py)
---------------------------------------
  final match score = 0.6 x cosine similarity (student skills vs the career's
                      required skills) + 0.4 x Random Forest probability

Why career families?  careers.csv / careers_tech.csv contain many variants of
the same role ("Intern Data Scientist", "Senior Data Scientist (Fintech)").
They need the same skills, so they are grouped (ml/families.py) and the model
predicts the family. The recommender then ranks the individual titles.

Training data
-------------
  1. Real job postings (data/raw/all_job_post.csv) -> one row per posting.
  2. Synthetic student profiles generated around each career's required skills.

Evaluation: 80:20 stratified train/test split. Reported
  - accuracy, precision, recall and F1-score (weighted over all families),
  - accuracy as top-1 (exact family) and top-3 / top-5 (the app shows 5 careers),
  - overall, on the synthetic test rows, and on the REAL posting test rows.

Run with:  python ml/train_model.py
"""
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "data_pipeline"))
from ml.families import career_family  # noqa: E402
from load_jobs import parse_skill_list, normalize_skill  # noqa: E402

DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_JOBS_PATH = os.path.join(DATA_DIR, "raw", "all_job_post.csv")
MODEL_DIR = os.path.join(BASE_DIR, "ml", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

RANDOM_SEED = 42
N_TREES = 100          # number of decision trees in the forest
MIN_SAMPLES_LEAF = 1   # larger value = smaller/faster model file, slightly less detail
SAMPLES_PER_CAREER = 6
rng = np.random.default_rng(RANDOM_SEED)


def load_careers():
    frames = [pd.read_csv(os.path.join(DATA_DIR, f)) for f in ("careers.csv", "careers_tech.csv")]
    df = pd.concat(frames).drop_duplicates("title").reset_index(drop=True)
    df["family"] = df["title"].apply(career_family)
    df["skills"] = df["required_skills"].apply(lambda s: [x.strip() for x in s.split(",") if x.strip()])
    return df


def synthetic_rows(careers, all_skills):
    idx = {s: i for i, s in enumerate(all_skills)}
    X, y = [], []
    for _, c in careers.iterrows():
        block = np.clip(rng.normal(25, 20, (SAMPLES_PER_CAREER, len(all_skills))), 0, 70)
        for s in c["skills"]:
            block[:, idx[s]] = np.clip(rng.normal(75, 15, SAMPLES_PER_CAREER), 20, 100)
        X.append(block)
        y += [c["family"]] * SAMPLES_PER_CAREER
    return np.vstack(X), np.array(y)


def real_rows(families, all_skills):
    if not os.path.exists(RAW_JOBS_PATH):
        return np.empty((0, len(all_skills))), np.array([])
    idx = {s: i for i, s in enumerate(all_skills)}
    df = pd.read_csv(RAW_JOBS_PATH)
    df["family"] = df["job_title"].apply(career_family)
    df = df[df["family"].isin(families)]
    X = np.zeros((len(df), len(all_skills)))
    for r, skills in enumerate(df["job_skill_set"]):
        for s in parse_skill_list(skills):
            s = normalize_skill(s)
            if s in idx:
                X[r, idx[s]] = 100
    return X, df["family"].to_numpy()


def topk(model, X, y, k):
    p = model.predict_proba(X)
    top = np.argsort(-p, axis=1)[:, :k]
    return float(np.mean([y[i] in model.classes_[top[i]] for i in range(len(y))]))


def report(name, model, X, y):
    if len(y) == 0:
        return {}
    out = {"rows": int(len(y))}
    pred = model.predict(X)
    out["accuracy"] = round(float(accuracy_score(y, pred)), 4)
    out["precision"] = round(float(precision_score(y, pred, average="weighted", zero_division=0)), 4)
    out["recall"] = round(float(recall_score(y, pred, average="weighted", zero_division=0)), 4)
    out["f1"] = round(float(f1_score(y, pred, average="weighted", zero_division=0)), 4)
    for k in (1, 3, 5):
        out[f"top{k}"] = round(topk(model, X, y, k), 4)
    print(f"{name:<22} rows={out['rows']:<6} accuracy={out['accuracy']:.3f} precision={out['precision']:.3f} "
          f"recall={out['recall']:.3f} f1={out['f1']:.3f} | top-3={out['top3']:.3f} top-5={out['top5']:.3f}")
    return out


def main():
    careers = load_careers()
    all_skills = sorted({s for sk in careers["skills"] for s in sk})
    families = set(careers["family"])
    print(f"{len(careers)} careers -> {len(families)} career families, {len(all_skills)} skills")

    Xs, ys = synthetic_rows(careers, all_skills)
    Xr, yr = real_rows(families, all_skills)
    print(f"Synthetic rows: {len(ys)} | Real posting rows: {len(yr)}")

    # 80:20 stratified split, done separately so real rows are always in the test set too
    Xs_tr, Xs_te, ys_tr, ys_te = train_test_split(Xs, ys, test_size=0.2, random_state=RANDOM_SEED, stratify=ys)
    if len(yr):
        _, counts = np.unique(yr, return_counts=True)
        strat = yr if counts.min() >= 2 else None
        Xr_tr, Xr_te, yr_tr, yr_te = train_test_split(Xr, yr, test_size=0.2, random_state=RANDOM_SEED, stratify=strat)
    else:
        Xr_tr = Xr_te = np.empty((0, len(all_skills))); yr_tr = yr_te = np.array([])

    X_train = np.vstack([Xs_tr, Xr_tr]); y_train = np.concatenate([ys_tr, yr_tr])
    X_test = np.vstack([Xs_te, Xr_te]); y_test = np.concatenate([ys_te, yr_te])
    print(f"Train rows: {len(y_train)} | Test rows: {len(y_test)} (80:20 split)\n")

    model = RandomForestClassifier(
        n_estimators=N_TREES,
        min_samples_leaf=MIN_SAMPLES_LEAF,
        n_jobs=-1,
        random_state=RANDOM_SEED,
    )
    print("Training Random Forest (can take 1-3 minutes)...")
    model.fit(X_train, y_train)

    metrics = {
        "overall_test": report("Overall test set", model, X_test, y_test),
        "synthetic_test": report("Synthetic test rows", model, Xs_te, ys_te),
        "real_postings_test": report("Real posting rows", model, Xr_te, yr_te),
        "model": "RandomForestClassifier",
        "n_estimators": N_TREES,
        "min_samples_leaf": MIN_SAMPLES_LEAF,
        "families": len(families),
        "train_rows": int(len(y_train)),
        "test_rows": int(len(y_test)),
    }

    joblib.dump(model, os.path.join(MODEL_DIR, "career_predictor.pkl"), compress=3)
    joblib.dump(all_skills, os.path.join(MODEL_DIR, "skill_columns.pkl"))
    with open(os.path.join(MODEL_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    size = os.path.getsize(os.path.join(MODEL_DIR, "career_predictor.pkl")) / 1e6
    print(f"\nModel saved ({size:.2f} MB) + metrics.json in {MODEL_DIR}")


if __name__ == "__main__":
    main()
