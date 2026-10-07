"""
generate_data.py — synthetic upay-style RAW transaction log (the kind of data upay actually stores).

ALL DATA IS SYNTHETIC. No real customer data or PII is used.

Output (same format the app accepts from real users, see pipeline.REQUIRED/OPTIONAL columns):
  data/transactions_raw.csv   txn_id, timestamp, sender_id, receiver_id, amount, device_id, district,
                              on_active_call, sender_created_at, receiver_created_at
  data/ground_truth.csv       labels kept SEPARATE, like a real fraud team's confirmed cases:
                              txn_id, is_fraud, scam_type, kind
  data/wallet_roles_ground_truth.csv   true role of each wallet (only for evaluating the network analysis)

Nothing in the raw log says which transfers are scams; every signal is computed later from history.
Usage:  python generate_data.py
"""
import os

import numpy as np
import pandas as pd

START = pd.Timestamp("2026-07-01")
DAYS = 90
WARMUP = 30   # first 30 days only build up customer history; training and evaluation use days 30-90
N_CUSTOMERS, N_PEOPLE, N_SHOPS, N_SUPPLIERS = 3000, 12000, 300, 30
N_MULES, N_RINGS = 80, 12
DISTRICTS = ["Dhaka", "Chattogram", "Gazipur", "Narayanganj", "Cumilla", "Sylhet", "Rajshahi", "Khulna",
             "Barishal", "Rangpur", "Mymensingh", "Bogura", "Jessore", "Noakhali", "Cox's Bazar", "Tangail"]
MAX_AMOUNT = 25000


def _ts(day, hour, rng, minute=None):
    m = rng.integers(0, 60) if minute is None else minute
    return START + pd.Timedelta(days=int(day), hours=int(hour), minutes=int(m), seconds=int(rng.integers(0, 60)))


def _amt(x):
    return float(min(max(round(x / 10) * 10, 10), MAX_AMOUNT))


def generate(seed=42, n_legit=84000, n_social=1000, n_takeover=220, n_low=270):
    rng = np.random.default_rng(seed)
    wid = iter(rng.choice(90000, 90000, replace=False) + 10000)
    W = lambda: f"W{next(wid):05d}"
    roles, created = {}, {}

    people = [W() for _ in range(N_PEOPLE)]
    shops = [W() for _ in range(N_SHOPS)]
    suppliers = [W() for _ in range(N_SUPPLIERS)]
    collectors = [W() for _ in range(N_RINGS)]
    mules = [W() for _ in range(N_MULES)]
    for lst, role, lo, hi in [(people, "person", 200, 3000), (shops, "shop", 300, 3000), (suppliers, "supplier", 500, 3000),
                              (collectors, "collector", 30, 200), (mules, "mule", 1, 60)]:
        for w in lst:
            roles[w] = role
            if role == "mule":     # 60% freshly opened, 40% older "rented/bought" accounts that look established
                off = int(rng.integers(WARMUP - 10, DAYS - 5)) if rng.random() < 0.6 else int(rng.integers(-2000, -100))
            elif role == "person" and rng.random() < 0.12:   # people who joined upay during the period
                off = int(rng.integers(0, DAYS - 1))
            else:
                off = int(rng.integers(-hi, -lo + 1))
            created[w] = START + pd.Timedelta(days=off)

    # customers and their stable habits
    cust = pd.DataFrame({"id": [f"U{i:05d}" for i in range(N_CUSTOMERS)]})
    cust["usual"] = rng.lognormal(7.0, 0.8, N_CUSTOMERS)
    cust["start"] = rng.integers(6, 13, N_CUSTOMERS)
    cust["end"] = np.minimum(cust.start + rng.integers(10, 15, N_CUSTOMERS), 23)
    cust["devices"] = [[f"DEV-{x:04X}" for x in rng.integers(0, 65535, k)] for k in rng.choice([1, 2], N_CUSTOMERS, p=[.7, .3])]
    cust["home"] = rng.choice(DISTRICTS, N_CUSTOMERS)
    popular = list(rng.choice(people, 60, replace=False))   # e.g. landlords, family collectors, community funds
    cust["contacts"] = [list(rng.choice(people, k, replace=False)) + list(rng.choice(shops, rng.integers(0, 3))) +
                        (list(rng.choice(popular, rng.integers(1, 3))) if rng.random() < 0.35 else [])
                        for k in rng.integers(3, 12, N_CUSTOMERS)]
    new_people = [p for p in people if created[p] >= START]
    cust["created"] = [START - pd.Timedelta(days=int(d)) for d in rng.integers(30, 2500, N_CUSTOMERS)]
    activity = rng.lognormal(0, 0.6, N_CUSTOMERS)
    activity /= activity.sum()

    rows, truth = [], []

    def add(ts, s, r, amount, dev, dist, call, s_created, is_fraud=0, scam_type="none", kind="customer"):
        tid = f"T{len(rows):06d}"
        rows.append((tid, ts, s, r, _amt(amount), dev, dist, int(call), s_created, created[r]))
        truth.append((tid, is_fraud, scam_type, kind))

    # ---- legitimate customer transfers ----
    for ci in rng.choice(N_CUSTOMERS, n_legit, p=activity):
        c = cust.iloc[ci]
        day = rng.integers(0, DAYS)
        hour = rng.integers(c.start, c.end + 1) if rng.random() < 0.92 else rng.integers(0, 24)
        if rng.random() < 0.10:      # pays someone new (shop, tutor, relative, a friend who just joined)
            u = rng.random()
            joined = [p for p in rng.choice(new_people, 8) if created[p] < START + pd.Timedelta(days=int(day))]
            r = rng.choice(shops) if u < 0.35 else (joined[0] if u < 0.6 and joined else rng.choice(people))
        else:
            r = c.contacts[rng.integers(0, len(c.contacts))]
        amount = c.usual * rng.lognormal(0, 0.5) * (rng.uniform(3, 8) if rng.random() < 0.03 else 1)
        dev = f"DEV-{rng.integers(0, 65535):04X}" if rng.random() < 0.01 else c.devices[rng.integers(0, len(c.devices))]
        dist = rng.choice(DISTRICTS) if rng.random() < 0.03 else c.home
        add(_ts(day, hour, rng), c.id, r, amount, dev, dist, rng.random() < 0.05, c.created)

    # ---- mule activity windows (each mule is used for a few days) ----
    m_start = {m: (min(DAYS - 3, max(WARMUP, (created[m] - START).days) + int(rng.integers(0, 5)))
                   if created[m] >= START else int(rng.integers(WARMUP, DAYS - 8))) for m in mules}
    m_len = {m: int(rng.integers(3, 10)) for m in mules}
    mw = 1 / np.arange(1, N_MULES + 1) ** 1.3
    busy = list(rng.permutation(mules))
    pick_mule = lambda: busy[rng.choice(N_MULES, p=mw / mw.sum())]
    in_window = lambda m: min(DAYS - 1, m_start[m] + int(rng.integers(0, m_len[m])))
    victim = lambda: cust.iloc[rng.choice(N_CUSTOMERS, p=activity)]   # active users are targeted too
    old_mules = [m for m in mules if created[m] < START]

    # social engineering: coached on the phone, during the victim's normal hours, from their own phone
    for _ in range(n_social):
        c, m = victim(), pick_mule()
        add(_ts(in_window(m), rng.integers(c.start, c.end + 1), rng), c.id, m, c.usual * rng.uniform(1.5, 8),
            c.devices[0], c.home, rng.random() < 0.7, c.created, 1, "social_engineering")
    # account takeover: new device, often a new place and at night, several quick drains
    for _ in range(n_takeover):
        c, m = victim(), pick_mule()
        day = in_window(m)
        hour = rng.integers(0, 6) if rng.random() < 0.6 else rng.integers(c.start, c.end + 1)
        if rng.random() < 0.85:   # a new phone; 6 in 10 takeovers come from one of 12 shared fraud-farm handsets
            x = int(rng.integers(0, 65535))
            dev = f"DEV-F{x % 12:02d}" if x % 10 < 6 else f"DEV-{x:04X}"
        else:
            dev = c.devices[0]
        dist = rng.choice([d for d in DISTRICTS if d != c.home]) if rng.random() < 0.7 else c.home
        minute = int(rng.integers(0, 30))
        for k in range(int(rng.integers(1, 5))):
            add(_ts(day, hour, rng, minute=min(59, minute + 6 * k)), c.id, m if rng.random() < 0.7 else pick_mule(),
                c.usual * rng.uniform(3, 15), dev, dist, rng.random() < 0.1, c.created, 1, "account_takeover")
    # low-signal scams: look almost normal
    for _ in range(n_low):
        c, m = victim(), rng.choice(old_mules)
        add(_ts(in_window(m), rng.integers(c.start, c.end + 1), rng), c.id, m, c.usual * rng.uniform(1, 3),
            c.devices[0], c.home, rng.random() < 0.05, c.created, 1, "low_signal")

    # ---- onward transfers: mules -> ring collector; shops -> suppliers (legit) ----
    for i, m in enumerate(mules):
        for _ in range(int(rng.integers(2, 7))):
            day = min(DAYS - 1, m_start[m] + int(rng.integers(0, m_len[m] + 1)))
            add(_ts(day, rng.integers(8, 23), rng), m, collectors[i % N_RINGS], rng.uniform(3000, 25000),
                f"DEV-M{i:03d}", "Dhaka", 0, created[m], 0, "none", "wallet_forward")
    for i, s in enumerate(shops):
        for _ in range(int(rng.integers(1, 5))):
            add(_ts(rng.integers(0, DAYS), rng.integers(9, 20), rng), s, suppliers[rng.integers(0, N_SUPPLIERS)],
                rng.uniform(2000, 25000), f"DEV-S{i:03d}", "Dhaka", 0, created[s], 0, "none", "wallet_forward")

    raw = pd.DataFrame(rows, columns=["txn_id", "timestamp", "sender_id", "receiver_id", "amount", "device_id",
                                      "district", "on_active_call", "sender_created_at", "receiver_created_at"])
    truth = pd.DataFrame(truth, columns=["txn_id", "is_fraud", "scam_type", "kind"])
    raw = raw.sort_values("timestamp").reset_index(drop=True)
    # renumber by time so the ID itself carries no hint of how the row was generated
    new_ids = {old: f"T{i:06d}" for i, old in enumerate(raw.txn_id)}
    raw["txn_id"] = raw.txn_id.map(new_ids)
    truth["txn_id"] = truth.txn_id.map(new_ids)
    roles = pd.DataFrame({"wallet_id": list(roles), "role": list(roles.values())})
    return raw, truth, roles


def write_all(folder="data"):
    os.makedirs(folder, exist_ok=True)
    raw, truth, roles = generate()
    raw.to_csv(os.path.join(folder, "transactions_raw.csv"), index=False)
    truth.to_csv(os.path.join(folder, "ground_truth.csv"), index=False)
    roles.to_csv(os.path.join(folder, "wallet_roles_ground_truth.csv"), index=False)
    return raw, truth


if __name__ == "__main__":
    raw, truth = write_all()
    cust = truth[truth.kind == "customer"]
    print(f"Wrote {len(raw):,} raw transfers ({len(cust):,} by customers, fraud rate {cust.is_fraud.mean():.2%})")
    print(cust.scam_type.value_counts().to_string())
