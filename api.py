"""
api.py — real-time scoring API: how upay's backend would call ScamShield before confirming a Send Money transfer.

Run:   uvicorn api:app --port 8000        then open http://localhost:8000/docs to try it
       (Dataset A, the demo). To run on your own data: build Dataset B first (python workspace.py your_log.csv),
       then set SCAMSHIELD_WORKSPACE=B before starting uvicorn.
Call:  POST /score  with the transfer details (see ScoreRequest) and the header  X-API-Key: <key>

Security (what is really implemented here):
  * API key on every data endpoint (header X-API-Key, constant-time comparison). Keys come from the environment:
    SCAMSHIELD_API_KEYS="key1:600,key2:60"  (key:requests per minute). If unset, a demo key "demo-key" is used
    and the API says so in /health. Never use the demo key outside a demo.
  * Rate limiting per key (sliding 60-second window) -> HTTP 429 with Retry-After.
  * Input validation: ID lengths, amount range, 0/1 flags (pydantic) -> HTTP 422 on bad input.
  * Logs carry pseudonymised IDs only (SHA-256), never raw customer or wallet numbers.
  * /metrics for monitoring: decisions, latency percentiles, rejected requests.

At startup it reads the active dataset's transaction history so it knows
every customer's habits. Each new transfer is turned into features with the SAME code used for training
(pipeline.FeatureState), scored by the models, and optionally added to history (commit=true).
"""
import hmac
import logging
import os
import threading
import time
from collections import Counter, defaultdict, deque
from datetime import datetime
from typing import List, Optional

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field

import engines as en
import mule_network as mn
import pipeline as pl
import risk_engine as re_
import signals as sg
import workspace as wsp
from cases import pseudonymise

WORKSPACE = os.environ.get("SCAMSHIELD_WORKSPACE", "A")
# Shadow mode: score every transfer and log what ScamShield WOULD have done, but always answer ALLOW, so customers
# see no change. Used for the first weeks on real data, before any warning is shown (README: path to production).
MODE = os.environ.get("SCAMSHIELD_MODE", "live").lower()
SHADOW_LOG = os.environ.get("SCAMSHIELD_SHADOW_LOG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "shadow_log.csv"))
if not wsp.exists(WORKSPACE):
    raise RuntimeError(f"Dataset {WORKSPACE} is not built. Run: python workspace.py your_log.csv")
P = wsp.paths(WORKSPACE)
LOG = P["raw"]
app = FastAPI(title="upay ScamShield API", version="1.1",
              description="Scores a Send Money transfer before it is confirmed. Decision support only: "
                          "HOLD means pause and re-verify, never an automatic permanent block.\n\n"
                          "**Authentication:** send the header `X-API-Key`. **Rate limit:** per key, per minute "
                          "(HTTP 429 when exceeded).")
log = logging.getLogger("scamshield.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---- API keys and rate limits ------------------------------------------------------------------------------
_env_keys = os.environ.get("SCAMSHIELD_API_KEYS", "").strip()
DEMO_KEY = not _env_keys
KEYS = {}
for part in (_env_keys or "demo-key:600").split(","):
    k, _, lim = part.strip().partition(":")
    if k:
        KEYS[k] = int(lim or 600)
_hits = defaultdict(deque)
_lock = threading.Lock()
METRICS = dict(decisions=Counter(), rejected=Counter(), latency_ms=deque(maxlen=5000), started=time.time())
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Your ScamShield API key")


def require_key(key: Optional[str] = Depends(api_key_header)):
    match = next((k for k in KEYS if key and hmac.compare_digest(key.encode(), k.encode())), None)
    if match is None:
        METRICS["rejected"]["401 missing or wrong API key"] += 1
        raise HTTPException(401, "Missing or invalid API key (header X-API-Key)")
    now = time.time()
    with _lock:
        q = _hits[match]
        while q and q[0] < now - 60:
            q.popleft()
        if len(q) >= KEYS[match]:
            METRICS["rejected"]["429 rate limit"] += 1
            raise HTTPException(429, f"Rate limit of {KEYS[match]} requests per minute exceeded",
                                headers={"Retry-After": str(int(60 - (now - q[0])) + 1)})
        q.append(now)
    return match

_raw = wsp.read_log(LOG)
_feats, STATE = pl.run(_raw)
MODEL, IFOREST = re_.load_model(P["model"]), re_.load_iforest(P["iforest"])
_scored = re_.score_frame(MODEL, IFOREST, _feats)
WALLETS = mn.find_mules(_scored)
_edges = _raw.rename(columns={"sender_id": "from_wallet", "receiver_id": "to_wallet"})
RINGS = mn.find_rings(WALLETS, _edges)
RING_OF = {m: r["ring_id"] for r in RINGS for m in r["mules"]}


ID = dict(min_length=1, max_length=64)


class ScoreRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [
        {"sender_id": "U00042", "receiver_id": "W12345", "amount": 6000, "device_id": "DEV-1A2B", "district": "Dhaka",
         "on_active_call": 1, "timestamp": "2026-09-30 14:05:00", "commit": False}]})
    sender_id: str = Field(..., **ID, examples=["U00042"])
    receiver_id: str = Field(..., **ID, examples=["W12345"])
    amount: float = Field(..., gt=0, le=10_000_000, examples=[6000])
    device_id: str = Field(..., **ID, examples=["DEV-1A2B"])
    district: str = Field(..., **ID, examples=["Dhaka"])
    on_active_call: int = Field(0, ge=0, le=1)
    timestamp: Optional[datetime] = Field(None, description="Defaults to now")
    commit: bool = Field(False, description="Add this transfer to history after scoring")


class Text(BaseModel):
    en: str
    bn: str


class Engine(BaseModel):
    name: str
    method: str
    score: float
    flagged: bool
    finding: str


class ScoreResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "decision": "WARN", "action": "Show a warning with reasons; user must confirm to continue.",
        "scam_probability": 0.62, "anomaly_percentile": 0.91, "engines_flagging": 2, "latency_ms": 24.1,
        "engines": [{"name": "Scam classifier", "method": "XGBoost + SHAP", "score": 0.62, "flagged": True,
                     "finding": "Scam probability 62%"}],
        "rules": ["CALL_COACHING_GUARD"],
        "reasons": [{"en": "You have never sent money to this number before.", "bn": "এই নম্বরে আপনি আগে কখনো টাকা পাঠাননি।"}],
        "advisories": [], "signals_checked": [], "safety_tip": {"en": "upay never asks for your PIN or OTP.", "bn": "..."},
        "features": {"amount": 6000.0}}]})
    decision: str = Field(..., description="ALLOW, WARN or HOLD (always ALLOW in shadow mode)")
    mode: str = Field("live", description="live or shadow")
    shadow_decision: Optional[str] = Field(None, description="In shadow mode: what ScamShield would have decided")
    action: str
    scam_probability: float
    anomaly_percentile: float
    engines_flagging: int
    latency_ms: float
    engines: List[Engine]
    rules: List[str]
    reasons: List[Text]
    advisories: List[Text]
    signals_checked: List[dict]
    safety_tip: Text
    features: dict


def _shadow_log(ts, req, level, prob, ms):
    """Append one pseudonymised line per transfer; joined later with confirmed fraud for the shadow report."""
    os.makedirs(os.path.dirname(SHADOW_LOG), exist_ok=True)
    new = not os.path.exists(SHADOW_LOG)
    with _lock, open(SHADOW_LOG, "a", encoding="utf-8") as fh:
        if new:
            fh.write("time,sender,receiver,amount,shadow_decision,scam_probability,latency_ms\n")
        fh.write(f"{ts},{pseudonymise(req.sender_id)},{pseudonymise(req.receiver_id)},{req.amount},{level},{prob:.4f},{ms:.1f}\n")


ERRORS = {401: {"description": "Missing or invalid X-API-Key"}, 422: {"description": "Invalid input"},
          429: {"description": "Rate limit exceeded (see Retry-After header)"}}


@app.get("/health")
def health():
    """Public liveness check (no customer data)."""
    return {"status": "ok", "mode": MODE, "dataset": WORKSPACE, "transfers_in_history": len(_raw), "suspected_mule_wallets": int(WALLETS.suspected_mule.sum()),
            "mule_rings": len(RINGS), "auth": "demo key in use: set SCAMSHIELD_API_KEYS" if DEMO_KEY else "API keys from environment"}


@app.get("/metrics", dependencies=[Depends(require_key)], responses=ERRORS)
def metrics():
    """Monitoring: decisions since start, latency percentiles of the last 5,000 requests, rejected requests."""
    lat = np.array(METRICS["latency_ms"]) if METRICS["latency_ms"] else np.array([0.0])
    return {"uptime_s": round(time.time() - METRICS["started"], 1), "decisions": dict(METRICS["decisions"]),
            "latency_ms": {p: round(float(np.percentile(lat, q)), 1) for p, q in (("p50", 50), ("p95", 95), ("p99", 99))},
            "rejected": dict(METRICS["rejected"])}


@app.post("/score", response_model=ScoreResponse, responses=ERRORS)
def score(req: ScoreRequest, key: str = Depends(require_key)):
    """Score one Send Money transfer before the customer confirms it."""
    t0 = time.perf_counter()
    ts = pd.Timestamp(req.timestamp or datetime.now())
    with _lock:   # the shared history is read and written by several requests: keep reads consistent
        f = STATE.peek(ts, req.sender_id, req.receiver_id, req.amount, req.device_id, req.district, req.on_active_call)
        sig = STATE.signals(ts, req.sender_id, req.receiver_id, req.amount)
    row = pd.Series(f)
    one = pd.DataFrame([row])
    prob, contribs = re_.score(MODEL, one)
    prob = float(prob[0])
    anom = float(re_.anomaly(IFOREST, one)[0])
    level, rules = re_.decide(prob, row, anom)
    engs, n_flag = en.engine_panel(prob, anom, row, req.receiver_id, WALLETS, RING_OF)
    if engs[3]["flagged"] and level == "ALLOW":
        level, rules = "WARN", rules + ["KNOWN_MULE_WALLET"]
    p_rules, notes = sg.pattern_rules(sig, row)
    if p_rules and level == "ALLOW":
        level = "WARN"
    rules = rules + p_rules
    reasons = [{"en": e, "bn": b} for lv, e, b in notes if lv == "warn"]
    reasons += [{"en": e, "bn": b} for _, _, e, b in re_.explain(row, contribs.iloc[0])]
    if "UNUSUAL_BEHAVIOUR" in rules:
        reasons.append({"en": re_.UNUSUAL_REASON[0], "bn": re_.UNUSUAL_REASON[1]})
    if req.commit:
        with _lock:
            STATE.update(int(ts.value // 10**9), req.sender_id, req.receiver_id, req.amount, req.device_id, req.district)
    ms = (time.perf_counter() - t0) * 1000
    METRICS["decisions"][level] += 1
    shadow = None
    if MODE == "shadow":
        shadow, level_out = level, "ALLOW"
        _shadow_log(ts, req, level, prob, ms)
    else:
        level_out = level
    METRICS["latency_ms"].append(ms)
    log.info("score sender=%s receiver=%s decision=%s p=%.3f ms=%.1f", pseudonymise(req.sender_id),
             pseudonymise(req.receiver_id), level, prob, ms)
    return {"decision": level_out, "mode": MODE, "shadow_decision": shadow, "latency_ms": round(ms, 1), "action": re_.ACTIONS[level_out][0], "scam_probability": round(prob, 4),
            "anomaly_percentile": round(anom, 4), "engines_flagging": int(n_flag),
            "engines": [dict(name=e["name"], method=e["method"], score=round(float(e["score"]), 4),
                             flagged=bool(e["flagged"]), finding=str(e["note"])) for e in engs],
            "rules": rules, "reasons": reasons,
            "advisories": [{"en": e, "bn": b} for lv, e, b in notes if lv == "info"],
            "signals_checked": [{"signal": n, "value": v, "status": s_} for n, v, s_ in
                                sg.checklist(row, sig, anom, bool(engs[3]["flagged"]), engs[3]["note"])], "safety_tip": {"en": re_.SAFETY_TIP[0], "bn": re_.SAFETY_TIP[1]},
            "features": {k: round(float(row[k]), 3) for k in re_.FEATURES}}


@app.get("/customers/{customer_id}/profile", dependencies=[Depends(require_key)], responses=ERRORS)
def profile(customer_id: str):
    """A customer's usual behaviour (for the analyst console)."""
    prep = pl.prepare(_raw)
    if customer_id not in set(prep.sender_id):
        raise HTTPException(404, "Unknown customer")
    return en.json_safe(pl.customer_profile(prep, customer_id, prep.timestamp.max() + pd.Timedelta(seconds=1)))
