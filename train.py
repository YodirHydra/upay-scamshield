"""
train.py — builds features from the RAW log, trains the models and evaluates them like a live system would.

Real-world evaluation choices:
  * Features come from pipeline.build_features (point-in-time, from each customer's own history).
  * Days 0-30 are a warm-up period that only builds history.
  * Time-based split: train on the earlier transfers, test on the LATER transfers (the future).
  * Labels (ground_truth.csv) are kept separate from the raw log, like a fraud team's confirmed cases.

Models:
  1. XGBoost classifier       -> probability that a transfer is a scam (supervised)
  2. Isolation Forest         -> how unusual a transfer is compared with normal behaviour (no labels)
  3. Mule network analysis    -> suspected mule wallets and rings from the transfer graph

Outputs: model/model.json, model/iforest.joblib, model/metrics.json,
         data/test_scored.parquet (analyst queue), data/scored_all.parquet (network), data/features_all.parquet
Usage:   python train.py
"""
import json
import os

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

import mule_network as mn
import pipeline as pl
import risk_engine as re_
from features import FEATURES
from generate_data import DAYS, START, WARMUP, write_all

RAW, TRUTH, ROLES = "data/transactions_raw.csv", "data/ground_truth.csv", "data/wallet_roles_ground_truth.csv"


def make_model(pos_w):
    return xgb.XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.08, subsample=0.9,
                             colsample_bytree=0.9, scale_pos_weight=pos_w, eval_metric="aucpr", random_state=7)


def flag_stats(y, flagged, amounts):
    y, flagged = np.asarray(y), np.asarray(flagged)
    tp = (flagged & (y == 1)).sum()
    return {
        "scam_recall": round(float(tp / max((y == 1).sum(), 1)), 3),
        "precision": round(float(tp / max(flagged.sum(), 1)), 3),
        "false_alarm_rate": round(float((flagged & (y == 0)).sum() / max((y == 0).sum(), 1)), 4),
        "scam_money_protected_pct": round(float(amounts[flagged & (y == 1)].sum() / max(amounts[y == 1].sum(), 1)), 3),
    }


def main():
    os.makedirs("data", exist_ok=True)
    os.makedirs("model", exist_ok=True)
    if not all(os.path.exists(p) for p in [RAW, TRUTH, ROLES]):
        write_all("data")
    raw = pd.read_csv(RAW)
    truth = pd.read_csv(TRUTH)
    roles = pd.read_csv(ROLES).set_index("wallet_id")   # ground truth, used ONLY for evaluation

    feats = pl.build_features(raw)
    feats.to_parquet("data/features_all.parquet", index=False)
    df = feats.merge(truth, on="txn_id")
    df = df[(df.kind == "customer") & (df.timestamp >= START + pd.Timedelta(days=WARMUP))].reset_index(drop=True)

    # Time-based split: learn from the past, test on the future
    cut = START + pd.Timedelta(days=WARMUP + int((DAYS - WARMUP) * 0.7))
    train_df, test_df = df[df.timestamp < cut], df[df.timestamp >= cut]
    pos_w = (train_df.is_fraud == 0).sum() / (train_df.is_fraud == 1).sum()

    model = make_model(pos_w).fit(train_df[FEATURES], train_df.is_fraud)
    model.save_model("model/model.json")
    iforest = re_.fit_iforest(train_df)          # unsupervised: labels are NOT used
    joblib.dump(iforest, "model/iforest.joblib")

    y, amounts = test_df.is_fraud.values, test_df.amount.values
    p = model.predict_proba(test_df[FEATURES])[:, 1]
    a = re_.anomaly(iforest, test_df)
    rules_only = test_df.apply(lambda r: len(re_.business_rules(r)) > 0, axis=1).values
    clf_only = p >= re_.WARN_THRESHOLD                                     # XGBoost alone, no rules, no anomaly
    flagged_xgb = clf_only | rules_only                                    # + takeover and call-coaching rules
    flagged_ai = (re_.score_frame(model, iforest, test_df).decision != "ALLOW").values   # full live policy
    baseline = ((test_df.is_new_recipient == 1) & (test_df.amount >= 5000)).values
    groups = {"new_users (<180 days)": test_df.user_tenure_days.values < 180,
              "established_users": test_df.user_tenure_days.values >= 180}

    # Unseen scam type test: train both models WITHOUT any account-takeover examples
    no_ato = train_df[train_df.scam_type != "account_takeover"]
    m2 = make_model((no_ato.is_fraud == 0).sum() / (no_ato.is_fraud == 1).sum()).fit(no_ato[FEATURES], no_ato.is_fraud)
    a2 = re_.anomaly(re_.fit_iforest(no_ato), test_df)
    p2 = m2.predict_proba(test_df[FEATURES])[:, 1]
    ato = (test_df.scam_type == "account_takeover").values
    novel = {"classifier_only": round(float((p2[ato] >= re_.WARN_THRESHOLD).mean()), 3),
             "anomaly_only": round(float((a2[ato] >= re_.ANOMALY_THRESHOLD).mean()), 3),
             "classifier_plus_anomaly": round(float(((p2[ato] >= re_.WARN_THRESHOLD) |
                                                     (a2[ato] >= re_.ANOMALY_THRESHOLD)).mean()), 3)}

    # Network: out-of-fold scores so no wallet is judged by a model that saw its own labels
    oof = cross_val_predict(make_model(pos_w), df[FEATURES], df.is_fraud, method="predict_proba",
                            cv=StratifiedKFold(3, shuffle=True, random_state=7))[:, 1]
    scored = df[["txn_id", "user_id", "recipient_id", "amount"]].assign(risk_score=oof.round(4))
    scored.to_parquet("data/scored_all.parquet", index=False)
    edges = raw.rename(columns={"sender_id": "from_wallet", "receiver_id": "to_wallet"})[["from_wallet", "to_wallet", "amount"]]
    wallets = mn.find_mules(scored)
    rings = mn.find_rings(wallets, edges)
    role = roles.role.reindex(wallets.index).fillna("person").values
    true_mule, sus = role == "mule", wallets.suspected_mule.values
    true_coll = set(roles.index[roles.role == "collector"])
    found = {c for r in rings for c in r["collector"].split(", ")}

    metrics = {
        "split": f"train: days {WARMUP}-{(cut - START).days}, test (future): days {(cut - START).days}-{DAYS}",
        "train_size": int(len(train_df)), "test_size": int(len(test_df)),
        "test_scam_rate": round(float(y.mean()), 4),
        "roc_auc": round(float(roc_auc_score(y, p)), 4),
        "pr_auc": round(float(average_precision_score(y, p)), 4),
        "anomaly_only_roc_auc": round(float(roc_auc_score(y, a)), 4),
        "thresholds": {"warn": re_.WARN_THRESHOLD, "hold": re_.HOLD_THRESHOLD, "anomaly": re_.ANOMALY_THRESHOLD,
                       "warn_new_customers": re_.NEW_CUSTOMER_WARN},
        "ai_system": flag_stats(y, flagged_ai, amounts),
        "classifier_only": flag_stats(y, clf_only, amounts),
        "classifier_and_rules_only": flag_stats(y, flagged_xgb, amounts),
        "note": ("ai_system = full live policy (classifier + rules + anomaly model, new-customer threshold). On KNOWN "
                 "scam types the anomaly model adds few catches, so ai_system and classifier_and_rules_only are close; "
                 "its value shows on the unseen scam type below and in model/evaluation.json (engine ablation)."),
        "rule_baseline": flag_stats(y, baseline, amounts),
        "recall_by_scam_type": {t: round(float(flagged_ai[(test_df.scam_type == t).values].mean()), 3)
                                for t in ["social_engineering", "account_takeover", "low_signal"]
                                if (test_df.scam_type == t).any()},
        "test_scams_by_type": test_df.scam_type.value_counts().to_dict(),
        "novel_scam_test_account_takeover_recall": novel,
        "fairness_by_tenure": {g: flag_stats(y[m], flagged_ai[m], amounts[m]) for g, m in groups.items()},
        "feature_importance": {f: round(float(v), 4) for f, v in
                               sorted(zip(FEATURES, model.feature_importances_), key=lambda x: -x[1])},
        "network": {
            "wallets_analysed": int(len(wallets)),
            "suspected_mules": int(sus.sum()),
            "true_mules": int((roles.role == "mule").sum()),
            "true_mules_seen": int(true_mule.sum()),
            "mule_precision": round(float((sus & true_mule).sum() / max(sus.sum(), 1)), 3),
            "mule_recall": round(float((sus & true_mule).sum() / max(true_mule.sum(), 1)), 3),
            "rings_found": len(rings), "true_rings": len(true_coll), "rings_correct": len(found & true_coll),
            "shops_wrongly_flagged": int((sus & (role == "shop")).sum()),
        },
    }
    with open("model/metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    test_df.assign(risk_score=p.round(4), anomaly_pct=a.round(4)).sort_values("risk_score", ascending=False) \
        .to_parquet("data/test_scored.parquet", index=False)
    print(json.dumps({k: metrics[k] for k in ["split", "roc_auc", "ai_system", "rule_baseline", "recall_by_scam_type",
                                               "novel_scam_test_account_takeover_recall", "fairness_by_tenure",
                                               "network"]}, indent=2))


if __name__ == "__main__":
    main()
