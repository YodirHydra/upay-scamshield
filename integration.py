"""
integration.py — how upay's Send Money (or cash-out) service calls ScamShield inside its authorization flow.

Production rules this client follows (Phase 1 feedback: "resilience" and "integration with authorization systems"):
  * Hard time budget: ScamShield must answer within `timeout_s` (default 150 ms) or it is skipped.
  * Fail-open: if ScamShield is slow, down or returns an error, the payment is NOT blocked. The transfer is
    authorised as usual and put on a retry queue, so it is still scored a moment later and, if risky, raised to
    the fraud team (a "late alert"). A ScamShield outage can never stop payments.
  * Circuit breaker: after `max_failures` failures in a row the client stops calling for `cooldown_s` seconds,
    so a broken ScamShield does not add delay to every payment.
  * Only the decision changes the flow: ALLOW → PIN screen; WARN → show reasons, customer decides; HOLD → pause,
    re-verify, analyst review.

Usage:
    client = ScamShieldClient("http://scamshield:8000", api_key="...")
    result = client.authorize(dict(sender_id=..., receiver_id=..., amount=..., device_id=..., district=...))
    # result["decision"], result["source"] ("scamshield" or "fallback"), result.get("reasons")
    late = client.drain_retry_queue()        # run every few seconds by a worker
"""
import json
import time
import urllib.error
import urllib.request
from collections import deque


def _http_transport(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())


class ScamShieldClient:
    def __init__(self, base_url, api_key, timeout_s=0.15, max_failures=5, cooldown_s=30, transport=_http_transport,
                 clock=time.monotonic):
        self.url = base_url.rstrip("/") + "/score"
        self.headers = {"Content-Type": "application/json", "X-API-Key": api_key}
        self.timeout, self.max_failures, self.cooldown = timeout_s, max_failures, cooldown_s
        self.transport, self.clock = transport, clock
        self.failures, self.open_until = 0, 0.0
        self.retry_queue = deque(maxlen=100_000)
        self.stats = {"scored": 0, "fallback": 0, "circuit_open_skips": 0, "late_alerts": 0}

    def _call(self, transfer):
        status, data = self.transport(self.url, transfer, self.headers, self.timeout)
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        return data

    def authorize(self, transfer):
        """Decision for one transfer inside the payment flow. Never raises, never blocks on a ScamShield problem."""
        now = self.clock()
        if now < self.open_until:                       # circuit open: skip straight to fallback
            self.stats["circuit_open_skips"] += 1
            return self._fallback(transfer, "circuit open")
        t0 = self.clock()
        try:
            data = self._call(transfer)
            if self.clock() - t0 > self.timeout:        # answered, but too late for the payment
                raise TimeoutError("over time budget")
        except Exception as ex:                         # timeout, connection refused, HTTP error, bad JSON ...
            self.failures += 1
            if self.failures >= self.max_failures:
                self.open_until = self.clock() + self.cooldown
            return self._fallback(transfer, type(ex).__name__)
        self.failures = 0
        self.stats["scored"] += 1
        return dict(data, source="scamshield")

    def _fallback(self, transfer, why):
        self.stats["fallback"] += 1
        self.retry_queue.append(dict(transfer, _queued_at=time.time()))
        return {"decision": "ALLOW", "source": "fallback", "reason": f"ScamShield unavailable ({why}); "
                "payment allowed and queued for scoring"}

    def drain_retry_queue(self, limit=1000):
        """Score queued transfers after the fact. Returns late alerts (WARN/HOLD) for the fraud team."""
        late, n = [], 0
        while self.retry_queue and n < limit and self.clock() >= self.open_until:
            t = self.retry_queue.popleft()
            n += 1
            body = {k: v for k, v in t.items() if not k.startswith("_")}
            try:
                data = self._call(body)
            except Exception:
                self.retry_queue.appendleft(t)          # still down: keep it and stop for now
                break
            if data.get("decision", data.get("shadow_decision")) in ("WARN", "HOLD"):
                late.append(dict(body, decision=data["decision"], scam_probability=data.get("scam_probability")))
        self.stats["late_alerts"] += len(late)
        return late
