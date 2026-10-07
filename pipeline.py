"""
pipeline.py — turns RAW transactions into model features. Works on any log in this format, in batch or live.

Real-world rules this follows:
  * Point-in-time: every signal for a transfer uses ONLY transfers that happened before it (no future data).
  * Customer-specific: "usual amount", "usual hours", "known devices" etc. come from that customer's own history.
  * Same code online and offline: FeatureState is used both to build training data (build_features) and to
    score a new live transfer (FeatureState.peek), so live features are computed exactly like training features.
  * Graceful with little history: a customer with too little history is not treated as unusual.

Required columns: txn_id, timestamp, sender_id, receiver_id, amount, device_id, district
Optional columns: on_active_call (0/1), sender_created_at, receiver_created_at (dates), is_fraud (0/1 labels)
"""
from collections import defaultdict, deque

import numpy as np
import pandas as pd

from features import FEATURES  # noqa: F401

REQUIRED = ["txn_id", "timestamp", "sender_id", "receiver_id", "amount", "device_id", "district"]
OPTIONAL = ["on_active_call", "sender_created_at", "receiver_created_at", "is_fraud"]
MIN_HISTORY_HOURS = 5      # transfers needed before "outside usual hours" is judged
GLOBAL_MEDIAN = 1100.0     # fallback usual amount for a customer with no history (BDT)
DAY, HOUR = 86400, 3600
# Memory bounds per customer (scalability): the state never grows without limit.
MAX_HISTORY = 300      # last 300 transfers are enough for a stable usual amount / usual hours
MAX_CONTACTS = 500     # most recent distinct recipients remembered per customer
MAX_PLACES = 20        # most recent devices and districts remembered per customer
MAX_DEVICE_USERS = 50  # most recent customers remembered per device
DEVICE_WINDOW = 30 * 86400


def parse_time(col):
    """Accepts ISO (2026-07-01 14:30) and day-first formats used in Bangladesh (01/07/2026 14:30)."""
    iso = pd.to_datetime(col, errors="coerce", format="ISO8601")
    if iso.isna().any():                      # only non-ISO values are read day-first
        other = pd.to_datetime(col[iso.isna()], errors="coerce", format="mixed", dayfirst=True)
        iso = iso.astype("datetime64[ns]")
        iso[iso.isna()] = other.astype("datetime64[ns]")
    return iso


def data_quality(raw: pd.DataFrame):
    """Warnings about things that make the signals weaker in real data (not errors)."""
    notes = []
    t = parse_time(raw.timestamp)
    days = (t.max() - t.min()).days
    if days < 45:
        notes.append(f"The log covers only {days} days. Customer habits need history: with less than about 45 days, "
                     "more transfers look 'new' and false alarms go up.")
    if "receiver_created_at" not in raw:
        notes.append("No receiver_created_at column: account age is estimated from when a wallet first appears in the "
                     "log, which makes many genuine wallets look new. Adding wallet opening dates reduces false alarms.")
    if "on_active_call" not in raw:
        notes.append("No on_active_call column: the phone-call signal is set to 0, so phone-coached scams rely on the "
                     "other signals.")
    few = (raw.sender_id.value_counts() < 5).mean()
    if few > 0.5:
        notes.append(f"{few:.0%} of senders have fewer than 5 transfers, so their usual behaviour is not known yet.")
    return notes


def validate(raw: pd.DataFrame):
    """Return a list of problems (empty list = OK)."""
    problems = [f"Missing required column: {c}" for c in REQUIRED if c not in raw.columns]
    if problems:
        return problems
    if raw.empty:
        return ["The file has no rows."]
    if parse_time(raw.timestamp).isna().any():
        problems.append("Some timestamps could not be read (use e.g. 2026-07-01 14:30:00).")
    if pd.to_numeric(raw.amount, errors="coerce").isna().any():
        problems.append("Some amounts are not numbers.")
    if raw.txn_id.duplicated().any():
        problems.append("txn_id values must be unique.")
    amt = pd.to_numeric(raw.amount, errors="coerce")
    if (amt <= 0).any():
        problems.append(f"{int((amt <= 0).sum())} amounts are zero or negative.")
    for c in ["sender_id", "receiver_id", "device_id", "district", "txn_id"]:
        if raw[c].isna().any() or (raw[c].astype(str).str.strip() == "").any():
            problems.append(f"Column {c} has empty values.")
        elif raw[c].astype(str).str.len().max() > 64:
            problems.append(f"Column {c} has values longer than 64 characters.")
    if "is_fraud" in raw:
        lab = pd.to_numeric(raw.is_fraud, errors="coerce").dropna()
        if not lab.isin([0, 1]).all():
            problems.append("is_fraud must be 0 or 1 (or empty when unknown).")
    return problems


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["timestamp"] = parse_time(df.timestamp)
    df["amount"] = pd.to_numeric(df.amount).astype(float)
    if "is_fraud" in df:
        df["is_fraud"] = pd.to_numeric(df.is_fraud, errors="coerce")
    df["on_active_call"] = pd.to_numeric(df["on_active_call"], errors="coerce").fillna(0).astype(int) \
        if "on_active_call" in df else 0
    for c in ["sender_created_at", "receiver_created_at"]:
        df[c] = pd.to_datetime(df[c], errors="coerce") if c in df else pd.NaT
    for c in ["sender_id", "receiver_id", "device_id", "district", "txn_id"]:
        df[c] = df[c].astype(str)
    return df.sort_values("timestamp", kind="stable").reset_index(drop=True)


def _secs(x):
    return None if pd.isna(x) else pd.Timestamp(x).value // 10**9


def _bounded_put(d: dict, key, value, limit):
    """Insert-or-keep in an insertion-ordered dict; evict the oldest key when over the limit."""
    if key not in d:
        d[key] = value
        if len(d) > limit:
            d.pop(next(iter(d)))


class FeatureState:
    """Running memory of everyone's history. update() adds a transfer; peek() scores one without storing it.

    Scalability: everything is keyed by wallet and bounded (MAX_HISTORY, MAX_CONTACTS, MAX_PLACES, 1h/24h windows),
    so memory grows with the number of active customers, not with the number of transfers. In production the
    same per-customer state would live in a key-value store (e.g. Redis), see export_customer()."""

    def __init__(self):
        self.amounts = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
        self.hours = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
        self.recips = defaultdict(dict)                         # recipient -> 1, insertion-ordered, bounded
        self.devices, self.districts = defaultdict(dict), defaultdict(dict)   # value -> first time seen
        self.cust_first, self.first_seen, self.created = {}, {}, {}
        self.recent_out, self.recent_in = defaultdict(deque), defaultdict(deque)
        self.out24 = defaultdict(deque)          # sender -> (time, amount, receiver) in the last 24h
        self.recv_count = defaultdict(int)       # receiver -> number of transfers ever received
        self.dev_users = defaultdict(dict)       # device -> {sender: last time}, bounded
        # Long-run history as RUNNING STATISTICS (constant memory, never truncated): count, mean and variance of
        # each customer's transfer amounts (Welford). Recent detail (last MAX_HISTORY transfers) stays in the deques.
        self.n_out, self.amt_mean, self.amt_m2 = defaultdict(int), defaultdict(float), defaultdict(float)

    def _features(self, t, s, r, a, dv, di, call, s_created, r_created):
        h, hh = self.amounts.get(s, ()), self.hours.get(s, ())  # .get: reads never create entries
        usual = float(np.median(h)) if h else GLOBAL_MEDIAN
        hour = int(pd.Timestamp(t, unit="s").hour)
        f = dict(amount=float(a), usual_amount=usual, history_count=len(h), amount_ratio=a / max(usual, 1.0),
                 hour=hour, on_active_call=int(call), outside_usual_hours=0.0, device_changed=0.0, new_location=0.0)
        if len(hh) >= MIN_HISTORY_HOURS:
            lo, hi = np.percentile(hh, 5), np.percentile(hh, 95)
            f["outside_usual_hours"] = float(hour < lo - 0.5 or hour > hi + 0.5)
        f["is_new_recipient"] = float(r not in self.recips.get(s, {}))
        if h:   # "new" = never used by this customer, or first used in the last 24h (so every drain stays flagged)
            fd, fl, cf = self.devices[s].get(dv), self.districts[s].get(di), self.cust_first[s]
            f["device_changed"] = float(fd is None or (t - fd < DAY and fd > cf))
            f["new_location"] = float(fl is None or (t - fl < DAY and fl > cf))
        f["user_txns_last_1h"] = sum(1 for x in self.recent_out.get(s, ()) if x >= t - HOUR)
        f["recipient_unique_senders_24h"] = len({x[1] for x in self.recent_in.get(r, ()) if x[0] >= t - DAY and x[1] != s})
        du = self.dev_users.get(dv, {})
        f["device_other_users_30d"] = float(sum(1 for u, lt in du.items() if u != s and lt >= t - DEVICE_WINDOW))
        f["txn_velocity_trend"] = self._velocity(s, t, len([1 for x in self.out24.get(s, ()) if x[0] >= t - DAY]))
        rc = r_created or self.created.get(r) or self.first_seen.get(r, t)
        sc = s_created or self.created.get(s) or self.first_seen.get(s, t)
        f["recipient_account_age_days"] = max(0.0, (t - rc) / DAY)
        f["user_tenure_days"] = max(0.0, (t - sc) / DAY)
        return f

    def _velocity(self, s, t, count_24h):
        """(transfers in the last 24h + this one) / the customer's long-run transfers per day. 1.0 = normal pace.
        Neutral (1.0) until the customer has 7 days and 5 transfers of history."""
        n, first = self.n_out.get(s, 0), self.cust_first.get(s)
        days = (t - first) / DAY if first is not None else 0
        if n < 5 or days < 7:
            return 1.0
        return round(min((count_24h + 1) / max(n / days, 0.2), 50.0), 2)

    def peek(self, timestamp, sender, receiver, amount, device, district, on_call=0, s_created=None, r_created=None,
             pending=None):
        """Features for a NEW transfer, from everything seen so far. Does not change the history.
        `pending` = transfers made earlier today that are not in the stored history yet (e.g. sent in a live demo):
        list of dicts with keys t (Timestamp), s, r, a."""
        t, s, r = _secs(timestamp), str(sender), str(receiver)
        f = self._features(t, s, r, float(amount), str(device), str(district), on_call, _secs(s_created), _secs(r_created))
        for p in pending or []:
            pt = _secs(p["t"])
            if pt is None or pt > t:
                continue
            if str(p["s"]) == s and pt >= t - HOUR:
                f["user_txns_last_1h"] += 1
            if str(p["s"]) == s and str(p["r"]) == r:
                f["is_new_recipient"] = 0.0
        if pending:
            extra = sum(1 for p in pending if str(p["s"]) == s and _secs(p["t"]) is not None and t - DAY <= _secs(p["t"]) <= t)
            base = len([1 for x in self.out24.get(s, ()) if x[0] >= t - DAY])
            f["txn_velocity_trend"] = self._velocity(s, t, base + extra)
        if pending:
            others = {str(p["s"]) for p in pending if str(p["r"]) == r and str(p["s"]) != s and _secs(p["t"]) is not None
                      and t - DAY <= _secs(p["t"]) <= t}
            known = {x[1] for x in self.recent_in.get(r, ()) if x[0] >= t - DAY}
            f["recipient_unique_senders_24h"] += len(others - known)
        return f

    def signals(self, timestamp, sender, receiver, amount, pending=None):
        """Extra pattern signals (not model features) used for warnings and advisories:
        similar amounts sent today, similar amounts received by the wallet today, and whether it ever received money."""
        t, s, r, a = _secs(timestamp), str(sender), str(receiver), float(amount)
        similar = lambda x: abs(x - a) <= max(0.10 * a, 50)
        out = [(pt, pa, pr) for pt, pa, pr in self.out24.get(s, ()) if t - DAY <= pt <= t]
        inc = [(pt, ps, pa) for pt, ps, pa in self.recent_in.get(r, ()) if t - DAY <= pt <= t]
        for p in pending or []:
            pt = _secs(p["t"])
            if pt is None or not (t - DAY <= pt <= t):
                continue
            if str(p["s"]) == s:
                out.append((pt, float(p["a"]), str(p["r"])))
            if str(p["r"]) == r:
                inc.append((pt, str(p["s"]), float(p["a"])))
        ever = self.recv_count.get(r, 0) + sum(1 for p in pending or [] if str(p["r"]) == r)
        return dict(sender_similar_24h=sum(1 for _, pa, _ in out if similar(pa)),
                    sender_count_24h=len(out),
                    recipient_similar_senders_24h=len({ps for _, ps, pa in inc if similar(pa) and ps != s}),
                    recipient_received_ever=int(ever))

    def update(self, t, s, r, a, dv, di, s_created=None, r_created=None):
        hour = int(pd.Timestamp(t, unit="s").hour)
        self.amounts[s].append(a); self.hours[s].append(hour)
        _bounded_put(self.recips[s], r, 1, MAX_CONTACTS)
        _bounded_put(self.devices[s], dv, t, MAX_PLACES); _bounded_put(self.districts[s], di, t, MAX_PLACES)
        self.cust_first.setdefault(s, t)
        self.first_seen.setdefault(s, t); self.first_seen.setdefault(r, t)
        if s_created: self.created.setdefault(s, s_created)
        if r_created: self.created.setdefault(r, r_created)
        q = self.recent_out[s]
        q.append(t)
        while q and q[0] < t - HOUR:
            q.popleft()
        rq = self.recent_in[r]
        rq.append((t, s, a))
        while rq and rq[0][0] < t - DAY:
            rq.popleft()
        o24 = self.out24[s]
        o24.append((t, a, r))
        while o24 and o24[0][0] < t - DAY:
            o24.popleft()
        self.recv_count[r] += 1
        du = self.dev_users[dv]
        du.pop(s, None)                      # re-insert so the dict stays ordered by last use
        du[s] = t
        if len(du) > MAX_DEVICE_USERS:
            du.pop(next(iter(du)))
        n = self.n_out[s] = self.n_out[s] + 1
        d = a - self.amt_mean[s]
        self.amt_mean[s] += d / n
        self.amt_m2[s] += d * (a - self.amt_mean[s])

    def long_run(self, s):
        """Lifetime statistics kept as running numbers: transfers, mean amount, standard deviation."""
        n = self.n_out.get(s, 0)
        return dict(transfers=n, mean_amount=self.amt_mean.get(s, 0.0),
                    std_amount=float(np.sqrt(self.amt_m2.get(s, 0.0) / (n - 1))) if n > 1 else 0.0)

    def compact(self, now):
        """Drop empty or expired short-term windows (run periodically, e.g. every hour)."""
        for store, span in ((self.recent_out, HOUR), (self.recent_in, DAY), (self.out24, DAY)):
            for k in list(store):
                q = store[k]
                while q and (q[0][0] if isinstance(q[0], tuple) else q[0]) < now - span:
                    q.popleft()
                if not q:
                    del store[k]
        for dv in list(self.dev_users):
            du = self.dev_users[dv]
            for u in [u for u, lt in du.items() if lt < now - DEVICE_WINDOW]:
                del du[u]
            if not du:
                del self.dev_users[dv]

    def export_customer(self, s):
        """Compact, JSON-serialisable state of one customer: what a key-value store would hold per key."""
        s = str(s)
        fs = self.cust_first.get(s)
        return dict(amounts=[float(x) for x in self.amounts.get(s, [])], hours=[int(x) for x in self.hours.get(s, [])],
                    recipients=list(self.recips.get(s, {})), devices={k: int(v) for k, v in self.devices.get(s, {}).items()},
                    districts={k: int(v) for k, v in self.districts.get(s, {}).items()},
                    first_seen=int(fs) if fs is not None else None,
                    long_run={k: float(v) for k, v in self.long_run(s).items()})


def run(raw: pd.DataFrame):
    """Process a raw log in time order. Returns (features DataFrame, FeatureState with the full history)."""
    df = prepare(raw)
    state, rows = FeatureState(), []
    ts = df.timestamp.values.astype("datetime64[s]").astype(np.int64)
    sc = [_secs(x) for x in df.sender_created_at] if df.sender_created_at.notna().any() else [None] * len(df)
    rc = [_secs(x) for x in df.receiver_created_at] if df.receiver_created_at.notna().any() else [None] * len(df)
    for i, (s, r, a, dv, di, call) in enumerate(zip(df.sender_id.values, df.receiver_id.values, df.amount.values,
                                                    df.device_id.values, df.district.values, df.on_active_call.values)):
        rows.append(state._features(ts[i], s, r, a, dv, di, call, sc[i], rc[i]))
        state.update(ts[i], s, r, a, dv, di, sc[i], rc[i])          # history updated AFTER (point-in-time)
    feats = pd.DataFrame(rows)
    keep = ["txn_id", "timestamp", "sender_id", "receiver_id", "device_id", "district"] + \
           (["is_fraud"] if "is_fraud" in df else [])
    res = pd.concat([df[keep], feats], axis=1).rename(columns={"sender_id": "user_id", "receiver_id": "recipient_id"})
    res["amount_ratio"] = res.amount_ratio.round(2)
    res["recipient_account_age_days"] = res.recipient_account_age_days.round(1)
    res["user_tenure_days"] = res.user_tenure_days.round(1)
    return res, state


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    return run(raw)[0]


def customer_profile(raw_prepared: pd.DataFrame, sender, before):
    """The customer's usual behaviour, built from their own transfers BEFORE a given time."""
    h = raw_prepared[(raw_prepared.sender_id == str(sender)) & (raw_prepared.timestamp < before)]
    if h.empty:
        return dict(usual_amount=GLOBAL_MEDIAN, active_start=0, active_end=23, devices="(no history yet)",
                    home_district="(no history yet)", known_recipients=0, history=0)
    hrs = h.timestamp.dt.hour
    enough = len(h) >= MIN_HISTORY_HOURS
    return dict(usual_amount=float(h.amount.median()),
                active_start=int(np.floor(np.percentile(hrs, 5))) if enough else 0,
                active_end=int(np.ceil(np.percentile(hrs, 95))) if enough else 23,
                devices=",".join(h.device_id.value_counts().index[:3]),
                home_district=h.district.mode().iat[0], known_recipients=int(h.receiver_id.nunique()),
                history=int(len(h)))
