"""
signals.py — pattern rules, advisories and the full "signals checked" list.

Business rules, kept separate from the ML models (the models are unchanged):
  SAME_AMOUNT_COLLECTION  the receiving wallet got a similar amount from 3+ different people in 24h (typical "fee" scam)
  REPEATED_SAME_AMOUNT    the customer already sent a similar amount 3+ times in 24h ("pay again to unlock" scams)
  BURST_THEN_LARGE        3+ transfers in the last hour and this one is 5x the usual amount or more (rushed emptying)
All of them raise the decision to at least WARN.

Advisories are information only and never block: e.g. a brand-new account that has never received money is not
suspicious by itself, so the transfer can stay ALLOW, but the customer sees "New account: make sure you know this person".
"""

NEW_ACCOUNT_DAYS = 30


def pattern_rules(sig: dict, feats: dict):
    """Returns (rules that raise to WARN, advisory notes). Notes are (level, english, bangla); level = 'warn' or 'info'."""
    rules, notes = [], []
    n_coll = sig.get("recipient_similar_senders_24h", 0)
    n_sent = sig.get("sender_similar_24h", 0)
    age = float(feats.get("recipient_account_age_days", 9999))
    ever = sig.get("recipient_received_ever", 1)
    if n_coll >= 3:
        rules.append("SAME_AMOUNT_COLLECTION")
        notes.append(("warn", f"This wallet received a similar amount from {n_coll} different people today.",
                      f"আজ {n_coll} জন আলাদা মানুষ এই অ্যাকাউন্টে প্রায় একই পরিমাণ টাকা পাঠিয়েছে।"))
    if feats.get("user_txns_last_1h", 0) >= 3 and feats.get("amount_ratio", 0) >= 5:
        rules.append("BURST_THEN_LARGE")
        notes.append(("warn", f"{int(feats['user_txns_last_1h'])} transfers in the last hour, and this one is "
                              f"{float(feats['amount_ratio']):.0f}x your usual amount.",
                      f"গত এক ঘণ্টায় {int(feats['user_txns_last_1h'])}টি লেনদেন, আর এটি আপনার স্বাভাবিক পরিমাণের "
                      f"{float(feats['amount_ratio']):.0f} গুণ।"))
    if n_sent >= 3:
        rules.append("REPEATED_SAME_AMOUNT")
        notes.append(("warn", f"You have sent a similar amount {n_sent + 1} times today, counting this one.",
                      f"আজ আপনি প্রায় একই পরিমাণ টাকা {n_sent + 1} বার পাঠাচ্ছেন।"))
    elif n_sent == 2:
        notes.append(("info", "You already sent a similar amount twice today.",
                      "আজ আপনি আগেও দুইবার প্রায় একই পরিমাণ টাকা পাঠিয়েছেন।"))
    when_en = "first seen today" if age < 1 else f"opened {age:.0f} days ago"
    when_bn = "আজই প্রথম দেখা গেছে" if age < 1 else f"{age:.0f} দিন আগে খোলা"
    if age < NEW_ACCOUNT_DAYS and ever == 0:
        notes.append(("info", f"New account: this wallet was {when_en} and has never received money. "
                              "Make sure you know this person.",
                      f"নতুন অ্যাকাউন্ট: {when_bn} এবং আগে কখনো টাকা আসেনি। প্রাপককে চেনেন কিনা নিশ্চিত হন।"))
    elif age < NEW_ACCOUNT_DAYS:
        notes.append(("info", f"This account is new ({when_en}).", f"এই অ্যাকাউন্টটি নতুন ({when_bn})।"))
    return rules, notes


def checklist(feats: dict, sig: dict, anom: float, network_flagged: bool, network_note: str):
    """Every factor ScamShield looked at, with status ok / caution / risk."""
    f = feats
    def st(risk, caution=False):
        return "risk" if risk else ("caution" if caution else "ok")
    age = float(f.get("recipient_account_age_days", 9999))
    ratio = float(f.get("amount_ratio", 1))
    snd = int(f.get("recipient_unique_senders_24h", 0))
    n_coll, n_sent = sig.get("recipient_similar_senders_24h", 0), sig.get("sender_similar_24h", 0)
    ever = sig.get("recipient_received_ever", None)
    rows = [
        ("Amount vs. usual", f"{ratio:.1f}x usual", st(ratio >= 3, ratio >= 1.5)),
        ("Time of day", "outside usual hours" if f.get("outside_usual_hours") else "within usual hours",
         st(False, bool(f.get("outside_usual_hours")))),
        ("Device", "new device" if f.get("device_changed") else "known device", st(bool(f.get("device_changed")))),
        ("Location", "new district" if f.get("new_location") else "usual district", st(False, bool(f.get("new_location")))),
        ("Recipient", "first time" if f.get("is_new_recipient") else "known contact", st(False, bool(f.get("is_new_recipient")))),
        ("Recipient account age", f"{age:,.0f} days", st(age < 7, age < NEW_ACCOUNT_DAYS)),
        ("Recipient history", "never received money" if ever == 0 else (f"received {ever:,} times" if ever is not None else "n/a"),
         st(False, ever == 0)),
        ("Other senders to recipient (24h)", f"{snd}", st(snd >= 5, snd >= 2)),
        ("Similar amounts to recipient today", f"{n_coll} people", st(n_coll >= 3, n_coll == 2)),
        ("Your similar payments today", f"{n_sent} before this", st(n_sent >= 3, n_sent == 2)),
        ("Your transfers in the last hour", f"{int(f.get('user_txns_last_1h', 0))}", st(f.get("user_txns_last_1h", 0) >= 3,
                                                                                         f.get("user_txns_last_1h", 0) >= 2)),
        ("Phone call while sending", "yes" if f.get("on_active_call") else "no", st(False, bool(f.get("on_active_call")))),
        ("Mule network", network_note, st(network_flagged)),
        ("Behaviour anomaly", f"more unusual than {anom:.0%}", st(anom >= 0.99, anom >= 0.95)),
    ]
    return rows
