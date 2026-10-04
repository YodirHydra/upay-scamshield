"""
business.py — business impact estimate: alerts, analyst hours, money protected and friction cost per 100,000 transfers.

Our test data has far more scams than real life, so we do NOT use its alert counts directly. We take the rates the
system achieved on the future test period (how often it warns or holds a genuine transfer, how many scams it catches,
how much scam money it protects) and apply them to a realistic number of scams worked out from:
  * the reported loss figure: Tk 92.60 crore per year (Bangladesh Bank data via the Daily Observer, 2025)
  * the send money (P2P) volume: 134.26 million transfers per month (Bangladesh Bank data, October 2025)
Every other number is an assumption the user can change.
"""
import numpy as np
import pandas as pd

LOSS_PER_YEAR_TK = 92.60e7          # Tk 92.60 crore, whole payment ecosystem, 2025
P2P_PER_MONTH = 134.26e6            # send money transfers per month, October 2025
DEFAULTS = dict(loss_share=1.0, avg_scam=7114.0, warn_cost=2.0, hold_customer_cost=20.0, analyst_minutes=10.0,
                analyst_rate=300.0, detection_factor=1.0, false_alarm_factor=1.0)


def measured_rates(scored: pd.DataFrame, label_col: str = "is_fraud") -> dict:
    """Rates achieved on a labelled test set that already has a `decision` column (ALLOW / WARN / HOLD)."""
    y = scored[label_col].astype(int).values == 1
    gen = max((~y).sum(), 1)
    sc = max(y.sum(), 1)
    d = scored.decision.values
    amt = scored.amount.values
    rule = ((scored.is_new_recipient == 1) & (scored.amount >= 5000)).values
    return dict(
        n_test=int(len(scored)), n_scams=int(y.sum()),
        warn_genuine=float(((d == "WARN") & ~y).sum() / gen), hold_genuine=float(((d == "HOLD") & ~y).sum() / gen),
        warn_scam=float(((d == "WARN") & y).sum() / sc), hold_scam=float(((d == "HOLD") & y).sum() / sc),
        money_protected=float(amt[(d != "ALLOW") & y].sum() / max(amt[y].sum(), 1)),
        avg_scam=float(amt[y].mean()) if y.any() else DEFAULTS["avg_scam"],
        rule_false_alarm=float((rule & ~y).sum() / gen), rule_recall=float((rule & y).sum() / sc),
        rule_money=float(amt[rule & y].sum() / max(amt[y].sum(), 1)))


def estimate(rates: dict, loss_share=1.0, avg_scam=7114.0, warn_cost=2.0, hold_customer_cost=20.0,
             analyst_minutes=10.0, analyst_rate=300.0, detection_factor=1.0, false_alarm_factor=1.0, per=100_000):
    """Per `per` send money transfers: ScamShield vs a simple rule (which has no WARN step: every alert is reviewed)."""
    loss = LOSS_PER_YEAR_TK / (P2P_PER_MONTH * 12) * per * loss_share
    scams = loss / avg_scam
    genuine = per - scams
    hold_cost = hold_customer_cost + analyst_minutes / 60 * analyst_rate
    warns = genuine * rates["warn_genuine"] * false_alarm_factor + scams * rates["warn_scam"] * detection_factor
    holds = genuine * rates["hold_genuine"] * false_alarm_factor + scams * rates["hold_scam"] * detection_factor
    protected = loss * min(rates["money_protected"] * detection_factor, 1.0)
    friction = genuine * rates["warn_genuine"] * false_alarm_factor * warn_cost + holds * hold_cost
    r_alerts = genuine * rates["rule_false_alarm"] + scams * rates["rule_recall"]
    r_protected = loss * rates["rule_money"]
    r_friction = r_alerts * hold_cost
    return {
        "ScamShield": dict(scams=scams, alerts=warns + holds, warn=warns, hold=holds, analyst_hours=holds * analyst_minutes / 60,
                           protected=protected, friction=friction, net=protected - friction,
                           ratio=protected / friction if friction else np.inf),
        "Simple rule": dict(scams=scams, alerts=r_alerts, warn=0.0, hold=r_alerts, analyst_hours=r_alerts * analyst_minutes / 60,
                            protected=r_protected, friction=r_friction, net=r_protected - r_friction,
                            ratio=r_protected / r_friction if r_friction else np.inf),
        "loss_per_unit": loss}
