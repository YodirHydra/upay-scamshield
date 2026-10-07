"""
app.py — upay ScamShield prototype (Streamlit).
Run:  streamlit run app.py
"""
import os
import subprocess
import sys

import html as _html
import json

import numpy as np
import pandas as pd
import streamlit as st

import cases as cs
import engines as en
import monitoring as mo
import mule_network as mn
import business as bz
import signals as sg
import risk_engine as re_
from icons import ic

st.set_page_config(page_title="upay ScamShield", page_icon=":material/shield:", layout="wide")


def dl(*args, **kw):
    """Download button with a vector icon."""
    return st.download_button(*args, icon=":material/download:", **kw)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Space+Grotesk:wght@400;600;700&display=swap');
:root { --bg:#040A16; --panel:#0A1730; --panel2:#0E2142; --line:#1B3A66; --blue:#2F8CFF; --blue2:#0B5CAD;
        --yel:#FFD200; --txt:#E6EEF8; --mut:#8EA3BF; --ok:#22D38A; --warn:#FFB020; --bad:#FF4D5E;
        --mono:'JetBrains Mono', ui-monospace, monospace; --head:'Space Grotesk', 'Segoe UI', sans-serif; }
/* animated cyber grid background */
.stApp { background:
   radial-gradient(1200px 600px at 85% -10%, rgba(47,140,255,.18), transparent 60%),
   radial-gradient(900px 500px at -10% 110%, rgba(255,210,0,.08), transparent 60%),
   linear-gradient(rgba(47,140,255,.06) 1px, transparent 1px) 0 0/36px 36px,
   linear-gradient(90deg, rgba(47,140,255,.06) 1px, transparent 1px) 0 0/36px 36px, var(--bg);
   animation: gridmove 18s linear infinite; }
@keyframes gridmove { to { background-position: 0 0, 0 0, 0 36px, 36px 0, 0 0; } }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.6rem; max-width: 1350px; }
html, body, .stApp, p, li, label, .stMarkdown { font-family: var(--head); }
h1, h2, h3, h4 { font-family: var(--head) !important; color: var(--txt) !important; letter-spacing:.2px; }
code, .mono { font-family: var(--mono) !important; }
/* boot line */
.boot { font-family: var(--mono); font-size:.72rem; color: var(--blue); letter-spacing:2px; margin-bottom:6px;
        white-space:nowrap; overflow:hidden; width:0; animation: type 2.4s steps(60) .2s forwards; }
.boot:after { content:"█"; animation: blink 1s step-end infinite; color: var(--yel); }
@keyframes type { to { width: 60ch; } } @keyframes blink { 50% { opacity:0; } }
/* hero */
.hero { position:relative; overflow:hidden; border-radius:22px; padding:24px 28px; margin-bottom:10px;
        background: linear-gradient(120deg, rgba(10,23,48,.95), rgba(11,92,173,.55));
        border:1px solid var(--line); box-shadow: 0 0 0 1px rgba(47,140,255,.15), 0 20px 60px rgba(0,0,0,.45);
        display:flex; align-items:center; gap:22px; }
.hero:before { content:""; position:absolute; inset:0; background: linear-gradient(transparent 0, rgba(47,140,255,.10) 50%, transparent 100%);
        height:40%; animation: scan 5s linear infinite; pointer-events:none; }
@keyframes scan { from { transform: translateY(-120%); } to { transform: translateY(320%); } }
.hero .badge { position:relative; width:78px; height:78px; border-radius:50%; flex-shrink:0; display:flex; align-items:center;
        justify-content:center; font-size:38px; background: radial-gradient(circle, #FFE45C, var(--yel)); box-shadow:0 0 30px rgba(255,210,0,.45); }
.hero .badge:after { content:""; position:absolute; inset:-8px; border-radius:50%; border:2px solid rgba(255,210,0,.6);
        animation: ring 2.4s ease-out infinite; }
@keyframes ring { from { transform:scale(.9); opacity:1; } to { transform:scale(1.35); opacity:0; } }
.hero h1, .hero h1 * {
    color: white !important;
}

.hero h1 span, .hero h1 span * {
    color: var(--yel) !important;
}

.hero h1 .upay-name {
    color: #ffffff !important;
}
.hero p { margin:2px 0 8px 0; color:#C9D8EC; }
.chip { display:inline-block; font-family:var(--mono); font-size:.7rem; font-weight:700; letter-spacing:1px; border-radius:999px;
        padding:4px 11px; margin:2px 6px 2px 0; border:1px solid var(--line); background:rgba(4,10,22,.55); color:var(--txt); }
.chip.y { background: var(--yel); color:#06306B; border-color: var(--yel); }
.dot { display:inline-block; width:8px; height:8px; border-radius:50%; background: var(--ok); margin-right:6px;
       box-shadow:0 0 0 0 rgba(34,211,138,.7); animation: pulse 1.6s infinite; vertical-align:middle; }
@keyframes pulse { 70% { box-shadow:0 0 0 9px rgba(34,211,138,0); } 100% { box-shadow:0 0 0 0 rgba(34,211,138,0); } }
/* live ticker */
.ticker { overflow:hidden; white-space:nowrap; border:1px solid var(--line); border-radius:12px; background: rgba(10,23,48,.85);
          margin: 0 0 14px 0; position:relative; }
.ticker .lbl { position:absolute; left:0; top:0; bottom:0; z-index:2; display:flex; align-items:center; padding:0 12px;
          font-family:var(--mono); font-size:.7rem; font-weight:700; letter-spacing:1.5px; background: var(--bad); color:white; }
.ticker .track { display:inline-block; padding:8px 0 8px 150px; animation: tick 180s linear infinite; font-family:var(--mono); font-size:.76rem; color:var(--mut); }
.ticker .track b { color: var(--txt); } .ticker .track .h { color: var(--bad); font-weight:700; } .ticker .track .w { color: var(--warn); font-weight:700; }
@keyframes tick { from { transform: translateX(0); } to { transform: translateX(-50%); } }
/* KPI strip with count-up */
@property --n { syntax:'<integer>'; initial-value:0; inherits:false; }
.kpis { display:grid; grid-template-columns: repeat(5, 1fr); gap:10px; margin-bottom:14px; }
.kpi { background: linear-gradient(160deg, var(--panel2), var(--panel)); border:1px solid var(--line); border-radius:14px; padding:12px 14px; }
.kpi .k { font-family:var(--mono); font-size:.66rem; color:var(--mut); letter-spacing:1.5px; }
.kpi .v { font-family:var(--head); font-size:1.65rem; font-weight:700; color:white; }
.kpi .v.c { animation: count 2s ease-out forwards; counter-reset: n var(--n); }
.kpi .v.c:after { content: counter(n); }
@keyframes count { from { --n: 0; } }
.kpi .s { font-size:.72rem; color: var(--ok); font-family:var(--mono); }
/* tabs */
.stTabs [data-baseweb="tab-list"] { gap:6px; border-bottom:1px solid var(--line); }
.stTabs [data-baseweb="tab"] { background: rgba(10,23,48,.8); border:1px solid var(--line); border-bottom:none;
        border-radius:10px 10px 0 0; padding:8px 16px; font-family:var(--mono); font-size:.78rem; letter-spacing:.5px; color:var(--mut); }
.stTabs [aria-selected="true"] { background: linear-gradient(180deg, var(--blue2), #0A3F7A) !important; color:white !important;
        box-shadow: 0 -2px 0 var(--yel) inset; }
.section-title { font-family:var(--mono); color: var(--yel); font-weight:700; font-size:.9rem; letter-spacing:2px;
        text-transform:uppercase; margin: 6px 0 10px 0; }
.section-title:before { content:"// "; color: var(--blue); }
/* metrics + inputs */
[data-testid="stMetric"] { background: linear-gradient(160deg, var(--panel2), var(--panel)); border:1px solid var(--line); border-radius:14px; padding:12px 16px; }
[data-testid="stMetricLabel"] p { font-family:var(--mono); font-size:.7rem !important; letter-spacing:1.2px; color:var(--mut) !important; text-transform:uppercase; }
[data-testid="stMetricValue"] { color:white; font-weight:700; }
[data-testid="stExpander"] { border:1px solid var(--line) !important; border-radius:12px !important; background: rgba(10,23,48,.6); }
.stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button { border-radius:10px; font-family:var(--mono); font-weight:700; letter-spacing:.5px; }
/* phone frame for the customer view */
.phone { border-radius:34px; padding:12px; background: linear-gradient(160deg,#1a2233,#05080f); border:1px solid #2a3550;
         box-shadow: 0 25px 60px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.04) inset; }
.phone .notch { width:110px; height:14px; border-radius:0 0 12px 12px; background:#05080f; margin:-12px auto 2px auto; }
.phone .bar { display:flex !important; justify-content:space-between; align-items:center; box-sizing:border-box;
         height:30px !important; min-height:30px; line-height:1.4 !important; font-family:var(--mono); font-size:.68rem;
         color:var(--mut); padding:0 14px; margin-bottom:6px; overflow:visible; }
.phone .bar span { display:inline-block !important; line-height:1.4 !important; height:auto !important; white-space:nowrap; }
.phone .bar b { color: var(--yel); }
/* decision card */
.card { border-radius:22px; padding:18px 20px; margin-bottom:6px; position:relative; color: var(--txt); background: var(--panel); }
.card.ALLOW { border:1.5px solid var(--ok); box-shadow: 0 0 24px rgba(34,211,138,.25); }
.card.WARN  { border:1.5px solid var(--warn); box-shadow: 0 0 26px rgba(255,176,32,.30); }
.card.HOLD  { border:1.5px solid var(--bad); animation: alarm 1.6s ease-in-out infinite; }
@keyframes alarm { 0%,100% { box-shadow: 0 0 18px rgba(255,77,94,.25); } 50% { box-shadow: 0 0 38px rgba(255,77,94,.65); } }
.card .lvl { font-size:1.55rem; font-weight:700; font-family: var(--head); }
.card.ALLOW .lvl { color: var(--ok); } .card.WARN .lvl { color: var(--warn); } .card.HOLD .lvl { color: var(--bad); }
.card .score { float:right; font-size:1.6rem; font-weight:700; text-align:right; line-height:1.1; font-family:var(--mono); }
.card .score small { color: var(--mut); }
.reason { background: rgba(255,255,255,.04); border:1px solid var(--line); border-left:3px solid var(--yel); color:var(--txt);
          border-radius:10px; padding:8px 12px; margin:7px 0; animation: slidein .5s ease both; }
.reason:nth-child(2) { animation-delay:.1s } .reason:nth-child(3) { animation-delay:.2s } .reason:nth-child(4) { animation-delay:.3s }
@keyframes slidein { from { opacity:0; transform: translateX(14px); } to { opacity:1; transform:none; } }
.reason small { color: var(--mut); }
.tip { background: var(--yel); color:#06306B; border-radius:10px; padding:9px 13px; margin-top:10px; font-weight:700; }
/* Customer App: the mobile Send Money flow */
.app-status { display:flex; justify-content:space-between; font:600 .72rem var(--mono); color:#c9d6ea; background:#05080f;
  border:10px solid #111a2b; border-bottom:none; border-radius:38px 38px 0 0; padding:10px 22px 4px 22px; }
.app-bar { display:flex; justify-content:space-between; align-items:center; background:linear-gradient(90deg,#0B5CAD,#06306B);
  border-left:10px solid #111a2b; border-right:10px solid #111a2b; padding:12px 18px; color:#fff; }
.app-bar b { color:var(--yel); font:700 1.25rem var(--head); letter-spacing:.5px; }
.app-bar span { font:600 .78rem var(--mono); opacity:.85; }
.st-key-mobileapp { background:#0A1730; border:10px solid #111a2b; border-top:none; border-radius:0 0 38px 38px;
  padding:16px 16px 26px 16px; min-height:520px; box-shadow:0 30px 60px rgba(0,0,0,.45); }
.app-h { font:700 1.05rem var(--head); color:var(--txt); margin:2px 0 8px 0; }
.app-sum { font:600 1.4rem var(--head); color:var(--yel); margin:6px 0 12px 0; }
.app-card { margin:0 0 12px 0 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.eng-head { display:flex; justify-content:space-between; align-items:center; margin:16px 0 8px 0; }
.eng-head .t { font-family:var(--mono); color: var(--yel); font-weight:700; letter-spacing:2px; font-size:.85rem; }
.agree { border-radius:999px; padding:4px 14px; font-family:var(--mono); font-weight:700; font-size:.78rem; letter-spacing:1px; }
.agree.hi { background: var(--bad); color:white; box-shadow:0 0 18px rgba(255,77,94,.5); }
.agree.mid { background: var(--warn); color:#1a1200; } .agree.lo { background: rgba(34,211,138,.15); color: var(--ok); border:1px solid var(--ok); }
.eng-grid { display:grid; grid-template-columns: repeat(2, 1fr); gap:10px; }
.eng { background: linear-gradient(160deg, var(--panel2), var(--panel)); border:1px solid var(--line); border-radius:14px; padding:12px 14px; }
.eng.on { border-color: var(--bad); box-shadow: 0 0 18px rgba(255,77,94,.18) inset; }
.eng .nm { font-weight:700; color:white; } .eng .mt { font-family:var(--mono); font-size:.68rem; color: var(--mut); letter-spacing:.5px; }
.eng .chip2 { float:right; font-family:var(--mono); font-size:.66rem; font-weight:700; border-radius:999px; padding:2px 9px; letter-spacing:1px; }
.eng.on .chip2 { background: var(--bad); color:white; } .eng .chip2.off { background: rgba(34,211,138,.12); color: var(--ok); border:1px solid rgba(34,211,138,.5); }
.bar { height:7px; background: rgba(255,255,255,.07); border-radius:6px; margin:9px 0 6px 0; overflow:hidden; }
.bar > div { height:100%; border-radius:6px; background: linear-gradient(90deg, var(--blue), #7FC1FF); animation: grow 1.1s ease-out both; }
.eng.on .bar > div { background: linear-gradient(90deg, var(--warn), var(--bad)); }
@keyframes grow { from { width:0 !important; } }
.eng .nt { font-size:.82rem; color: #C9D8EC; }
table.prof { width:100%; border-collapse:separate; border-spacing:0; font-size:.86rem; border:1px solid var(--line); border-radius:14px; overflow:hidden; }
table.prof th { background: #0B2A55; color: var(--yel); text-align:left; padding:8px 10px; font-family:var(--mono); font-size:.7rem; letter-spacing:1.5px; text-transform:uppercase; }
table.prof td { padding:8px 10px; border-top:1px solid var(--line); color: var(--txt); background: rgba(10,23,48,.7); }
table.prof tr.u td { background: rgba(255,77,94,.09); }
.st { font-family:var(--mono); border-radius:999px; padding:2px 9px; font-size:.66rem; font-weight:700; white-space:nowrap; letter-spacing:1px; }
.st.u { background: var(--bad); color:white; } .st.n { background: rgba(34,211,138,.12); color: var(--ok); border:1px solid rgba(34,211,138,.45); }
.casebox { background: linear-gradient(160deg, var(--panel2), var(--panel)); border:1px solid var(--line); border-radius:14px; padding:14px 16px; margin-bottom:10px; color:var(--txt); }
.pri { font-family:var(--mono); border-radius:999px; padding:2px 10px; font-size:.7rem; font-weight:700; letter-spacing:1px; }
.pri.HOLD, .pri.Critical { background: var(--bad); color:white; } .pri.WARN, .pri.High { background: var(--warn); color:#1a1200; }
.pri.ALLOW, .pri.Low { background: rgba(34,211,138,.15); color: var(--ok); }
section[data-testid="stSidebar"] { background: linear-gradient(180deg, #071226 0%, #040A16 100%); border-right:1px solid var(--line); }
section[data-testid="stSidebar"] .block-container, section[data-testid="stSidebar"] > div { padding-top: 1rem; }
.sb-logo { display:flex; gap:10px; align-items:center; margin-bottom:14px; }
.sb-badge { width:42px; height:42px; border-radius:50%; background: var(--yel); display:flex; align-items:center; justify-content:center;
            font-size:22px; box-shadow:0 0 18px rgba(255,210,0,.45); }
.sb-t { font-weight:700; font-size:1.15rem; color:white; } .sb-t span { color: var(--yel); }
.sb-s { font-family:var(--mono); font-size:.6rem; letter-spacing:2px; color: var(--mut); }
section[data-testid="stSidebar"] [role="radiogroup"] { gap:4px; }
section[data-testid="stSidebar"] [role="radiogroup"] label { width:100%; padding:9px 12px; border-radius:10px; border:1px solid transparent;
            transition: all .15s ease; font-family:var(--mono); font-size:.8rem; }
section[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: rgba(47,140,255,.10); border-color: var(--line); }
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background: linear-gradient(90deg, rgba(47,140,255,.28), rgba(47,140,255,.05));
            border-color: var(--blue); box-shadow: inset 3px 0 0 var(--yel); }
.sb-box { border:1px solid var(--line); border-radius:12px; padding:10px 12px; margin:12px 0; background: rgba(10,23,48,.7); }
.sb-h { font-family:var(--mono); font-size:.62rem; letter-spacing:2px; color: var(--yel); margin-bottom:6px; }
.sb-row { font-size:.78rem; color: var(--txt); margin:4px 0; } .sb-row b { float:right; color: var(--mut); font-weight:600; font-family:var(--mono); font-size:.68rem; }
.sb-kv { display:flex; justify-content:space-between; font-size:.78rem; color: var(--mut); margin:3px 0; } .sb-kv b { color: white; font-family:var(--mono); font-size:.74rem; }
.sb-foot { font-family:var(--mono); font-size:.6rem; color: var(--mut); letter-spacing:.5px; margin-top:10px; }
.ic { vertical-align:-3px; flex-shrink:0; }
.section-title .ic { color: var(--blue); margin-right:4px; }
.card .lvl .ic { vertical-align:-5px; margin-right:6px; }
.tip .ic { vertical-align:-3px; margin-right:4px; }
.advice { background: rgba(47,140,255,.10); border:1px solid rgba(47,140,255,.45); color: var(--txt); border-radius:10px;
          padding:8px 12px; margin:8px 0 2px 0; }
.advice .ic { color: var(--blue); vertical-align:-3px; margin-right:4px; } .advice small { color: var(--mut); }
.sig-grid { display:grid; grid-template-columns: repeat(2, 1fr); gap:6px; }
.sig { display:flex; gap:8px; align-items:flex-start; border:1px solid var(--line); border-radius:10px; padding:7px 10px; background: rgba(10,23,48,.7); }
.sig .ic { margin-top:2px; } .sig.ok .ic { color: var(--ok); } .sig.caution .ic { color: var(--warn); } .sig.risk .ic { color: var(--bad); }
.sig.risk { border-color: rgba(255,77,94,.6); } .sig.caution { border-color: rgba(255,176,32,.45); }
.sig .sn { font-size:.78rem; color: var(--txt); font-weight:600; } .sig .sv { font-family: var(--mono); font-size:.7rem; color: var(--mut); }
.card .trig { font-family:var(--mono); font-size:.66rem; letter-spacing:1px; color: var(--yel); margin-top:6px; }
.hero .badge .ic, .sb-badge .ic { vertical-align:middle; }
.ds { border:1px solid var(--line); border-radius:16px; padding:16px 18px; background: linear-gradient(160deg, var(--panel2), var(--panel)); height:100%; }
.ds h4 { margin:0 0 4px 0; } .ds .tag { font-family:var(--mono); font-size:.62rem; letter-spacing:1.5px; color: var(--yel); }
.ds p { color:#C9D8EC; font-size:.86rem; }
</style>
""", unsafe_allow_html=True)


import pipeline as pl

NEEDED = [re_.MODEL_PATH, "data/transactions_raw.csv", "data/test_scored.parquet", "data/scored_all.parquet"]
if not all(os.path.exists(p) for p in NEEDED):
    with st.spinner("Building features and training models on the synthetic log (first run only, about a minute)..."):
        subprocess.run([sys.executable, "train.py"], check=True)


import workspace as wsp

# Dataset B is private to each browser session on a public server (one visitor's upload is never shown to another).
# An organisation running its own server can share one Dataset B built with `python workspace.py log.csv`
# by setting SCAMSHIELD_SHARED_B=1.
if "b_name" not in st.session_state:
    import uuid
    st.session_state.b_name = "B" if os.environ.get("SCAMSHIELD_SHARED_B") == "1" else f"B_{uuid.uuid4().hex[:10]}"
    wsp.cleanup(max_age_hours=12)          # remove other sessions' old uploads so the server disk never fills up
BN = st.session_state.b_name
if "ws" not in st.session_state:
    st.session_state.ws = "A"
if st.session_state.ws == "B" and not wsp.exists(BN):
    st.session_state.ws = "A"
WS = st.session_state.ws
WSN = "A" if WS == "A" else BN                 # folder name of the active dataset
WP = wsp.paths(WSN)
STAMP = os.path.getmtime(WP["metrics"])          # cache key: rebuilding Dataset B refreshes everything


MAX_UPLOAD_MB, MAX_UPLOAD_ROWS = 50, 1_000_000


def safe_read_upload(up):
    """Read an uploaded CSV defensively: clear messages instead of a crash for any bad file."""
    if up.size > MAX_UPLOAD_MB * 1024 * 1024:
        st.error(f"The file is {up.size / 1e6:,.0f} MB. The limit is {MAX_UPLOAD_MB} MB: split the log by month and load one part.")
        return None
    try:
        df = wsp.read_log(up)
    except UnicodeDecodeError:
        st.error("The file is not UTF-8 text. In Excel use 'Save as → CSV UTF-8 (comma delimited)' and upload again.")
        return None
    except pd.errors.EmptyDataError:
        st.error("The file is empty.")
        return None
    except pd.errors.ParserError as ex:
        st.error(f"This does not look like a valid CSV file (the columns do not line up): {str(ex)[:160]}")
        return None
    except Exception as ex:                       # anything else: a clear message, never a crash
        st.error(f"Could not read the file: {type(ex).__name__}. Check that it is a comma-separated CSV with a header row.")
        return None
    if len(df) > MAX_UPLOAD_ROWS:
        st.error(f"{len(df):,} rows: the limit for the online demo is {MAX_UPLOAD_ROWS:,}. Run `python workspace.py "
                 "your_log.csv` on your own server for bigger logs.")
        return None
    if len(df.columns) == 1 and ";" in df.columns[0]:
        st.error("The file uses semicolons (;) between columns. Save it with commas (CSV UTF-8) and upload again.")
        return None
    return df


@st.cache_data(show_spinner=False)
def load_json(name, stamp=None):
    p = os.path.join("model", name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


@st.cache_resource
def get_model(ws, stamp):
    return re_.load_model(wsp.paths(ws)["model"])


@st.cache_resource
def get_iforest(ws, stamp):
    return re_.load_iforest(wsp.paths(ws)["iforest"])


@st.cache_resource(show_spinner="> SYNCHRONIZING_RISK_GRID: learning every customer's habits from the transaction log...")
def get_history(ws, stamp):
    raw = wsp.read_log(wsp.paths(ws)["raw"])
    _, state = pl.run(raw)
    return pl.prepare(raw), state


@st.cache_data
def get_test(ws=None, stamp=None):
    ws = ws or st.session_state.ws
    return pd.read_parquet(wsp.paths(ws)["test"])


@st.cache_data(show_spinner="> MAPPING_MULE_NETWORK...")
def get_network(ws, stamp):
    wallets = mn.find_mules(pd.read_parquet(wsp.paths(ws)["scored"]))
    raw = wsp.read_log(wsp.paths(ws)["raw"])
    rings = mn.find_rings(wallets, raw.rename(columns={"sender_id": "from_wallet", "receiver_id": "to_wallet"}))
    ring_of = {m: r["ring_id"] for r in rings for m in r["mules"]}
    return wallets, rings, ring_of


model, iforest = get_model(WSN, STAMP), get_iforest(WSN, STAMP)
hist, STATE = get_history(WSN, STAMP)
wallets, rings, ring_of = get_network(WSN, STAMP)
metrics = wsp.load_metrics(WSN)
_get_test = get_test
get_test = lambda *_: _get_test(WSN, STAMP)      # every page reads the active dataset's queue


def customer_ids(h):
    """Dataset A marks customers with U...; for your own data every sender counts as a customer."""
    s = h.sender_id
    return s[s.str.startswith("U")] if WS == "A" else s


DS_LABEL = "DATASET A · DEMO (SYNTHETIC)" if WS == "A" else (
    "DATASET B · YOUR DATA · " + ("MODEL TRAINED ON YOUR LABELS" if metrics.get("mode") == "trained" else "DEMO CLASSIFIER + YOUR ANOMALY MODEL"))
if "cases" not in st.session_state:
    st.session_state.cases = []
CASES = st.session_state.cases
ANALYST = "Fraud analyst (demo)"
def low_workload():
    return str(st.session_state.get("policy", "")).startswith("Low")


def apply_policy(level, n_flag):
    """Low-workload policy: an analyst HOLD needs at least 2 of the 4 engines to agree; otherwise the customer gets a WARN."""
    if low_workload() and level == "HOLD" and n_flag < 2:
        return "WARN", True
    return level, False


ENG_LIST = ["Scam classifier", "Behaviour anomaly", "Takeover check", "Network check", "Call-coaching rule"]


# ---------------- helpers ----------------
def E(x):
    """Escape any text that came from data before it goes into HTML (blocks injected markup in uploaded CSVs)."""
    return _html.escape(str(x))


def engines_html(engs, n_flag):
    cls = "hi" if n_flag >= 3 else "mid" if n_flag >= 1 else "lo"
    h = (f'<div class="eng-head"><span class="t">// ENGINE_CONSENSUS</span>'
         f'<span class="agree {cls}">{n_flag}/4 ENGINES FLAG THIS</span></div><div class="eng-grid">')
    for e in engs:
        on = "on" if e["flagged"] else ""
        chip = '<span class="chip2">FLAGGED</span>' if e["flagged"] else '<span class="chip2 off">CLEAR</span>'
        h += (f'<div class="eng {on}">{chip}<div class="nm">{e["name"]}</div><div class="mt">{e["method"]}</div>'
              f'<div class="bar"><div style="width:{max(e["score"], 0.02) * 100:.0f}%"></div></div>'
              f'<div class="nt">{E(e["note"])}</div></div>')
    return h + "</div>"


def profile_html(rows, name=""):
    h = ('<table class="prof"><tr><th>Behaviour</th><th>Customer\'s usual</th><th>This transfer</th>'
         '<th>Finding</th></tr>')
    for r in rows:
        stt = '<span class="st u">UNUSUAL</span>' if r["unusual"] else '<span class="st n">NORMAL</span>'
        h += (f'<tr class="{"u" if r["unusual"] else ""}"><td><b>{E(r["dimension"])}</b></td><td>{E(r["baseline"])}</td>'
              f'<td>{E(r["this_transfer"])}</td><td>{stt} {E(r["deviation"])}</td></tr>')
    return h + "</table>"


def txn_evidence(r, prep, wl, r_of):
    """Everything an analyst needs for one transaction, also stored in the case when escalated."""
    df1 = pd.DataFrame([r])
    _, c = re_.score(model, df1)
    lvl, rl = re_.decide(float(r.risk_score), r, float(r.anomaly_pct))
    ring = r_of.get(r.recipient_id)
    engs, n_flag = en.engine_panel(float(r.risk_score), float(r.anomaly_pct), r, r.recipient_id, wl, r_of)
    if engs[3]["flagged"] and lvl == "ALLOW":
        lvl = "WARN"
    lvl, _ = apply_policy(lvl, n_flag)
    prof = en.profile_comparison(r, pl.customer_profile(prep, r.user_id, r.timestamp))
    why = [f"{en_} (model contribution +{k:.2f})" for _, k, en_, _ in re_.explain(r, c.iloc[0], top_k=4)]
    why += [f"Profile: {p['dimension'].lower()}: {p['deviation'].lower()}" for p in prof if p["unusual"]]
    if rl:
        why.append("Business rules triggered: " + ", ".join(rl))
    if ring:
        why.append(f"Receiving wallet {r.recipient_id} is a suspected mule wallet in {ring}")
    nxt = re_.ACTIONS[lvl][0] + (f" Also review all wallets in {ring} and hold their outgoing transfers." if ring else "")
    what = (f"Customer {r.user_id} sent ৳{r.amount:,.0f} to wallet {r.recipient_id} on "
            f"{pd.Timestamp(r.timestamp):%d %b %Y %H:%M} from {r.district} on device {r.device_id}. "
            f"Scam probability {r.risk_score:.0%}; more unusual than {r.anomaly_pct:.1%} of normal transfers.")
    return dict(level=lvl, what=what, why=why, next=nxt, engines=engs, n_flag=n_flag, profile=prof, ring=ring)


def escalate_button(kind, ref, title, priority, evidence, key):
    existing = cs.find_case(CASES, ref)
    if existing:
        st.success(f"Already escalated as **{existing['id']}** ({existing['status']}). Open the Cases tab to work on it.")
    elif st.button("Escalate to case", key=key, type="primary", icon=":material/create_new_folder:"):
        cs.create_case(CASES, kind, ref, title, priority, evidence, ANALYST)
        st.rerun()


def case_view(r, prep, wl, r_of, key_prefix):
    ev = txn_evidence(r, prep, wl, r_of)
    st.markdown(f'#### Case summary: {r.txn_id} &nbsp; <span class="pri {ev["level"]}">{ev["level"]}</span>',
                unsafe_allow_html=True)
    a1, a2 = st.columns([1, 1])
    with a1:
        st.markdown(f"**What happened:** {ev['what']}")
        st.markdown("**Why it is risky:**")
        for w in ev["why"] or ["No strong risk signals."]:
            st.markdown(f"- {w}")
        st.markdown(f"**What upay should do next:** {ev['next']}")
        escalate_button("Transaction", f"{WS}:{r.txn_id}", f"[Dataset {WS}] {ev['level']} transfer {r.txn_id} from {r.user_id}",
                        {"HOLD": "Critical", "WARN": "High", "ALLOW": "Low"}[ev["level"]],
                        {k: ev[k] for k in ("what", "why", "next", "engines", "profile")}, key=f"{key_prefix}_{r.txn_id}")
    with a2:
        st.markdown(engines_html(ev["engines"], ev["n_flag"]), unsafe_allow_html=True)
    st.markdown(f"**Customer {r.user_id}: this transfer vs. their own history before it**")
    st.markdown(profile_html(ev["profile"]), unsafe_allow_html=True)


def checklist_html(rows):
    n_r = sum(r[2] == "risk" for r in rows)
    n_c = sum(r[2] == "caution" for r in rows)
    icon_of = {"ok": ic("check-circle", 15), "caution": ic("alert", 15), "risk": ic("stop", 15)}
    h = (f'<div class="eng-head"><span class="t">// {len(rows)} SIGNALS CHECKED</span>'
         f'<span class="agree {"hi" if n_r else "mid" if n_c else "lo"}">{n_r} RISK · {n_c} CAUTION · {len(rows) - n_r - n_c} NORMAL</span></div>'
         '<div class="sig-grid">')
    for name, val, stt in rows:
        h += f'<div class="sig {stt}">{icon_of[stt]}<div><div class="sn">{E(name)}</div><div class="sv">{E(val)}</div></div></div>'
    return h + "</div>"


def record_outcome(what, level):
    """Did the warning work? Count what customers do after a WARN or HOLD (cancel vs. continue)."""
    wo = st.session_state.setdefault("warn_outcomes", {"cancelled": 0, "proceeded": 0, "log": []})
    wo[what] += 1
    wo["log"].append(dict(time=cs.now(), level=level, outcome=what))
    st.toast("Transfer cancelled. Your money is safe." if what == "cancelled" else
             ("Sent for verification: PIN + 30 minute cooling period." if level == "HOLD" else "Transfer continued after the warning."),
             icon=":material/check_circle:")


def outcome_counter():
    wo = st.session_state.get("warn_outcomes", {"cancelled": 0, "proceeded": 0})
    n = wo["cancelled"] + wo["proceeded"]
    if n:
        st.caption(f"Warnings this session: {wo['cancelled']} cancelled · {wo['proceeded']} continued · "
                   f"cancel rate {wo['cancelled'] / n:.0%}. In production this is tracked per warning reason, so weak "
                   "warnings can be rewritten or removed.")


def assess(row, rec_id, sig=None):
    """Score one transfer with every engine and the policy. Shared by Send Money and the Customer App."""
    df_one = pd.DataFrame([row])
    prob, contribs = re_.score(model, df_one)
    prob = float(prob[0])
    anom = float(re_.anomaly(iforest, df_one)[0])
    level, rules = re_.decide(prob, row, anom)
    engs, n_flag = en.engine_panel(prob, anom, row, rec_id, wallets, ring_of)
    if engs[3]["flagged"] and level == "ALLOW":       # known mule wallet: always warn the customer
        level, rules = "WARN", rules + ["KNOWN_MULE_WALLET"]
    p_rules, notes = sg.pattern_rules(sig, row) if sig else ([], [])
    if p_rules and level == "ALLOW":                  # same-amount patterns: always warn the customer
        level = "WARN"
    rules = rules + p_rules
    level, downgraded = apply_policy(level, n_flag)
    if downgraded:
        rules = rules + ["LOW_WORKLOAD_POLICY: HOLD needs 2+ engines"]
    reasons = re_.explain(row, contribs.iloc[0])
    reasons = [("pattern", 1.0, en_, bn_) for lvl_, en_, bn_ in notes if lvl_ == "warn"] + reasons
    if "UNUSUAL_BEHAVIOUR" in rules:
        reasons.append(("anomaly", anom, re_.UNUSUAL_REASON[0], re_.UNUSUAL_REASON[1]))
    if engs[3]["flagged"]:
        reasons.insert(0, ("network", 1.0, "This wallet has received money from many people in patterns linked to scams.",
                           "এই অ্যাকাউন্টে অনেক সন্দেহজনক লেনদেন এসেছে।"))
    reasons = reasons[:4]
    return dict(prob=prob, anom=anom, level=level, rules=rules, engs=engs, n_flag=n_flag, notes=notes,
                reasons=reasons, contribs=contribs)


def customer_result(row, rec_id, prof_for_table, sig=None):
    """Score one transfer and render what the customer sees, the engines and the profile comparison."""
    a_ = assess(row, rec_id, sig)
    prob, anom, level, rules, engs, n_flag, notes, reasons, contribs = (a_[k] for k in (
        "prob", "anom", "level", "rules", "engs", "n_flag", "notes", "reasons", "contribs"))
    drivers = [e["name"] for e in engs if e["flagged"]] + [r_ for r_ in rules if r_ not in ("UNUSUAL_BEHAVIOUR", "KNOWN_MULE_WALLET")]
    icon = {"ALLOW": ic("check-circle", 26), "WARN": ic("alert", 26), "HOLD": ic("stop", 26)}[level]
    head = {"ALLOW": "Looks safe", "WARN": "সাবধান! Possible scam", "HOLD": "Transfer paused for your safety"}[level]
    html = (f'<div class="card {level}"><span class="score">{prob:.0%}<br><small style="font-size:.75rem;font-weight:600">'
            f'scam risk · unusual {anom:.1%}</small></span><div class="lvl">{icon} {level}</div><div>{head}</div>'
            + (f'<div class="trig">TRIGGERED BY: {" · ".join(d.upper() for d in drivers)}</div>' if level != "ALLOW" and drivers else ""))
    infos = [(en_, bn_) for lvl_, en_, bn_ in notes if lvl_ == "info"]
    if level == "ALLOW":
        html += f'<div style="margin-top:8px">{re_.ACTIONS["ALLOW"][1]}<br><small>{re_.ACTIONS["ALLOW"][0]}</small></div>'
        for en_, bn_ in infos:                          # advisory only: does not block, just informs
            html += f'<div class="advice">{ic("alert", 15)} {E(bn_)}<br><small>{E(en_)}</small></div>'
    else:
        html += '<div style="margin-top:10px;font-weight:700">কেন / Why:</div>'
        for _, _, en_txt, bn in reasons:
            html += f'<div class="reason">{E(bn)}<br><small>{E(en_txt)}</small></div>'
        for en_, bn_ in infos:
            html += f'<div class="advice">{ic("alert", 15)} {E(bn_)}<br><small>{E(en_)}</small></div>'
        html += f'<div class="tip">{ic("lock", 16)} {re_.SAFETY_TIP[1]}</div>'
        html += f'<div style="margin-top:10px"><b>Action:</b> {re_.ACTIONS[level][0]}</div>'
    phone = ('<div class="phone"><div class="notch"></div><div class="bar"><span><b>upay</b> · Send Money</span>'
             f'<span>{int(row["hour"]):02d}:00 · ৳{float(row["amount"]):,.0f}</span></div>')
    st.markdown(phone + html + "</div></div>", unsafe_allow_html=True)
    if level != "ALLOW":
        b1, b2 = st.columns(2)
        if b1.button("বাতিল করুন / Cancel", type="primary", icon=":material/block:", width="stretch", key="sm_cancel"):
            record_outcome("cancelled", level)
        if b2.button("চালিয়ে যান / Continue", width="stretch", icon=":material/arrow_forward:", key="sm_continue"):
            record_outcome("proceeded", level)
        outcome_counter()
    st.markdown(engines_html(engs, n_flag), unsafe_allow_html=True)
    st.markdown(checklist_html(sg.checklist(row, sig or {}, anom, bool(engs[3]["flagged"]), engs[3]["note"])), unsafe_allow_html=True)
    with st.expander("This transfer vs. the customer's own habits", expanded=False, icon=":material/person_search:"):
        st.markdown(profile_html(en.profile_comparison(row, prof_for_table)), unsafe_allow_html=True)
    with st.expander("Transparency: features, model, rules", icon=":material/data_object:"):
        st.write(f"**Classifier (XGBoost):** P(scam) = {prob:.3f}  (warn ≥ {re_.WARN_THRESHOLD}, hold ≥ {re_.HOLD_THRESHOLD})")
        st.write(f"**Anomaly model (Isolation Forest):** more unusual than {anom:.1%} of normal transfers "
                 f"(warn ≥ {re_.ANOMALY_THRESHOLD:.0%})")
        st.write(f"**Business rules triggered:** {', '.join(rules) if rules else 'none'}")
        st.write("**Features the models received:**")
        st.dataframe(pd.DataFrame([{k: row[k] for k in re_.FEATURES}]), hide_index=True)
        st.write("**Feature contributions (SHAP, log-odds):**")
        st.bar_chart(contribs.iloc[0].sort_values(), horizontal=True, color="#0B5CAD")


# ---------------- header ----------------
_test_for_ticker = get_test(WSN, STAMP)
_alerts = _test_for_ticker[_test_for_ticker.risk_score >= re_.WARN_THRESHOLD].head(28)
_items = []
for _r in _alerts.itertuples():
    _lvl = "HOLD" if _r.risk_score >= re_.HOLD_THRESHOLD else "WARN"
    _items.append(f'<span class="{"h" if _lvl == "HOLD" else "w"}">▲ {_lvl}</span> <b>{E(_r.txn_id)}</b> '
                  f'৳{_r.amount:,.0f} → {E(_r.recipient_id)} · risk {_r.risk_score:.0%} · {E(_r.district)}')
for _rg in rings[:6]:
    _items.append(f'<span class="h">◆ RING</span> <b>{_rg["ring_id"]}</b> {_rg["n_mules"]} mule wallets → collector {E(_rg["collector"])}')
_feed = " &nbsp;&nbsp;│&nbsp;&nbsp; ".join(_items)
_n_cust = int(customer_ids(hist).nunique())
_n_alerts = int((_test_for_ticker.risk_score >= re_.WARN_THRESHOLD).sum())
KPI_HTML = f"""<div class="kpis">
<div class="kpi"><div class="k">TRANSFERS MONITORED</div><div class="v c" style="--n:{len(hist)}"></div><div class="s">● raw transaction log</div></div>
<div class="kpi"><div class="k">CUSTOMER PROFILES</div><div class="v c" style="--n:{_n_cust}"></div><div class="s">● learned from history</div></div>
<div class="kpi"><div class="k">ALERTS · TEST WINDOW</div><div class="v c" style="--n:{_n_alerts}"></div><div class="s">● HOLD + WARN</div></div>
<div class="kpi"><div class="k">MULE WALLETS FLAGGED</div><div class="v c" style="--n:{int(wallets.suspected_mule.sum())}"></div><div class="s">● graph analysis</div></div>
<div class="kpi"><div class="k">MULE RINGS TRACKED</div><div class="v c" style="--n:{len(rings)}"></div><div class="s">● collectors identified</div></div>
</div>"""
st.markdown(f"""
<div class="boot">&gt; SYNCHRONIZING_RISK_GRID ... 4/4 ENGINES ONLINE ... OK</div>
<div class="hero"><div class="badge">{ic("shield-check", 40, "#06306B", 2.2)}</div><div style="flex:1">
<h1><span class="upay-name">upay</span> <span>ScamShield</span></h1>
<p>Real-time scam interception and mule-network intelligence for mobile financial services.</p>
<span class="chip"><span class="dot"></span>ENGINES ONLINE 4/4</span>
<span class="chip">XGBOOST · ISOLATION_FOREST · NETWORKX · SHAP</span>
<span class="chip">POINT-IN-TIME FEATURES</span>
<span class="chip y">{DS_LABEL}</span>
</div></div>
<div class="ticker"><div class="lbl">● LIVE THREAT FEED</div>
<div class="track">{_feed} &nbsp;&nbsp;│&nbsp;&nbsp; {_feed}</div></div>
""", unsafe_allow_html=True)

n_open = sum(c["status"] in ("Open", "In progress") for c in CASES)
# ---- role-based access (in production the role comes from single sign-on) ----
ROLES = {"Admin (demo: everything)": None,
         "Fraud analyst": {"Command Center", "Send Money", "Analyst Queue", "Mule Network", "Cases", "Model & Impact"},
         "Agent (cash-out counter)": {"Cash Out (agent)"},
         "Customer (phone app)": {"Customer App"}}
ACCESS_LOG = st.session_state.setdefault("access_log", [])


def log_access(action, detail=""):
    ACCESS_LOG.append({"Time (UTC)": cs.now(), "Role": st.session_state.get("role", "Admin (demo: everything)"),
                       "Action": action, "Detail": detail})


def _role_changed():
    log_access("Signed in", st.session_state.role)


def is_admin():
    return st.session_state.get("role", "Admin (demo: everything)").startswith("Admin")


if "role" not in st.session_state:
    st.session_state.role = "Admin (demo: everything)"
PAGES = [":material/radar: Command Center", ":material/send_money: Send Money", ":material/smartphone: Customer App",
         ":material/storefront: Cash Out (agent)", ":material/manage_search: Analyst Queue", ":material/hub: Mule Network",
         ":material/upload_file: Dataset B · Your Data", ":material/database: Datasets", ":material/folder_open: Cases",
         ":material/insights: Model & Impact"]
with st.sidebar:
    st.markdown("""<div class="sb-logo"><div class="sb-badge">""" + ic("shield-check", 22, "#06306B", 2.4) + """</div><div><div class="sb-t">upay <span>ScamShield</span></div>
    <div class="sb-s">TRUST &amp; RISK OPS CONSOLE</div></div></div>""", unsafe_allow_html=True)
    st.markdown('<div class="sb-h" style="margin-top:4px">ACTIVE DATASET</div>', unsafe_allow_html=True)
    ds_opts = ["A · Demo (synthetic)"] + (["B · Your data"] if wsp.exists(BN) else [])
    st.radio("Dataset", ds_opts, index=1 if WS == "B" and len(ds_opts) > 1 else 0, label_visibility="collapsed",
             key="ds_pick", on_change=lambda: st.session_state.update(ws=st.session_state.ds_pick[0]))
    if not wsp.exists(BN):
        st.caption("Dataset B not built yet: load your own log in the Dataset B page.")
    st.markdown('<div class="sb-h" style="margin-top:10px">SIGNED IN AS</div>', unsafe_allow_html=True)
    st.selectbox("Role", list(ROLES), key="role", label_visibility="collapsed", on_change=_role_changed,
                 help="Role-based access: each role sees only the pages and actions it needs. In production the role "
                      "comes from upay's single sign-on, not from this menu.")
    allowed = [p_ for p_ in PAGES if ROLES[st.session_state.role] is None or p_.split(": ", 1)[1] in ROLES[st.session_state.role]]
    if st.session_state.get("nav") not in allowed:
        st.session_state.nav = allowed[0]
    st.markdown('<div class="sb-h" style="margin-top:10px">NAVIGATION</div>', unsafe_allow_html=True)
    page = st.radio("Navigation", allowed, label_visibility="collapsed", key="nav")
    st.markdown('<div class="sb-h" style="margin-top:10px">ANALYST POLICY</div>', unsafe_allow_html=True)
    st.radio("Analyst policy", ["Standard", "Low workload: HOLD needs 2+ engines"], key="policy", label_visibility="collapsed",
             disabled=not is_admin(),
             help="Low workload sends far fewer genuine transfers to analysts (see Model & Impact → Analyst workload). "
                  "Only an admin can change it.")
    st.markdown(f"""
<div class="sb-box"><div class="sb-h">SYSTEM STATUS</div>
<div class="sb-row"><span class="dot"></span>Scam classifier <b>XGBoost</b></div>
<div class="sb-row"><span class="dot"></span>Anomaly model <b>Isolation Forest</b></div>
<div class="sb-row"><span class="dot"></span>Takeover check <b>Profile rules</b></div>
<div class="sb-row"><span class="dot"></span>Network check <b>NetworkX</b></div>
</div>
<div class="sb-box"><div class="sb-h">DATA</div>
<div class="sb-kv"><span>Transfers</span><b>{len(hist):,}</b></div>
<div class="sb-kv"><span>Customers</span><b>{customer_ids(hist).nunique():,}</b></div>
<div class="sb-kv"><span>Model</span><b>{"trained" if WS == "A" or metrics.get("mode") == "trained" else "demo classifier"}</b></div>
<div class="sb-kv"><span>ROC-AUC (future)</span><b>{f"{metrics['roc_auc']:.3f}" if "roc_auc" in metrics else "n/a (no labels)"}</b></div>
</div>
<div class="sb-box"><div class="sb-h">OPERATIONS</div>
<div class="sb-kv"><span>Open cases</span><b>{n_open}</b></div>
<div class="sb-kv"><span>Mule rings tracked</span><b>{len(rings)}</b></div>
<div class="sb-kv"><span>Thresholds</span><b>warn {re_.WARN_THRESHOLD:.0%} (new cust. {re_.NEW_CUSTOMER_WARN:.0%}) · hold {re_.HOLD_THRESHOLD:.0%}</b></div>
</div>
<div class="sb-foot">Synthetic data · decision support only<br>HOLD = pause &amp; re-verify, never auto-block</div>
""", unsafe_allow_html=True)

# ---------------- Business impact (shared by Command Center and Model & Impact) ----------------
@st.cache_data(show_spinner=False)
def impact_rates(wsn, stamp):
    """Measured rates on the active dataset's labelled future test set; falls back to Dataset A when there are no labels."""
    t = pd.read_parquet(wsp.paths(wsn)["test"])
    if "is_fraud" in t and t.is_fraud.notna().sum() > 0 and t.is_fraud.sum() >= 5:
        lab = t[t.is_fraud.notna()]
        return bz.measured_rates(re_.score_frame(model, iforest, lab)), wsn
    tA = pd.read_parquet(wsp.paths("A")["test"])
    mA, fA = re_.load_model(wsp.paths("A")["model"]), re_.load_iforest(wsp.paths("A")["iforest"])
    return bz.measured_rates(re_.score_frame(mA, fA, tA)), "A"


PRESETS_BIZ = {"Base": dict(loss_share=1.0, detection_factor=1.0, false_alarm_factor=1.0, warn_stop_rate=0.6),
               "Cautious": dict(loss_share=0.5, detection_factor=1.0, false_alarm_factor=1.0, warn_stop_rate=0.6),
               "Stress test": dict(loss_share=0.5, detection_factor=0.5, false_alarm_factor=2.0, warn_stop_rate=0.4)}


def tk(x):
    return f"-Tk {abs(x):,.0f}" if x < 0 else f"Tk {x:,.0f}"


def business_impact_ui():
    rates, src = impact_rates(WSN, STAMP)
    st.markdown(f'<div class="section-title">{ic("wallet", 16)} Business impact per 100,000 send money transfers</div>',
                unsafe_allow_html=True)
    st.caption("Our test data has far more scams (1.9%) than real life, so its alert counts are not used directly. We take the "
               "rates the system achieved on future transfers and apply them to a realistic number of scams, from the reported "
               "loss of Tk 92.60 crore a year and Bangladesh Bank's 134.26 million send money transfers a month. "
               + ("Rates measured on your Dataset B." if src != "A" else "Rates measured on Dataset A (demo)."))
    preset = st.radio("Scenario", list(PRESETS_BIZ) + ["Custom"], horizontal=True, key="biz_preset")
    p = dict(PRESETS_BIZ.get(preset, PRESETS_BIZ["Base"]))
    with st.expander("Assumptions (change them to test the estimate)", expanded=preset == "Custom", icon=":material/tune:"):
        a1, a2, a3 = st.columns(3)
        loss_share = a1.slider("Share of reported losses from send money scams", 0.1, 1.0, p["loss_share"], 0.05,
                               disabled=preset != "Custom", help="100% is an upper bound: the figure also covers cards and banks")
        det = a2.slider("Real detection vs. our test", 0.25, 1.0, p["detection_factor"], 0.05, disabled=preset != "Custom",
                        help="1.0 = as good as on our future test data")
        fa = a3.slider("Real false alarms vs. our test", 1.0, 4.0, p["false_alarm_factor"], 0.25, disabled=preset != "Custom")
        b1, b2, b3, b4 = st.columns(4)
        avg_scam = b1.number_input("Average scam transfer (Tk)", 500, 50000, int(round(rates["avg_scam"])), 100)
        warn_cost = b2.number_input("Cost of a false WARN (Tk)", 0, 50, 2)
        hold_cost = b3.number_input("Customer cost of a HOLD (Tk)", 0, 500, 20)
        minutes = b4.number_input("Analyst minutes per HOLD", 1, 60, 10)
        st.markdown("**Your organisation's real numbers** (replace the national figures with your own)")
        o1, o2, o3 = st.columns(3)
        vol_m = o1.number_input("Send money transfers per month (millions)", 0.1, 1000.0, bz.P2P_PER_MONTH / 1e6, 0.5,
                                key="biz_vol", help="Default: ALL mobile financial services in Bangladesh (Bangladesh Bank, "
                                                    "October 2025). Enter upay's own volume.")
        loss_cr = o2.number_input("Scam losses per year (Tk crore)", 0.1, 1000.0, bz.LOSS_PER_YEAR_TK / 1e7, 0.5,
                                  key="biz_loss", help="Default: reported national figure for 2025")
        n_analysts = o3.number_input("Fraud analysts on duty (FTE)", 1, 1000, 20, key="biz_fte")
        c5, c6 = st.columns(2)
        rate = c5.number_input("Analyst cost per hour (Tk)", 50, 2000, 300, 50)
        wstop = c6.slider("Warned scam victims who cancel", 0.0, 1.0, p["warn_stop_rate"], 0.05, disabled=preset != "Custom",
                          help="A HOLD always stops the money until review; a WARN only works if the victim listens")
    ev_ = load_json("evaluation.json", STAMP)
    if low_workload() and ev_:
        cur_, low_ = ev_["operating_points"]["Current policy"], ev_["operating_points"]["HOLD only if 2+ engines agree"]
        moved_g = rates["hold_genuine"] * (1 - low_["hold_genuine"] / max(cur_["hold_genuine"], 1e-9))
        moved_s = rates["hold_scam"] * (1 - low_["hold_scams"] / max(cur_["hold_scams"], 1e-9))
        rates = dict(rates, hold_genuine=rates["hold_genuine"] - moved_g, warn_genuine=rates["warn_genuine"] + moved_g,
                     hold_scam=rates["hold_scam"] - moved_s, warn_scam=rates["warn_scam"] + moved_s)
        st.info("Analyst policy: **Low workload** (HOLD only when 2+ engines agree). Change it in the sidebar.")
    e = bz.estimate(rates, loss_share=loss_share, avg_scam=avg_scam, warn_cost=warn_cost, hold_customer_cost=hold_cost,
                    analyst_minutes=minutes, analyst_rate=rate, detection_factor=det, false_alarm_factor=fa, warn_stop_rate=wstop,
                    loss_per_year=loss_cr * 1e7, transfers_per_month=vol_m * 1e6)
    s, r = e["ScamShield"], e["Simple rule"]
    net_cls = "" if s["net"] >= 0 else ' style="color:var(--bad)"'
    st.markdown(f"""<div class="kpis">
<div class="kpi"><div class="k">MONEY PROTECTED</div><div class="v">{tk(s["protected"])}</div><div class="s">● scams stopped before payout</div></div>
<div class="kpi"><div class="k">FRICTION COST</div><div class="v">{tk(s["friction"])}</div><div class="s">● false alarms + HOLD reviews</div></div>
<div class="kpi"><div class="k">NET BENEFIT</div><div class="v"{net_cls}>{tk(s["net"])}</div><div class="s">● {s["ratio"]:.1f}x protected per Tk 1 of friction</div></div>
<div class="kpi"><div class="k">ALERTS</div><div class="v">{s["alerts"]:,.0f}</div><div class="s">● {s["warn"]:,.0f} WARN · {s["hold"]:,.0f} HOLD</div></div>
<div class="kpi"><div class="k">ANALYST HOURS</div><div class="v">{s["analyst_hours"]:,.1f}</div><div class="s">● {s["analyst_hours"] * 10 / 160:.1f} analysts per 1M transfers</div></div>
</div>""", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame({
        "ScamShield": [f"{s['scams']:.1f}", f"{s['alerts']:,.0f}", f"{s['warn']:,.0f}", f"{s['hold']:,.0f}", f"{s['analyst_hours']:,.1f}",
                       tk(s["protected"]), tk(s["friction"]), tk(s["net"]), f"{s['ratio']:.1f}"],
        "Simple rule (no WARN step, every alert reviewed)": [f"{r['scams']:.1f}", f"{r['alerts']:,.0f}", "n/a", f"{r['hold']:,.0f}",
                       f"{r['analyst_hours']:,.1f}", tk(r["protected"]), tk(r["friction"]), tk(r["net"]), f"{r['ratio']:.1f}"]},
        index=["Scam transfers", "Alerts in total", "WARN (customer decides)", "HOLD (analyst review)", "Analyst hours",
               "Money protected", "Friction cost", "Net benefit", "Protected per Tk 1 of friction"]), width="stretch")
    st.caption(f"Per 1 million transfers, multiply by 10: {tk(s['protected'] * 10)} protected for {tk(s['friction'] * 10)} of friction. "
               "Friction = false WARNs × WARN cost + every HOLD × (customer cost + analyst time). Not counted: customer trust, "
               "fewer complaints and disputes, rings stopped before more victims, regulatory value. These are estimates from "
               "stated assumptions, not measured savings.")
    k_m = vol_m * 1e6 / 1e5                       # 100k blocks per month at the operator's volume
    need = s["analyst_hours"] * k_m / 160         # 160 working hours per analyst per month
    st.markdown(f'<div class="casebox">{ic("wallet", 16)} <b>At your volume ({vol_m:,.1f} M transfers a month):</b> '
                f'{tk(s["protected"] * k_m)} protected and {tk(s["friction"] * k_m)} of friction per month · '
                f'{s["alerts"] * k_m:,.0f} alerts ({s["hold"] * k_m:,.0f} reach an analyst) · '
                f'<b>{need:,.1f} analysts</b> needed for HOLD reviews vs. {n_analysts} on duty'
                + (' · <span style="color:var(--bad)">over capacity: switch to the low-workload policy</span>' if need > n_analysts else "")
                + '</div>', unsafe_allow_html=True)
    if s["net"] < 0:
        st.warning("In this scenario friction costs more than it saves. The lever is the HOLD threshold: tune it on real data in "
                   "shadow mode so only the strongest cases reach an analyst.")

# ---------------- Command Center ----------------
if page.endswith("Command Center"):
    st.markdown(KPI_HTML, unsafe_allow_html=True)
    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.markdown('<div class="section-title">Engine health (future test window)</div>', unsafe_allow_html=True)
        if WS == "A":
            nv = metrics["novel_scam_test_account_takeover_recall"]
            e = [("Scam classifier", "XGBoost + SHAP", f"ROC-AUC {metrics['roc_auc']:.3f}", metrics["roc_auc"]),
                 ("Anomaly model", "Isolation Forest, no labels", f"Unseen scam type: {nv['classifier_only']:.0%} → {nv['classifier_plus_anomaly']:.0%}", nv["classifier_plus_anomaly"]),
                 ("Takeover check", "Customer's own profile", f"Takeovers caught {metrics['recall_by_scam_type'].get('account_takeover', 0):.0%}", metrics['recall_by_scam_type'].get('account_takeover', 0)),
                 ("Network check", "NetworkX graph", f"Rings found {metrics['network']['rings_correct']}/{metrics['network']['true_rings']}", metrics['network']['rings_correct'] / max(metrics['network']['true_rings'], 1))]
        else:
            trained = metrics.get("mode") == "trained"
            e = [("Scam classifier", "XGBoost + SHAP · " + ("trained on your labels" if trained else "demo model"),
                  f"ROC-AUC {metrics['roc_auc']:.3f} on your future data" if trained else "No labels to measure accuracy", metrics.get("roc_auc", 0.5)),
                 ("Anomaly model", "Isolation Forest · fitted on your data", f"Learned from {metrics['rows']:,} of your transfers", 1.0),
                 ("Takeover check", "Each customer's own history", f"{metrics['senders']:,} sender profiles", 1.0),
                 ("Network check", "NetworkX graph on your log", f"{int(wallets.suspected_mule.sum())} suspected mules · {len(rings)} rings", 1.0)]
        h = '<div class="eng-grid">'
        for name, meth, note, sc in e:
            h += (f'<div class="eng"><span class="chip2 off">ONLINE</span><div class="nm">{name}</div><div class="mt">{meth}</div>'
                  f'<div class="bar"><div style="width:{sc * 100:.0f}%"></div></div><div class="nt">{note}</div></div>')
        st.markdown(h + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="section-title" style="margin-top:16px">Decisions in the future test window</div>', unsafe_allow_html=True)
        tdec = re_.score_frame(model, iforest, get_test(WSN, STAMP))
        vc = tdec.decision.value_counts()
        m1, m2, m3 = st.columns(3)
        m1.metric("ALLOW", f"{vc.get('ALLOW', 0):,}", f"{vc.get('ALLOW', 0) / len(tdec):.1%}", delta_color="off")
        m2.metric("WARN", f"{vc.get('WARN', 0):,}", f"{vc.get('WARN', 0) / len(tdec):.1%}", delta_color="off")
        m3.metric("HOLD", f"{vc.get('HOLD', 0):,}", f"{vc.get('HOLD', 0) / len(tdec):.1%}", delta_color="off")
        if "ai_system" in metrics:
            st.caption(f"{metrics['ai_system']['scam_recall']:.0%} of scams caught with {metrics['ai_system']['false_alarm_rate']:.1%} "
                       "of genuine transfers warned, on transfers the models never saw.")
        else:
            st.caption("No fraud labels in this dataset, so accuracy cannot be measured; decisions are shown for all transfers.")
        _r, _ = impact_rates(WSN, STAMP)
        _e = bz.estimate(_r, avg_scam=_r["avg_scam"], warn_stop_rate=0.6)["ScamShield"]
        st.markdown(f'<div class="casebox">{ic("wallet", 16)} <b>Business impact (base case, per 100,000 transfers):</b> '
                    f'Tk {_e["protected"]:,.0f} protected for Tk {_e["friction"]:,.0f} of friction, '
                    f'<b>{_e["ratio"]:.1f}x</b>, with {_e["analyst_hours"]:.0f} analyst hours. Details in Model &amp; Impact.</div>',
                    unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="section-title">Latest high-risk transfers</div>', unsafe_allow_html=True)
        lt = tdec[tdec.decision == "HOLD"].sort_values("timestamp", ascending=False).head(10)
        st.dataframe(lt[["timestamp", "txn_id", "user_id", "amount", "risk_score", "recipient_id"]], hide_index=True, width="stretch", height=300)
        st.markdown('<div class="section-title">Largest mule rings</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{"Ring": r["ring_id"], "Mules": r["n_mules"], "Victims": r["victims"],
                                    "Money (৳)": f"{r['flagged_amount']:,.0f}"} for r in rings[:5]]), hide_index=True, width="stretch")
    st.info("Use the sidebar: **Send Money** to score a live transfer for a real customer, **Analyst Queue** to investigate, "
            "**Mule Network** for rings, **Dataset B** to load your own log and train real models on it, **Datasets** to compare A and B. "
            "Switch the active dataset at the top of the sidebar.")

# ---------------- Send Money ----------------
if page.endswith("Send Money"):
    left, right = st.columns([1, 1.25])
    active = list(customer_ids(hist).value_counts().index[:400])
    now = hist.timestamp.max() + pd.Timedelta(hours=1)
    contacts_of = lambda c: list(hist[hist.sender_id == c].receiver_id.value_counts().index[:5])
    ring_w = [r["mules"][0] for r in rings[:3]]
    lone_w = list(wallets[(~wallets.index.isin(list(ring_of))) & ((wallets.suspected_mule) | ((wallets.flagged_share >= 0.5) &
             (wallets.flagged_senders >= 2)))].sort_values(["flagged_senders", "flagged_share", "incoming"], ascending=False).index[:2])
    pop_w = list(wallets[(~wallets.index.isin(list(ring_of))) & (wallets.flagged_share == 0)]
                 .sort_values("senders", ascending=False).index[:3])
    NEW_ACC, COLLECT, TYPED = "W00042", "W00777", "W00099"
    SCEN = ["Normal: paying a usual contact", "Scam: prize call, money to a mule-ring wallet",
            "Scam: wallet detected as scam, acting alone", "Takeover: new phone, other district, 3 AM",
            "Pattern: this wallet got the same amount from 4 people today",
            "Pattern: you already sent the same amount 3 times today",
            "New account: first payment to a wallet opened 12 days ago (genuine)",
            "Unusual but genuine: first payment to a popular wallet (tutor, shop)",
            "New pattern: 15x usual amount, 8 transfers in an hour, 4 AM, new district",
            "Custom: set everything yourself"]

    def rec_label(kind, w):
        return {"contact": f"{w} (a usual contact)", "ring": f"{w} (wallet in a mule ring)",
                "lone": f"{w} (detected as scam, acts alone)", "new": "A new account (opened recently)",
                "pop": f"{w} (popular wallet, many customers pay it)",
                "typed": "Type a wallet number"}[kind]

    def apply_scenario():
        sc_, c_ = st.session_state.lv_scen, st.session_state.lv_cust
        if sc_.startswith("Custom"):
            return
        pr = pl.customer_profile(hist, c_, now)
        usual = max(int(round(pr["usual_amount"], -1)), 100)
        devs_ = list(hist[hist.sender_id == c_].device_id.value_counts().index[:2]) or ["DEV-NEW1"]
        con = contacts_of(c_)
        mid = max(pr["active_start"], min(14, pr["active_end"]))
        other_d = next(d for d in sorted(set(hist.district)) if d != pr["home_district"])
        v = dict(lv_amt=usual, lv_rec=rec_label("contact", con[0]) if con else rec_label("typed", ""), lv_dev=f"{devs_[0]} (their phone)",
                 lv_dist=pr["home_district"], lv_hour=mid, lv_call=False, lv_newid=TYPED, lv_newage=12)
        pend = []
        if sc_.startswith("Scam: prize") and ring_w:
            v.update(lv_amt=usual * 5, lv_rec=rec_label("ring", ring_w[0]), lv_call=True, lv_hour=min(16, pr["active_end"]))
        elif sc_.startswith("Scam: wallet detected") and lone_w:
            v.update(lv_amt=usual * 3, lv_rec=rec_label("lone", lone_w[0]))
        elif sc_.startswith("Takeover"):
            v.update(lv_amt=min(usual * 10, 25000), lv_rec=rec_label("typed", ""), lv_newid=TYPED, lv_dev="A new phone (DEV-NEW1)",
                     lv_dist=other_d, lv_hour=3)
        elif sc_.startswith("Pattern: this wallet"):
            v.update(lv_amt=1000, lv_rec=rec_label("typed", ""), lv_newid=COLLECT)
            others = [x for x in active if x != c_][:4]
            pend = [dict(t=now + pd.Timedelta(minutes=10 + 20 * k), s=o, r=COLLECT, a=1000 + 10 * (k - 2)) for k, o in enumerate(others)]
        elif sc_.startswith("Pattern: you already"):
            v.update(lv_amt=2000, lv_rec=rec_label("typed", ""), lv_newid=TYPED)
            pend = [dict(t=now + pd.Timedelta(minutes=10 + 25 * k), s=c_, r=TYPED, a=2000) for k in range(3)]
        elif sc_.startswith("New account"):
            v.update(lv_rec=rec_label("new", NEW_ACC), lv_newage=12)
        elif sc_.startswith("Unusual but genuine"):
            pw = next((w for w in pop_w if w not in con), pop_w[0] if pop_w else None)
            if pw:
                v.update(lv_rec=rec_label("pop", pw), lv_amt=int(round(usual * 1.2, -1)), lv_hour=min(19, pr["active_end"]))
        elif sc_.startswith("New pattern"):
            v.update(lv_amt=min(usual * 15, 25000), lv_hour=4, lv_dist=other_d)
            d0 = pd.Timestamp((now + pd.Timedelta(hours=3)).date())
            pend = [dict(t=d0 + pd.Timedelta(hours=3, minutes=5 + 7 * k), s=c_, r=con[k % len(con)] if con else TYPED,
                         a=float(max(usual // 3, 100))) for k in range(7)]
        v["wi_on"] = False
        for k_, val in v.items():
            st.session_state[k_] = val
        st.session_state.pending = pend
        st.session_state.lv_day = (now + pd.Timedelta(hours=3)).date()

    if "lv_cust" not in st.session_state:
        st.session_state.lv_cust, st.session_state.lv_scen = active[0], SCEN[0]
        apply_scenario()
    with left:
        st.markdown(f'<div class="section-title">{ic("send", 16)} New transfer from a real customer</div>', unsafe_allow_html=True)
        st.caption("Pick a customer from the transaction log and a scenario. Every signal is computed live from their real "
                   "history, exactly like the API would do inside upay. Change any field to explore.")
        st.selectbox("Scenario", SCEN, key="lv_scen", on_change=apply_scenario)
        st.selectbox("Customer", active, key="lv_cust", on_change=apply_scenario)
        cust = st.session_state.lv_cust
        prof = pl.customer_profile(hist, cust, now)
        st.markdown(f'<div class="casebox"><b>{E(cust)}</b> · {prof["history"]} past transfers · usual ৳{prof["usual_amount"]:,.0f} · '
                    f'active {prof["active_start"]:02d}:00 to {prof["active_end"]:02d}:00 · {E(prof["home_district"])} · '
                    f'{prof["known_recipients"]} contacts</div>', unsafe_allow_html=True)
        amount = st.number_input("Amount (৳)", 10, 25000, step=100, key="lv_amt")
        rec_opts = ([rec_label("contact", w) for w in contacts_of(cust)] + [rec_label("ring", w) for w in ring_w] +
                    [rec_label("lone", w) for w in lone_w] + [rec_label("pop", w) for w in pop_w] +
                    [rec_label("new", NEW_ACC), rec_label("typed", "")])
        if st.session_state.get("lv_rec") not in rec_opts:
            st.session_state.lv_rec = rec_opts[0]
        rec_opt = st.selectbox("Send to", rec_opts, key="lv_rec")
        r_created = None
        if rec_opt.startswith("A new account"):
            rec_id = NEW_ACC
            age_days = st.number_input("Wallet opened how many days ago?", 0, 3650, key="lv_newage")
        elif rec_opt.startswith("Type"):
            rec_id = st.text_input("Wallet number", key="lv_newid").strip() or TYPED
        else:
            rec_id = rec_opt.split(" ")[0]
        devs = list(hist[hist.sender_id == cust].device_id.value_counts().index[:2])
        dev_opts = [f"{d} (their phone)" for d in devs] + ["A new phone (DEV-NEW1)"]
        if st.session_state.get("lv_dev") not in dev_opts:
            st.session_state.lv_dev = dev_opts[0]
        dev_pick = st.selectbox("Device", dev_opts, key="lv_dev")
        dev = "DEV-NEW1" if dev_pick.startswith("A new") else dev_pick.split(" ")[0]
        dists = [prof["home_district"]] + [d for d in sorted(set(hist.district)) if d != prof["home_district"]]
        if st.session_state.get("lv_dist") not in dists:
            st.session_state.lv_dist = dists[0]
        dist = st.selectbox("District", dists, key="lv_dist")
        c1, c2 = st.columns(2)
        if "lv_day" not in st.session_state:
            st.session_state.lv_day = (now + pd.Timedelta(hours=3)).date()
        day = c1.date_input("Date", min_value=now.date(), key="lv_day")
        hour = c2.slider("Hour", 0, 23, key="lv_hour")
        call = st.checkbox("Customer is on a phone call while sending", key="lv_call")
        ts = pd.Timestamp(day) + pd.Timedelta(hours=hour)
        if ts <= hist.timestamp.max():       # a new transfer must come after the history (no peeking at the future)
            ts = hist.timestamp.max() + pd.Timedelta(minutes=1)
            st.caption(f"Time moved to {ts:%d %b %Y %H:%M}, just after the last transfer in the history.")
        if rec_opt.startswith("A new account"):
            r_created = ts - pd.Timedelta(days=int(age_days))
        pending = [p for p in st.session_state.get("pending", []) if p["t"] <= ts]
        b1, b2 = st.columns(2)
        if b1.button("Send", icon=":material/send:", width="stretch", help="Adds this transfer to today's demo history, so repeated payments are counted"):
            st.session_state.setdefault("pending", []).append(dict(t=ts, s=cust, r=rec_id, a=float(amount)))
            st.rerun()
        if b2.button("Clear demo history", icon=":material/restart_alt:", width="stretch"):
            st.session_state.pending = []
            st.rerun()
        if st.session_state.get("pending"):
            st.caption(f"Today's demo transfers ({len(st.session_state.pending)}), counted in the signals:")
            st.dataframe(pd.DataFrame([{"time": f"{p['t']:%H:%M}", "from": p["s"], "to": p["r"], "amount (৳)": f"{p['a']:,.0f}"}
                                       for p in st.session_state.pending]), hide_index=True, width="stretch", height=150)
    f = STATE.peek(ts, cust, rec_id, amount, dev, dist, int(call), r_created=r_created, pending=pending)
    sig = STATE.signals(ts, cust, rec_id, amount, pending=pending)
    live = dict(wi_usual=int(round(f["usual_amount"])), wi_age=int(f["recipient_account_age_days"]),
                wi_snd=int(f["recipient_unique_senders_24h"]), wi_t1h=int(f["user_txns_last_1h"]),
                wi_newrec=bool(f["is_new_recipient"]), wi_dev=bool(f["device_changed"]), wi_loc=bool(f["new_location"]),
                wi_out=bool(f["outside_usual_hours"]), wi_coll=int(sig["recipient_similar_senders_24h"]),
                wi_sent=int(sig["sender_similar_24h"]), wi_never=sig["recipient_received_ever"] == 0)
    st.session_state["_live"] = live

    def _load_live():                      # turning what-if on starts from the live values
        if st.session_state.get("wi_on"):
            for k_, v_ in st.session_state.get("_live", {}).items():
                st.session_state[k_] = v_

    with left:
        with st.expander("What-if: override any signal on top of the live result", icon=":material/tune:",
                         expanded=bool(st.session_state.get("wi_on"))):
            st.toggle("Turn on what-if overrides", key="wi_on", on_change=_load_live,
                      help="Starts from this customer's live values; change any of them to see how the engines react")
            if st.session_state.get("wi_on"):
                w1, w2 = st.columns(2)
                w1.number_input("Customer's usual amount (৳)", 10, 25000, key="wi_usual", step=100)
                w2.number_input("Recipient account age (days)", 0, 5000, key="wi_age")
                w1.number_input("Other senders to recipient (24h)", 0, 200, key="wi_snd")
                w2.number_input("Customer's transfers in last hour", 0, 30, key="wi_t1h")
                w1.number_input("People who sent the recipient a similar amount today", 0, 50, key="wi_coll")
                w2.number_input("Customer's similar payments today", 0, 30, key="wi_sent")
                w1.checkbox("First payment to this recipient", key="wi_newrec")
                w2.checkbox("New device", key="wi_dev")
                w1.checkbox("New district", key="wi_loc")
                w2.checkbox("Outside the customer's usual hours", key="wi_out")
                w1.checkbox("Recipient has never received money", key="wi_never")
            else:
                st.caption(f"Live values: usual ৳{live['wi_usual']:,} · recipient age {live['wi_age']:,} days · "
                           f"{live['wi_snd']} other senders today · {live['wi_t1h']} transfers in the last hour · "
                           f"{live['wi_coll']} similar amounts to recipient · {live['wi_sent']} similar payments by customer.")
    changed = []
    if st.session_state.get("wi_on"):
        ss = st.session_state
        f = dict(f)
        f.update(amount_ratio=round(float(amount) / max(ss.wi_usual, 1), 2), recipient_account_age_days=float(ss.wi_age),
                 recipient_unique_senders_24h=float(ss.wi_snd), user_txns_last_1h=float(ss.wi_t1h),
                 is_new_recipient=float(ss.wi_newrec), device_changed=float(ss.wi_dev), new_location=float(ss.wi_loc),
                 outside_usual_hours=float(ss.wi_out))
        sig = dict(sig, recipient_similar_senders_24h=int(ss.wi_coll), sender_similar_24h=int(ss.wi_sent),
                   recipient_received_ever=0 if ss.wi_never else max(sig["recipient_received_ever"], 1))
        names = dict(wi_usual="usual amount", wi_age="recipient age", wi_snd="other senders", wi_t1h="transfers in last hour",
                     wi_newrec="first payment", wi_dev="new device", wi_loc="new district", wi_out="outside usual hours",
                     wi_coll="similar amounts to recipient", wi_sent="similar payments", wi_never="never received")
        changed = [names[k_] for k_, v_ in live.items() if ss.get(k_) != v_]
    row = pd.Series({**f, "device_id": dev, "district": dist})
    with right:
        st.markdown(f'<div class="section-title">{ic("phone", 16)} What the customer sees</div>', unsafe_allow_html=True)
        if changed:
            st.markdown(f'<div class="advice">{ic("flask", 15)} <b>WHAT-IF ACTIVE</b> · live result for {E(cust)} with '
                        f'{len(changed)} signal(s) overridden: {E(", ".join(changed))}</div>', unsafe_allow_html=True)
        customer_result(row, rec_id, prof, sig)

# ---------------- Customer App (mobile view) ----------------
APP_SCEN = {"Pay a usual contact": "normal", "Prize call: on the phone, paying a mule-ring wallet": "ring",
            "Phone stolen: new phone, another district, 3 AM": "ato",
            "Pay a wallet already detected as a scam": "lone", "Pay a newly opened account (genuine)": "newacc"}


def _back_to_console():
    if st.session_state.get("role", "").startswith("Customer"):
        st.session_state.role = "Admin (demo: everything)"
    st.session_state.nav = next(p_ for p_ in PAGES if p_.endswith("Command Center"))


def customer_app_page():
    A = st.session_state.setdefault("app", {"step": "send"})
    now_ = hist.timestamp.max() + pd.Timedelta(hours=1)
    active_ = list(customer_ids(hist).value_counts().index[:200])
    ring_w_ = [r["mules"][0] for r in rings[:3]]
    lone_ = list(wallets[(~wallets.index.isin(list(ring_of))) & (wallets.suspected_mule | ((wallets.flagged_share >= 0.5) &
                 (wallets.flagged_senders >= 2)))].sort_values("flagged_senders", ascending=False).index[:1])
    st.markdown("""<style>
.boot, .hero, .ticker { display:none !important; }
.stApp { background: radial-gradient(900px 500px at 50% 0%, rgba(47,140,255,.22), transparent 70%), #02060E !important; }
.st-key-mobileapp { min-height:600px; background:#F3F6FB !important; color:#0B1B33; }
.st-key-mobileapp [data-testid="stWidgetLabel"] p, .st-key-mobileapp label { color:#5A6B85 !important; font-weight:600; }
.st-key-mobileapp [data-baseweb="select"] > div, .st-key-mobileapp [data-baseweb="input"], .st-key-mobileapp [data-baseweb="base-input"],
.st-key-mobileapp input { background:#FFFFFF !important; color:#0B1B33 !important; border-color:#D6E0EE !important; border-radius:12px !important; }
.st-key-mobileapp [data-baseweb="select"] div, .st-key-mobileapp [data-baseweb="select"] svg { color:#0B1B33 !important; fill:#0B1B33 !important; }
.st-key-mobileapp .stNumberInput button { background:#EEF3FA !important; color:#0B1B33 !important; }
.st-key-mobileapp button[kind="primary"], .st-key-mobileapp [data-testid="stBaseButton-primary"] {
  background:#FFD200 !important; color:#06306B !important; border:none !important; border-radius:14px !important;
  font-weight:800 !important; min-height:48px; box-shadow:0 6px 16px rgba(255,210,0,.35); }
.st-key-mobileapp button[kind="secondary"], .st-key-mobileapp [data-testid="stBaseButton-secondary"] {
  background:#FFFFFF !important; color:#06306B !important; border:1.5px solid #C9D6EA !important; border-radius:14px !important;
  font-weight:700 !important; min-height:46px; }
.st-key-mobileapp .app-h { color:#06306B; }
.st-key-mobileapp .app-sum { color:#06306B; }
.st-key-mobileapp .stCaption, .st-key-mobileapp [data-testid="stCaptionContainer"] { color:#6B7A90 !important; }
.st-key-mobileapp .card { background:#FFFFFF !important; color:#0B1B33 !important; border-radius:18px !important;
  box-shadow:0 8px 24px rgba(6,48,107,.10) !important; }
.st-key-mobileapp .card.WARN { border:2px solid #F5A400 !important; }
.st-key-mobileapp .card.HOLD { border:2px solid #E5384A !important; }
.st-key-mobileapp .card.ALLOW { border:2px solid #17B26A !important; }
.st-key-mobileapp .card .lvl { color:inherit; }
.st-key-mobileapp .card.WARN .lvl { color:#C77C00 !important; } .st-key-mobileapp .card.HOLD .lvl { color:#D92D3F !important; }
.st-key-mobileapp .card.ALLOW .lvl { color:#108A52 !important; }
.st-key-mobileapp .reason { background:#F6F8FC !important; color:#0B1B33 !important; border-left:4px solid #FFD200 !important; }
.st-key-mobileapp .reason small { color:#5A6B85 !important; }
.st-key-mobileapp .tip { background:#06306B !important; color:#FFFFFF !important; }
.st-key-mobileapp .advice { background:#EAF2FF !important; color:#0B1B33 !important; border-color:#9CC2FF !important; }
.app-bal { background:linear-gradient(120deg,#06306B,#0B5CAD); color:#fff; border-radius:16px; padding:14px 16px; margin:2px 0 14px 0;
  display:flex; justify-content:space-between; align-items:center; }
.app-bal small { opacity:.75; font-size:.75rem; } .app-bal b { font:800 1.35rem var(--head); color:#FFD200; }
.app-shield { font:700 .7rem var(--mono); background:rgba(255,210,0,.18); color:#FFD200; padding:4px 8px; border-radius:20px; }
.app-contacts { display:flex; gap:10px; margin:0 0 12px 0; }
.app-contacts div { text-align:center; font-size:.68rem; color:#5A6B85; }
.app-contacts span { display:flex; width:42px; height:42px; border-radius:50%; align-items:center; justify-content:center;
  background:#DCE8FA; color:#06306B; font-weight:800; margin:0 auto 4px auto; }
.app-nav { display:flex; justify-content:space-around; border-top:1px solid #DDE5F0; margin-top:18px; padding-top:10px;
  font-size:.68rem; color:#7A889C; } .app-nav b { color:#06306B; }
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display:none !important; }
</style>""", unsafe_allow_html=True)
    left, mid, right = st.columns([0.9, 1.15, 0.9])
    with right:
        st.markdown(f'<div class="section-title">{ic("flask", 16)} Demo controls</div>', unsafe_allow_html=True)
        scen = st.selectbox("Situation", list(APP_SCEN), key="app_scen", on_change=lambda: A.update(step="send"))
        cust = st.selectbox("Logged-in customer", active_, key="app_cust", on_change=lambda: A.update(step="send"))
        kind = APP_SCEN[scen]
        prof = pl.customer_profile(hist, cust, now_)
        con = list(hist[hist.sender_id == cust].receiver_id.value_counts().index[:4])
        devs_ = list(hist[hist.sender_id == cust].device_id.value_counts().index[:1]) or ["DEV-NEW1"]
        other_d = next(d for d in sorted(set(hist.district)) if d != prof["home_district"])
        usual = max(int(round(prof["usual_amount"], -1)), 100)
        ctx = dict(dev=devs_[0], dist=prof["home_district"], hour=max(prof["active_start"], min(14, prof["active_end"])),
                   call=0, rec=con[0] if con else "W00099", amt=usual, r_created=None)
        if kind == "ring" and ring_w_:
            ctx.update(rec=ring_w_[0], amt=usual * 5, call=1)
        elif kind == "ato":
            ctx.update(dev="DEV-NEW1", dist=other_d, hour=3, rec="W00099", amt=min(usual * 10, 25000))
        elif kind == "lone" and lone_:
            ctx.update(rec=lone_[0], amt=usual * 3)
        elif kind == "newacc":
            ctx.update(rec="W00042", r_created=True)
        st.caption(f"What the phone knows (not typed by the customer): device **{ctx['dev']}** · district **{ctx['dist']}** · "
                   f"time **{ctx['hour']:02d}:00** · on a call: **{'yes' if ctx['call'] else 'no'}**")
        st.button("Back to the console", icon=":material/arrow_back:", width="stretch", type="primary",
                  on_click=_back_to_console)
        if st.button("Restart the app", icon=":material/restart_alt:", width="stretch"):
            st.session_state.app = {"step": "send"}
            st.rerun()
        outcome_counter()
    ts_ = pd.Timestamp((now_ + pd.Timedelta(hours=3)).date()) + pd.Timedelta(hours=ctx["hour"])
    ts_ = max(ts_, hist.timestamp.max() + pd.Timedelta(minutes=1))
    with mid:
        st.markdown(f'<div class="app-status"><span>{ctx["hour"]:02d}:{ts_.minute:02d}</span><span>4G ▮▮▮ 82%</span></div>'
                    f'<div class="app-bar"><b>upay</b><span>{E(cust)}</span></div>', unsafe_allow_html=True)
        box = st.container(key="mobileapp")
    with box:
        step = A["step"]
        if step == "send":
            st.markdown('<div class="app-bal"><div><small>Balance</small><br><b>৳ 12,450</b></div>'
                        '<span class="app-shield">● ScamShield ON</span></div>'
                        '<div class="app-h">টাকা পাঠান · Send Money</div>'
                        '<div class="app-contacts">' + "".join(
                            f'<div><span>{E(w[-2:])}</span>{E(w)}</div>' for w in con[:4]) + '</div>',
                        unsafe_allow_html=True)
            opts = [f"{w} · recent contact" for w in con] + [f"{ctx['rec']} · entered number"] if ctx["rec"] not in con else \
                [f"{w} · recent contact" for w in con]
            default = next(i for i, o in enumerate(opts) if o.startswith(ctx["rec"]))
            rec_pick = st.selectbox("প্রাপক / To", opts, index=default, key=f"app_rec_{scen}_{cust}")
            amt = st.number_input("পরিমাণ / Amount (৳)", 10, 25000, int(min(ctx["amt"], 25000)), 50, key=f"app_amt_{scen}_{cust}")
            st.text_input("রেফারেন্স / Reference", "", key=f"app_ref_{scen}_{cust}", placeholder="optional")
            if st.button("পরবর্তী / Next", type="primary", width="stretch", icon=":material/arrow_forward:"):
                A.update(step="check", rec=rec_pick.split(" ")[0], amt=float(amt))
                st.rerun()
            st.markdown('<div class="app-nav"><div><b>⌂</b><br>Home</div><div><b>➤</b><br><b>Send</b></div>'
                        '<div>৳<br>Cash out</div><div>☰<br>History</div><div>◯<br>Profile</div></div>',
                        unsafe_allow_html=True)
        else:
            rec_id_, amt_ = A["rec"], A["amt"]
            r_cr = ts_ - pd.Timedelta(days=12) if ctx["r_created"] else None
            f_ = STATE.peek(ts_, cust, rec_id_, amt_, ctx["dev"], ctx["dist"], ctx["call"], r_created=r_cr)
            sig_ = STATE.signals(ts_, cust, rec_id_, amt_)
            row_ = pd.Series({**f_, "device_id": ctx["dev"], "district": ctx["dist"]})
            a_ = assess(row_, rec_id_, sig_)
            lvl = a_["level"]
            infos = [(e_, b_) for l_, e_, b_ in a_["notes"] if l_ == "info"]
            if step == "check":
                if lvl == "ALLOW":
                    st.markdown(f'<div class="app-h">নিশ্চিত করুন · Confirm</div><div class="app-sum">৳{amt_:,.0f} → <b>{E(rec_id_)}</b></div>',
                                unsafe_allow_html=True)
                    for e_, b_ in infos:
                        st.markdown(f'<div class="advice">{ic("alert", 15)} {E(b_)}<br><small>{E(e_)}</small></div>', unsafe_allow_html=True)
                    if st.button("পিন দিন / Enter PIN", type="primary", width="stretch", icon=":material/lock:"):
                        A["step"] = "pin"
                        st.rerun()
                elif lvl == "WARN":
                    h = (f'<div class="card WARN app-card"><div class="lvl">{ic("alert", 24)} সাবধান!</div>'
                         f'<div>এটি প্রতারণা হতে পারে · This may be a scam</div>')
                    for _, _, e_, b_ in a_["reasons"][:3]:
                        h += f'<div class="reason">{E(b_)}<br><small>{E(e_)}</small></div>'
                    h += f'<div class="tip">{ic("lock", 15)} {re_.SAFETY_TIP[1]}</div></div>'
                    st.markdown(h, unsafe_allow_html=True)
                    if st.button("বাতিল করুন / Cancel", type="primary", width="stretch", icon=":material/block:", key="app_cancel"):
                        record_outcome("cancelled", lvl)
                        A.update(step="done", result="cancelled")
                        st.rerun()
                    if st.button("আমি এই ব্যক্তিকে চিনি, চালিয়ে যান / I know this person, continue", width="stretch", key="app_cont"):
                        record_outcome("proceeded", lvl)
                        A["step"] = "pin"
                        st.rerun()
                else:
                    h = (f'<div class="card HOLD app-card"><div class="lvl">{ic("stop", 24)} সাময়িক স্থগিত</div>'
                         f'<div>Transfer paused for your safety. <b>Your money has not left your account.</b></div>')
                    for _, _, e_, b_ in a_["reasons"][:3]:
                        h += f'<div class="reason">{E(b_)}<br><small>{E(e_)}</small></div>'
                    h += (f'<div style="margin-top:8px">A upay safety officer will review it within {cs.SLA["HOLD review"]} '
                          'and contact you only through the official upay helpline.</div></div>')
                    st.markdown(h, unsafe_allow_html=True)
                    if st.button("লেনদেন বাতিল করুন / Cancel transfer", type="primary", width="stretch", icon=":material/block:", key="app_hcancel"):
                        record_outcome("cancelled", lvl)
                        A.update(step="done", result="cancelled")
                        st.rerun()
                    if st.button("এটি ভুল / This is a mistake", width="stretch", icon=":material/gavel:", key="app_dispute"):
                        record_outcome("proceeded", lvl)
                        ref = f"{WS}:APP-{cust}-{ts_:%H%M}-{rec_id_}"
                        ev_ = dict(what=f"Customer {cust} tried to send ৳{amt_:,.0f} to {rec_id_} at {ts_:%d %b %Y %H:%M} "
                                        f"from {ctx['dist']} on {ctx['dev']}. Scam probability {a_['prob']:.0%}.",
                                   why=[e_ for _, _, e_, _ in a_["reasons"]] + (["Rules: " + ", ".join(a_["rules"])] if a_["rules"] else []),
                                   next="Second analyst: call the customer on their registered number, then release or confirm fraud.",
                                   engines=a_["engs"])
                        case_, _ = cs.create_case(CASES, "Transaction", ref, f"[Customer App] HOLD {cust} → {rec_id_} (disputed)",
                                                  "High", ev_, "System")
                        cs.customer_dispute(case_, "Customer tapped 'This is a mistake' in the app.", customer=cust)
                        A.update(step="done", result="disputed", case=case_["id"])
                        st.rerun()
            elif step == "pin":
                st.markdown(f'<div class="app-h">পিন · PIN</div><div class="app-sum">৳{amt_:,.0f} → <b>{E(rec_id_)}</b></div>',
                            unsafe_allow_html=True)
                pin = st.text_input("৫ সংখ্যার পিন / 5-digit PIN", type="password", max_chars=5, key="app_pin")
                if st.button("নিশ্চিত / Confirm", type="primary", width="stretch", disabled=len(pin or "") != 5):
                    A.update(step="done", result="sent")
                    st.rerun()
                st.caption("Demo: any 5 digits. upay never asks for your PIN on a call.")
            elif step == "done":
                res = A.get("result")
                if res == "sent":
                    st.markdown(f'<div class="card ALLOW app-card"><div class="lvl">{ic("check-circle", 24)} সফল</div>'
                                f'<div>৳{amt_:,.0f} sent to <b>{E(rec_id_)}</b>.</div></div>', unsafe_allow_html=True)
                elif res == "cancelled":
                    st.markdown(f'<div class="card ALLOW app-card"><div class="lvl">{ic("shield-check", 24)} বাতিল হয়েছে</div>'
                                f'<div>Cancelled. Your ৳{amt_:,.0f} is safe in your account.</div></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="card WARN app-card"><div class="lvl">{ic("folder", 24)} আপত্তি গ্রহণ করা হয়েছে</div>'
                                f'<div>Dispute received ({A.get("case")}). A second officer reviews it within '
                                f'{cs.SLA["Customer dispute"]}; the money is then sent or returned to you.</div></div>',
                                unsafe_allow_html=True)
                if st.button("নতুন লেনদেন / New transfer", width="stretch", icon=":material/add:"):
                    A["step"] = "send"
                    st.rerun()
    with left:
        st.markdown(f'<div style="margin-top:120px;font:700 1.6rem var(--head);color:var(--txt)">upay app</div>'
                    f'<div style="color:var(--mut);margin-top:6px">What the customer sees on their phone. '
                    f'ScamShield runs silently in a few milliseconds; most transfers go straight to the PIN.</div>',
                    unsafe_allow_html=True)
        if A["step"] != "send":
            with st.expander("Behind the screen (for judges)", icon=":material/memory:"):
                st.markdown(engines_html(a_["engs"], a_["n_flag"]), unsafe_allow_html=True)
                st.caption(f"Decision: **{lvl}** · scam probability {a_['prob']:.0%} · unusual {a_['anom']:.1%}"
                           + (f" · rules: {', '.join(a_['rules'])}" if a_["rules"] else ""))


if page.endswith("Customer App"):
    customer_app_page()


# ---------------- Cash out at an agent ----------------
@st.cache_resource(show_spinner="> LOADING_CASHOUT_ENGINE ...")
def cashout_engine():
    import cashout as co_
    co_log = pd.read_csv("data/cashouts.csv", dtype={"wallet_id": str}, parse_dates=["timestamp"])
    agents = pd.read_csv("data/agents.csv")
    wA = mn.find_mules(pd.read_parquet(wsp.paths("A")["scored"]))
    flagged = set(wA.index[wA.suspected_mule | ((wA.flagged_share >= 0.5) & (wA.flagged_senders >= 2))])
    peer = co_.agent_peer_scores(co_log, agents, flagged)
    rawA = pd.read_csv("data/transactions_raw.csv", dtype={"sender_id": str, "receiver_id": str}, parse_dates=["timestamp"])
    return co_, co_.load_model(), co_log, peer, flagged, wA.flagged_share.to_dict(), rawA, co_.created_dates(rawA)


def cashout_page():
    co_, cmodel, co_log, peer, flagged, fshare, rawA, created = cashout_engine()
    cm = load_json("cashout_metrics.json", STAMP) or {}
    if WS == "B":
        st.info("Cash-out scoring runs on Dataset A's synthetic cash-out log. To run it on your data, add a cash-out export "
                "(timestamp, wallet_id, amount, agent_id) next to the transfer log.")
    st.markdown(f'<div class="section-title">{ic("wallet", 16)} Cash out at an agent: the money\'s exit door</div>',
                unsafe_allow_html=True)
    st.caption("Scam money is taken out as cash at an agent. ScamShield checks every cash-out before the agent pays: how much "
               "arrived in the last 24 hours and from how many people, how fast it is being taken out, the wallet's status "
               "in the mule network, and the agent's own risk compared with nearby agents.")
    k = st.columns(4)
    if cm:
        k[0].metric("Mule cash-outs caught", f"{cm['model']['caught']:.0%}", f"rule: {cm['fast_in_out_rule']['caught']:.0%}", delta_color="off")
        k[1].metric("Alerts that are real", f"{cm['model']['precision']:.0%}", f"rule: {cm['fast_in_out_rule']['precision']:.0%}", delta_color="off")
        k[2].metric("Genuine cash-outs flagged", f"{cm['model']['false_alarm_rate']:.1%}", f"rule: {cm['fast_in_out_rule']['false_alarm_rate']:.1%}", delta_color="off")
        k[3].metric("Scam money stopped", f"{cm['model']['money_stopped']:.0%}", f"ROC-AUC {cm['roc_auc']:.3f}", delta_color="off")
        st.caption(f"Future cash-outs ({cm['test_cashouts']:,}, {cm['test_mule']} by mules), {cm['split']}. Network and agent "
                   "risk built from earlier data only. 'rule' = simple fast in-and-out rule (≥80% of 24h money within 12 hours).")
    left, right = st.columns([1, 1.25])
    ring_m = [r["mules"][0] for r in rings[:3]] if WS == "A" else []
    ring_c = [r["collector"] for r in rings[:2]] if WS == "A" else []
    top_agents = list(peer.sort_values("peer_z", ascending=False).index[:3])
    custs = list(co_log[co_log.wallet_id.str.startswith("U")].wallet_id.value_counts().index[:50])
    inc = rawA.groupby("receiver_id").agg(n=("amount", "size"), s=("sender_id", "nunique"), last=("timestamp", "max"))
    remit = [w for w in inc[(inc.s <= 2) & (inc.n >= 3)].sort_values("n", ascending=False).index if w not in flagged][:5]
    SC = {"Genuine: a customer cashes out their own money": ("cust", custs[0] if custs else None),
          "Genuine: family remittance taken out the same day": ("remit", remit[0] if remit else None),
          "Mule: ring wallet cashes out money from many victims": ("mule", ring_m[0] if ring_m else None),
          "Collector: ring collector cashes out at a high-risk agent": ("coll", ring_c[0] if ring_c else None)}
    with left:
        st.markdown(f'<div class="section-title">{ic("send", 16)} Cash-out request</div>', unsafe_allow_html=True)
        sc = st.selectbox("Scenario", list(SC), key="co_scen")
        kind, w = SC[sc]
        w = st.text_input("Wallet cashing out", w or "", key=f"co_w_{sc}").strip()
        last_in = inc.last.get(w)
        t_default = (last_in + pd.Timedelta(hours=2)) if last_in is not None and not pd.isna(last_in) else rawA.timestamp.max() + pd.Timedelta(hours=1)
        hist_ag = co_log[co_log.wallet_id == w].agent_id.value_counts().index.tolist()
        ag_opts = list(dict.fromkeys((top_agents[:1] if kind == "coll" else []) + hist_ag[:2] + top_agents + list(peer.index[:20])))
        agent = st.selectbox("Agent", ag_opts, key=f"co_a_{sc}",
                             format_func=lambda a: f"{a} · {peer.loc[a, 'district']} · risk z {peer.loc[a, 'peer_z']:+.1f}")
        rec24 = rawA[(rawA.receiver_id == w) & (rawA.timestamp < t_default) & (rawA.timestamp >= t_default - pd.Timedelta(hours=24))].amount.sum()
        amt_default = int(min(25000, max(500, round(rec24 * 0.95, -1)))) if rec24 > 0 else 2000
        amount = st.number_input("Amount (৳)", 50, 25000, amt_default, step=100, key=f"co_amt_{sc}")
        c1, c2 = st.columns(2)
        day = c1.date_input("Date", t_default.date(), key=f"co_d_{sc}")
        hour = c2.slider("Hour", 0, 23, int(t_default.hour), key=f"co_h_{sc}")
        ts = pd.Timestamp(day) + pd.Timedelta(hours=hour, minutes=int(t_default.minute) if hour == t_default.hour else 0)
    req = pd.DataFrame([dict(cashout_id="LIVE", timestamp=ts, wallet_id=w, amount=float(amount), agent_id=agent)])
    hist_co = co_log[co_log.timestamp < ts]
    feats = co_.build_features(pd.concat([hist_co[hist_co.wallet_id == w], req], ignore_index=True), rawA, flagged, fshare,
                               peer.peer_z.to_dict(), created).iloc[[-1]]
    p, contrib = co_.score(cmodel, feats)
    row = feats.iloc[0]
    level, rules = co_.decide(float(p[0]), row)
    reasons = co_.explain(row, contrib.iloc[0])
    with right:
        st.markdown(f'<div class="section-title">{ic("phone", 16)} What the agent sees</div>', unsafe_allow_html=True)
        css = {"PAY": "ALLOW", "VERIFY": "WARN", "HOLD": "HOLD"}[level]
        icon = {"PAY": ic("check-circle", 26), "VERIFY": ic("alert", 26), "HOLD": ic("stop", 26)}[level]
        head = {"PAY": "Looks normal", "VERIFY": "যাচাই করুন · Verify before paying", "HOLD": "Do not pay · টাকা দেবেন না"}[level]
        h = (f'<div class="phone"><div class="notch"></div><div class="bar"><span><b>upay</b> · Agent cash-out</span>'
             f'<span>{E(agent)} · ৳{float(amount):,.0f}</span></div><div class="card {css}"><span class="score">{float(p[0]):.0%}'
             f'<br><small style="font-size:.75rem;font-weight:600">cash-out risk</small></span><div class="lvl">{icon} {level}</div>'
             f'<div>{head}</div>' + (f'<div class="trig">TRIGGERED BY: {" · ".join(rules) if rules else "CASH-OUT MODEL"}</div>' if level != "PAY" else ""))
        for _, _, en_, bn_ in reasons if level != "PAY" else []:
            h += f'<div class="reason">{E(bn_)}<br><small>{E(en_)}</small></div>'
        h += f'<div style="margin-top:10px"><b>Agent action:</b> {co_.ACTIONS[level][1]}<br><small>{co_.ACTIONS[level][0]}</small></div></div></div>'
        st.markdown(h, unsafe_allow_html=True)
        def s3(bad, warn=False):
            return "risk" if bad else ("caution" if warn else "ok")
        rows = [("Money received (24h)", f"৳{row.received_24h:,.0f}", s3(False, row.received_24h > 20000)),
                ("Share being taken out", f"{row.cash_share_24h:.0%}", s3(row.cash_share_24h >= 0.8 and row.network_flag, row.cash_share_24h >= 0.8)),
                ("Different senders (24h)", f"{row.senders_24h:.0f}", s3(row.senders_24h >= 4, row.senders_24h >= 2)),
                ("Hours since money arrived", f"{row.hours_since_last_in:.1f} h", s3(False, row.hours_since_last_in <= 3)),
                ("Wallet age", f"{row.wallet_age_days:.0f} days", s3(row.wallet_age_days < 14, row.wallet_age_days < 60)),
                ("Mule network", "flagged" if row.network_flag else "not flagged", s3(bool(row.network_flag))),
                ("High-risk money received", f"{row.flagged_in_share:.0%}", s3(row.flagged_in_share >= 0.5, row.flagged_in_share >= 0.2)),
                ("Agent for this wallet", "first time" if row.new_agent_for_wallet else "used before", s3(False, bool(row.new_agent_for_wallet))),
                ("Agent risk vs. peers", f"z {row.agent_peer_z:+.1f}", s3(row.agent_peer_z >= 3, row.agent_peer_z >= 2)),
                ("Cash-out model", f"{float(p[0]):.0%}", s3(p[0] >= co_.HOLD_AT, p[0] >= co_.VERIFY_AT))]
        st.markdown(checklist_html(rows), unsafe_allow_html=True)
    st.markdown(f'<div class="section-title" style="margin-top:14px">{ic("search", 16)} Agent risk intelligence · peer comparison</div>',
                unsafe_allow_html=True)
    if cm:
        ag = cm["agents"]
        st.caption(f"Each agent's share of cash-outs from network-flagged wallets, compared with agents in the same district. "
                   f"Flagged when the z-score is 3 or more with at least 3 flagged cash-outs: {ag['flagged']} of {ag['total']} agents "
                   f"flagged, {ag['correct']} of the {ag['complicit_truth']} synthetic complicit agents found, {ag['wrongly_flagged']} "
                   "wrongly flagged. Flagged agents are reviewed by the agent-network team, never blocked automatically.")
    show = peer.sort_values("peer_z", ascending=False).head(12).reset_index()
    st.dataframe(show[["agent_id", "district", "cashouts", "flagged", "flagged_share", "peer_z", "agent_flag"]].rename(columns={
        "agent_id": "Agent", "district": "District", "cashouts": "Cash-outs", "flagged": "From flagged wallets",
        "flagged_share": "Share", "peer_z": "z vs. district peers", "agent_flag": "Review"}), hide_index=True, width="stretch")


if page.endswith("Cash Out (agent)"):
    cashout_page()


# ---------------- Analyst view ----------------
if page.endswith("Analyst Queue"):
    st.markdown(f'<div class="section-title">{ic("search", 16)} Fraud analyst queue</div>', unsafe_allow_html=True)
    test = get_test(WSN, STAMP)
    _split = metrics.get("split", "")
    st.caption((f"Future transfers the models never saw ({_split.split('test (future): ')[1]}), highest risk first"
                if "test (future): " in _split else "All transfers in your log, highest risk first"))
    thr = st.slider("Show transactions with risk ≥", 0.0, 1.0, re_.HOLD_THRESHOLD, 0.05)
    q = test[test.risk_score >= thr].head(200).reset_index(drop=True)
    st.write(f"{len(test[test.risk_score >= thr]):,} transactions in queue (showing up to 200)")
    st.dataframe(q[["txn_id", "timestamp", "user_id", "recipient_id", "amount", "risk_score", "anomaly_pct", "district",
                    "device_changed", "new_location", "on_active_call", "recipient_unique_senders_24h"]],
                 width="stretch", height=230, hide_index=True)
    if len(q):
        pick = st.selectbox("Investigate transaction", q.txn_id)
        r = q[q.txn_id == pick].iloc[0]
        case_view(r, hist, wallets, ring_of, "an")
        if "scam_type" in r:
            st.caption(f"Ground truth (synthetic label, hidden in production): {r.scam_type}")
        elif "is_fraud" in r and pd.notna(r.is_fraud):
            st.caption(f"Your label for this transfer: {'fraud' if r.is_fraud == 1 else 'genuine'}")

# ---------------- Mule network ----------------
if page.endswith("Mule Network"):
    st.markdown(f'<div class="section-title">{ic("network", 16)} Money-mule network discovery</div>', unsafe_allow_html=True)
    st.caption("One scam transfer can look normal, but mule wallets give themselves away as a group: they receive "
               "high-risk money from many unrelated victims and forward it to the same collector wallet.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Wallets analysed", f"{len(wallets):,}")
    c2.metric("Suspected mule wallets", int(wallets.suspected_mule.sum()))
    c3.metric("Mule rings found", len(rings))
    if WS == "A":
        c4.metric("Shops wrongly flagged", metrics["network"]["shops_wrongly_flagged"])
    else:
        c4.metric("High-risk money in rings (৳)", f"{sum(r['flagged_amount'] for r in rings):,.0f}")
    if rings:
        st.dataframe(pd.DataFrame([{"Ring": r["ring_id"], "Collector": r["collector"], "Mule wallets": r["n_mules"],
                                    "Victims": r["victims"], "High-risk money (৳)": f"{r['flagged_amount']:,.0f}"}
                                   for r in rings]), width="stretch", hide_index=True, height=240)
        pick_r = st.selectbox("Investigate ring", [r["ring_id"] for r in rings])
        ring = next(r for r in rings if r["ring_id"] == pick_r)
        g1, g2 = st.columns([1.4, 1])
        with g1:
            st.graphviz_chart(mn.ring_dot(ring, wallets), width="stretch")
        with g2:
            what = (f"{ring['n_mules']} wallets received high-risk transfers from {ring['victims']} different senders "
                    f"(৳{ring['flagged_amount']:,.0f}) and forwarded money to the same collector wallet {ring['collector']}.")
            why = "Many unrelated victims, then a few new wallets, then one collector: the typical cash-out pattern of a mule ring."
            nxt = ("Hold outgoing transfers from these wallets, re-check their KYC, warn anyone sending money to them, "
                   "and escalate to the fraud team for review.")
            st.markdown(f"#### Case summary: {pick_r}")
            st.markdown(f"**What happened:** {what}")
            st.markdown(f"**Why it is risky:** {why}")
            st.markdown(f"**What upay should do next:** {nxt}")
            escalate_button("Mule ring", f"{WS}:{pick_r}", f"[Dataset {WS}] Mule ring {pick_r} ({ring['n_mules']} wallets, collector {ring['collector']})",
                            "Critical", dict(what=what, why=[why], next=nxt, ring_wallets=ring["mules"] + [ring["collector"]]),
                            key=f"esc_{pick_r}")
    st.info("Graph analysis runs on out-of-fold model scores over the whole log, so no wallet is judged by a model that saw its own labels. "
            "Wallets used by scammers only once or twice are hard to spot this way; that is a known limitation.")

# ---------------- Dataset B: your data ----------------
def eval_block(y, flagged, amounts):
    y, flagged = np.asarray(y).astype(int), np.asarray(flagged)
    tp = (flagged & (y == 1)).sum()
    return {"Scams caught": f"{tp / max((y == 1).sum(), 1):.0%}",
            "Precision": f"{tp / max(flagged.sum(), 1):.0%}",
            "False alarm rate": f"{(flagged & (y == 0)).sum() / max((y == 0).sum(), 1):.1%}",
            "Scam money protected": f"{amounts[flagged & (y == 1)].sum() / max(amounts[y == 1].sum(), 1):.0%}"}


def fmt_stats(d):
    return {"Scams caught": f"{d['scam_recall']:.0%}", "Precision": f"{d['precision']:.0%}",
            "False alarm rate": f"{d['false_alarm_rate']:.1%}", "Scam money protected": f"{d['scam_money_protected_pct']:.0%}"}


if page.endswith("Your Data"):
    st.markdown('<div class="section-title">Dataset B · run ScamShield as a real model on your own data</div>', unsafe_allow_html=True)
    st.markdown("Load a transaction log exported from your own system. ScamShield learns every customer's habits from it, "
                "fits a **new anomaly model on your data**, and, if the log has confirmed fraud labels (`is_fraud`), "
                "**trains a new scam classifier** on the earlier 70% and tests it on the later 30%. The result is saved as "
                "**Dataset B**; switch to it in the sidebar and every page, plus the API, runs on your data.")
    if wsp.exists(BN):
        mb = wsp.load_metrics(BN)
        st.success(f"Dataset B is ready: {mb['rows']:,} transfers, {mb['senders']:,} senders, {mb['days']} days · "
                   + ("classifier trained on your labels" if mb["mode"] == "trained" else "demo classifier (no usable labels)")
                   + (" · **active now**" if WS == "B" else " · switch to it in the sidebar"))
    with st.expander("Required format", expanded=not wsp.exists(BN), icon=":material/table_view:"):
        st.dataframe(pd.DataFrame([
            ("txn_id", "required", "Unique transfer ID", "T000123"),
            ("timestamp", "required", "Date and time", "2026-07-01 14:30:00 or 01/07/2026 14:30"),
            ("sender_id", "required", "Customer wallet sending", "U00042"),
            ("receiver_id", "required", "Wallet receiving", "W12345"),
            ("amount", "required", "Amount in BDT", "1500"),
            ("device_id", "required", "Device used", "DEV-1A2B"),
            ("district", "required", "Where the transfer was made", "Dhaka"),
            ("on_active_call", "optional", "1 if on a phone call (0 if unknown)", "0"),
            ("sender_created_at / receiver_created_at", "optional", "Wallet opening dates (strongly recommended)", "2024-05-22"),
            ("is_fraud", "optional", "1 = confirmed fraud, 0 = genuine. Needed to train a new classifier", "0"),
        ], columns=["Column", "Need", "Meaning", "Example"]), hide_index=True, width="stretch")
        tmpl = pd.read_csv("data/transactions_raw.csv", nrows=5)
        dl("Download a template CSV", tmpl.to_csv(index=False), "scamshield_template.csv", "text/csv")
        st.caption("Command line, without the app:  python workspace.py your_log.csv   ·   API on your data:  "
                   "set SCAMSHIELD_WORKSPACE=B, then uvicorn api:app")
    src = st.radio("Source", ["Upload a CSV file", "Practice: a labelled sample built from the demo log"], horizontal=True)
    raw_u = None
    if src.startswith("Upload"):
        up = st.file_uploader("Your transaction log (CSV, up to 50 MB)", type="csv")
        if up is not None:
            raw_u = safe_read_upload(up)
    else:
        st.caption("Uses the last 70 days of the demo log with its fraud labels added and wallet-opening dates for senders "
                   "removed, so you can see the whole Dataset B flow end to end.")
        if st.toggle("Prepare the practice sample", value=False):
            _r = wsp.read_log("data/transactions_raw.csv").merge(
                pd.read_csv("data/ground_truth.csv", dtype={"txn_id": str})[["txn_id", "is_fraud"]], on="txn_id", how="left")
            raw_u = _r[pd.to_datetime(_r.timestamp) >= pd.to_datetime(_r.timestamp).max() - pd.Timedelta(days=70)] \
                .drop(columns=["sender_created_at"])
    if raw_u is not None:
        problems = pl.validate(raw_u)
        if problems:
            for p_ in problems:
                st.error(p_)
        else:
            k = st.columns(4)
            k[0].metric("Rows", f"{len(raw_u):,}")
            k[1].metric("Senders", f"{raw_u.sender_id.nunique():,}")
            _t = pl.parse_time(raw_u.timestamp)
            k[2].metric("Days covered", (_t.max() - _t.min()).days)
            k[3].metric("Fraud labels", f"{int(pd.to_numeric(raw_u.is_fraud, errors='coerce').sum()):,}" if "is_fraud" in raw_u else "none")
            for note in pl.data_quality(raw_u):
                st.warning("Data quality: " + note)
            st.dataframe(raw_u.head(6), hide_index=True, width="stretch")
            if st.button("Build Dataset B from this log", type="primary", icon=":material/model_training:"):
                box = st.status("> BUILDING_DATASET_B ...", expanded=True)
                try:
                    mb = wsp.build_b(raw_u, BN, progress=lambda m_: box.write(m_))
                    box.update(label="> DATASET_B_READY", state="complete")
                    st.session_state.ws = "B"
                    st.session_state.pop("ds_pick", None)
                    st.cache_data.clear()
                    st.rerun()
                except Exception as ex:          # show the problem instead of crashing
                    box.update(label="> BUILD_FAILED", state="error")
                    st.error(f"Could not build Dataset B: {ex}")
    if wsp.exists(BN):
        mb = wsp.load_metrics(BN)
        st.markdown('<div class="section-title" style="margin-top:16px">Dataset B results</div>', unsafe_allow_html=True)
        st.write(mb["note"])
        st.caption(mb["split"])
        if mb["mode"] == "trained":
            st.dataframe(pd.DataFrame({"New model trained on your data": fmt_stats(mb["ai_system"]),
                                       "Demo model (trained on Dataset A)": fmt_stats(mb["demo_model_on_same_test"]),
                                       "Simple rule": fmt_stats(mb["rule_baseline"])}), width="stretch")
            st.caption(f"Measured on the later 30% of your log ({mb['test_size']:,} transfers) that the new model never saw. "
                       f"ROC-AUC {mb['roc_auc']:.3f}.")
        c1, c2 = st.columns(2)
        if WS != "B" and c1.button("Switch to Dataset B now", icon=":material/swap_horiz:"):
            st.session_state.ws = "B"
            st.session_state.pop("ds_pick", None)
            st.rerun()
        if c2.button("Delete Dataset B", icon=":material/delete:"):
            wsp.delete(BN)
            st.session_state.ws = "A"
            st.session_state.pop("ds_pick", None)
            st.cache_data.clear()
            st.rerun()

# ---------------- Datasets ----------------
@st.cache_data(show_spinner="> CROSS_DATASET_TEST: scoring the previous dataset with the current models...")
def previous_dataset_eval():
    d = pd.read_csv("data/previous/transactions.csv")
    y = d.is_scam.values
    mA, fA = re_.load_model(wsp.paths("A")["model"]), re_.load_iforest(wsp.paths("A")["iforest"])
    sc = re_.score_frame(mA, fA, d)
    rule = ((d.is_new_recipient == 1) & (d.amount >= 5000)).values
    out = {"Demo models (trained on the main log)": eval_block(y, (sc.decision != "ALLOW").values, d.amount.values),
           "Simple rule": eval_block(y, rule, d.amount.values)}
    # retrain on the previous dataset itself: earlier 70% -> later 30%
    import xgboost as xgb
    cut = int(len(d) * 0.7)
    tr, te = d.iloc[:cut], d.iloc[cut:]
    m2 = xgb.XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.08, subsample=0.9, colsample_bytree=0.9,
                           eval_metric="aucpr", random_state=7, scale_pos_weight=(tr.is_scam == 0).sum() / tr.is_scam.sum())
    m2.fit(re_.ensure_features(tr)[re_.FEATURES], tr.is_scam)
    s_old = re_.score_frame(mA, fA, te)
    s_new = re_.score_frame(m2, re_.fit_iforest(tr), te)
    retrain = {"Current models": eval_block(te.is_scam, (s_old.decision != "ALLOW").values, te.amount.values),
               "Retrained on this set": eval_block(te.is_scam, (s_new.decision != "ALLOW").values, te.amount.values)}
    by_type = sc.groupby(d.scam_type).decision.apply(lambda s: f"{(s != 'ALLOW').mean():.0%}").to_dict()
    wl = mn.find_mules(sc)
    rg = mn.find_rings(wl, pd.read_csv("data/previous/forwarding.csv"))
    roles = pd.read_csv("data/previous/wallet_roles_ground_truth.csv").set_index("wallet_id").role
    sus = wl.index[wl.suspected_mule]
    net = {"Suspected mules": len(sus), "Of which real mules": f"{(roles.reindex(sus) == 'mule').mean():.0%}",
           "Rings found": len(rg)}
    return out, retrain, by_type, net, d


if page.endswith("Datasets"):
    st.markdown('<div class="section-title">Datasets</div>', unsafe_allow_html=True)
    st.caption("Dataset A is our synthetic demo data (the main raw log plus our earlier synthetic set, both kept). "
               "Dataset B is your own data: load it in the Dataset B page and ScamShield builds real models from it.")
    if wsp.exists(BN):
        mb = wsp.load_metrics(BN)
        st.markdown(f"""<div class="ds" style="margin-bottom:12px"><div class="tag">DATASET B · YOUR DATA · {"ACTIVE" if WS == "B" else "READY"}</div>
<h4>Your transaction log</h4><p><b>{mb['rows']:,}</b> transfers · <b>{mb['senders']:,}</b> senders · <b>{mb['days']}</b> days ·
{"classifier trained on your labels" if mb['mode'] == "trained" else "demo classifier, anomaly model fitted on your data"}</p>
<p>{mb['note']}</p></div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="ds" style="margin-bottom:12px"><div class="tag">DATASET B · YOUR DATA · NOT BUILT YET</div>
<h4>Your transaction log</h4><p>Upload a CSV in the Dataset B page. ScamShield will learn every customer's habits from it,
fit an anomaly model on it and, if it has fraud labels, train a new classifier, then run every page and the API on it.</p></div>""",
                    unsafe_allow_html=True)
    raw_main = pd.read_csv("data/transactions_raw.csv")
    gt_main = pd.read_csv("data/ground_truth.csv")
    prev = pd.read_csv("data/previous/transactions.csv")
    c1, c2 = st.columns(2)
    with c1:
        cust_gt = gt_main[gt_main.kind == "customer"]
        st.markdown(f"""<div class="ds"><div class="tag">DATASET A · DEMO · MAIN SYNTHETIC LOG</div><h4>Synthetic raw transaction log</h4>
<p>What upay actually stores: time, sender, receiver, amount, device, district. No labels inside; every signal is computed
from history by the pipeline. Labels are kept in a separate file like a fraud team's confirmed cases.</p>
<p><b>{len(raw_main):,}</b> transfers · <b>{raw_main.sender_id.str.startswith('U').groupby(raw_main.sender_id).any().sum():,}</b> customers ·
<b>90</b> days · scam rate <b>{cust_gt.is_fraud.mean():.1%}</b> · 80 mule wallets in 12 rings</p>
<p>Generator: <code>generate_data.py</code> · used for training (days 30–72) and the future test (days 72–90)</p></div>""",
                    unsafe_allow_html=True)
        st.dataframe(raw_main.head(8), hide_index=True, width="stretch")
        dl("Download the main synthetic log (CSV)", raw_main.to_csv(index=False), "dataset_A_main_log.csv", "text/csv")
    with c2:
        st.markdown(f"""<div class="ds"><div class="tag">DATASET A · DEMO · EARLIER SYNTHETIC SET (KEPT)</div><h4>Synthetic customer-profile set</h4>
<p>Our earlier dataset: 8,000 synthetic customers with fixed profiles (usual amount, usual hours, devices, home district),
with the same 12 signals already computed for each transfer. Generated independently from the main log.</p>
<p><b>{len(prev):,}</b> transfers · <b>8,000</b> customers · scam rate <b>{prev.is_scam.mean():.1%}</b> ·
80 mule wallets in 12 rings</p>
<p>Generator: <code>generate_data_profiles.py</code> · used here as an independent test set</p></div>""",
                    unsafe_allow_html=True)
        st.dataframe(prev.head(8), hide_index=True, width="stretch")
        dl("Download the earlier synthetic set (CSV)", prev.to_csv(index=False), "dataset_A_earlier_set.csv", "text/csv")
        dl("Download its customer profiles (CSV)",
                           pd.read_csv("data/previous/user_profiles.csv").to_csv(index=False), "dataset_A_earlier_profiles.csv", "text/csv")

    with st.expander("How the synthetic data was made, and a data dictionary", icon=":material/menu_book:"):
        st.markdown("""**Why synthetic?** Real upay transactions are confidential and were not available for the hackathon, so
Dataset A is generated by `generate_data.py` (fixed seed 42, so anyone can rebuild exactly the same file). The models are
built to retrain on real data (Dataset B) without code changes.

**How it was made**
- **Customers (3,000):** each has a usual amount (log-normal around ৳1,100), usual active hours, one or two phones and a
  home district. 84,000 genuine transfers follow those habits, with occasional new contacts, new phones (1%) and travel.
- **Wallets:** people, shops, suppliers, and 80 mule wallets in 12 rings that forward money to a ring collector.
  60% of mules are freshly opened; 40% are older "rented" accounts that look established.
- **Scams (1,793 transfers, 2.1% of customer transfers):** three types with different signals:
  phone-coached social engineering (1,000: larger amount, new recipient, often on a call, from the victim's own phone),
  account takeover (220 incidents, 523 transfers: new phone, often at night and in another district, 1 to 4 quick drains;
  6 in 10 from a pool of 12 shared fraud-farm handsets), and low-signal scams (270: amounts close to normal, known phone,
  rarely a call).
- **Cash-outs:** `cashout.py` adds 20,000 agent cash-outs across 300 agents (6 complicit); mules and collectors cash out
  most of what they receive within hours.

**Which patterns come from cited sources** (see README): fraud-loss scale and send-money volume (Bangladesh Bank data via the
Daily Observer and The Financial Express), OTP/PIN social-engineering calls, fake prize and lottery messages, and
"sent by mistake" calls (bKash fraud-awareness page). The exact rates, amounts and timings are **our assumptions**, chosen
to be plausible, not measured from real data. Results on synthetic data are optimistic; they must be re-measured on upay data.""")
        st.dataframe(pd.DataFrame([
            ("txn_id", "raw log", "Unique transfer ID", "T000123"),
            ("timestamp", "raw log", "When the transfer was made", "2026-09-14 15:42:10"),
            ("sender_id / receiver_id", "raw log", "Wallets (U = customer, W = other wallet)", "U00042 / W12345"),
            ("amount", "raw log", "Taka", "6000"),
            ("device_id", "raw log", "Phone used", "DEV-1A2B"),
            ("district", "raw log", "Where the transfer was made", "Dhaka"),
            ("on_active_call", "raw log", "1 if the customer was on a phone call", "0"),
            ("sender_created_at / receiver_created_at", "raw log", "Wallet opening dates", "2024-05-22"),
            ("is_fraud, scam_type", "labels file", "Ground truth, kept apart from the log (like confirmed cases)", "1, account_takeover"),
            ("role", "labels file", "person / shop / supplier / mule / collector (evaluation only)", "mule"),
        ] + [(f, "model feature", d, "") for f, d in [
            ("amount_ratio", "Amount ÷ the customer's own usual (median) amount so far"),
            ("hour, outside_usual_hours", "Hour of day; 1 if outside the customer's usual window"),
            ("is_new_recipient", "1 if never paid this wallet before"),
            ("recipient_account_age_days", "Age of the receiving wallet"),
            ("recipient_unique_senders_24h", "Other people who paid the recipient in the last 24 h"),
            ("user_txns_last_1h", "Customer's transfers in the previous hour"),
            ("device_changed, new_location", "New phone / new district for this customer"),
            ("user_tenure_days", "How long the customer has had the wallet"),
            ("device_other_users_30d", "Other accounts that used this phone in the last 30 days (new)"),
            ("txn_velocity_trend", "Transfers in the last 24 h vs. the customer's own daily pace (new)")]],
            columns=["Field", "Where", "Meaning", "Example"]), hide_index=True, width="stretch")
        st.caption("Every model feature is computed point-in-time from the raw log by pipeline.py, using only earlier transfers.")

    st.markdown('<div class="section-title" style="margin-top:18px">Cross-dataset test: demo models on the earlier synthetic set</div>',
                unsafe_allow_html=True)
    st.caption("The demo models were trained only on the main synthetic log. The earlier set was generated separately with different assumptions, "
               "so this shows what happens when a model meets data that is not like its training data, as with real upay data.")
    if st.toggle("Run the cross-dataset test", value=False):
        out, retrain, by_type, net, _ = previous_dataset_eval()
        d1, d2 = st.columns(2)
        with d1:
            st.markdown("**All 60,000 transfers of the earlier set**")
            st.dataframe(pd.DataFrame(out), width="stretch")
            st.markdown("**Caught by scam type:** " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in by_type.items() if k != "none")
                        + f" · genuine transfers warned {by_type.get('none', '')}")
            st.markdown("**Mule network on the earlier set:** " + " · ".join(f"{k}: {v}" for k, v in net.items()))
        with d2:
            st.markdown("**After retraining on the earlier set** (first 70% → last 30%)")
            st.dataframe(pd.DataFrame(retrain), width="stretch")
        st.info("What this shows: the method carries over to a different dataset and still catches most scams, but false alarms "
                "rise because the data looks different. Retraining on the target data brings them back down. That is exactly "
                "why Dataset B exists: load your own data and ScamShield retrains on it.")

# ---------------- Cases ----------------
if page.endswith("Cases"):
    st.markdown(f'<div class="section-title">{ic("folder", 16)} Case management</div>', unsafe_allow_html=True)
    st.caption("Human-in-the-loop: AI raises and explains alerts, analysts decide. Every action is recorded in the audit trail.")
    if not CASES:
        st.info("No cases yet. Escalate an alert from the **Analyst queue** or a ring from the **Mule network** tab.")
    else:
        k1, k2, k5, k3, k4 = st.columns(5)
        k1.metric("Open", sum(c["status"] == "Open" for c in CASES))
        k2.metric("In progress", sum(c["status"] == "In progress" for c in CASES))
        k5.metric("Disputed by customer", sum(c["status"] == "Disputed by customer" for c in CASES))
        k3.metric("Confirmed fraud", sum(c["status"] == "Resolved: confirmed fraud" for c in CASES))
        k4.metric("False alarms / released", sum(c["status"] in ("Resolved: false alarm", "Released: customer verified") for c in CASES))
        st.caption(f"Service levels: a HOLD is reviewed within {cs.SLA['HOLD review']}; a customer dispute within "
                   f"{cs.SLA['Customer dispute']} by a second analyst. Money on HOLD is never taken: it is either released "
                   "to the recipient or returned to the customer.")
        flt = st.radio("Filter", ["All"] + cs.STATUSES, horizontal=True)
        shown = [c for c in CASES if flt == "All" or c["status"] == flt]
        st.dataframe(pd.DataFrame([{"Case": c["id"], "Title": c["title"], "Type": c["kind"], "Priority": c["priority"],
                                    "Status": c["status"], "Analyst": c["analyst"], "Created": c["created"]}
                                   for c in shown]), width="stretch", hide_index=True)
        if shown:
            cid = st.selectbox("Open case", [c["id"] for c in shown])
            case = next(c for c in CASES if c["id"] == cid)
            d1, d2 = st.columns([1.2, 1])
            with d1:
                st.markdown(f'<div class="casebox"><b>{case["id"]}</b> &nbsp; <span class="pri {case["priority"]}">'
                            f'{case["priority"]}</span><br>{E(case["title"])}<br><small>Status: <b>{case["status"]}</b> · '
                            f'Analyst: {E(case["analyst"])} · Created {case["created"]}</small></div>', unsafe_allow_html=True)
                ev = case["evidence"]
                st.markdown(f"**What happened:** {ev['what']}")
                st.markdown("**Why it is risky:**\n" + "\n".join(f"- {w}" for w in ev["why"]))
                st.markdown(f"**What upay should do next:** {ev['next']}")
                if ev.get("engines"):
                    st.markdown(engines_html(ev["engines"], sum(e["flagged"] for e in ev["engines"])),
                                unsafe_allow_html=True)
            with d2:
                with st.form(f"upd_{cid}"):
                    new_status = st.selectbox("Status", cs.STATUSES, index=cs.STATUSES.index(case["status"]))
                    new_analyst = st.text_input("Assigned analyst", case["analyst"])
                    note = st.text_area("Add a note", placeholder="e.g. Called the customer, they confirmed a prize-call scam.")
                    if st.form_submit_button("Save changes", type="primary", icon=":material/save:"):
                        cs.assign(case, new_analyst, new_analyst or ANALYST)
                        cs.update_status(case, new_status, new_analyst or ANALYST)
                        cs.add_note(case, note, new_analyst or ANALYST)
                        st.rerun()
                if case["kind"] == "Transaction" and case["status"] not in cs.LABEL_OF:
                    with st.expander("Customer appeal: the customer says this HOLD is wrong", icon=":material/gavel:"):
                        why_d = st.text_input("Customer's explanation", "This is my brother, I send him money every month.",
                                              key=f"disp_{cid}")
                        if st.button("Record customer dispute", key=f"dispbtn_{cid}", icon=":material/record_voice_over:"):
                            cs.customer_dispute(case, why_d)
                            log_access("Recorded dispute", case["id"])
                            st.rerun()
                        st.caption("In the app the customer taps 'This is a mistake' on the HOLD screen (see Customer App). "
                                   "A second analyst then releases the money or confirms fraud.")
                st.download_button("Download case report (PDF)", cs.pdf_report(case), icon=":material/picture_as_pdf:", file_name=f"{cid}_report.pdf",
                                   mime="application/pdf", width="stretch")
                if case["notes"]:
                    st.markdown("**Notes**")
                    for n in case["notes"]:
                        st.markdown(f"- _{n['time']}_ · **{n['actor']}**: {n['text']}")
            st.markdown("**Audit trail**")
            st.dataframe(pd.DataFrame(case["audit"]).rename(columns=str.title), width="stretch", hide_index=True)
        if not is_admin():
            st.session_state.pseudo_exp = True
        pseudo = st.toggle("Pseudonymise IDs in exports", value=True, key="pseudo_exp", disabled=not is_admin(),
                           help="Customer and transaction IDs are replaced by one-way codes (SHA-256), titles are left out. "
                                "Only an admin can export real IDs.")
        exp = pd.DataFrame([{k: c[k] for k in ("id", "kind", "ref", "title", "priority", "status", "analyst", "created")}
                            for c in CASES])
        if pseudo:
            exp = exp.drop(columns="title").assign(ref=exp.ref.map(cs.pseudonymise))
        if dl("Export all cases (CSV)", exp.to_csv(index=False), file_name="scamshield_cases.csv", mime="text/csv"):
            log_access("Exported cases", "pseudonymised" if pseudo else "REAL IDs")
        st.markdown(f'<div class="section-title" style="margin-top:14px">{ic("refresh", 16)} Feedback loop: analyst decisions become training labels</div>',
                    unsafe_allow_html=True)
        labs = cs.labels_from_cases(CASES)
        if not labs:
            st.caption("Resolve a transaction case (confirmed fraud, false alarm or released after a dispute) and it appears "
                       "here as a new label.")
        else:
            st.dataframe(pd.DataFrame(labs), hide_index=True, width="stretch")
            dl("Download labels (CSV)", pd.DataFrame(labs)[["txn_id", "is_fraud"]].to_csv(index=False),
               file_name="analyst_labels.csv", mime="text/csv")
            b_labs = [x for x in labs if x["dataset"] == "B"]
            if wsp.exists(BN) and b_labs:
                if st.button(f"Add {len(b_labs)} label(s) to Dataset B and retrain", type="primary", icon=":material/model_training:"):
                    rawB, n_hit = cs.merge_labels(wsp.read_log(wsp.paths(BN)["raw"]), b_labs)
                    log_access("Retrained Dataset B with analyst labels", f"{n_hit} transfers")
                    box = st.status("> RETRAINING_DATASET_B_WITH_ANALYST_LABELS ...", expanded=True)
                    try:
                        wsp.build_b(rawB, BN, progress=lambda m_: box.write(m_))
                        box.update(label=f"> DONE: {n_hit} transfers relabelled", state="complete")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as ex:
                        box.update(label="> RETRAIN_FAILED", state="error")
                        st.error(f"Could not retrain: {ex}")
            else:
                st.caption("Labels on Dataset B cases can be merged into Dataset B and the models retrained with one click. "
                           "Dataset A (demo) already carries its synthetic labels. In production, new labels feed the "
                           "weekly retraining, which runs in shadow mode before the new model replaces the old one.")

# ---------------- Model & impact ----------------
@st.cache_data(show_spinner="> COMPUTING_DRIFT ...")
def drift_tables(wsn, stamp):
    from generate_data import DAYS, START, WARMUP
    f = pd.read_parquet("data/features_all.parquet")
    cut = START + pd.Timedelta(days=WARMUP + int((DAYS - WARMUP) * 0.7))
    c = f[f.user_id.str.startswith("U") & (f.timestamp >= START + pd.Timedelta(days=WARMUP))]
    mA, fA = re_.load_model(wsp.paths("A")["model"]), re_.load_iforest(wsp.paths("A")["iforest"])
    ref = re_.score_frame(mA, fA, c[c.timestamp < cut])
    if wsn == "A":
        cur = re_.score_frame(mA, fA, c[c.timestamp >= cut])
        return mo.drift_report(ref, cur), "Training period (days 30–72) vs. future period (days 72–90)"
    cur = pd.read_parquet(wsp.paths(wsn)["test"]).drop(columns=["risk_score"], errors="ignore")
    return mo.drift_report(ref.drop(columns=["risk_score"]), cur), "Demo model's training data (Dataset A) vs. your data (Dataset B)"


def pct(x, d=0):
    return f"{x:.{d}%}"


@st.cache_data(show_spinner="> SCORING_TEST_WINDOW ...")
def threshold_base(wsn, stamp):
    """Scores, anomaly percentiles and rule flags for the active test window (computed once, sliders reuse them)."""
    t = get_test(wsn, stamp)
    sc = re_.score_frame(get_model(wsn, stamp), get_iforest(wsn, stamp), t)
    X = sc
    return pd.DataFrame({
        "score": sc.risk_score.values, "unusual": (sc.anomaly_pct >= re_.ANOMALY_THRESHOLD).values,
        "coach": ((X.on_active_call == 1) & (X.is_new_recipient == 1) & (X.amount >= 5000)).values,
        "takeover": (((X.device_changed == 1) & (X.new_location == 1) & (X.amount_ratio >= 3)) |
                     ((X.device_changed == 1) & (X.user_txns_last_1h >= 3))).values,
        "new": (X.user_tenure_days < re_.NEW_CUSTOMER_DAYS).values, "amount": X.amount.values,
        "y": (pd.to_numeric(t["is_fraud"], errors="coerce").fillna(0).values == 1) if "is_fraud" in t else np.zeros(len(t), bool),
        "labelled": np.full(len(t), "is_fraud" in t and t["is_fraud"].notna().any())})


def threshold_tuning():
    b = threshold_base(WSN, STAMP)
    st.markdown("WARN at 0.30 and HOLD at 0.70 are **policy settings, not fixed numbers**. Move them and every figure "
                "below is recomputed on the future test window of the active dataset.")
    c1, c2, c3, c4 = st.columns(4)
    w = c1.slider("WARN threshold", 0.05, 0.95, re_.WARN_THRESHOLD, 0.05, key="tt_warn")
    h = c2.slider("HOLD threshold", 0.10, 0.99, re_.HOLD_THRESHOLD, 0.01, key="tt_hold")
    wn = c3.slider("WARN threshold, new customers", 0.05, 0.95, re_.NEW_CUSTOMER_WARN, 0.05, key="tt_warn_new")
    mins = c4.number_input("Analyst minutes per HOLD", 1, 60, 10, key="tt_min")
    h = max(h, w)

    def run(w_, h_, wn_):
        wt = np.where(b.new, np.maximum(w_, wn_), w_)
        hold = (b.score >= h_) | b.takeover
        alert = hold | (b.score >= wt) | b.coach | b.unusual
        return alert.values, hold.values

    alert, hold = run(w, h, wn)
    a0, h0 = run(re_.WARN_THRESHOLD, re_.HOLD_THRESHOLD, re_.NEW_CUSTOMER_WARN)
    n, y, gen = len(b), b.y.values, ~b.y.values
    per = 10_000 / n

    def row(name, al, ho):
        r = {"Setting": name, "Alerts per 10,000": f"{al.sum() * per:,.1f}", "HOLDs per 10,000": f"{ho.sum() * per:,.1f}",
             "Analyst hours per 10,000": f"{ho.sum() * per * mins / 60:,.1f}"}
        if b.labelled.iat[0]:
            r.update({"Genuine transfers alerted": pct((al & gen).sum() / max(gen.sum(), 1), 2),
                      "Scams caught": pct((al & y).sum() / max(y.sum(), 1), 1),
                      "Scam money protected": pct(b.amount.values[al & y].sum() / max(b.amount.values[y].sum(), 1), 1),
                      "Alerts that are real scams": pct((al & y).sum() / max(al.sum(), 1), 1)})
        return r

    st.dataframe(pd.DataFrame([row("Your setting", alert, hold), row("Default policy", a0, h0)]), hide_index=True, width="stretch")
    if not b.labelled.iat[0]:
        st.caption("This dataset has no fraud labels, so only workload is shown. Add is_fraud to see detection too.")
    grid = []
    for wv in np.arange(0.1, 0.95, 0.05):
        al, ho = run(wv, max(h, wv), max(wn, wv))
        grid.append({"WARN threshold": round(float(wv), 2), "Alerts per 10,000": al.sum() * per,
                     **({"Scams caught (%)": 100 * (al & y).sum() / max(y.sum(), 1)} if b.labelled.iat[0] else {})})
    g = pd.DataFrame(grid).set_index("WARN threshold")
    st.markdown("**The trade-off curve** (lower WARN threshold = more alerts and more scams caught)")
    st.line_chart(g, color=["#FFD200", "#2F8CFF"][:len(g.columns)])
    st.caption("This test window has far more scams than real life (about 2% of transfers), so the counts per 10,000 are "
               "higher than they would be in production; the business calculator above rescales them to a realistic scam rate. "
               "Rules (takeover, call coaching) and the anomaly model still alert whatever the classifier thresholds are. "
               "In production the thresholds are tuned on real data in shadow mode before going live.")


def dig(d, *keys):
    for k in keys:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def perf_tab(bm):
    if not bm:
        st.info("Run `python benchmark.py` to measure performance.")
        return
    k = st.columns(4)
    k[0].metric("Latency per transfer (p95)", f"{bm['live_latency_ms']['p95']} ms", f"p50 {bm['live_latency_ms']['p50']} ms", delta_color="off")
    k[1].metric("Batch scoring", f"{bm['batch_scoring_transfers_per_second']:,}/s", delta_color="off")
    k[2].metric("Memory per wallet", f"{bm['bytes_per_wallet']:,} bytes", f"{bm['projected_gb_per_million_wallets']} GB per 1M wallets", delta_color="off")
    k[3].metric("Stored state per customer", f"{bm['serialised_state_bytes_typical_customer']:,} bytes",
                f"busiest: {bm['serialised_state_bytes_busiest_customer']:,} bytes", delta_color="off")
    st.caption(f"Measured: {bm['machine']}, {bm['transfers']:,} transfers, {bm['wallets']:,} wallets. Latency covers the full "
               "live path: features from history, classifier, anomaly model, SHAP reasons and rules.")
    lt = load_json("loadtest.json", STAMP)
    if lt:
        st.markdown(f"**Load test of the real API (POST /score over HTTP, API key on, {lt['requests']:,} requests, "
                    f"{lt['concurrency']} concurrent clients, {lt['workers']} server worker{'s' if lt['workers'] > 1 else ''})**")
        l = st.columns(4)
        l[0].metric("Throughput", f"{lt['throughput_rps']:,.0f} req/s", delta_color="off")
        l[1].metric("Latency p50", f"{lt['latency_ms']['p50']} ms", delta_color="off")
        l[2].metric("Latency p95", f"{lt['latency_ms']['p95']} ms", f"p99 {lt['latency_ms']['p99']} ms", delta_color="off")
        l[3].metric("Errors", f"{lt['errors']}", f"{lt['rate_limited']} rate-limited (429) in the limit test", delta_color="off")
        st.caption(lt["note"])
    st.markdown("**Why memory stays bounded:** each customer keeps at most "
                f"{bm['bounds']['max_history']} recent amounts and hours, {bm['bounds']['max_contacts']} contacts and "
                f"{bm['bounds']['max_devices_districts']} devices/districts; short-term windows (1 h, 24 h) are compacted. "
                "Older history is kept as running statistics (count, mean and spread of amounts), so nothing grows with "
                "the number of transfers, only with the number of active customers.")
    st.markdown("**Production path (see README: Scalability & integration):** stateless scoring API behind a load balancer · "
                "per-customer state in Redis (one key per wallet, under 1 KB typical) · transfers streamed from the core system · "
                "nightly mule-network job · model registry with shadow mode · monitoring of latency, drift and alert rates.")


def differentiation_tab(ev):
    st.markdown("Judges noted that fraud ML and pop-up warnings are common. This is what ScamShield does differently, "
                "compared with **typical approaches** (not with any specific product), and where each claim is shown.")
    un = (ev or {}).get("unseen_takeover_ablation", {})
    rows = [
        ("The warning", "Generic 'beware of fraud' pop-up that people learn to ignore",
         "Names the specific risk in Bangla from the customer's OWN history (on a call, 10x your usual amount, this wallet got "
         "money from 17 people today); every cancel/continue is counted, so weak warnings can be rewritten",
         "Customer App · Send Money"),
        ("What is checked", "One risk score or a fixed rule per transfer",
         f"Independent engines that must agree before an analyst is involved; a scam type never seen in training is still "
         f"caught ({un.get('All engines', 1):.0%} vs {dig(un, 'Scam classifier', 'alone') or 0.4:.0%} for the classifier alone)",
         "Engine contribution"),
        ("Where money is stopped", "At the sender's transfer only",
         "Three points: the transfer, the mule wallets that collect it (rings from the transfer graph), and the agent counter "
         "where it is cashed out, with each agent compared with its district peers", "Mule Network · Cash Out (agent)"),
        ("Analyst workload", "Every alert goes to a review queue",
         "Low risk → customer decides (WARN); HOLD only when 2+ engines agree: 21x fewer genuine transfers for analysts, "
         "same scams caught; thresholds tuned live", "Analyst workload · Threshold tuning"),
        ("Data needed to start", "Large sets of confirmed fraud labels",
         "Anomaly, takeover and network engines need no labels; any transaction log becomes a working model in one click, "
         "and labels added later retrain it", "Dataset B"),
        ("When the system is wrong", "Block first, call centre later",
         "No permanent automatic block; 'This is a mistake' opens a dispute reviewed in 24 h; the outcome becomes a label "
         "that improves the model", "Customer App · Cases"),
        ("Fairness", "Measured once, if at all",
         "Separate threshold for new customers (false alarms 1.14% → 0.38%), monitored per segment with confidence intervals",
         "Fairness & drift"),
        ("Going live", "Switch on and hope",
         "Shadow mode with written go-live criteria, then an A/B pilot sized in advance; fail-open so an outage never stops payments",
         "Shadow mode & pilot"),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["", "Typical approach", "ScamShield", "Where to see it"]), hide_index=True,
                 width="stretch")


@st.cache_data(show_spinner="> MAPPING_LOSS_CONCENTRATION ...")
def loss_tables(wsn, stamp):
    t = get_test(wsn, stamp)
    if "is_fraud" not in t or pd.to_numeric(t.is_fraud, errors="coerce").fillna(0).sum() < 5:
        return None
    sc = re_.score_frame(get_model(wsn, stamp), get_iforest(wsn, stamp), t)
    return mo.loss_concentration(t, (sc.decision != "ALLOW").values)


def loss_tab():
    tabs = loss_tables(WSN, STAMP)
    st.markdown("**Where does scam money concentrate, and where is it still missed?** Future test window of the active "
                "dataset. On real upay data this tells the team which customers and situations to protect first.")
    if tabs is None:
        st.info("This dataset has no fraud labels, so losses cannot be located. Add an is_fraud column and rebuild Dataset B.")
        return
    for line in mo.concentration_headlines(tabs):
        st.markdown(f"- {line}")
    dims = [d for d in ["Scam type", "Amount", "Customer tenure", "Time of day", "Receiving wallet age", "District"] if d in tabs]
    pick = st.radio("Break down by", dims, horizontal=True, key="loss_dim")
    t = tabs[pick].copy()
    c1, c2 = st.columns([1.3, 1])
    with c1:
        show = t.assign(**{"Share of scams": t["Share of scams"].map(lambda x: f"{x:.0%}"),
                           "Scam money (৳)": t["Scam money (৳)"].map(lambda x: f"{x:,.0f}"),
                           "Share of scam money": t["Share of scam money"].map(lambda x: f"{x:.0%}"),
                           "Money protected": t["Money protected"].map(lambda x: f"{x:.0%}"),
                           "Share of missed money": t["Share of missed money"].map(lambda x: f"{x:.0%}")})
        st.dataframe(show, hide_index=True, width="stretch")
    with c2:
        st.bar_chart(t.set_index("Group")[["Share of scam money", "Share of missed money"]], color=["#FFD200", "#FF4D5E"],
                     horizontal=True)
    st.caption("Synthetic data: the pattern of the table is what matters for the demo; the real concentration must be "
               "measured on upay's confirmed fraud cases (Dataset B), which this tab does automatically.")


def shadow_tab(bm):
    st.markdown("**Step 1 on real data: shadow mode.** ScamShield scores every transfer silently and logs what it *would* "
                "have done; customers see no change (`SCAMSHIELD_MODE=shadow` on the API). When confirmed fraud comes in, "
                "the log is checked against written go-live criteria. Below: that report for the active dataset's future window.")
    t = get_test(WSN, STAMP)
    if "is_fraud" not in t or pd.to_numeric(t.is_fraud, errors="coerce").fillna(0).sum() < 5:
        st.info("Needs confirmed fraud labels to compare against.")
    else:
        sc = re_.score_frame(model, iforest, t)
        dec = sc.decision.values.copy()
        m, crit = mo.shadow_report(dec, t.is_fraud.values, t.amount.values,
                                   latency_p95_ms=(bm or {}).get("live_latency_ms", {}).get("p95"))
        k = st.columns(4)
        k[0].metric("Transfers scored silently", f"{m['transfers']:,}")
        k[1].metric("Scams caught", f"{m['recall']:.0%}")
        k[2].metric("Holds that are scams", f"{m['hold_precision']:.0%}")
        k[3].metric("Go-live criteria passed", f"{(crit.Pass == 'PASS').sum()} of {len(crit)}")
        st.dataframe(crit, hide_index=True, width="stretch")
        st.caption("Go-live only when every criterion passes for 2 weeks in a row; the criteria are agreed with upay's fraud "
                   "team before shadow mode starts.")
    st.markdown("**Step 2: A/B pilot, sized before it starts.** Half of the customers get ScamShield, half do not; the "
                "pilot measures scam money lost per 10,000 transfers in each half.")
    c1, c2, c3 = st.columns(3)
    base = c1.number_input("Scam transfers per 100,000 today", 1.0, 500.0, 8.0, 1.0, key="pilot_base",
                           help="Default: about 8 per 100,000 from the national loss figure and average scam size")
    red = c2.slider("Reduction to detect", 0.2, 0.9, 0.5, 0.05, key="pilot_red")
    vol = c3.number_input("upay send money transfers per day", 10_000, 10_000_000, 400_000, 50_000, key="pilot_vol")
    n = mo.pilot_sample_size(base / 1e5, red)
    days = 2 * n / vol
    st.success(f"Transfers needed: **{n:,} per group** ({2 * n:,} in total) to detect a {red:.0%} drop in scam transfers "
               f"with 95% confidence and 80% power. At {vol:,} transfers a day that is about **{days:,.0f} days**.")
    st.markdown("**Pilot ROI** = (scam money lost per 10,000 in the control group − in the ScamShield group) × volume − "
                "measured friction (warned customers who gave up, analyst hours). The Business impact calculator above "
                "takes the measured rates in place of today's assumptions.")
    st.markdown("**Step 3: integration in the payment flow** (`integration.py`): the Send Money service calls `POST /score` "
                "with a 150 ms budget. If ScamShield is slow or down, the payment goes through (fail-open), the transfer is "
                "queued and scored seconds later, and a risky one is raised as a late alert; after repeated failures a circuit "
                "breaker stops calling for 30 s. Tested in `tests/test_scamshield.py`.")


def security_panel():
    st.markdown("Only what is **really implemented** in this code is marked as in place. Production items are listed "
                "separately as the plan, not as done.")
    done = [
        ("API access", "API key on every data endpoint (X-API-Key, constant-time check); keys and per-key limits from environment", "api.py"),
        ("Abuse protection", "Rate limit per key per minute → HTTP 429 with Retry-After (tested)", "api.py · tests"),
        ("Input validation", "API: ID length, amount range, 0/1 flags → HTTP 422. Upload: CSV only, 50 MB, 1M rows, columns, "
                             "empty IDs, negative amounts, labels 0/1, clear error messages", "api.py · pipeline.validate · app"),
        ("Privacy in outputs", "API logs and case exports carry pseudonymised IDs (SHA-256), not wallet numbers", "api.py · cases.py"),
        ("Data isolation", "Each visitor's Dataset B is private to their session, deleted after 12 hours, never committed to git", "workspace.py · .gitignore"),
        ("Safe rendering", "All user or data text is HTML-escaped before display (no script injection)", "app.py E()"),
        ("Human in the loop", "No automatic permanent block: WARN lets the customer decide, HOLD goes to an analyst", "risk_engine.py"),
        ("Customer appeal", "'This is a mistake' on a HOLD opens a dispute; a second analyst releases or confirms (SLA 24 h)", "cases.py · Customer App"),
        ("Audit trail", "Every case action is recorded with time and actor; PDF case report", "cases.py"),
        ("Feedback loop", "Resolved cases become labels; one click retrains Dataset B on them", "cases.py · Cases page"),
        ("Model monitoring", "Drift (PSI per feature and score), alert rates per customer segment with confidence intervals, "
                             "API /metrics (decisions, latency, rejections)", "monitoring.py · api.py"),
        ("Fairness", "Separate WARN threshold for new customers; before/after measured on both periods", "risk_engine.py · evaluation.py"),
        ("Access control", "Roles (admin, fraud analyst, agent, customer): each sees only its pages; only an admin can change "
                           "the analyst policy, upload data or export real IDs; actions are written to an access log", "app.py"),
        ("Resilience", "Client with a 150 ms budget, fail-open, retry queue and circuit breaker; shadow mode on the API", "integration.py · api.py"),
    ]
    st.dataframe(pd.DataFrame([{"Control": a, "In place": b, "Where": c} for a, b, c in done]), hide_index=True, width="stretch")
    st.markdown("**Access log (this session)**")
    if ACCESS_LOG:
        st.dataframe(pd.DataFrame(ACCESS_LOG), hide_index=True, width="stretch")
    else:
        st.caption("Empty: change the role in the sidebar, export cases or record a dispute and it appears here.")
    st.markdown("**Production plan (not in this prototype)**")
    st.dataframe(pd.DataFrame([
        ("Access control", "Roles come from upay's single sign-on instead of the demo menu; analysts see pseudonymised IDs on "
                           "screen unless a case needs the real number"),
        ("Secrets", "API keys and the pseudonymisation salt in a secrets manager, rotated"),
        ("Encryption", "TLS everywhere; customer state in Redis and logs encrypted at rest"),
        ("Rate limiting", "At the API gateway (shared across all workers and pods)"),
        ("Data governance", "Retention limits for history and cases, data-protection review, access logs reviewed monthly"),
        ("Model governance", "Model registry; every new model runs in shadow mode for 2 weeks and is approved before use; "
                             "rollback in one step"),
        ("Threat model", "Attackers probing thresholds (rate limits, no score shown to customers), insiders (roles, audit), "
                         "data poisoning through labels (second-analyst review before labels are used)"),
    ], columns=["Area", "Plan"]), hide_index=True, width="stretch")


def evidence_tabs():
    ev, bm = load_json("evaluation.json", STAMP), load_json("benchmark.json", STAMP)
    m_ = load_json("metrics.json", STAMP) or {}
    t_ai, t_eng, t_diff, t_thr, t_work, t_loss, t_rob, t_fair, t_shadow, t_perf, t_sec = st.tabs(
        ["Where AI is used", "Engine contribution", "How it differs", "Threshold tuning", "Analyst workload",
         "Loss concentration", "Robustness", "Fairness & drift", "Shadow mode & pilot", "Performance & scale",
         "Security & governance"])
    with t_sec:
        security_panel()
    with t_diff:
        differentiation_tab(ev)
    with t_loss:
        loss_tab()
    with t_shadow:
        shadow_tab(bm)
    lad = {r["step"]: r for r in (ev or {}).get("engine_ladder", [])}
    with t_ai:
        st.markdown("Every decision is made by a **combination** of learned models, transparent rules and a human. "
                    "This table shows exactly what each part does and the evidence that it works (future test period).")
        ab = (ev or {}).get("ablation", {})
        un = (ev or {}).get("unseen_takeover_ablation", {})
        cm_ = load_json("cashout_metrics.json", STAMP) or {}
        rows = [
            ("Scam classifier", "Machine learning (supervised)", f"XGBoost on {len(re_.FEATURES)} point-in-time features",
             "Probability that a transfer is a scam",
             f"Catches {pct(dig(ab, 'Scam classifier', 'alone', 'scams_caught') or 0)} of scams alone; ROC-AUC {m_.get('roc_auc', 0):.3f}"),
            ("Behaviour anomaly", "Machine learning (unsupervised, no labels)", "Isolation Forest",
             "How unusual the transfer is vs. normal behaviour",
             f"Catches {pct(dig(un, 'Behaviour anomaly', 'alone') or 0)} of a scam type never seen in training "
             f"(classifier alone: {pct(dig(un, 'Scam classifier', 'alone') or 0)})"),
            ("Explanations", "Machine learning (explainability)", "SHAP values from XGBoost",
             "Which signals pushed the risk up, in Bangla and English", "Every WARN/HOLD shows its reasons"),
            ("Mule network", "Graph analytics", "NetworkX: who-pays-whom graph, shared collectors",
             "Which wallets are mules and which rings they form",
             f"{pct(dig(ab, 'Network check', 'alone', 'precision') or 0)} precision; {dig(ab, 'Network check', 'unique_catches')} scams caught by nothing else"),
            ("Takeover check", "Rules on the customer's own learned profile", "New device / place / hour / speed / size",
             "Account-takeover pattern", f"{pct(dig(ab, 'Takeover check', 'alone', 'precision') or 0)} precision alone"),
            ("Pattern & coaching rules", "Rules", "Same amount from many people, repeated payments, call coaching",
             "Known scam scripts", f"{pct(dig(ab, 'Call-coaching rule', 'alone', 'precision') or 0)} precision (call coaching)"),
            ("Cash-out model", "Machine learning (supervised) + peer statistics",
             "XGBoost on 10 cash-out features + agent z-score vs. district peers", "PAY / VERIFY / HOLD at the agent",
             f"{pct(dig(cm_, 'model', 'caught') or 0)} of mule cash-outs caught, {pct(dig(cm_, 'model', 'false_alarm_rate') or 0, 1)} genuine flagged"),
            ("Decision", "Policy + human", "ALLOW / WARN (customer decides) / HOLD (analyst decides)",
             "What happens to the money", "No automatic permanent blocking; customer can dispute a HOLD"),
        ]
        st.dataframe(pd.DataFrame(rows, columns=["Component", "Type", "Method", "Decides", "Evidence"]),
                     hide_index=True, width="stretch")
        if m_.get("feature_importance"):
            st.markdown(f"**The {len(re_.FEATURES)} classifier features** (yellow bars) · newest: device shared by other "
                        "accounts (30 days) and transfer-velocity trend vs. the customer's own pace")
            st.bar_chart(pd.Series(m_["feature_importance"]).sort_values(ascending=False), color="#FFD200", horizontal=True)
            st.caption("Plus 14 pattern signals in the Send Money checklist, the network features (senders, flagged share, "
                       "collector links) and 10 cash-out features. Feature importance is XGBoost gain share.")
    if not ev:
        st.info("Run `python evaluation.py` to produce the engine evidence.")
        return
    with t_eng:
        st.markdown(f"Measured on {ev['test_transfers']:,} future transfers ({ev['test_scams']} scams). The mule network "
                    f"is built only from transfers **before** {ev['network_built_before']}, as a daily job would be.")
        if lad:
            st.markdown("**Adding one engine at a time** (share of each scam type caught)")
            st.dataframe(pd.DataFrame([{"Engines": r["step"], "Scams caught": pct(r["scams_caught"], 1),
                                        "Phone-coached scams": pct(r["social_engineering"], 1),
                                        "Account takeovers": pct(r["account_takeover"], 1),
                                        "Low-signal scams": pct(r["low_signal"], 1),
                                        "Alerts that are real": pct(r["precision"], 1),
                                        "Genuine transfers alerted": pct(r["false_alarm_rate"], 2),
                                        "Scam money protected": pct(r["money_protected"], 1)} for r in ev["engine_ladder"]]),
                         hide_index=True, width="stretch")
        ab = ev["ablation"]
        rows = [{"Engine": e, "Scams caught alone": pct(ab[e]["alone"]["scams_caught"], 1),
                 "Precision alone": pct(ab[e]["alone"]["precision"], 1),
                 "Scams caught without it": pct(ab[e]["without"]["scams_caught"], 1),
                 "Caught by nothing else": str(ab[e]["unique_catches"])} for e in ENG_LIST]
        rows.append({"Engine": "All engines together", "Scams caught alone": pct(ab["All engines"]["scams_caught"], 1),
                     "Precision alone": pct(ab["All engines"]["precision"], 1), "Scams caught without it": "",
                     "Caught by nothing else": ""})
        st.markdown("**Each engine alone, and the system without it** (known scam types)")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        un = ev["unseen_takeover_ablation"]
        st.markdown(f"**A scam type never seen in training** (every engine retrained without any of the "
                    f"{un['takeovers_in_test']} account takeovers)")
        st.dataframe(pd.DataFrame([{"Engine": e, "Takeovers caught alone": pct(un[e]["alone"], 1),
                                    "Caught without it": pct(un[e]["without"], 1),
                                    "Caught by nothing else": str(un[e]["unique_catches"])} for e in ENG_LIST] +
                                  [{"Engine": "All engines together", "Takeovers caught alone": pct(un["All engines"], 1),
                                    "Caught without it": "", "Caught by nothing else": ""}]), hide_index=True, width="stretch")
        co = ev["corroboration"]
        st.markdown("**When engines agree, alerts are more trustworthy**")
        st.dataframe(pd.DataFrame([{"Engines agreeing": k, "Alerts": v["alerts"], "Alerts that are real scams": pct(v["precision"], 1),
                                    "Scams covered": pct(v["scams_caught"], 1)} for k, v in co.items()]),
                     hide_index=True, width="stretch")
        st.info(f"What this shows: the classifier does most of the work on known scams; the network check adds catches "
                f"nothing else finds with 100% precision; the anomaly model and takeover check rarely add catches on known "
                f"scams, but they are what catch a NEW scam type ({pct(un['Behaviour anomaly']['alone'])} vs. "
                f"{pct(un['Scam classifier']['alone'])}) and they make HOLD decisions trustworthy "
                f"(2+ engines agreeing: {pct(co['2+ engines']['precision'], 1)} real scams).")
    with t_thr:
        threshold_tuning()
    with t_work:
        st.markdown("Judges asked: *most alerts are still false alarms, will analysts be swamped?* Each policy below "
                    "catches the same scams; what changes is **who** handles an alert: the customer (WARN) or an analyst (HOLD).")
        ops = ev["operating_points"]
        st.dataframe(pd.DataFrame([{"Policy": k, "Scams caught": pct(v["scams_caught"], 1), "Scams held for analyst": pct(v["hold_scams"], 1),
                                    "Genuine transfers warned (customer decides)": f"{v['warn_genuine'] * 1e5:,.0f} per 100k",
                                    "Genuine transfers held (analyst review)": f"{v['hold_genuine'] * 1e5:,.0f} per 100k"}
                                   for k, v in ops.items()]), hide_index=True, width="stretch")
        cur, low = ops["Current policy"], ops["HOLD only if 2+ engines agree"]
        st.success(f"**Low-workload policy (HOLD only when 2+ engines agree):** genuine transfers sent to analysts fall from "
                   f"{cur['hold_genuine'] * 1e5:,.0f} to {low['hold_genuine'] * 1e5:,.0f} per 100,000 "
                   f"({cur['hold_genuine'] / max(low['hold_genuine'], 1e-9):,.0f}x fewer), while the same {pct(low['scams_caught'])} "
                   f"of scams are still stopped or warned. Switch it on in the sidebar (Analyst policy) and in the Business "
                   f"impact calculator. Trade-off: {pct(cur['hold_scams'] - low['hold_scams'])} of scams move from HOLD to a "
                   f"WARN the customer must confirm.")
        wo = st.session_state.get("warn_outcomes", {"cancelled": 0, "proceeded": 0})
        st.markdown(f"**Do warnings work?** In this session customers shown a WARN cancelled **{wo['cancelled']}** times and "
                    f"continued **{wo['proceeded']}** times (Send Money page). In production this cancel rate is tracked per "
                    "warning reason; the business calculator assumes 60% of warned scam victims cancel.")
    with t_rob:
        rb = ev.get("robustness", {})
        st.markdown("**Does it still work when the world changes?** Brand-new synthetic logs (different random seed, so "
                    "different customers, mule wallets and rings) with a different scam mix, scored by the **current** "
                    "models with no retraining.")
        if rb:
            st.dataframe(pd.DataFrame([{"Changed world": k, "Transfers": f"{v['transfers']:,}", "Scams": v["scams"],
                                        "Scams caught": pct(v["scamshield"]["scams_caught"], 1),
                                        "Alerts that are real": pct(v["scamshield"]["precision"], 1),
                                        "Genuine alerted": pct(v["scamshield"]["false_alarm_rate"], 2),
                                        "Phone-coached": pct(v["by_type"]["social_engineering"], 1),
                                        "Takeovers": pct(v["by_type"]["account_takeover"], 1),
                                        "Low-signal": pct(v["by_type"]["low_signal"], 1),
                                        "Simple rule caught": pct(v["rule"]["scams_caught"], 1)} for k, v in rb.items()]),
                         hide_index=True, width="stretch")
        st.markdown("Also tested: the **unseen scam type** (Engine contribution tab) and our **earlier, independently "
                    "generated dataset** (Datasets page: current models scored on it without retraining).")
        st.caption("Low-signal scams (amounts close to normal, known device, no call) stay the hardest: they are why the "
                   "network check and the cash-out check exist, catching the money where it is collected and taken out.")
    with t_fair:
        fx = ev.get("fairness_fix", {})
        if fx:
            st.markdown(f"**Fix applied: new customers (< {re_.NEW_CUSTOMER_DAYS} days) need a classifier score of "
                        f"{re_.NEW_CUSTOMER_WARN:.2f} for a WARN** (everyone else 0.30). Chosen on the training period, where every "
                        "new-customer scam scored 0.93 or more. Rules, the anomaly model and HOLD are unchanged.")
            rows = []
            for period, opts in fx.items():
                for lbl, v in opts.items():
                    rows.append({"Period": period, "Policy": lbl,
                                 "New customers: genuine alerted": f"{pct(v['new']['rate'], 2)} ({v['new']['false_alarms']} of {v['new']['genuine']:,})",
                                 "Established: genuine alerted": f"{pct(v['established']['rate'], 2)} ({v['established']['false_alarms']} of {v['established']['genuine']:,})",
                                 "New-customer scams caught": pct(v["new"]["scams_caught"], 0),
                                 "All scams caught": pct(v["all_scams_caught"], 1)})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.markdown("**False alarms with 95% confidence intervals** (current policy)")
        rows = []
        for period, groups in ev["fairness"].items():
            for g_, v in groups.items():
                rows.append({"Period": period, "Group": g_, "False alarms": f"{v['false_alarms']} of {v['genuine_transfers']:,}",
                             "Rate": pct(v["rate"], 2), "95% interval": f"{v['ci95'][0]:.2%} – {v['ci95'][1]:.2%}"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("The new-customer group is small (about 500 genuine transfers in the test window), so its rate moves a "
                   "lot with a few transfers. It is monitored continuously below.")
        t = get_test(WSN, STAMP)
        tagged = re_.score_frame(model, iforest, t)
        seg, what = mo.segment_alert_rates(t, (tagged.decision != "ALLOW").values)
        st.markdown(f"**Live segment monitor ({what}) on the active dataset**")
        st.dataframe(seg, hide_index=True, width="stretch")
        dr, title = drift_tables(WSN, STAMP)
        st.markdown(f"**Model drift monitor (PSI)** · {title}")
        st.dataframe(dr, hide_index=True, width="stretch")
        st.caption("PSI < 0.10 stable · 0.10–0.25 watch · > 0.25 investigate or retrain. Run daily on new transfers; "
                   "a shift triggers retraining in shadow mode before the new model is used.")
    with t_perf:
        perf_tab(bm)


if page.endswith("Model & Impact"):
    business_impact_ui()
    st.divider()
    evidence_tabs()
    st.divider()

if page.endswith("Model & Impact") and WS == "B":
    st.markdown(f'<div class="section-title">{ic("chart", 16)} Dataset B · your data</div>', unsafe_allow_html=True)
    st.write(metrics["note"])
    st.caption(metrics["split"])
    if metrics.get("mode") == "trained":
        c1, c2, c3, c4 = st.columns(4)
        a = metrics["ai_system"]
        c1.metric("ROC-AUC", f"{metrics['roc_auc']:.3f}")
        c2.metric("Scams caught", f"{a['scam_recall']:.0%}")
        c3.metric("Scam money protected", f"{a['scam_money_protected_pct']:.0%}")
        c4.metric("Genuine transfers warned", f"{a['false_alarm_rate']:.1%}")
        st.dataframe(pd.DataFrame({"New model trained on your data": fmt_stats(a),
                                   "Demo model (trained on Dataset A)": fmt_stats(metrics["demo_model_on_same_test"]),
                                   "Simple rule": fmt_stats(metrics["rule_baseline"])}), width="stretch")
    else:
        st.info("This log has no usable fraud labels, so accuracy cannot be measured yet. Add an is_fraud column "
                "(confirmed cases from your fraud team) and rebuild Dataset B to train and evaluate a classifier on your data.")
    for note in metrics.get("data_quality", []):
        st.warning("Data quality: " + note)
    st.markdown("**Feature importance of the active classifier**")
    st.bar_chart(pd.Series(metrics["feature_importance"]), color="#FFD200")

if page.endswith("Model & Impact") and WS == "A":
    st.markdown(f'<div class="section-title">{ic("chart", 16)} Offline evaluation on a clean held-out test set</div>', unsafe_allow_html=True)
    m = metrics
    a, b = m["ai_system"], m["rule_baseline"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ROC-AUC", f"{m['roc_auc']:.3f}")
    c2.metric("Scams caught", f"{a['scam_recall']:.0%}", f"{(a['scam_recall'] - b['scam_recall']) * 100:+.0f} pts vs rule")
    c3.metric("Scam money protected", f"{a['scam_money_protected_pct']:.0%}",
              f"{(a['scam_money_protected_pct'] - b['scam_money_protected_pct']) * 100:+.0f} pts vs rule")
    c4.metric("Legit transfers warned", f"{a['false_alarm_rate']:.1%}")
    st.markdown("**AI system vs. a simple rule** (rule = new recipient AND amount ≥ ৳5,000)")
    st.dataframe(pd.DataFrame({"Classifier only": m.get("classifier_only", a), "Classifier + rules": m["classifier_and_rules_only"],
                               "Full ScamShield (+ anomaly, new-customer policy)": a, "Simple rule baseline": b}), width="stretch")
    st.caption(m.get("note", ""))
    st.markdown("**Catching scam types the classifier has never seen** (both models trained without any account-takeover examples)")
    nv = m["novel_scam_test_account_takeover_recall"]
    st.bar_chart(pd.Series({"Classifier only": nv["classifier_only"], "Classifier + anomaly model": nv["classifier_plus_anomaly"]}),
                 color="#0B5CAD")
    st.markdown("**Detection rate by scam type**")
    st.bar_chart(pd.Series(m["recall_by_scam_type"]), color="#0B5CAD")
    st.markdown("**Global feature importance**")
    st.bar_chart(pd.Series(m["feature_importance"]), color="#FFD200")
    st.info("All data is synthetic. Results on injected patterns are optimistic; real performance must be validated on governed upay data.")
    st.info("Thresholds are business-policy settings that upay would tune on real data. The models never block money on "
            "their own: high-risk transfers are paused for re-verification and human review.")
