"""
engines.py — per-customer behavioural profile comparison and the four-engine agreement panel.

The four engines look at a transfer independently:
  1. Scam classifier      (XGBoost, supervised)        does it look like a known scam?
  2. Behaviour anomaly    (Isolation Forest, no labels) is it unusual compared with normal behaviour?
  3. Takeover check       (profile deviation rules)     does it break THIS customer's own habits?
  4. Network check        (graph analysis)              is the receiving wallet part of a mule ring?
Alerts that several engines agree on are more trustworthy for analysts.
"""
import risk_engine as re_


def profile_comparison(row, profile):
    """Compare one transfer with the customer's own baseline. Returns a list of rows for display."""
    usual = float(profile["usual_amount"])
    s, e = int(profile["active_start"]), int(profile["active_end"])
    devices = str(profile["devices"]).replace(",", ", ")
    ratio = float(row["amount"]) / max(usual, 1)
    out = [
        ("Transfer amount", f"৳{usual:,.0f} usual", f"৳{float(row['amount']):,.0f}",
         f"{ratio:.1f}x usual", ratio >= 3),
        ("Time of day", f"{s:02d}:00 to {e:02d}:00", f"{int(row['hour']):02d}:00",
         "Outside usual hours" if row["outside_usual_hours"] else "Within usual hours", bool(row["outside_usual_hours"])),
        ("Device", devices, str(row.get("device_id", "this device")),
         "New device" if row["device_changed"] else "Known device", bool(row["device_changed"])),
        ("Location", str(profile["home_district"]), str(row.get("district", profile["home_district"])),
         "New location" if row["new_location"] else "Usual location", bool(row["new_location"])),
        ("Recipient", f"{int(profile['known_recipients'])} known contacts", "New number" if row["is_new_recipient"] else "Known contact",
         "First transfer to this number" if row["is_new_recipient"] else "Known contact", bool(row["is_new_recipient"])),
        ("Speed", "Usually 0 to 1 transfers per hour", f"{int(row['user_txns_last_1h'])} in the last hour",
         "Burst of transfers" if row["user_txns_last_1h"] >= 3 else "Normal pace", row["user_txns_last_1h"] >= 3),
    ]
    return [dict(dimension=a, baseline=b, this_transfer=c, deviation=d, unusual=bool(u)) for a, b, c, d, u in out]


TAKEOVER_SIGNALS = [("device_changed", "new device"), ("new_location", "new location"),
                    ("outside_usual_hours", "unusual hour")]


def takeover_check(row):
    sig = [label for f, label in TAKEOVER_SIGNALS if row[f]]
    if row["user_txns_last_1h"] >= 3:
        sig.append("burst of transfers")
    if row["amount_ratio"] >= 3:
        sig.append("much larger than usual")
    rules = re_.business_rules(row)
    flagged = len(sig) >= 3 or "NEW_DEVICE_NEW_LOCATION" in rules or "NEW_DEVICE_VELOCITY" in rules
    return len(sig) / 5, flagged, sig


def network_check(recipient_id, wallets, ring_of):
    if recipient_id is None or recipient_id not in wallets.index:
        return 0.0, False, "No network history for this wallet"
    w = wallets.loc[recipient_id]
    ring = ring_of.get(recipient_id)
    if ring:
        return 1.0, True, f"Wallet is a suspected mule in {ring} ({int(w.flagged_senders)} high-risk senders)"
    if w.suspected_mule:
        return 0.9, True, f"Suspected mule wallet ({int(w.flagged_senders)} high-risk senders)"
    return float(w.flagged_share), w.flagged_share >= 0.5, f"{int(w.senders)} senders, {w.flagged_share:.0%} high risk"


def engine_panel(prob, anom, row, recipient_id, wallets, ring_of):
    t_score, t_flag, t_sig = takeover_check(row)
    n_score, n_flag, n_note = network_check(recipient_id, wallets, ring_of)
    engines = [
        dict(name="Scam classifier", method="XGBoost + SHAP", score=prob,
             flagged=prob >= re_.warn_threshold(row.get("user_tenure_days")),
             note=f"Scam probability {prob:.0%}" + (f" (new customer: warns at {re_.NEW_CUSTOMER_WARN:.0%})"
                                                     if re_.warn_threshold(row.get("user_tenure_days")) != re_.WARN_THRESHOLD else "")),
        dict(name="Behaviour anomaly", method="Isolation Forest", score=anom, flagged=anom >= re_.ANOMALY_THRESHOLD,
             note=f"More unusual than {anom:.1%} of normal transfers (flag at {re_.ANOMALY_THRESHOLD:.0%})"),
        dict(name="Takeover check", method="Customer profile rules", score=t_score, flagged=t_flag,
             note=", ".join(t_sig).capitalize() if t_sig else "Matches the customer's habits"),
        dict(name="Network check", method="NetworkX graph", score=n_score, flagged=n_flag, note=n_note),
    ]
    return engines, sum(e["flagged"] for e in engines)


def json_safe(d):
    return {k: (v.item() if hasattr(v, "item") else v) for k, v in d.items()}
