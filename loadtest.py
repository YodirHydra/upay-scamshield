"""
loadtest.py — load test of the real scoring API over HTTP (Phase 1 feedback: "show production latency and throughput").

Starts `uvicorn api:app` as a separate process with two API keys, then:
  1. sends N real transfers (customers and recipients from the log) with C concurrent clients and measures
     end-to-end latency (client side, including HTTP) and throughput;
  2. bursts a key that is limited to 50 requests per minute and counts the HTTP 429 answers (rate limiting works).
Writes model/loadtest.json, read by the app (Model & Impact -> Performance & scale).

Usage:  python loadtest.py [--requests 2000] [--concurrency 8] [--workers 1 2]
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8765


def call(path, body=None, key=None, timeout=30):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method="POST" if body else "GET",
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json", **({"X-API-Key": key} if key else {})})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    return code, (time.perf_counter() - t0) * 1000


def main(n=2000, conc=8, workers=(1, 2)):
    runs = {w: one_run(n, conc, w) for w in workers}
    best = runs[max(runs)]
    out = dict(requests=n, concurrency=conc, workers=max(runs), throughput_rps=best["throughput_rps"],
               latency_ms=best["latency_ms"], errors=sum(r["errors"] for r in runs.values()),
               rate_limited=runs[min(runs)]["rate_limited"], rate_limit_test=runs[min(runs)]["rate_limit_test"],
               no_key_status=best["no_key_status"], machine=best["machine"],
               by_workers={str(w): dict(throughput_rps=r["throughput_rps"], latency_ms=r["latency_ms"]) for w, r in runs.items()},
               note=("Real HTTP calls to uvicorn on one 2-core machine, latency measured by the client including HTTP. "
                     + " · ".join(f"{w} worker{'s' if w > 1 else ''}: {r['throughput_rps']:.0f} req/s, p95 {r['latency_ms']['p95']} ms"
                                  for w, r in runs.items())
                     + ". Throughput grows with workers or pods (scoring is CPU-bound and stateless apart from the history). "
                     + f"Rate limit (single worker): a key limited to 50/min got HTTP 429 for {runs[min(runs)]['rate_limited']} "
                       "of 80 burst requests; no key gives 401. With several workers the limiter is per process, so in production it belongs "
                       "in the API gateway or Redis."))
    with open(os.path.join(HERE, "model", "loadtest.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    return out


def one_run(n, conc, workers):
    env = dict(os.environ, SCAMSHIELD_API_KEYS="load-key:1000000,limited-key:50")
    srv = subprocess.Popen([sys.executable, "-W", "ignore", "-m", "uvicorn", "api:app", "--port", str(PORT),
                            "--workers", str(workers), "--log-level", "warning"], cwd=HERE, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        t_start = time.time()
        while True:
            try:
                if call("/health", timeout=2)[0] == 200:
                    break
            except Exception:
                pass
            if time.time() - t_start > 180 or srv.poll() is not None:
                raise RuntimeError("API did not start")
            time.sleep(1)
        startup = time.time() - t_start
        raw = pd.read_csv(os.path.join(HERE, "data", "transactions_raw.csv"), dtype=str)
        s = raw.sample(n, random_state=11, replace=len(raw) < n)
        bodies = [dict(sender_id=r.sender_id, receiver_id=r.receiver_id, amount=float(r.amount), device_id=r.device_id,
                       district=r.district, on_active_call=int(r.on_active_call or 0), timestamp="2026-09-30 14:00:00")
                  for r in s.itertuples()]
        for b in bodies[:20]:                         # warm-up
            call("/score", b, "load-key")
        t0 = time.perf_counter()
        with ThreadPoolExecutor(conc) as ex:
            res = list(ex.map(lambda b: call("/score", b, "load-key"), bodies))
        wall = time.perf_counter() - t0
        codes = np.array([c for c, _ in res])
        lat = np.array([ms for c, ms in res if c == 200])
        burst = [call("/score", bodies[i % len(bodies)], "limited-key")[0] for i in range(80)]
        no_key = call("/score", bodies[0])[0]
        return dict(requests=n, concurrency=conc, workers=workers, startup_seconds=round(startup, 1),
                   throughput_rps=round(n / wall, 1),
                   latency_ms={p: round(float(np.percentile(lat, q)), 1) for p, q in (("p50", 50), ("p95", 95), ("p99", 99))},
                   errors=int((codes != 200).sum()), rate_limited=int(sum(c == 429 for c in burst)),
                   rate_limit_test="80 requests in a burst on a key limited to 50 per minute",
                   no_key_status=no_key, machine=f"{platform.system()} {platform.machine()}, Python {platform.python_version()}",
                   )
    finally:
        srv.terminate()
        try:
            srv.wait(10)
        except Exception:
            srv.kill()
        time.sleep(2)                     # let the port close before the next run


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", type=int, default=2000)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--workers", type=int, nargs="+", default=[1, 2])
    a = ap.parse_args()
    print(json.dumps(main(a.requests, a.concurrency, a.workers), indent=2))
