"""
workspace.py — the two datasets ScamShield can run on.

  Dataset A  = DEMO. Our synthetic data (main raw log + the earlier profile dataset kept for comparison).
               Models in model/, data in data/.
  Dataset B  = YOUR DATA. Anyone's own transaction log. build_b() learns everything from that log and saves a
               complete, independent set of models in workspaces/B/, so the whole app and the API can run on it
               as a real model.

How Dataset B is built (build_b):
  1. Validate the log and compute point-in-time features from history (pipeline.py), same as for Dataset A.
  2. If the log has enough confirmed fraud labels (is_fraud), train a NEW classifier on the earlier 70% of
     the log and test it on the later 30% (the future). Otherwise keep the demo classifier and say so.
  3. Always fit a NEW anomaly model on this log (it needs no labels), so "unusual" means unusual for THIS data.
  4. Score every transfer, save everything; the mule network is computed from these scores and the log itself.

Command line:  python workspace.py path/to/your_log.csv
"""
import json
import os
import shutil
import sys

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, roc_auc_score

import pipeline as pl
import risk_engine as re_
from features import FEATURES

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_FRAUD_TRAIN, MIN_FRAUD_TEST = 20, 5


def paths(name: str) -> dict:
    if name == "A":
        return dict(raw=os.path.join(HERE, "data", "transactions_raw.csv"),
                    model=os.path.join(HERE, "model", "model.json"),
                    iforest=os.path.join(HERE, "model", "iforest.joblib"),
                    metrics=os.path.join(HERE, "model", "metrics.json"),
                    test=os.path.join(HERE, "data", "test_scored.parquet"),
                    scored=os.path.join(HERE, "data", "scored_all.parquet"),
                    labels=os.path.join(HERE, "data", "ground_truth.csv"))
    root = os.path.join(HERE, "workspaces", name)
    return dict(raw=os.path.join(root, "raw.csv"), model=os.path.join(root, "model.json"),
                iforest=os.path.join(root, "iforest.joblib"), metrics=os.path.join(root, "metrics.json"),
                test=os.path.join(root, "test_scored.parquet"), scored=os.path.join(root, "scored_all.parquet"),
                labels=None, root=root)


def read_log(path_or_file) -> pd.DataFrame:
    """Read a transaction log keeping every ID as text (phone-style wallet numbers keep their leading zeros)."""
    return pd.read_csv(path_or_file, dtype=str, keep_default_na=False, na_values=[""])


def exists(name: str) -> bool:
    p = paths(name)
    return all(os.path.exists(p[k]) for k in ("raw", "model", "iforest", "metrics", "test", "scored"))


def load_metrics(name: str) -> dict:
    with open(paths(name)["metrics"], encoding="utf-8") as f:
        return json.load(f)


def _stats(y, flagged, amounts):
    y, flagged = np.asarray(y).astype(int), np.asarray(flagged)
    tp = (flagged & (y == 1)).sum()
    return {"scam_recall": round(float(tp / max((y == 1).sum(), 1)), 3),
            "precision": round(float(tp / max(flagged.sum(), 1)), 3),
            "false_alarm_rate": round(float((flagged & (y == 0)).sum() / max((y == 0).sum(), 1)), 4),
            "scam_money_protected_pct": round(float(amounts[flagged & (y == 1)].sum() / max(amounts[y == 1].sum(), 1)), 3)}


def build_b(raw: pd.DataFrame, name: str = "B", progress=lambda msg: None) -> dict:
    """Learn everything from a user's own log and save it as workspace `name`. Returns the metrics dict."""
    problems = pl.validate(raw)
    if problems:
        raise ValueError("; ".join(problems))
    p = paths(name)
    os.makedirs(p["root"], exist_ok=True)
    progress("Computing point-in-time features from each customer's history...")
    feats, _ = pl.run(raw)
    feats = feats.sort_values("timestamp").reset_index(drop=True)
    has_labels = "is_fraud" in feats and feats.is_fraud.notna().sum() > 0
    cut_i = int(len(feats) * 0.7)
    cut_time = feats.timestamp.iloc[cut_i] if len(feats) > 10 else feats.timestamp.max()
    train, test = feats.iloc[:cut_i], feats.iloc[cut_i:]

    mode, note = "demo_classifier", "No fraud labels: the demo classifier is used; anomaly and network engines learn from your data."
    model = re_.load_model(paths("A")["model"])
    if has_labels:
        tr_l, te_l = train[train.is_fraud.notna()], test[test.is_fraud.notna()]
        if tr_l.is_fraud.sum() >= MIN_FRAUD_TRAIN and te_l.is_fraud.sum() >= MIN_FRAUD_TEST:
            progress("Training a new scam classifier on the earlier 70% of your log...")
            pos_w = (tr_l.is_fraud == 0).sum() / max(tr_l.is_fraud.sum(), 1)
            model = xgb.XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.08, subsample=0.9,
                                      colsample_bytree=0.9, scale_pos_weight=pos_w, eval_metric="aucpr", random_state=7)
            model.fit(tr_l[FEATURES], tr_l.is_fraud.astype(int))
            mode, note = "trained", "A new classifier was trained on your labelled data (earlier 70%) and tested on the later 30%."
        else:
            note = (f"Not enough fraud labels to train (need {MIN_FRAUD_TRAIN} in the earlier 70% and {MIN_FRAUD_TEST} in the "
                    "later 30%): the demo classifier is used; anomaly and network engines learn from your data.")
    model.save_model(p["model"])

    progress("Fitting the anomaly model on your data (no labels needed)...")
    iforest = re_.fit_iforest(train if len(train) > 200 else feats)
    joblib.dump(iforest, p["iforest"])

    progress("Scoring every transfer...")
    scored = re_.score_frame(model, iforest, feats)
    scored[["txn_id", "user_id", "recipient_id", "amount", "risk_score"]].to_parquet(p["scored"], index=False)
    q = scored.iloc[cut_i:] if mode == "trained" else scored
    q.sort_values("risk_score", ascending=False).to_parquet(p["test"], index=False)
    raw.to_csv(p["raw"], index=False)

    t = feats.timestamp
    metrics = {"dataset": name, "mode": mode, "note": note, "rows": int(len(feats)),
               "senders": int(feats.user_id.nunique()), "days": int((t.max() - t.min()).days),
               "split": (f"train: {t.min():%d %b %Y} to {cut_time:%d %b %Y}, test (future): {cut_time:%d %b %Y} to {t.max():%d %b %Y}"
                         if mode == "trained" else "no split (no training labels): all transfers scored"),
               "data_quality": pl.data_quality(raw),
               "thresholds": {"warn": re_.WARN_THRESHOLD, "hold": re_.HOLD_THRESHOLD, "anomaly": re_.ANOMALY_THRESHOLD},
               "feature_importance": {f: round(float(v), 4) for f, v in
                                      sorted(zip(FEATURES, model.feature_importances_), key=lambda x: -x[1])}}
    if mode == "trained":
        te = scored.iloc[cut_i:]
        te = te[te.is_fraud.notna()]
        y = te.is_fraud.astype(int).values
        metrics.update({
            "test_size": int(len(te)), "test_scam_rate": round(float(y.mean()), 4),
            "roc_auc": round(float(roc_auc_score(y, te.risk_score)), 4),
            "pr_auc": round(float(average_precision_score(y, te.risk_score)), 4),
            "ai_system": _stats(y, (te.decision != "ALLOW").values, te.amount.values),
            "rule_baseline": _stats(y, ((te.is_new_recipient == 1) & (te.amount >= 5000)).values, te.amount.values),
            "demo_model_on_same_test": _stats(y, (re_.score_frame(re_.load_model(paths("A")["model"]), iforest, te)
                                                  .decision != "ALLOW").values, te.amount.values)})
    with open(p["metrics"], "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    progress("Done.")
    return metrics


def cleanup(max_age_hours: float = 12):
    """Delete per-session Dataset B folders (workspaces/B_*) not touched for a while."""
    import time
    root = os.path.join(HERE, "workspaces")
    if not os.path.isdir(root):
        return
    for d in os.listdir(root):
        full = os.path.join(root, d)
        if d.startswith("B_") and os.path.isdir(full) and time.time() - os.path.getmtime(full) > max_age_hours * 3600:
            shutil.rmtree(full, ignore_errors=True)


def delete(name: str = "B"):
    shutil.rmtree(paths(name)["root"], ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python workspace.py path/to/your_log.csv")
        sys.exit(1)
    m = build_b(read_log(sys.argv[1]), progress=print)
    print(json.dumps({k: v for k, v in m.items() if k != "feature_importance"}, indent=2, default=str))
