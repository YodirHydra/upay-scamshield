"""
monitoring.py — model drift and fairness monitoring (Phase 1 feedback: "model-drift monitoring and ongoing
fairness monitoring").

Population Stability Index (PSI) compares the distribution of each input feature and of the risk score between a
reference period (what the model was trained on) and a current period. Common reading:
  PSI < 0.10 stable · 0.10–0.25 moderate shift, watch · > 0.25 significant shift, investigate / retrain.
"""
import numpy as np
import pandas as pd

from features import FEATURES

BINARY = {"outside_usual_hours", "is_new_recipient", "device_changed", "new_location", "on_active_call"}


def psi(ref, cur, bins=10):
    ref, cur = np.asarray(ref, float), np.asarray(cur, float)
    if len(ref) == 0 or len(cur) == 0:
        return float("nan")
    if len(np.unique(ref)) <= 2:
        edges = np.array([-np.inf, 0.5, np.inf])
    else:
        edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
        edges[0], edges[-1] = -np.inf, np.inf
    r = np.histogram(ref, edges)[0] / len(ref)
    c = np.histogram(cur, edges)[0] / len(cur)
    r, c = np.clip(r, 1e-4, None), np.clip(c, 1e-4, None)
    return float(np.sum((c - r) * np.log(c / r)))


def status(v):
    return "stable" if v < 0.10 else ("watch" if v < 0.25 else "investigate")


def drift_report(ref: pd.DataFrame, cur: pd.DataFrame, score_col="risk_score") -> pd.DataFrame:
    rows = []
    for f in FEATURES + ([score_col] if score_col in ref and score_col in cur else []):
        v = psi(ref[f], cur[f])
        rows.append(dict(signal=f, psi=round(v, 3), status=status(v),
                         reference_mean=round(float(ref[f].mean()), 3), current_mean=round(float(cur[f].mean()), 3)))
    return pd.DataFrame(rows).sort_values("psi", ascending=False).reset_index(drop=True)


def segment_alert_rates(df: pd.DataFrame, flagged, label_col="is_fraud"):
    """False-alarm rate by customer segment (needs labels) or alert rate (no labels), with Wilson 95% intervals."""
    from evaluation import wilson
    flagged = np.asarray(flagged, bool)
    has_lab = label_col in df and df[label_col].notna().any()
    genuine = (df[label_col].fillna(0).values == 0) if has_lab else np.ones(len(df), bool)
    segs = {"new customers (<180 days)": df.user_tenure_days.values < 180,
            "established customers (180+ days)": df.user_tenure_days.values >= 180,
            "night transfers (00–05)": df.hour.values < 6,
            "large transfers (≥ ৳10,000)": df.amount.values >= 10000}
    rows = []
    for name, m in segs.items():
        n = int((genuine & m).sum())
        k = int((flagged & genuine & m).sum())
        lo, hi = wilson(k, n)
        rows.append({"segment": name, "transfers": n, "alerts": k, "rate": round(k / max(n, 1), 4),
                     "95% interval": f"{lo:.2%} – {hi:.2%}"})
    return pd.DataFrame(rows), ("false-alarm rate on genuine transfers" if has_lab else "alert rate (no labels)")


# ---------------------------------------------------------------------------------------------------------------
# Loss concentration: where does scam money come from, and where does the system still miss it?
# ---------------------------------------------------------------------------------------------------------------
def _bands(df: pd.DataFrame) -> dict:
    hour = df["hour"] if "hour" in df else pd.to_datetime(df.timestamp).dt.hour
    return {
        "Customer tenure": np.where(df.user_tenure_days < 180, "New (< 180 days)",
                                    np.where(df.user_tenure_days < 730, "6 months – 2 years", "2 years +")),
        "Amount": pd.cut(df.amount, [0, 1000, 5000, 10000, 25000, np.inf],
                         labels=["< ৳1k", "৳1k – 5k", "৳5k – 10k", "৳10k – 25k", "৳25k +"], right=False).astype(str),
        "Time of day": np.where((hour >= 0) & (hour < 6), "Night (00–06)",
                                np.where(hour < 12, "Morning (06–12)", np.where(hour < 18, "Afternoon (12–18)", "Evening (18–24)"))),
        "Receiving wallet age": np.where(df.recipient_account_age_days < 30, "< 30 days",
                                         np.where(df.recipient_account_age_days < 180, "30–180 days", "180 days +")),
        "District": df.district.astype(str).values,
    }


def loss_concentration(df: pd.DataFrame, flagged, label_col="is_fraud"):
    """For each dimension: share of scams, share of scam money, share of that money the system protects, and the
    money it still misses. Returns {dimension: DataFrame}. Needs labels."""
    y = pd.to_numeric(df[label_col], errors="coerce").fillna(0).values == 1
    fl = np.asarray(flagged, bool)
    amt = df.amount.values.astype(float)
    total, total_n = amt[y].sum(), y.sum()
    missed_total = amt[y & ~fl].sum()
    out = {}
    for dim, band in _bands(df).items():
        band = np.asarray(band)
        rows = []
        for b in pd.unique(band[y]):
            m = (band == b) & y
            rows.append({"Group": b, "Scams": int(m.sum()), "Share of scams": m.sum() / max(total_n, 1),
                         "Scam money (৳)": amt[m].sum(), "Share of scam money": amt[m].sum() / max(total, 1),
                         "Money protected": amt[m & fl].sum() / max(amt[m].sum(), 1),
                         "Share of missed money": amt[m & ~fl].sum() / max(missed_total, 1)})
        out[dim] = pd.DataFrame(rows).sort_values("Scam money (৳)", ascending=False).reset_index(drop=True)
    if "scam_type" in df:
        rows = []
        for b in pd.unique(df.scam_type.values[y]):
            m = (df.scam_type.values == b) & y
            rows.append({"Group": str(b).replace("_", " "), "Scams": int(m.sum()), "Share of scams": m.sum() / max(total_n, 1),
                         "Scam money (৳)": amt[m].sum(), "Share of scam money": amt[m].sum() / max(total, 1),
                         "Money protected": amt[m & fl].sum() / max(amt[m].sum(), 1),
                         "Share of missed money": amt[m & ~fl].sum() / max(missed_total, 1)})
        out = {"Scam type": pd.DataFrame(rows).sort_values("Scam money (৳)", ascending=False).reset_index(drop=True), **out}
    return out


def concentration_headlines(tables: dict, top=4):
    """Plain-language findings: the groups holding the most scam money and the most missed money."""
    lines = []
    for dim, t in tables.items():
        if dim == "District" or t.empty:
            continue
        a = t.iloc[0]
        lines.append(f"{dim}: '{a.Group}' carries {a['Share of scam money']:.0%} of scam money "
                     f"({a['Money protected']:.0%} of it protected).")
        miss = t.sort_values("Share of missed money", ascending=False).iloc[0]
        if miss["Share of missed money"] > 0.3:
            lines.append(f"{dim}: most money still missed is in '{miss.Group}' ({miss['Share of missed money']:.0%} of all missed money).")
    return lines[: top * 2]


# ---------------------------------------------------------------------------------------------------------------
# Shadow mode and pilot design
# ---------------------------------------------------------------------------------------------------------------
GO_LIVE_CRITERIA = [   # (name, metric key, comparison, threshold, unit)
    ("Scams caught (warn or hold)", "recall", ">=", 0.70, "%"),
    ("Held transfers that are real scams", "hold_precision", ">=", 0.50, "%"),
    ("Genuine transfers held for an analyst", "hold_genuine", "<=", 0.002, "%"),
    ("Genuine transfers warned", "warn_genuine", "<=", 0.01, "%"),
    ("Scoring latency p95", "latency_p95_ms", "<=", 50, "ms"),
]


def shadow_report(decisions, labels, amounts, latency_p95_ms=None):
    """What a shadow-mode run (score silently, change nothing for the customer) would report after confirmed fraud
    labels arrive, and whether each go-live criterion passes."""
    d = np.asarray(decisions)
    y = pd.to_numeric(pd.Series(labels), errors="coerce").fillna(0).values == 1
    amt = np.asarray(amounts, float)
    hold, alert = d == "HOLD", d != "ALLOW"
    m = dict(transfers=int(len(d)), scams=int(y.sum()), recall=float((alert & y).sum() / max(y.sum(), 1)),
             hold_precision=float((hold & y).sum() / max(hold.sum(), 1)),
             hold_genuine=float((hold & ~y).sum() / max((~y).sum(), 1)),
             warn_genuine=float((alert & ~hold & ~y).sum() / max((~y).sum(), 1)),
             money_protected=float(amt[alert & y].sum() / max(amt[y].sum(), 1)),
             latency_p95_ms=latency_p95_ms)
    rows = []
    for name, key, op, thr, unit in GO_LIVE_CRITERIA:
        v = m[key]
        ok = None if v is None else (v >= thr if op == ">=" else v <= thr)
        fmt = (lambda x: f"{x:.1%}") if unit == "%" else (lambda x: f"{x:.1f} ms")
        rows.append({"Criterion": name, "Target": f"{op} {fmt(thr)}", "Shadow result": "n/a" if v is None else fmt(v),
                     "Pass": "n/a" if ok is None else ("PASS" if ok else "FAIL")})
    return m, pd.DataFrame(rows)


def pilot_sample_size(base_rate, reduction, alpha=0.05, power=0.8):
    """Transfers needed PER ARM of an A/B pilot to detect that scam transfers that get through fall from base_rate to
    base_rate * (1 - reduction) (two-sided two-proportion z-test, normal approximation)."""
    from math import sqrt
    from statistics import NormalDist
    p1, p2 = base_rate, base_rate * (1 - reduction)
    za, zb = NormalDist().inv_cdf(1 - alpha / 2), NormalDist().inv_cdf(power)
    pbar = (p1 + p2) / 2
    n = (za * sqrt(2 * pbar * (1 - pbar)) + zb * sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p1 - p2) ** 2
    return int(np.ceil(n))
