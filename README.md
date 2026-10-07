# upay ScamShield: AI early warning for scam transfers

**AI DEV FEST 2026 AI Hackathon (DIU CPC x upay), Track 01: Trust and Risk Intelligence**

**Live demo:** https://upay-scamshield.streamlit.app
**Team:** M4LW4R3HYDR4S: Shobnom Sultana Muskan, Parvez Hossen Badal, Hakeemul Adnan Rafee
**University:** University of Information Technology and Sciences (UITS)

---

## 1. Project overview

**Problem.** Mobile wallet users in Bangladesh lose money to "send money" scams: fake prize calls, "I sent money to your number by mistake, please return it", and account takeovers after a PIN or OTP is stolen. The victim usually approves the transfer themselves, so the PIN does not protect them, and once money reaches a mule wallet it is cashed out quickly at an agent.

**Background.** The scam patterns in our synthetic data are based on public reports. Bangladesh Bank data reported by the Daily Observer puts payment-ecosystem fraud losses at about Tk 92.60 crore in 2025 ([source](https://observerbd.com/news/590829)). Reported methods include social engineering calls asking for the OTP ([source](https://observerbd.com/news/590830)), fake prize and lottery messages ([example case](https://en.prothomalo.com/bangladesh/Brahmanbaria-tea-seller-loses-Tk-65-000-in-Bkash)), and "money sent to you by mistake" calls, which bKash warns about on its fraud awareness page ([source](https://www.bkash.com/en/help/avoid-fraud)).

**Problem statement.** For first-time and less digitally confident upay users, phone-coached scam transfers cause direct money loss and reduce trust in the wallet. We built ScamShield, which uses each customer's own transaction history, the receiving wallet and the transfer network to warn or pause a risky transfer before the money leaves, to find the mule wallets that collect the money, and to stop that money at the agent when it is cashed out. Success is measured by scam money protected, false alarms on genuine transfers, analyst workload and mule rings discovered.

**Two datasets, one system.**

| Dataset | What it is | Models |
|---|---|---|
| **A · Demo** | Our synthetic data: the main raw transaction log, a cash-out log at 300 agents, and our earlier synthetic set (kept for comparison) | Trained on days 30 to 72, tested on the future days 72 to 90 |
| **B · Your data** | Anyone's own transaction log, loaded in the app or from the command line | ScamShield builds new models from it: a new anomaly model always, and a new classifier when the log has fraud labels |

**Solution.** ScamShield works directly on a raw transaction log, the kind of data upay already stores:

| Level | What it does |
|---|---|
| Each transfer | Independent engines check it in real time against the customer's own history; the result is ALLOW, WARN (Bangla reasons, the customer decides) or HOLD (re-verify and analyst review) |
| The network | Finds mule wallets that receive high-risk money from many victims and groups them into rings by their shared collector wallet |
| The agent counter | Scores every cash-out before the agent pays (PAY / VERIFY / HOLD) and compares each agent with its district peers |
| The fraud team | Evidence-based cases with status, notes, audit trail, PDF report, customer disputes, and a feedback loop that turns decisions into training labels |
| upay's systems | A secured real-time scoring API (`api.py`) that the Send Money flow calls before a transfer is confirmed |

The system never blocks money permanently on its own. High-impact cases go to a human, and the customer can dispute a HOLD.

## What changed after Phase 1 feedback

| Judge feedback | What we changed | Where to see it |
|---|---|---|
| Show where AI is used and that each engine adds something | "Where AI is used" table; engines added one at a time with detection per scam type; each engine alone and leave-one-out; unseen scam type retrained without it; engine agreement vs. precision | Model & Impact → Where AI is used, Engine contribution · `evaluation.py` |
| `ai_system` and `classifier_and_rules_only` had identical numbers | Explained and split: classifier only 86.5% → full system 87.4% (anomaly adds little on *known* scams); its value is the unseen type (classifier 40% → all engines 100%) | `model/metrics.json` (`note`), Engine contribution tab |
| Only 12 basic features | 2 new features (other accounts on the same phone in 30 days; transfer-velocity trend vs. the customer's own pace), retrained, shown in the feature chart; plus 14 pattern signals, network features and 10 cash-out features | Model & Impact → Where AI is used · `features.py`, `pipeline.py` |
| Robustness to new patterns not tested enough | Three brand-new synthetic worlds (new customers, 3x low-signal scams, 3x takeovers) scored by the current models without retraining, plus the unseen-type and cross-dataset tests | Model & Impact → Robustness |
| Too many false alarms keep analysts busy; WARN 0.3 / HOLD 0.7 are fixed | Low-workload policy (HOLD only when 2+ engines agree: 21x fewer genuine transfers to analysts, same scams caught); live threshold sliders with alerts per 10,000, HOLDs, analyst hours, scams caught and money protected | Sidebar → Analyst policy · Model & Impact → Threshold tuning, Analyst workload |
| Economics are assumed | Calculator inputs for your own monthly volume, yearly losses, analyst cost and analysts on duty; shows monthly totals and analysts needed | Model & Impact → Business impact |
| Warnings only help if users act | WARN outcome counter (cancelled vs. continued), and a "warned victims who cancel" assumption in the calculator | Send Money, Customer App, Analyst workload tab |
| Only Send Money, not cash-out at agents | Cash-out model (XGBoost on 10 features) + agent peer risk; 91% of mule cash-outs caught with 0.9% of genuine cash-outs flagged | Cash Out (agent) page · `cashout.py` |
| Looks like a dashboard, not a mobile app | Customer App page: the phone flow (recipient, amount, warning or pause in Bangla, PIN, outcome, dispute) | Customer App page |
| New users warned about twice as often | Classifier WARN for customers under 180 days needs 0.65 (chosen on the training period); test period 1.14% → 0.38% false alarms for new customers, no new-customer scam missed | Model & Impact → Fairness & drift · `risk_engine.py` |
| No appeal path; decisions don't improve the model | "Disputed by customer" and "Released: customer verified" statuses, SLA, second-analyst review; resolved cases exported as labels and merged into Dataset B with one-click retraining | Cases page · `cases.py` |
| API security not checked | API key (`X-API-Key`), per-key rate limit (429), input validation (422), request/response examples in `/docs`, pseudonymised logs, `/metrics` | `api.py` · tests |
| Holding everyone's history in memory won't scale; latency not shown | Bounded per-customer state (recent window) with older history as running statistics; compiled anomaly model for the live path; measured latency, throughput and memory; HTTP load test | Model & Impact → Performance & scale · `benchmark.py`, `loadtest.py` |
| Security, privacy, governance not clear | Security & governance panel listing only what is implemented, plus the production plan | Model & Impact → Security & governance |
| Synthetic data: how was it made? | Data note and data dictionary | Datasets page |
| Validate affected segments and loss concentration | Loss-concentration analysis by scam type, amount, customer tenure, time of day, receiving-wallet age and district: share of scam money, share protected, share still missed. Runs automatically on any labelled Dataset B | Model & Impact → Loss concentration · `monitoring.py` |
| Shadow mode, controlled pilot, pilot ROI on real data | `SCAMSHIELD_MODE=shadow` on the API (always answers ALLOW, logs what it would have done, pseudonymised); shadow report with written go-live criteria; A/B pilot sample-size calculator; ROI from the business calculator | Model & Impact → Shadow mode & pilot · `api.py`, `monitoring.py` |
| Integration with transaction authorization; resilience | `integration.py`: client for the Send Money service with a 150 ms budget, fail-open, retry queue with late alerts, circuit breaker (tested) | `integration.py` · tests |
| Differentiation vs. existing tools; pop-up warnings are common | "How it differs" comparison: personal reasons + measured cancel rate, engines that must agree, three stopping points (transfer, mule wallet, agent), label-free start, appeal that improves the model, staged go-live | Model & Impact → How it differs |
| Access controls | Roles (admin, fraud analyst, agent, customer) with page and action restrictions and an access log | Sidebar → Signed in as · Security & governance |

## 2. Features

- **Works on raw transaction logs.** Input is just `timestamp, sender, receiver, amount, device, district`. Every signal is computed from history by `pipeline.py`, point-in-time (only data from before each transfer), exactly as a live system would.
- **Per-customer behaviour.** Each customer's usual amount, usual hours, known devices, usual districts, contacts and normal pace are learned from their own past transfers.
- **14 model features**, including two added after Phase 1: `device_other_users_30d` (other accounts that used this phone in the last 30 days, which exposes shared fraud-farm handsets) and `txn_velocity_trend` (transfers in the last 24 hours vs. the customer's own long-run daily pace).
- **Engines with an agreement panel:** a scam classifier (XGBoost), a behaviour anomaly model (Isolation Forest, no labels needed), a takeover check against the customer's own habits, a network check of the receiving wallet, and the call-coaching rule. The app shows how many engines agree.
- **Money-mule network discovery:** graph analysis (NetworkX) finds wallets receiving high-risk money from many unrelated senders and groups them into rings by their shared collector.
- **Agent cash-out protection:** every cash-out is scored before the agent pays: money received in 24 h, share taken out, different senders, hours since it arrived, wallet age, mule-network status, high-risk money received, first visit to this agent, and the agent's risk vs. district peers. PAY / VERIFY / HOLD with Bangla reasons for the agent.
- **Customer App:** the Send Money flow as a customer sees it on the phone (recipient, amount, warning or pause, PIN, success, or dispute).
- **Explainable warnings:** SHAP values (XGBoost `pred_contribs`) turned into plain-language reasons in Bangla and English.
- **Business rules kept separate from ML** (`risk_engine.py`), including a separate WARN threshold for new customers.
- **Analyst policy switch:** Standard, or Low workload (HOLD only when 2+ engines agree; everything else is a WARN the customer decides).
- **Dataset B · your data:** load any CSV in the format below (in the app, or `python workspace.py your_log.csv`). ScamShield validates it (clear messages for bad files), learns every customer's habits, fits a new anomaly model and, with fraud labels, trains a new classifier on the earlier 70% and tests it on the later 30%. Each browser session gets its own private Dataset B, deleted after 12 hours.
- **Live customer scoring with scenarios and what-if, on one screen** (Send Money): 10 scenarios on real customers, every signal computed live, with a What-if panel to override any signal.
- **Pattern rules and advisories** (`signals.py`): same amount from 3+ people today, the 4th similar payment today, a burst followed by a 5x amount; new accounts get an advisory, not a block.
- **Case management:** escalate alerts or rings, status, analyst, notes, audit trail, PDF report, customer disputes with SLA, pseudonymised CSV export, and analyst decisions as new labels.
- **Model & Impact:** business impact calculator plus tabs for where AI is used, engine contribution, threshold tuning, analyst workload, robustness, fairness and drift, performance and scale, security and governance.
- **Secured real-time API:** `POST /score` with API key, rate limit, validation and documented examples; **shadow mode** (`SCAMSHIELD_MODE=shadow`) for the first weeks on real data.
- **Payment-flow client (`integration.py`):** 150 ms budget, fail-open (an outage never blocks a payment), retry queue with late alerts, circuit breaker.
- **Roles:** admin, fraud analyst, agent and customer each see only their pages; only an admin changes the policy, uploads data or exports real IDs; actions go to an access log.
- **Loss concentration, shadow report and pilot sizing:** where scam money concentrates and where it is still missed; go-live criteria; transfers needed for an A/B pilot.

## 3. Technology stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Data pipeline | pandas, NumPy (`pipeline.py`, point-in-time features with bounded memory; `signals.py`, pattern rules) |
| Classifiers | XGBoost (transfers and cash-outs) |
| Anomaly detection | scikit-learn Isolation Forest (compiled to NumPy arrays for the live path) |
| Network analysis | NetworkX, Graphviz (built into Streamlit) |
| Explainability | SHAP values via XGBoost `pred_contribs` |
| Monitoring | PSI drift, segment alert rates with Wilson intervals (`monitoring.py`), API `/metrics` |
| App / UI | Streamlit, custom CSS, inline SVG icons (`icons.py`) and Material Symbols; no emoji |
| API | FastAPI + Uvicorn |
| Case reports | ReportLab (PDF) |
| Testing | pytest (34 tests) |
| Hosting | Streamlit Community Cloud |

No external AI API or paid service is used.

## 4. Requirements

- Python 3.11 or newer, `pip`, `git`
- About 1 GB free disk space and 2 GB RAM; any laptop (no GPU needed)
- Python packages pinned in `requirements.txt` (the exact versions we tested)

## 5. Installation and setup

```bash
git clone https://github.com/YodirHydra/upay-scamshield
cd upay-scamshield
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 6. Environment variables

None are required. Optional:
- `SCAMSHIELD_API_KEYS="key1:600,key2:60"`: API keys and each key's requests per minute. If unset, the API uses the demo key `demo-key` and says so in `/health`. Set real keys outside a demo.
- `SCAMSHIELD_MODE=shadow` makes the API score silently: it always answers ALLOW and logs (pseudonymised) what it would have decided to `logs/shadow_log.csv`, for the shadow-mode report.
- `SCAMSHIELD_WORKSPACE` chooses the dataset the API runs on: `A` (demo, default) or `B` (your data, after `python workspace.py your_log.csv`).
- `SCAMSHIELD_SHARED_B=1` makes the app use that same shared Dataset B. By default every browser session gets its **own private Dataset B**; old uploads are deleted after 12 hours.

## 7. Run and build commands

```bash
python generate_data.py           # Dataset A: the main synthetic raw log in data/ (optional, already included)
python generate_data_profiles.py  # Dataset A: the earlier synthetic set in data/previous/ (optional, already included)
python train.py                   # features, both models, network analysis (optional, already included)
python cashout.py                 # agent cash-out log, cash-out model, agent peer risk (optional, already included)
python evaluation.py              # engine contribution, robustness, operating points, fairness (optional, already included)
python benchmark.py               # latency, throughput, memory (optional, already included)
python loadtest.py                # HTTP load test of the API, 1 and 2 workers (optional, already included)
SCAMSHIELD_MODE=shadow uvicorn api:app --port 8000   # shadow mode: always ALLOW, logs what it would have done
streamlit run app.py              # the app: open http://localhost:8501
uvicorn api:app --port 8000       # the API on Dataset A: open http://localhost:8000/docs (header X-API-Key: demo-key)

# Run ScamShield as a real model on your own data (Dataset B):
python workspace.py your_log.csv            # builds Dataset B in workspaces/B/
set SCAMSHIELD_WORKSPACE=B                   # Windows (macOS/Linux: export SCAMSHIELD_WORKSPACE=B)
uvicorn api:app --port 8000                  # the API now scores against your data
```

Example API call:

```bash
curl -X POST http://localhost:8000/score -H "X-API-Key: demo-key" -H "Content-Type: application/json" \
  -d '{"sender_id":"U00042","receiver_id":"W12345","amount":6000,"device_id":"DEV-1A2B","district":"Dhaka","on_active_call":1}'
```

The answer contains `decision` (ALLOW / WARN / HOLD), `scam_probability`, `anomaly_percentile`, `engines`, `rules`, Bangla and English `reasons`, `advisories`, the 14 `signals_checked`, `features` and `latency_ms`. A missing key returns 401, bad input 422, too many requests 429.

The trained models and data are committed, so `streamlit run app.py` works straight after install (the first load takes about 30 seconds while it learns every customer's history).

**Deploy (Streamlit Community Cloud):** push to a public GitHub repo, go to share.streamlit.io, choose *New app*, select the repo, branch `main`, main file `app.py`, Python 3.11 or newer in *Advanced settings*, then *Deploy*. Make sure the `.streamlit` folder is pushed too.

## 8. Live deployment URL

https://upay-scamshield.streamlit.app

## 9. Testing instructions

```bash
pytest -q
```

The 34 tests check, among other things: the payment-flow client failing open, scoring later and opening its circuit breaker; shadow mode always answering ALLOW with pseudonymised logs; loss concentration, the shadow report and pilot sizing; no future data leaks into features; the API's live features equal the training features; the model beats the rule baseline on future data; the anomaly model on an unseen scam type; mule rings without flagging shops; pattern rules and the new-account advisory; Dataset B from an unlabelled log with phone-style IDs and day-first dates; training on labels; the business estimate with an operator's own numbers; the two new features (point-in-time, bounded memory, running statistics); older logs without the new features still score; the new-customer threshold (and that rules and HOLD still fire); customer disputes, labels from cases and pseudonymised IDs; upload validation; the cash-out model against the rule; and the API's decisions, key check, input validation, rate limit and `/metrics`.

**Roles (sidebar → Signed in as):** Admin sees everything (default for the demo); Fraud analyst, Agent and Customer see only their pages.

**Pages (sidebar):** Command Center, Send Money, Customer App, Cash Out (agent), Analyst Queue, Mule Network, Dataset B · Your Data, Datasets, Cases, Model & Impact.

**Manual check in the app:**
1. *Customer App*: choose "Pay a usual contact" → Next → PIN screen. "Phone stolen" → paused, tap *This is a mistake* → the dispute appears in *Cases*. "Prize call" → warning in Bangla; *Cancel* or *Continue* is counted.
2. *Cash Out (agent)*: genuine scenarios PAY; the mule and collector scenarios HOLD with reasons for the agent.
3. *Send Money*: pick a customer and scenario; open What-if to override signals.
4. *Model & Impact*: move the threshold sliders; switch the sidebar Analyst policy to Low workload and watch analyst hours fall.
5. *Cases*: change status, record a customer dispute, release it, see the new label; on Dataset B, add the labels and retrain.
6. *Dataset B · Your Data*: upload a CSV (or the practice sample), then *Build Dataset B*.
7. API: `uvicorn api:app`, open `/docs`, *Authorize* with `demo-key`, try `POST /score`.

## 10. Data format and other configuration

| Column | Need | Meaning |
|---|---|---|
| txn_id | required | Unique transfer ID |
| timestamp | required | `2026-07-01 14:30:00` or `01/07/2026 14:30` |
| sender_id, receiver_id | required | Wallet IDs (up to 64 characters) |
| amount | required | BDT, more than 0 |
| device_id, district | required | Device used and where |
| on_active_call | optional | 1 if the customer was on a phone call |
| sender_created_at, receiver_created_at | optional | Wallet opening dates (strongly recommended) |
| is_fraud | optional | Confirmed fraud labels, 0 or 1 (enables accuracy check and retraining) |

Uploads: CSV in UTF-8, at most 50 MB and 1 million rows in the online app (no limit from the command line). Thresholds are in `risk_engine.py` and `mule_network.py`; they are business-policy settings. `data/ground_truth.csv` and `data/wallet_roles_ground_truth.csv` hold the synthetic labels and are used only for evaluation.

---

## Results

**Evaluated like a live system:** trained on days 30 to 72, tested on the *future*, days 72 to 90 (17,038 transfers, 325 scams).

| Metric | ScamShield | Classifier only | Simple rule* |
|---|---|---|---|
| Scams caught | **87.4%** | 86.5% | 42.5% |
| Precision (alerts that are real scams) | **75.9%** | 76.4% | 41.3% |
| Genuine transfers alerted | **0.54%** | 0.52% | 1.17% |
| Scam money protected | **93.1%** | 91.5% | 68.2% |
| ROC-AUC | 0.997 | 0.997 | N/A |

\*Rule: new recipient AND amount of at least BDT 5,000.

**Adding one engine at a time** (all engines plus the network check built from earlier data only): classifier 86.5% → + takeover check 87.4% (takeovers 93% → 97%) → + call-coaching rule 87.7% → + anomaly model 87.7% → + network check **88.9%** (takeovers 100%). The network check has 100% precision and catches 4 scams nothing else finds.

**Unseen scam type.** Every engine retrained with no account-takeover examples: the classifier alone caught 40% of the 73 test takeovers, the anomaly model alone 99%, all engines together **100%**.

**When engines agree:** 2+ engines agreeing are real scams 97.7% of the time, 3+ engines 100%. This is the basis of the low-workload policy.

**Robustness (changed world, no retraining).** New synthetic logs with different customers, mules and rings: same scam mix 94% caught (rule 41%); 3x low-signal scams 91% (rule 33%); a 3x takeover wave 95% (rule 41%). False alarms 0.8% in all three.

**Network.** 55 wallets flagged as mules, all real mules (100% precision), covering 71% of mule wallets that received money; all 12 rings found; 0 shops wrongly flagged.

**Cash-out at agents** (future cash-outs, 6,017 with 247 by mules): the cash-out model caught **91%** of mule cash-outs with 81% precision and **0.9%** of genuine cash-outs flagged (ROC-AUC 0.999); a simple fast in-and-out rule caught 37% while flagging 12.5% of genuine ones. 99% of genuine fast cash-outs were paid normally. Agent peer risk flagged 3 agents, all of them complicit, 0 wrongly.

**Fairness (tenure).** New customers (< 180 days) first had more false alarms (1.14% vs 0.54% in the test period). With the new-customer WARN threshold of 0.65 (chosen on the training period, where every new-customer scam scored 0.93 or more) the rate is **0.38%**, with no new-customer scam missed in either period. The group is small (528 genuine transfers in the test period), so the app shows confidence intervals and monitors it continuously.

**Cross-dataset test (earlier synthetic set).** Scoring our earlier, independently generated set with models trained only on the main log still catches 88% of scams (vs 49% for the simple rule), but false alarms rise to 6.2% because the data looks different. Retraining on that set brings false alarms down to 3.1% with 89% caught. This is why retraining in shadow mode is the first real-world step.

**Where losses concentrate (test window).** Phone-coached social engineering carries 52% of scam money (97% of it protected); low-signal scams are only 13% of scam money but **68% of the money still missed**, almost all sent to older "rented" mule accounts (receiving wallets older than 180 days hold 94% of missed money). This is why the network check and the cash-out check matter: they catch that money where it is collected and taken out.

**Shadow-mode report (test window, as it would be run on real data).** All 5 go-live criteria pass: scams caught 87% (target ≥ 70%), holds that are real scams 93% (≥ 50%), genuine transfers held 0.13% (≤ 0.2%), genuine transfers warned 0.4% (≤ 1%), latency p95 6.8 ms (≤ 50 ms). **Pilot size:** to detect a 50% drop from about 8 scam transfers per 100,000, an A/B pilot needs about 589,000 transfers per group, roughly 3 days at 400,000 send money transfers a day.

**Performance.** Live scoring of one transfer (features, classifier, anomaly model, SHAP reasons, rules): p50 4.4 ms, p95 6.8 ms in process. Over HTTP with API keys on a 2-core machine: 121 requests/s with 1 worker, **279 requests/s** with 2 workers (p95 52 ms with 8 concurrent clients). Customer state is about 1 KB per wallet (1.0 GB per million wallets in memory, about 0.6 KB serialised for a typical customer). Batch scoring: about 75,000 transfers/s.

**Business impact (estimate, per 100,000 send money transfers).** Our test data has far more scams than real life, so we apply the rates measured on future transfers to a realistic number of scams, from the Tk 92.60 crore yearly loss figure and Bangladesh Bank's 134.26 million send money transfers a month ([source](https://thefinancialexpress.com.bd/home/mfs-transactions-maintain-rising-trend-in-oct-25)). Assumptions: all reported losses are send money scams (base) or half of them (cautious); average scam Tk 7,114; a false WARN costs Tk 2; a HOLD costs Tk 20 for the customer plus 10 analyst minutes at Tk 300/hour; 60% of warned scam victims cancel. In the app, upay can replace the national volume and loss figures with its own.

| Per 100,000 transfers | Standard, base | Low workload, base | Low workload, cautious | Simple rule (base) |
|---|---|---|---|---|
| Alerts | 545 (413 WARN, 132 HOLD) | 545 (534 WARN, 11 HOLD) | 542 | 1,176 (all reviewed) |
| Analyst hours | 22.0 | **1.8** | 1.4 | 196 |
| Money protected | Tk 51,701 | Tk 47,255 | Tk 23,628 | Tk 39,172 |
| Friction cost | Tk 10,073 | Tk 1,834 | Tk 1,659 | Tk 82,325 |
| Protected per Tk 1 of friction | 5.1 | **25.8** | 14.2 | 0.5 |

In the stress test (half the losses, half the detection, twice the false alarms, 40% of warned victims cancel) the standard policy loses money (0.7x) but the low-workload policy still returns 3.6x, because few genuine transfers reach an analyst.

**Data quality matters.** On a short 15-day log with no wallet opening dates, false alarms rose to about 7%, because with little history many genuine transfers look "new". The app warns about this automatically.

## Synthetic data assumptions

All data is generated by `generate_data.py` (seed 42) and `cashout.py`; no real customer data or PII is used. The raw log contains no labels; labels are kept in a separate file, like a fraud team's confirmed cases. The Datasets page has a data note and a data dictionary.
- 3,000 customers over 90 days (the first 30 days only build history), each with a usual amount (median about BDT 1,100), usual active hours, one or two phones, a home district and 3 to 13 contacts; 92% of genuine transfers are inside usual hours; 10% go to someone new; 3% are large payments; 1% use a new phone; 3% are from another district.
- 12,000 people wallets (12% opened during the period), 300 shops, 60 popular wallets (e.g. landlords, family collectors).
- 80 mule wallets in 12 rings: 60% freshly opened, 40% older "rented" accounts; mules forward money to their ring's collector. Shops pay suppliers, so forwarding money is not suspicious by itself.
- Social engineering (1,000): normal hours, the customer's own phone, 1.5 to 8 times the usual amount, on a call 70% of the time. Account takeover (220 events, 523 transfers): new phone 85% (6 in 10 of those from a pool of 12 shared fraud-farm handsets), other district 70%, night 60%, 1 to 4 quick drains of 3 to 15 times the usual amount. Low-signal (270): normal-looking amounts to older mule accounts.
- Cash-outs: 20,056 at 300 agents (6 complicit). Mules and collectors take out 70 to 100% of what they receive within 0.3 to 8 hours, 65% at complicit agents; 30% of genuine cash-outs are also fast (e.g. family remittances), so speed alone is not suspicious.
- The patterns follow the cited public reports; the exact rates, amounts and timings are our assumptions, so the results are optimistic and must be re-measured on upay data.

## Responsible AI, security and governance

What is implemented (Model & Impact → Security & governance lists the same):
- **Privacy:** synthetic data only; the pipeline needs no names, phone numbers or NID; API logs and case exports use pseudonymised IDs (SHA-256); Dataset B is private per session, deleted after 12 hours and never committed (`workspaces/` is git-ignored).
- **API security:** API key on data endpoints (constant-time check), per-key rate limit (429 with Retry-After), input validation (422), public `/health` only.
- **Safe input handling:** uploads limited to CSV, 50 MB, 1 million rows, with column, ID, amount and label checks and clear error messages; every value from uploaded data or typed notes is HTML-escaped before display and in PDF reports.
- **Explainability:** every warning, cash-out decision and ring shows its reasons.
- **Human oversight and appeal:** WARN lets the customer decide; HOLD goes to an analyst within 30 minutes; the customer can dispute a HOLD ("This is a mistake"), and a second analyst releases the money or confirms fraud within 24 hours. Agents flagged by peer risk are reviewed, never blocked automatically.
- **Feedback loop:** resolved cases become labels; Dataset B can be retrained on them in one click.
- **Fairness:** separate WARN threshold for new customers, before/after measured on both periods, segment alert rates with confidence intervals monitored live.
- **Monitoring:** PSI drift per feature and score (stable < 0.10, watch 0.10 to 0.25, investigate > 0.25), API `/metrics` (decisions, latency percentiles, rejected requests).

- **Access control:** roles (admin, fraud analyst, agent, customer) limit pages and actions; only an admin can change the analyst policy, upload data or export real IDs; role changes, exports, disputes and retraining are written to an access log.

Production plan (not in this prototype): roles taken from upay's single sign-on instead of the demo menu, and pseudonymised IDs on screen for analysts by default; secrets manager for keys and the pseudonymisation salt; TLS and encryption at rest for state and logs; rate limiting at the API gateway (shared across workers); retention limits and a data-protection review; model registry with 2 weeks of shadow mode and approval before a model goes live; second-analyst review before labels are used for training (against label poisoning).

## Scalability and integration

```
upay app ──► Send Money service ──► POST /score (ScamShield API, stateless pods behind a load balancer)
                                        │  reads/updates per-customer state (Redis, one key per wallet, ~0.6 KB)
                                        ├─ XGBoost + compiled Isolation Forest + rules (≈ 5 ms)
                                        └─ mule-wallet list (refreshed by the nightly network job)
Agent app ──► Cash-out service ──► cash-out score (same pattern)        Analysts ──► console (cases, disputes, labels)
Core ledger ──► event stream ──► state updates, nightly network job, weekly retraining in shadow mode, drift monitor
```

- **Memory:** each customer keeps at most 300 recent amounts and hours, 500 contacts and 20 devices/districts; 1-hour and 24-hour windows are compacted; older history is kept as running statistics (count, mean and spread). Memory grows with active customers, not with transfers.
- **Throughput:** about 140 requests/s per CPU core over HTTP (measured); 1 million transfers in a peak hour (about 280/s) needs 2 to 4 cores with headroom.
- **Resilience (built in `integration.py`, tested):** the Send Money service gives ScamShield 150 ms. If it is slow or down, the transfer goes through (fail-open), is queued and scored a moment later, and a risky one is raised as a late alert; after 5 failures in a row a circuit breaker stops calling for 30 seconds. A ScamShield outage never stops payments.
- **Staged go-live:** shadow mode (`SCAMSHIELD_MODE=shadow`) → go-live criteria checked on confirmed fraud → A/B pilot sized in advance → full rollout.

## Path to production

1. Point `pipeline.py` at a governed, anonymised export of upay transfers (same columns) and retrain all models.
2. Run in shadow mode with upay's fraud team: score silently, compare with confirmed fraud, tune thresholds with the sliders.
3. Call `POST /score` from the Send Money flow and the cash-out score from the agent flow; run the network job daily.
4. A/B pilot measuring scam loss per 10,000 transfers, analyst hours and the cancel rate after warnings.
5. Feed analyst decisions and customer disputes back as labels; retrain weekly in shadow mode.
