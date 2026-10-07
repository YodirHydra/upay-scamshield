"""Run from the project root:  pytest -q"""
import json
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import engines as en  # noqa: E402
import mule_network as mn  # noqa: E402
import pipeline as pl  # noqa: E402
import risk_engine as re_  # noqa: E402
from features import FEATURES  # noqa: E402

RAW = pd.read_csv("data/transactions_raw.csv")


def _row(**kw):
    base = dict(amount=1200, amount_ratio=1.1, hour=14, outside_usual_hours=0, is_new_recipient=0,
                recipient_account_age_days=900, recipient_unique_senders_24h=1, user_txns_last_1h=0,
                device_changed=0, new_location=0, on_active_call=0, user_tenure_days=700)
    base.update(kw)
    return pd.Series(base)


def _network():
    w = mn.find_mules(pd.read_parquet("data/scored_all.parquet"))
    rings = mn.find_rings(w, RAW.rename(columns={"sender_id": "from_wallet", "receiver_id": "to_wallet"}))
    return w, rings, {m: r["ring_id"] for r in rings for m in r["mules"]}


# ---------- data and pipeline ----------
def test_raw_log_has_no_labels_and_validates():
    assert pl.validate(RAW) == []
    assert "is_fraud" not in RAW.columns and "scam_type" not in RAW.columns


def test_validate_catches_bad_input():
    bad = RAW.head(10).drop(columns=["amount"])
    assert any("amount" in p for p in pl.validate(bad))


def test_point_in_time_no_future_leakage():
    """Features of early transfers must not change when later transfers are added."""
    head = RAW.head(3000)
    a = pl.build_features(head)
    b = pl.build_features(RAW.head(6000)).head(3000)
    assert (a[FEATURES].values == b[FEATURES].values).all()


def test_live_scoring_matches_batch_features():
    """The API's live path (FeatureState.peek) gives exactly the batch features."""
    prep = pl.prepare(RAW)
    _, state = pl.run(prep.iloc[:-1])
    last = prep.iloc[-1]
    live = state.peek(last.timestamp, last.sender_id, last.receiver_id, last.amount, last.device_id, last.district,
                      last.on_active_call, last.sender_created_at, last.receiver_created_at)
    batch = pl.build_features(RAW).iloc[-1]
    for k in FEATURES:
        assert abs(float(live[k]) - float(batch[k])) < 0.01, k


def test_day_first_dates_and_data_quality_notes():
    small = RAW.head(200)[pl.REQUIRED].copy()
    small["timestamp"] = pd.to_datetime(small.timestamp).dt.strftime("%d/%m/%Y %H:%M")
    assert pl.validate(small) == []
    assert len(pl.data_quality(small)) >= 2


# ---------- models ----------
def test_model_beats_rule_baseline_on_future_data():
    m = json.load(open("model/metrics.json"))
    assert m["roc_auc"] > 0.9
    assert m["ai_system"]["scam_recall"] > m["rule_baseline"]["scam_recall"]


def test_normal_transfer_allowed():
    model, r = re_.load_model(), _row()
    p, _ = re_.score(model, pd.DataFrame([r]))
    assert re_.decide(float(p[0]), r)[0] == "ALLOW"


def test_phone_scam_flagged_with_reasons():
    model = re_.load_model()
    r = _row(amount=6000, amount_ratio=5.0, is_new_recipient=1, recipient_account_age_days=12,
             recipient_unique_senders_24h=23, on_active_call=1)
    p, c = re_.score(model, pd.DataFrame([r]))
    assert re_.decide(float(p[0]), r)[0] in ("WARN", "HOLD")
    assert len(re_.explain(r, c.iloc[0])) >= 1


def test_business_rule_independent_of_model():
    r = _row(device_changed=1, user_txns_last_1h=4)
    assert re_.decide(0.0, r)[0] == "HOLD"


def test_anomaly_model_flags_never_seen_pattern():
    f = re_.load_iforest()
    weird = _row(amount=20000, amount_ratio=15.0, hour=4, outside_usual_hours=1, user_txns_last_1h=8, new_location=1)
    a = re_.anomaly(f, pd.DataFrame([_row(), weird]))
    assert a[1] > a[0] and a[1] >= re_.ANOMALY_THRESHOLD


def test_anomaly_helps_on_unseen_scam_type():
    m = json.load(open("model/metrics.json"))["novel_scam_test_account_takeover_recall"]
    assert m["classifier_plus_anomaly"] > m["classifier_only"]


def test_mule_network_finds_rings_without_flagging_shops():
    w, rings, _ = _network()
    roles = pd.read_csv("data/wallet_roles_ground_truth.csv").set_index("wallet_id").role
    assert len(rings) >= 10
    assert not any(roles.get(x) == "shop" for x in w.index[w.suspected_mule])
    assert all(roles.get(r["collector"]) == "collector" for r in rings)


# ---------- engines and cases ----------
def test_profile_comparison_flags_deviations_from_own_baseline():
    prof = dict(usual_amount=1000, active_start=9, active_end=21, devices="DEV-AAAA", home_district="Dhaka",
                known_recipients=5)
    normal = en.profile_comparison(_row(amount=1100, device_id="DEV-AAAA", district="Dhaka"), prof)
    odd = en.profile_comparison(_row(amount=9000, hour=3, outside_usual_hours=1, device_changed=1, new_location=1,
                                     device_id="DEV-BBBB", district="Sylhet"), prof)
    assert not any(r["unusual"] for r in normal)
    assert sum(r["unusual"] for r in odd) >= 4


def test_engine_panel_counts_agreement():
    w, rings, ring_of = _network()
    takeover = _row(amount=15000, amount_ratio=10, hour=2, outside_usual_hours=1, device_changed=1, new_location=1,
                    user_txns_last_1h=3, is_new_recipient=1)
    assert en.engine_panel(0.95, 0.999, takeover, rings[0]["mules"][0], w, ring_of)[1] == 4
    assert en.engine_panel(0.01, 0.2, _row(), None, w, ring_of)[1] == 0


def test_case_workflow_no_duplicates_and_audit_and_pdf():
    import cases as cs
    store = []
    ev = dict(what="Test ৳1,000 transfer", why=["reason"], next="hold")
    c1, new1 = cs.create_case(store, "Transaction", "T1", "test", "Critical", ev)
    _, new2 = cs.create_case(store, "Transaction", "T1", "test", "Critical", ev)
    assert new1 and not new2 and len(store) == 1
    cs.update_status(c1, "In progress", "analyst")
    cs.add_note(c1, "called customer", "analyst")
    assert [a["action"] for a in c1["audit"]] == ["Case created", "Status changed", "Note added"]
    assert cs.pdf_report(c1)[:4] == b"%PDF"


# ---------- API ----------
def test_api_scores_live_transfers():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    import api
    c = TestClient(api.app, headers={"X-API-Key": next(iter(api.KEYS))})
    assert c.get("/health").json()["status"] == "ok"
    cust = api._raw.sender_id.value_counts().index[0]
    prof = c.get(f"/customers/{cust}/profile").json()
    ok = c.post("/score", json=dict(sender_id=cust, receiver_id=api._raw[api._raw.sender_id == cust].receiver_id.iloc[-1],
                                     amount=prof["usual_amount"], device_id=prof["devices"].split(",")[0],
                                     district=prof["home_district"], timestamp="2026-09-29 14:00:00")).json()
    bad = c.post("/score", json=dict(sender_id=cust, receiver_id="W00001", amount=prof["usual_amount"] * 10,
                                      device_id="DEV-NEW1", district="Bandarban", timestamp="2026-09-29 03:00:00")).json()
    assert ok["decision"] == "ALLOW" and bad["decision"] == "HOLD"


def test_previous_dataset_kept_and_scorable():
    """Dataset B (the previous synthetic dataset) is kept and can be scored by the current models."""
    prev = pd.read_csv("data/previous/transactions.csv")
    from features import NEUTRAL
    assert set(FEATURES) - set(NEUTRAL) <= set(prev.columns) and len(prev) == 60000   # newest features filled neutral
    sc = re_.score_frame(re_.load_model(), re_.load_iforest(), prev.head(5000))
    assert set(sc.decision.unique()) <= {"ALLOW", "WARN", "HOLD"}


def test_dataset_b_unlabelled_log_with_phone_ids():
    """Someone's own log (phone-style IDs, day-first dates, no labels) builds a working Dataset B."""
    import workspace as wsp
    raw = RAW.tail(20000).reset_index(drop=True)
    ids = pd.Series(pd.concat([raw.sender_id, raw.receiver_id]).unique())
    mp = dict(zip(ids, ["01" + str(7000000000 + i)[1:] for i in range(len(ids))]))
    log = pd.DataFrame({"txn_id": "TX" + raw.index.astype(str),
                        "timestamp": pd.to_datetime(raw.timestamp).dt.strftime("%d/%m/%Y %H:%M"),
                        "sender_id": raw.sender_id.map(mp), "receiver_id": raw.receiver_id.map(mp),
                        "amount": raw.amount.astype(str), "device_id": raw.device_id, "district": raw.district})
    log.to_csv("/tmp/_b_test.csv", index=False)
    try:
        m = wsp.build_b(wsp.read_log("/tmp/_b_test.csv"), "TEST")
        assert m["mode"] == "demo_classifier" and wsp.exists("TEST")
        scored = pd.read_parquet(wsp.paths("TEST")["test"])
        assert scored.user_id.str.startswith("01").all()          # leading zeros kept
        assert set(scored.decision.unique()) <= {"ALLOW", "WARN", "HOLD"}
    finally:
        wsp.delete("TEST")


def test_dataset_b_trains_new_model_when_labels_exist():
    import workspace as wsp
    gt = pd.read_csv("data/ground_truth.csv")
    log = RAW.merge(gt[["txn_id", "is_fraud"]], on="txn_id").tail(40000)
    try:
        m = wsp.build_b(log, "TEST")
        assert m["mode"] == "trained" and m["roc_auc"] > 0.8
        assert m["ai_system"]["scam_recall"] > m["rule_baseline"]["scam_recall"]
    finally:
        wsp.delete("TEST")


def test_business_impact_estimate():
    """ScamShield saves more than its friction in the base case and beats the simple rule; stress case is reported honestly."""
    import business as bz
    t = pd.read_parquet("data/test_scored.parquet")
    rates = bz.measured_rates(re_.score_frame(re_.load_model(), re_.load_iforest(), t))
    base = bz.estimate(rates, avg_scam=rates["avg_scam"])
    s, r = base["ScamShield"], base["Simple rule"]
    assert s["net"] > 0 and s["ratio"] > 2 and s["net"] > r["net"] and s["alerts"] < r["alerts"]
    stress = bz.estimate(rates, avg_scam=rates["avg_scam"], loss_share=0.5, detection_factor=0.5, false_alarm_factor=2)
    assert stress["ScamShield"]["friction"] > base["ScamShield"]["friction"]


def test_pattern_rules_and_new_account_advisory():
    """Same amount from many people / repeated same payments raise a WARN; a new account alone is only an advisory."""
    import signals as sg
    rules, notes = sg.pattern_rules(dict(recipient_similar_senders_24h=4, sender_similar_24h=0, recipient_received_ever=4),
                                    dict(recipient_account_age_days=400))
    assert "SAME_AMOUNT_COLLECTION" in rules and notes[0][0] == "warn"
    rules, _ = sg.pattern_rules(dict(recipient_similar_senders_24h=0, sender_similar_24h=3, recipient_received_ever=9),
                                dict(recipient_account_age_days=400))
    assert rules == ["REPEATED_SAME_AMOUNT"]
    rules, notes = sg.pattern_rules(dict(recipient_similar_senders_24h=0, sender_similar_24h=0, recipient_received_ever=0),
                                    dict(recipient_account_age_days=12))
    assert rules == [] and notes and notes[0][0] == "info" and "New account" in notes[0][1]
    rules, _ = sg.pattern_rules(dict(recipient_similar_senders_24h=0, sender_similar_24h=0, recipient_received_ever=5),
                                dict(recipient_account_age_days=900, user_txns_last_1h=7, amount_ratio=15))
    assert rules == ["BURST_THEN_LARGE"]
    assert len(sg.checklist(_row(), {}, 0.2, False, "no history")) == 14


def test_pending_transfers_count_in_live_signals():
    """Transfers sent earlier today in a live session are counted (same amount 3 times before -> 4th is flagged)."""
    _, state = pl.run(RAW.tail(5000))
    t = pl.prepare(RAW).timestamp.max() + pd.Timedelta(hours=2)
    cust = RAW.tail(5000).sender_id.value_counts().index[0]
    pend = [dict(t=t - pd.Timedelta(minutes=30 * k + 5), s=cust, r="W00099", a=2000) for k in range(3)]
    base = state.signals(t, cust, "W00099", 2000)
    sig = state.signals(t, cust, "W00099", 2000, pending=pend)
    f = state.peek(t, cust, "W00099", 2000, "DEV-X", "Dhaka", pending=pend)
    assert sig["sender_similar_24h"] - base["sender_similar_24h"] == 3 and f["is_new_recipient"] == 0.0


def test_api_requires_key_validates_input_and_rate_limits():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    import api
    body = dict(sender_id="U00001", receiver_id="W00001", amount=500, device_id="DEV-1", district="Dhaka")
    anon = TestClient(api.app)
    assert anon.post("/score", json=body).status_code == 401
    assert anon.post("/score", json=body, headers={"X-API-Key": "wrong"}).status_code == 401
    key = next(iter(api.KEYS))
    c = TestClient(api.app, headers={"X-API-Key": key})
    assert c.post("/score", json=dict(body, amount=-5)).status_code == 422
    assert c.post("/score", json=dict(body, sender_id="U" * 500)).status_code == 422
    old = api.KEYS[key]
    try:
        api.KEYS[key] = len(api._hits[key]) + 2
        codes = [c.post("/score", json=body).status_code for _ in range(4)]
        assert codes[:2] == [200, 200] and codes[-1] == 429
    finally:
        api.KEYS[key] = old
        api._hits[key].clear()
    m = c.get("/metrics").json()
    assert m["rejected"]["429 rate limit"] >= 1 and m["latency_ms"]["p95"] > 0


# ---------- Phase 1 feedback additions ----------
def test_new_features_are_point_in_time_and_bounded():
    import pipeline as pl
    st_ = pl.FeatureState()
    t0 = 1_780_000_000
    for i in range(10):                     # ten days of normal, one transfer a day
        st_.update(t0 + i * 86400, "U1", "W9", 500.0, "DEV-A", "Dhaka")
    f = st_.peek(pd.Timestamp(t0 + 10 * 86400, unit="s"), "U1", "W9", 500, "DEV-A", "Dhaka")
    assert f["txn_velocity_trend"] <= 2 and f["device_other_users_30d"] == 0
    for k in range(6):                      # a drain: six transfers in an hour from the same phone
        st_.update(t0 + 10 * 86400 + k * 300, "U1", f"W{k}", 900.0, "DEV-A", "Dhaka")
    f = st_.peek(pd.Timestamp(t0 + 10 * 86400 + 2000, unit="s"), "U1", "W7", 900, "DEV-A", "Dhaka")
    assert f["txn_velocity_trend"] >= 4      # 7 today vs. about 1.6 a day normally
    st_.update(t0 + 10 * 86400 + 4000, "U2", "W1", 100.0, "DEV-A", "Dhaka")   # another account on the same phone
    f = st_.peek(pd.Timestamp(t0 + 10 * 86400 + 5000, unit="s"), "U1", "W1", 100, "DEV-A", "Dhaka")
    assert f["device_other_users_30d"] == 1
    lr = st_.long_run("U1")
    assert lr["transfers"] == 16 and lr["mean_amount"] > 0
    for u in range(pl.MAX_DEVICE_USERS + 30):
        st_.update(t0 + 11 * 86400 + u, f"X{u}", "W1", 10.0, "DEV-SHARED", "Dhaka")
    assert len(st_.dev_users["DEV-SHARED"]) <= pl.MAX_DEVICE_USERS


def test_older_logs_without_new_features_still_score():
    import risk_engine as re_
    model, iforest = re_.load_model(), re_.load_iforest()
    old = pd.DataFrame([dict(amount=1000, amount_ratio=1, hour=12, outside_usual_hours=0, is_new_recipient=0,
                             recipient_account_age_days=900, recipient_unique_senders_24h=0, user_txns_last_1h=0,
                             device_changed=0, new_location=0, on_active_call=0, user_tenure_days=700)])
    out = re_.score_frame(model, iforest, old)
    assert out.decision.iat[0] == "ALLOW"


def test_new_customer_threshold_is_higher_but_rules_still_fire():
    import risk_engine as re_
    base = dict(amount=1000, amount_ratio=1, hour=12, outside_usual_hours=0, is_new_recipient=0,
                recipient_account_age_days=900, recipient_unique_senders_24h=0, user_txns_last_1h=0, device_changed=0,
                new_location=0, on_active_call=0, device_other_users_30d=0, txn_velocity_trend=1)
    assert re_.decide(0.5, pd.Series(dict(base, user_tenure_days=700)))[0] == "WARN"
    assert re_.decide(0.5, pd.Series(dict(base, user_tenure_days=30)))[0] == "ALLOW"
    coached = dict(base, user_tenure_days=30, on_active_call=1, is_new_recipient=1, amount=6000)
    assert re_.decide(0.1, pd.Series(coached))[0] == "WARN"
    assert re_.decide(0.9, pd.Series(dict(base, user_tenure_days=30)))[0] == "HOLD"


def test_dispute_and_feedback_labels():
    import cases as cs
    cases = []
    c, _ = cs.create_case(cases, "Transaction", "B:T000010", "t", "High", dict(what="w", why=[], next="n"))
    cs.customer_dispute(c, "It is my brother")
    assert c["status"] == "Disputed by customer" and any(a["action"] == "Customer dispute" for a in c["audit"])
    cs.update_status(c, "Released: customer verified", "Analyst 2")
    labs = cs.labels_from_cases(cases)
    assert labs == [dict(dataset="B", txn_id="T000010", is_fraud=0, case=c["id"], status="Released: customer verified")]
    raw = pd.DataFrame({"txn_id": ["T000009", "T000010"], "is_fraud": [1, 1]})
    merged, n = cs.merge_labels(raw, labs)
    assert n == 1 and list(merged.is_fraud) == [1, 0]
    p = cs.pseudonymise("U00042")
    assert p == cs.pseudonymise("U00042") and "U00042" not in p


def test_business_uses_operator_numbers():
    import business as bz
    r = dict(warn_genuine=0.004, hold_genuine=0.001, warn_scam=0.1, hold_scam=0.78, money_protected=0.93,
             rule_false_alarm=0.01, rule_recall=0.4, rule_money=0.6)
    a = bz.estimate(r)["ScamShield"]["protected"]
    b = bz.estimate(r, loss_per_year=bz.LOSS_PER_YEAR_TK * 2)["ScamShield"]["protected"]
    assert abs(b - 2 * a) < 1e-6


def test_cashout_model_scores_mule_above_customer():
    import cashout as co
    m = json.load(open("model/cashout_metrics.json"))
    assert m["model"]["caught"] > m["fast_in_out_rule"]["caught"] and m["model"]["false_alarm_rate"] < 0.03


def test_upload_validation_catches_bad_files():
    good = dict(txn_id="T1", timestamp="2026-07-01 10:00", sender_id="U1", receiver_id="W1", amount="100",
                device_id="D1", district="Dhaka")
    assert pl.validate(pd.DataFrame([good])) == []
    assert any("negative" in p for p in pl.validate(pd.DataFrame([dict(good, amount="-5")])))
    assert any("empty" in p for p in pl.validate(pd.DataFrame([dict(good, sender_id=" ")])))
    assert any("is_fraud" in p for p in pl.validate(pd.DataFrame([dict(good, is_fraud="7")])))
    assert any("Missing" in p for p in pl.validate(pd.DataFrame([{"a": 1}])))


def test_integration_client_fails_open_and_scores_later():
    from integration import ScamShieldClient
    state = {"up": False}

    def transport(url, body, headers, timeout):
        if not state["up"]:
            raise ConnectionRefusedError("down")
        return 200, {"decision": "HOLD" if body["amount"] > 10000 else "ALLOW", "scam_probability": 0.9}

    c = ScamShieldClient("http://scamshield", "k", max_failures=2, cooldown_s=0, transport=transport)
    t = dict(sender_id="U1", receiver_id="W1", amount=20000, device_id="D", district="Dhaka")
    r = c.authorize(t)
    assert r["decision"] == "ALLOW" and r["source"] == "fallback" and len(c.retry_queue) == 1   # payment not blocked
    state["up"] = True
    assert c.authorize(dict(t, amount=500))["source"] == "scamshield"
    late = c.drain_retry_queue()
    assert len(late) == 1 and late[0]["decision"] == "HOLD" and not c.retry_queue                # risky one raised later


def test_integration_client_circuit_breaker():
    from integration import ScamShieldClient
    calls = {"n": 0}
    clock = {"t": 0.0}

    def transport(url, body, headers, timeout):
        calls["n"] += 1
        raise TimeoutError()

    c = ScamShieldClient("http://x", "k", max_failures=3, cooldown_s=30, transport=transport, clock=lambda: clock["t"])
    for _ in range(10):
        assert c.authorize(dict(sender_id="U", receiver_id="W", amount=1, device_id="D", district="X"))["decision"] == "ALLOW"
    assert calls["n"] == 3 and c.stats["circuit_open_skips"] == 7       # stopped calling after 3 failures


def test_monitoring_loss_concentration_shadow_and_pilot():
    import monitoring as mo
    t = pd.read_parquet("data/test_scored.parquet")
    sc = re_.score_frame(re_.load_model(), re_.load_iforest(), t)
    tabs = mo.loss_concentration(t, (sc.decision != "ALLOW").values)
    assert abs(tabs["Amount"]["Share of scam money"].sum() - 1) < 1e-9 and "Scam type" in tabs
    m, crit = mo.shadow_report(sc.decision.values, t.is_fraud.values, t.amount.values, latency_p95_ms=7)
    assert set(crit.Pass) <= {"PASS", "FAIL"} and m["recall"] > 0.8
    assert mo.pilot_sample_size(1e-3, 0.5) < mo.pilot_sample_size(1e-4, 0.5)


def test_api_shadow_mode_always_allows(monkeypatch, tmp_path):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    import api
    monkeypatch.setattr(api, "MODE", "shadow")
    monkeypatch.setattr(api, "SHADOW_LOG", str(tmp_path / "shadow.csv"))
    c = TestClient(api.app, headers={"X-API-Key": next(iter(api.KEYS))})
    cust = api._raw.sender_id.value_counts().index[0]
    r = c.post("/score", json=dict(sender_id=cust, receiver_id="W00001", amount=20000, device_id="DEV-NEW1",
                                   district="Bandarban", timestamp="2026-09-29 03:00:00")).json()
    assert r["decision"] == "ALLOW" and r["shadow_decision"] == "HOLD" and r["mode"] == "shadow"
    log = open(tmp_path / "shadow.csv").read()
    assert "HOLD" in log and cust not in log                       # pseudonymised
