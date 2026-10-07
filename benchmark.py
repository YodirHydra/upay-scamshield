"""
benchmark.py — throughput, latency and memory, measured (Phase 1 feedback: "demonstrate production throughput,
latency" and "holding millions of user records in memory will take too much space").

Measures on this machine:
  * memory of the per-customer state after learning the whole log, per active wallet (tracemalloc)
  * serialised size of one customer's state (what a key-value store such as Redis would hold per key)
  * single-transfer latency of the full live path: features from history + classifier + anomaly + SHAP + rules
  * batch throughput of the scoring step

Run:  python benchmark.py     (writes model/benchmark.json, shown on the Model & Impact page)
"""
import json
import os
import platform
import statistics
import time
import tracemalloc

import pandas as pd

import pipeline as pl
import risk_engine as re_
import signals as sg

HERE = os.path.dirname(os.path.abspath(__file__))


def main(n_live=500):
    raw = pd.read_csv(os.path.join(HERE, "data", "transactions_raw.csv"), dtype=str, keep_default_na=False, na_values=[""])
    model, iforest = re_.load_model(), re_.load_iforest()

    t0 = time.perf_counter()
    feats, _ = pl.run(raw)                   # features + history, timed without the memory tracer
    build_s = time.perf_counter() - t0
    # memory of the customer state ONLY (no feature table), as a live service would hold it
    prep = pl.prepare(raw)
    ts = prep.timestamp.values.astype("datetime64[s]").astype("int64")
    cols = list(zip(ts, prep.sender_id, prep.receiver_id, prep.amount, prep.device_id, prep.district))
    tracemalloc.start()
    state = pl.FeatureState()
    for t, s_, r_, a_, d_, di_ in cols:
        state.update(int(t), s_, r_, float(a_), d_, di_)
    state.compact(int(ts.max()))
    mem_bytes = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    wallets = len(set(raw.sender_id) | set(raw.receiver_id))
    senders = raw.sender_id.nunique()

    top = raw.sender_id.value_counts().index[0]
    blob = json.dumps(state.export_customer(top))
    typical = raw.sender_id.value_counts().index[len(raw.sender_id.value_counts()) // 2]
    blob_typ = json.dumps(state.export_customer(typical))

    # live path latency: one transfer at a time, exactly as POST /score does
    now = prep.timestamp.max() + pd.Timedelta(hours=1)
    sample = prep.sample(n_live, random_state=7)
    lat = []
    for r in sample.itertuples():
        t1 = time.perf_counter()
        f = state.peek(now, r.sender_id, r.receiver_id, r.amount, r.device_id, r.district, r.on_active_call)
        sig = state.signals(now, r.sender_id, r.receiver_id, r.amount)
        one = pd.DataFrame([f])
        p, c = re_.score(model, one)
        a = float(re_.anomaly(iforest, one)[0])
        lvl, rules = re_.decide(float(p[0]), pd.Series(f), a)
        sg.pattern_rules(sig, f)
        re_.explain(pd.Series(f), c.iloc[0])
        lat.append((time.perf_counter() - t1) * 1000)
    lat.sort()

    # batch scoring throughput
    t2 = time.perf_counter()
    re_.score_frame(model, iforest, feats)
    batch_s = time.perf_counter() - t2

    per_wallet = mem_bytes / max(wallets, 1)
    out = dict(
        machine=f"{platform.system()} {platform.machine()}, Python {platform.python_version()}, 1 process",
        transfers=int(len(raw)), wallets=int(wallets), senders=int(senders),
        history_build_seconds=round(build_s, 1),
        history_build_transfers_per_second=int(len(raw) / build_s),
        state_memory_mb=round(mem_bytes / 1e6, 1), bytes_per_wallet=int(per_wallet),
        projected_gb_per_million_wallets=round(per_wallet * 1e6 / 1e9, 2),
        serialised_state_bytes_busiest_customer=len(blob), serialised_state_bytes_typical_customer=len(blob_typ),
        bounds=dict(max_history=pl.MAX_HISTORY, max_contacts=pl.MAX_CONTACTS, max_devices_districts=pl.MAX_PLACES,
                    short_windows="1 hour and 24 hours, compacted"),
        live_latency_ms=dict(p50=round(statistics.median(lat), 1), p95=round(lat[int(0.95 * len(lat)) - 1], 1),
                             p99=round(lat[int(0.99 * len(lat)) - 1], 1), n=n_live),
        batch_scoring_transfers_per_second=int(len(feats) / batch_s),
    )
    with open(os.path.join(HERE, "model", "benchmark.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
