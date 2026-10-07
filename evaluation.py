"""
evaluation.py — evidence for "where AI is used and whether it works" (Phase 1 judge feedback).

  1. Engine ablation      : what each engine catches alone, and what is lost when it is removed (leave-one-out),
                            measured on the future test period. The mule network is built ONLY from transfers before
                            the test period, as a daily batch job would be in production.
  2. Operating points     : alert policies with different analyst workloads (e.g. HOLD only when 2+ engines agree).
  3. Fairness significance: is the new-user false-alarm gap real? Wilson 95% intervals on both periods.

Run:  python evaluation.py     (writes model/evaluation.json, read by the app's Model & Impact page)
"""
import json
import math
import os

import numpy as np
import pandas as pd

import mule_network as mn
import risk_engine as re_
from generate_data import DAYS, START, WARMUP

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINES = ["Scam classifier", "Behaviour anomaly", "Takeover check", "Network check", "Call-coaching rule"]


def engine_flags(df: pd.DataFrame, scored: pd.DataFrame, suspect_wallets: set) -> pd.DataFrame:
    """One boolean column per engine (vectorised version of engines.engine_panel / risk_engine.decide)."""
    sig = (df.device_changed.astype(int) + df.new_location.astype(int) + df.outside_usual_hours.astype(int)
           + (df.user_txns_last_1h >= 3).astype(int) + (df.amount_ratio >= 3).astype(int))
    dev_loc = (df.device_changed == 1) & (df.new_location == 1) & (df.amount_ratio >= 3)
    dev_vel = (df.device_changed == 1) & (df.user_txns_last_1h >= 3)
    return pd.DataFrame({
        "Scam classifier": scored.risk_score.values >= np.where(df.user_tenure_days.values < re_.NEW_CUSTOMER_DAYS,
                                                                re_.NEW_CUSTOMER_WARN, re_.WARN_THRESHOLD),
        "Behaviour anomaly": scored.anomaly_pct.values >= re_.ANOMALY_THRESHOLD,
        "Takeover check": ((sig >= 3) | dev_loc | dev_vel).values,
        "Network check": df.recipient_id.isin(suspect_wallets).values,
        "Call-coaching rule": ((df.on_active_call == 1) & (df.is_new_recipient == 1) & (df.amount >= 5000)).values,
    }, index=df.index)


def stats(y, flagged, amounts):
    y, flagged = np.asarray(y, bool), np.asarray(flagged, bool)
    tp = (flagged & y).sum()
    return {"scams_caught": round(float(tp / max(y.sum(), 1)), 4),
            "precision": round(float(tp / max(flagged.sum(), 1)), 4),
            "false_alarm_rate": round(float((flagged & ~y).sum() / max((~y).sum(), 1)), 5),
            "money_protected": round(float(amounts[flagged & y].sum() / max(amounts[y].sum(), 1)), 4)}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(c - h, 0), 5), round(min(c + h, 1), 5))


def robustness(model, iforest):
    """Robustness to a CHANGED world: brand-new synthetic logs (different random seed, so different customers, mules
    and rings) with a different scam mix, scored by the CURRENT models without retraining."""
    import pipeline as pl
    from generate_data import generate
    worlds = {"Same mix, new customers (seed 2027)": dict(seed=2027),
              "More low-signal scams (x3), fewer phone scams (/2)": dict(seed=2028, n_social=500, n_low=810),
              "Takeover wave (x3 takeovers)": dict(seed=2029, n_takeover=660)}
    res = {}
    for name, kw in worlds.items():
        raw, truth, _ = generate(**kw)
        f = pl.build_features(raw).merge(truth, on="txn_id")
        f = f[(f.kind == "customer") & (f.timestamp >= START + pd.Timedelta(days=WARMUP))]
        s = re_.score_frame(model, iforest, f)
        yy, fl_ = f.is_fraud.values == 1, (s.decision != "ALLOW").values
        rule = ((f.is_new_recipient == 1) & (f.amount >= 5000)).values
        r = dict(transfers=int(len(f)), scams=int(yy.sum()), scamshield=stats(yy, fl_, f.amount.values),
                 rule=stats(yy, rule, f.amount.values))
        r["by_type"] = {t: round(float(fl_[(f.scam_type == t).values].mean()), 3)
                        for t in ["social_engineering", "account_takeover", "low_signal"]}
        res[name] = r
    return res


def main():
    feats = pd.read_parquet(os.path.join(HERE, "data", "features_all.parquet")).merge(
        pd.read_csv(os.path.join(HERE, "data", "ground_truth.csv")), on="txn_id")
    cut = START + pd.Timedelta(days=WARMUP + int((DAYS - WARMUP) * 0.7))
    cust = feats[(feats.kind == "customer") & (feats.timestamp >= START + pd.Timedelta(days=WARMUP))]
    train, test = cust[cust.timestamp < cut].reset_index(drop=True), cust[cust.timestamp >= cut].reset_index(drop=True)
    model, iforest = re_.load_model(), re_.load_iforest()

    # network known BEFORE the test period (daily batch job), from out-of-fold scores of earlier transfers only
    oof = pd.read_parquet(os.path.join(HERE, "data", "scored_all.parquet")).merge(
        feats[["txn_id", "timestamp"]], on="txn_id")
    wl = mn.find_mules(oof[oof.timestamp < cut])
    suspects = set(wl.index[wl.suspected_mule | ((wl.flagged_share >= 0.5) & (wl.flagged_senders >= 2))])

    sc = re_.score_frame(model, iforest, test)
    fl = engine_flags(test, sc, suspects)
    y, amt = test.is_fraud.values == 1, test.amount.values
    full = fl.any(axis=1).values

    ablation = {"All engines": dict(stats(y, full, amt), unique_catches=None)}
    for e in ENGINES:
        others = fl.drop(columns=e).any(axis=1).values
        ablation[e] = dict(alone=stats(y, fl[e].values, amt), without=stats(y, others, amt),
                           unique_catches=int((fl[e].values & ~others & y).sum()))
    by_type = {}
    for t in ["social_engineering", "account_takeover", "low_signal"]:
        m = (test.scam_type == t).values
        by_type[t] = {e: round(float(fl[e].values[m].mean()), 3) for e in ENGINES}
        by_type[t]["All engines"] = round(float(full[m].mean()), 3)

    # unseen scam type: every engine retrained WITHOUT any account-takeover examples, scored on test takeovers
    import xgboost as xgb
    from features import FEATURES
    no_ato = train[train.scam_type != "account_takeover"]
    m_n = xgb.XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.08, subsample=0.9, colsample_bytree=0.9,
                            scale_pos_weight=(no_ato.is_fraud == 0).sum() / no_ato.is_fraud.sum(), eval_metric="aucpr",
                            random_state=7).fit(no_ato[FEATURES], no_ato.is_fraud)
    sc_n = re_.score_frame(m_n, re_.fit_iforest(no_ato), test)
    fl_n = engine_flags(test, sc_n, suspects)
    ato = (test.scam_type == "account_takeover").values
    unseen = {"All engines": round(float(fl_n.any(axis=1).values[ato].mean()), 3)}
    for e in ENGINES:
        others = fl_n.drop(columns=e).any(axis=1).values
        unseen[e] = dict(alone=round(float(fl_n[e].values[ato].mean()), 3),
                         without=round(float(others[ato].mean()), 3),
                         unique_catches=int((fl_n[e].values & ~others & ato).sum()))
    unseen["takeovers_in_test"] = int(ato.sum())

    # corroboration: how trustworthy is an alert when several engines agree?
    n_all = fl.sum(axis=1).values
    corroboration = {f"{k}+ engines": dict(alerts=int((n_all >= k).sum()),
                                           precision=round(float((y & (n_all >= k)).sum() / max((n_all >= k).sum(), 1)), 4),
                                           scams_caught=round(float((y & (n_all >= k)).sum() / max(y.sum(), 1)), 4))
                     for k in (1, 2, 3)}

    # operating points: who goes to an analyst (HOLD) vs. a customer warning (WARN)
    n_eng = fl.sum(axis=1).values
    hold_now = (sc.decision == "HOLD").values
    points = {
        "Current policy": (full, hold_now),
        "HOLD only if 2+ engines agree": (full, hold_now & (n_eng >= 2)),
        "HOLD only if 3+ engines agree": (full, hold_now & (n_eng >= 3)),
        "Strict: warn only on classifier >= 0.5": ((sc.risk_score.values >= 0.5) | fl.drop(columns="Scam classifier").any(axis=1).values,
                                                   hold_now),
    }
    ops = {}
    for name, (alert, hold) in points.items():
        s = stats(y, alert, amt)
        ops[name] = dict(s, hold_genuine=round(float((hold & ~y).sum() / max((~y).sum(), 1)), 5),
                         hold_scams=round(float((hold & y).sum() / max(y.sum(), 1)), 4),
                         warn_genuine=round(float((alert & ~hold & ~y).sum() / max((~y).sum(), 1)), 5))

    # fairness: is the new-user gap real?
    fair = {}
    for name, d in [("train period", train), ("test period", test)]:
        s2 = re_.score_frame(model, iforest, d)
        f2 = (s2.decision != "ALLOW").values
        yy = d.is_fraud.values == 1
        new = d.user_tenure_days.values < 180
        fair[name] = {}
        for g, mk in [("new customers (<180 days)", new), ("established customers", ~new)]:
            gen = (~yy & mk)
            k, n = int((f2 & gen).sum()), int(gen.sum())
            fair[name][g] = dict(false_alarms=k, genuine_transfers=n, rate=round(k / max(n, 1), 5), ci95=wilson(k, n))

    # fairness fix: before (one WARN threshold for everyone) vs. after (new customers: classifier WARN at 0.65)
    fix = {}
    for name, d in [("train period", train), ("test period", test)]:
        s2 = re_.score_frame(model, iforest, d)
        yy, new = d.is_fraud.values == 1, d.user_tenure_days.values < 180
        before = (s2.decision != "ALLOW").values | (s2.risk_score.values >= re_.WARN_THRESHOLD)
        after = (s2.decision != "ALLOW").values
        fix[name] = {}
        for lbl, f2 in [("before (warn 0.30 for all)", before), (f"after (new customers warn {re_.NEW_CUSTOMER_WARN})", after)]:
            row = {}
            for g, mk in [("new", new), ("established", ~new)]:
                gen = ~yy & mk
                k, n = int((f2 & gen).sum()), int(gen.sum())
                row[g] = dict(rate=round(k / max(n, 1), 5), false_alarms=k, genuine=n, ci95=wilson(k, n),
                              scams_caught=round(float((f2 & yy & mk).sum() / max((yy & mk).sum(), 1)), 4))
            row["all_scams_caught"] = round(float((f2 & yy).sum() / max(yy.sum(), 1)), 4)
            fix[name][lbl] = row

    # engine ladder: add one engine at a time (known scam types), with recall by scam type
    ladder, acc = [], np.zeros(len(test), bool)
    for e in ["Scam classifier", "Takeover check", "Call-coaching rule", "Behaviour anomaly", "Network check"]:
        acc = acc | fl[e].values
        row = dict(step=("XGBoost classifier only" if e == "Scam classifier" else f"+ {e.lower()}"), **stats(y, acc, amt))
        for t in ["social_engineering", "account_takeover", "low_signal"]:
            row[t] = round(float(acc[(test.scam_type == t).values].mean()), 3)
        ladder.append(row)
    rule = ((test.is_new_recipient == 1) & (test.amount >= 5000)).values
    rb = dict(step="Simple rule (new recipient and ৳5,000+)", **stats(y, rule, amt))
    for t in ["social_engineering", "account_takeover", "low_signal"]:
        rb[t] = round(float(rule[(test.scam_type == t).values].mean()), 3)
    ladder.append(rb)

    out = dict(test_period=f"{cut:%d %b %Y} onwards", test_transfers=int(len(test)), test_scams=int(y.sum()),
               network_built_before=f"{cut:%d %b %Y}", suspect_wallets=len(suspects),
               ablation=ablation, unseen_takeover_ablation=unseen, corroboration=corroboration,
               detection_by_type=by_type, operating_points=ops, fairness=fair, fairness_fix=fix, engine_ladder=ladder,
               robustness=robustness(model, iforest))
    with open(os.path.join(HERE, "model", "evaluation.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
