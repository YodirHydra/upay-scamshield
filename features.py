"""features.py — the model features, computed by pipeline.build_features from a raw transaction log."""
FEATURES = [
    "amount",                       # BDT
    "amount_ratio",                 # amount / this customer's usual (median) transfer so far
    "hour",                         # 0-23
    "outside_usual_hours",          # 1 if the hour is outside this customer's usual active window so far
    "is_new_recipient",             # 1 if the customer never sent to this wallet before
    "recipient_account_age_days",   # age of the receiving wallet
    "recipient_unique_senders_24h", # distinct other senders to the receiving wallet in the last 24h
    "user_txns_last_1h",            # customer's transfers in the previous hour
    "device_changed",               # 1 if the device was never used by this customer before
    "new_location",                 # 1 if the district was never used by this customer before
    "on_active_call",               # 1 if the customer is on a phone call while sending (optional signal)
    "user_tenure_days",             # how long the customer has had the wallet
    "device_other_users_30d",       # other customers who sent money from this same device in the last 30 days
    "txn_velocity_trend",           # transfers in the last 24h vs. this customer's own long-run daily average
]
# Value used when a log or an older dataset does not have a feature (it then carries no risk signal).
NEUTRAL = {"device_other_users_30d": 0.0, "txn_velocity_trend": 1.0}
