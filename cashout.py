"""
cashout.py — protection at the agent counter (Phase 1 feedback: "it only watches Send Money and does not protect people
when they take out cash at local shops") and agent risk intelligence (Track 01: "unusual agent behaviour vs. peers").

Scam money leaves the system through CASH-OUT at an agent. ScamShield scores every cash-out request:
  * Cash-out model (XGBoost, supervised) on point-in-time signals: how much came in during the last 24 hours, from how
    many different senders, how fast it is being taken out, wallet age, the wallet's status in the mule network,
    whether this agent is new for the wallet, and the agent's own risk.
  * Agent risk (peer comparison): each agent's share of cash-outs from network-flagged wallets compared with the other
    agents in the same district (z-score). Agents far above their peers are flagged for review, not punished.
Decision for the agent's screen: PAY / VERIFY (check ID, ask the customer, call upay) / HOLD (do not pay, analyst review).

ALL DATA IS SYNTHETIC. Cash-outs are generated on top of the transfer log (generate()).
Run:  python cashout.py      (writes data/cashouts.csv, data/agents.csv, model/cashout_model.json, model/cashout_metrics.json)
"""
import json
import os

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
N_AGENTS, N_COMPLICIT = 300, 6
CO_FEATURES = ["amount", "received_24h", "cash_share_24h", "senders_24h", "hours_since_last_in", "wallet_age_days",
               "network_flag", "flagged_in_share", "new_agent_for_wallet", "agent_peer_z"]
VERIFY_AT, HOLD_AT = 0.30, 0.70


# ---------------------------------------------------------------- synthetic cash-out log
def generate(seed=42):
    rng = np.random.default_rng(seed)
    raw = pd.read_csv(os.path.join(HERE, "data", "transactions_raw.csv"), dtype={"sender_id": str, "receiver_id": str},
                      parse_dates=["timestamp"])
    roles = pd.read_csv(os.path.join(HERE, "data", "wallet_roles_ground_truth.csv")).set_index("wallet_id").role
    districts = sorted(raw.district.unique())
    agents = pd.DataFrame({"agent_id": [f"AGT-{i:03d}" for i in range(N_AGENTS)],
                           "district": [districts[i % len(districts)] for i in range(N_AGENTS)]})
    complicit = set(rng.choice(agents.agent_id, N_COMPLICIT, replace=False))
    agents["complicit_truth"] = agents.agent_id.isin(complicit).astype(int)
    by_d = agents.groupby("district").agent_id.apply(list).to_dict()
    home = {}

    def home_agents(w, d):
        if w not in home:
            home[w] = list(rng.choice(by_d[d], 2, replace=False))
        return home[w]

    rows = []
    raw["role"] = raw.receiver_id.map(roles).fillna("customer")
    raw["day"] = raw.timestamp.dt.floor("D")
    inc = raw[raw.role.isin(["mule", "collector", "person"])].groupby(["receiver_id", "day", "role"]).agg(
        total=("amount", "sum"), last=("timestamp", "max"), dist=("district", "first")).reset_index()
    for r in inc.itertuples():
        if r.role in ("mule", "collector"):
            if rng.random() > 0.75:
                continue
            share, lag = rng.uniform(0.7, 1.0), rng.uniform(0.3, 8)
            agent_pool = list(complicit) if rng.random() < 0.65 else list(agents.agent_id)
            fraud = 1
        else:
            if rng.random() > 0.12:
                continue
            fast = rng.random() < 0.30            # genuine fast cash-out, e.g. family remittance taken out at once
            share, lag = (rng.uniform(0.8, 1.0), rng.uniform(0.5, 10)) if fast else (rng.uniform(0.2, 0.9), rng.uniform(6, 60))
            agent_pool = home_agents(r.receiver_id, r.dist)
            fraud = 0
        total = r.total * share
        n = int(np.ceil(total / 25000))
        t = r.last + pd.Timedelta(hours=float(lag))
        for k in range(n):
            amt = float(min(25000, total - 25000 * k))
            if amt < 100:
                continue
            rows.append((t + pd.Timedelta(minutes=12 * k), r.receiver_id, round(amt, -1), rng.choice(agent_pool), fraud,
                         r.role))
    # customers (U...) also cash out their own money at their home agents
    cust = raw[raw.sender_id.str.startswith("U")].groupby("sender_id").agg(usual=("amount", "median"), dist=("district", "first"))
    for c in cust.itertuples():
        for _ in range(rng.poisson(4)):
            t = raw.timestamp.min() + pd.Timedelta(days=float(rng.uniform(0, 89)), hours=float(rng.uniform(8, 20)))
            rows.append((t, c.Index, round(float(c.usual * rng.uniform(1, 4)), -1), rng.choice(home_agents(c.Index, c.dist)), 0,
                         "customer"))
    co = pd.DataFrame(rows, columns=["timestamp", "wallet_id", "amount", "agent_id", "is_mule_cashout", "role_truth"])
    co = co.sort_values("timestamp").reset_index(drop=True)
    co.insert(0, "cashout_id", [f"CO{i:06d}" for i in range(len(co))])
    co.to_csv(os.path.join(HERE, "data", "cashouts.csv"), index=False)
    agents.to_csv(os.path.join(HERE, "data", "agents.csv"), index=False)
    return co, agents


# ---------------------------------------------------------------- point-in-time features
def network_suspects(before=None):
    import mule_network as mn
    sc = pd.read_parquet(os.path.join(HERE, "data", "scored_all.parquet"))
    if before is not None:
        f = pd.read_parquet(os.path.join(HERE, "data", "features_all.parquet"), columns=["txn_id", "timestamp"])
        sc = sc.merge(f, on="txn_id")
        sc = sc[sc.timestamp < before]
    wl = mn.find_mules(sc)
    flagged = set(wl.index[wl.suspected_mule | ((wl.flagged_share >= 0.5) & (wl.flagged_senders >= 2))])
    return flagged, wl.flagged_share.to_dict()


def agent_peer_scores(co_hist: pd.DataFrame, agents: pd.DataFrame, flagged: set):
    """Each agent's share of cash-outs from network-flagged wallets vs. the other agents in its district (z-score)."""
    g = co_hist.assign(fl=co_hist.wallet_id.isin(flagged)).groupby("agent_id").agg(cashouts=("fl", "size"), flagged=("fl", "sum"))
    a = agents.set_index("agent_id").join(g).fillna({"cashouts": 0, "flagged": 0})
    a["flagged_share"] = a.flagged / a.cashouts.clip(lower=1)
    stats = a.groupby("district").flagged_share.agg(["mean", "std"])
    a = a.join(stats, on="district")
    a["peer_z"] = ((a.flagged_share - a["mean"]) / a["std"].replace(0, np.nan).fillna(1e-3).clip(lower=0.02)).round(2)
    a["agent_flag"] = (a.peer_z >= 3) & (a.flagged >= 3)
    return a.drop(columns=["mean", "std"])


def build_features(co: pd.DataFrame, raw: pd.DataFrame, flagged: set, fshare: dict, agent_z: dict, created: dict):
    raw = raw.sort_values("timestamp")
    by_w = {w: g[["timestamp", "sender_id", "amount"]].to_numpy() for w, g in raw.groupby("receiver_id")}
    seen = {}
    out = []
    for r in co.itertuples():
        t = r.timestamp
        arr = by_w.get(r.wallet_id)
        rec, snd, last = 0.0, 0, 72.0
        if arr is not None:
            m = (arr[:, 0] < t) & (arr[:, 0] >= t - pd.Timedelta(hours=24))
            rec = float(arr[m, 2].sum()) if m.any() else 0.0
            snd = len(set(arr[m, 1])) if m.any() else 0
            prev = arr[arr[:, 0] < t]
            if len(prev):
                last = min((t - prev[-1, 0]).total_seconds() / 3600, 72.0)
        c = created.get(r.wallet_id)
        age = (t - c).days if c is not None and not pd.isna(c) else 365
        key = (r.wallet_id, r.agent_id)
        out.append(dict(received_24h=rec, cash_share_24h=min(r.amount / rec, 2.0) if rec > 0 else 0.0,
                        senders_24h=snd, hours_since_last_in=round(last, 2), wallet_age_days=max(age, 0),
                        network_flag=int(r.wallet_id in flagged), flagged_in_share=float(fshare.get(r.wallet_id, 0.0)),
                        new_agent_for_wallet=int(key not in seen), agent_peer_z=float(agent_z.get(r.agent_id, 0.0))))
        seen[key] = 1
    return pd.concat([co.reset_index(drop=True), pd.DataFrame(out)], axis=1)


def created_dates(raw):
    rc = raw.dropna(subset=["receiver_created_at"]).drop_duplicates("receiver_id").set_index("receiver_id").receiver_created_at
    sc = raw.dropna(subset=["sender_created_at"]).drop_duplicates("sender_id").set_index("sender_id").sender_created_at
    return {**pd.to_datetime(sc).to_dict(), **pd.to_datetime(rc).to_dict()}


# ---------------------------------------------------------------- explain + decide
REASONS = {
    "cash_share_24h": ("Takes out {v:.0%} of the money that arrived in the last 24 hours.", "গত ২৪ ঘণ্টায় আসা টাকার {v:.0%} তুলছে।"),
    "senders_24h": ("{v:.0f} different people sent money to this wallet in the last 24 hours.", "গত ২৪ ঘণ্টায় {v:.0f} জন আলাদা মানুষ টাকা পাঠিয়েছে।"),
    "hours_since_last_in": ("Cash-out only {v:.1f} hours after the money arrived.", "টাকা আসার মাত্র {v:.1f} ঘণ্টা পরে তুলছে।"),
    "network_flag": ("This wallet is flagged in the mule network.", "এই অ্যাকাউন্টটি সন্দেহজনক নেটওয়ার্কে চিহ্নিত।"),
    "flagged_in_share": ("{v:.0%} of the money it received came from high-risk transfers.", "প্রাপ্ত টাকার {v:.0%} ঝুঁকিপূর্ণ লেনদেন থেকে এসেছে।"),
    "wallet_age_days": ("The wallet is only {v:.0f} days old.", "অ্যাকাউন্টটি মাত্র {v:.0f} দিনের পুরনো।"),
    "new_agent_for_wallet": ("First cash-out at this agent.", "এই এজেন্টে প্রথমবার টাকা তুলছে।"),
    "agent_peer_z": ("This agent handles far more flagged-wallet cash-outs than nearby agents.", "এই এজেন্টে আশেপাশের এজেন্টদের চেয়ে অনেক বেশি সন্দেহজনক ক্যাশ-আউট হয়।"),
    "received_24h": ("Large amount received in the last 24 hours (৳{v:,.0f}).", "গত ২৪ ঘণ্টায় বড় অঙ্কের টাকা এসেছে (৳{v:,.0f})।"),
    "amount": ("Large cash-out (৳{v:,.0f}).", "বড় অঙ্কের ক্যাশ-আউট (৳{v:,.0f})।"),
}


def load_model(path=None):
    m = xgb.XGBClassifier()
    m.load_model(path or os.path.join(HERE, "model", "cashout_model.json"))
    return m


def score(model, feats: pd.DataFrame):
    X = feats[CO_FEATURES].astype(float)
    p = model.predict_proba(X)[:, 1]
    contribs = model.get_booster().predict(xgb.DMatrix(X), pred_contribs=True)[:, :-1]
    return p, pd.DataFrame(contribs, columns=CO_FEATURES, index=feats.index)


def decide(prob, row):
    rules = []
    if row["network_flag"] and row["cash_share_24h"] >= 0.7 and row["hours_since_last_in"] <= 12:
        rules.append("FLAGGED_WALLET_FAST_CASHOUT")
    if row["agent_peer_z"] >= 3:
        rules.append("HIGH_RISK_AGENT")
    if prob >= HOLD_AT or "FLAGGED_WALLET_FAST_CASHOUT" in rules:
        return "HOLD", rules
    if prob >= VERIFY_AT or rules:
        return "VERIFY", rules
    return "PAY", rules


def explain(row, contrib, top_k=3):
    out = []
    for f, c in contrib.sort_values(ascending=False).items():
        if c <= 0.05 or len(out) >= top_k:
            break
        v = float(row[f])
        if (f == "network_flag" and v == 0) or (f == "new_agent_for_wallet" and v == 0) or (f == "agent_peer_z" and v < 2) \
                or (f == "wallet_age_days" and v > 90) or (f == "senders_24h" and v < 2) or (f == "cash_share_24h" and v < 0.5) \
                or (f == "hours_since_last_in" and v > 24) or (f == "flagged_in_share" and v < 0.2):
            continue
        en, bn = REASONS[f]
        out.append((f, float(c), en.format(v=v), bn.format(v=v)))
    return out


ACTIONS = {"PAY": ("Pay the customer normally.", "স্বাভাবিকভাবে টাকা দিন।"),
           "VERIFY": ("Check the customer's NID and ask who sent the money; call upay if unsure.",
                      "গ্রাহকের NID যাচাই করুন এবং কে টাকা পাঠিয়েছে জিজ্ঞেস করুন; সন্দেহ হলে upay-কে কল করুন।"),
           "HOLD": ("Do not pay. The cash-out is paused and sent to upay's fraud team.",
                    "টাকা দেবেন না। ক্যাশ-আউটটি স্থগিত এবং upay-এর ফ্রড টিমের কাছে পাঠানো হয়েছে।")}


# ---------------------------------------------------------------- train + evaluate
def main():
    co, agents = generate()
    raw = pd.read_csv(os.path.join(HERE, "data", "transactions_raw.csv"), dtype={"sender_id": str, "receiver_id": str},
                      parse_dates=["timestamp"])
    co["timestamp"] = pd.to_datetime(co.timestamp)
    cut = co.timestamp.quantile(0.7)
    flagged, fshare = network_suspects(before=cut)                 # network known before the test period
    ap = agent_peer_scores(co[co.timestamp < cut], agents, flagged)  # agent risk from the training period only
    feats = build_features(co, raw, flagged, fshare, ap.peer_z.to_dict(), created_dates(raw))
    tr, te = feats[feats.timestamp < cut], feats[feats.timestamp >= cut]
    pos_w = (tr.is_mule_cashout == 0).sum() / max(tr.is_mule_cashout.sum(), 1)
    model = xgb.XGBClassifier(n_estimators=250, max_depth=4, learning_rate=0.08, subsample=0.9, colsample_bytree=0.9,
                              scale_pos_weight=pos_w, eval_metric="aucpr", random_state=7).fit(tr[CO_FEATURES], tr.is_mule_cashout)
    model.save_model(os.path.join(HERE, "model", "cashout_model.json"))
    p, _ = score(model, te)
    dec = np.array([decide(pi, r)[0] for pi, (_, r) in zip(p, te.iterrows())])
    y, amt = te.is_mule_cashout.values == 1, te.amount.values
    alert = dec != "PAY"
    rule = ((te.cash_share_24h >= 0.8) & (te.hours_since_last_in <= 12)).values   # simple "fast in-and-out" rule

    def st_(f):
        tp = (f & y).sum()
        return dict(caught=round(float(tp / max(y.sum(), 1)), 3), precision=round(float(tp / max(f.sum(), 1)), 3),
                    false_alarm_rate=round(float((f & ~y).sum() / max((~y).sum(), 1)), 4),
                    money_stopped=round(float(amt[f & y].sum() / max(amt[y].sum(), 1)), 3))
    ap_full = agent_peer_scores(co, agents, flagged)
    found = set(ap_full.index[ap_full.agent_flag])
    truth = set(agents.agent_id[agents.complicit_truth == 1])
    metrics = dict(
        cashouts=int(len(co)), mule_cashouts=int(co.is_mule_cashout.sum()), test_cashouts=int(len(te)), test_mule=int(y.sum()),
        split=f"train before {cut:%d %b %Y}, test after",
        roc_auc=round(float(roc_auc_score(y, p)), 4), pr_auc=round(float(average_precision_score(y, p)), 4),
        model=st_(alert), fast_in_out_rule=st_(rule),
        hold_share_of_mule=round(float(((dec == "HOLD") & y).sum() / max(y.sum(), 1)), 3),
        genuine_fast_cashouts_paid=round(float(((dec == "PAY") & ~y & rule).sum() / max((~y & rule).sum(), 1)), 3),
        agents=dict(total=N_AGENTS, complicit_truth=len(truth), flagged=len(found), correct=len(found & truth),
                    wrongly_flagged=len(found - truth)),
        feature_importance={f: round(float(v), 4) for f, v in sorted(zip(CO_FEATURES, model.feature_importances_), key=lambda x: -x[1])})
    with open(os.path.join(HERE, "model", "cashout_metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    feats.to_parquet(os.path.join(HERE, "data", "cashouts_features.parquet"), index=False)
    return metrics


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
