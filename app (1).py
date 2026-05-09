# -*- coding: utf-8 -*-
# ============================================================
# MLB STRIKEOUT PROP ENGINE — ONE FILE — v9.6 CLEAN MERGE
# Refresh first, then save official before-game snapshot
# Real lines only. No fake prop lines.
# Google Drive persistent logs + grading + learning.
# ============================================================

import os
import json
import math
import difflib
import io
import requests
import numpy as np
import pandas as pd
import streamlit as st
from math import exp, factorial
from datetime import datetime, timedelta

try:
    import pytz
except Exception:
    pytz = None

# =========================
# STORAGE
# =========================
DRIVE_DIR = "/content/drive/MyDrive/mlb_engine"
LOCAL_DIR = "mlb_engine"

try:
    from google.colab import drive
    if not os.path.exists("/content/drive/MyDrive"):
        drive.mount("/content/drive", force_remount=False)
    os.makedirs(DRIVE_DIR, exist_ok=True)
    STORAGE_DIR = DRIVE_DIR
except Exception:
    os.makedirs(LOCAL_DIR, exist_ok=True)
    STORAGE_DIR = LOCAL_DIR

PICK_LOG = os.path.join(STORAGE_DIR, "auto_pick_log.json")
RESULT_LOG = os.path.join(STORAGE_DIR, "auto_result_log.json")
LEARN_FILE = os.path.join(STORAGE_DIR, "pitcher_learning.json")
CLV_FILE = os.path.join(STORAGE_DIR, "clv_tracker.json")
REQUEST_LOG_FILE = os.path.join(STORAGE_DIR, "request_log.json")
SIGNAL_TRACKING_FILE = os.path.join(STORAGE_DIR, "signal_tracking.json")
LONG_BACKTEST_FILE = os.path.join(STORAGE_DIR, "long_backtest_rows.json")
LINEUP_CACHE_FILE = os.path.join(STORAGE_DIR, "locked_lineup_cache.json")
LINE_HISTORY_FILE = os.path.join(STORAGE_DIR, "line_history.json")

MLB_BASE = "https://statsapi.mlb.com/api/v1"
MLB_LIVE = "https://statsapi.mlb.com/api/v1.1"
ODDS_BASE = "https://api.the-odds-api.com/v4"
PRIZEPICKS_URL = "https://api.prizepicks.com/projections"
UNDERDOG_URLS = [
    "https://api.underdogfantasy.com/beta/v5/over_under_lines",
    "https://api.underdogfantasy.com/v1/over_under_lines",
]
SPORTSGAMEODDS_BASE = "https://api.sportsgameodds.com/v2"
OPTICODDS_BASE = "https://api.opticodds.com/api/v3"

SPORTSBOOK_PITCHER_K_MARKETS = [
    "pitcher_strikeouts",
    "player_pitcher_strikeouts",
    "pitcher_strikeouts_alternate",
    "player_pitcher_strikeouts_alternate",
    "pitcher_strikeouts_over_under",
]

LEAGUE_AVG_K = 0.225
DEFAULT_BF = 22.0
MIN_BETTABLE_GAP_KS = 0.70
MIN_ELITE_DATA_SCORE = 88
MIN_ELITE_NO_VIG_EDGE = 6.0
MIN_MATCH_SCORE_STRICT = 0.86

# =========================
# v9.6 CLEAN MERGE SAFETY LOCK SETTINGS
# =========================
# These make the model slower, stricter, and safer.
MIN_OFFICIAL_SAVE_SCORE = 75
MIN_BETTABLE_SCORE = 80
MIN_BETTABLE_PROB = 0.60
MIN_BETTABLE_EV = 0.03
MIN_CONFIRMED_LINEUP_SCORE = 88
MAX_RECOMMENDED_KELLY = 0.03
LEARNING_MIN_PRIOR_STARTS = 3
LEARNING_RATE = 0.06
LEARNING_SCALE_MIN = 0.88
LEARNING_SCALE_MAX = 1.12


LEAGUE_AVG_WHIFF_BY_PITCH_TYPE = {
    "FF": 0.22, "SI": 0.17, "FC": 0.20, "SL": 0.34, "CU": 0.31,
    "KC": 0.31, "CH": 0.31, "FS": 0.34, "ST": 0.36, "SV": 0.30,
    "KN": 0.25, "EP": 0.15, "UNK": 0.25
}

def get_secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

ODDS_API_KEY = get_secret("ODDS_API_KEY", "")
SPORTSGAMEODDS_API_KEY = get_secret("SPORTSGAMEODDS_API_KEY", "")
OPTICODDS_API_KEY = get_secret("OPTICODDS_API_KEY", "")

# =========================
# PAGE CONFIG + UI
# =========================
st.set_page_config(
    page_title="MLB K Prop Engine — Refresh Then Save",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.stApp {background: radial-gradient(circle at top,#260000 0%,#090909 42%,#020202 100%); color:#fff;}
.block-container {padding-top:1.1rem; max-width:1550px;}
h1,h2,h3 {color:#fff;}
[data-testid="stMetric"] {
    background:linear-gradient(145deg,#111,#1b0000);
    border:1px solid rgba(255,45,45,.36);
    border-radius:18px;
    padding:16px;
    box-shadow:0 0 18px rgba(255,0,0,.18);
}
.hero-panel {
    background:linear-gradient(135deg,rgba(50,0,0,.92),rgba(8,8,8,.96));
    border:1px solid rgba(255,70,70,.42);
    border-radius:26px;
    padding:22px;
    box-shadow:0 0 34px rgba(255,0,0,.18);
    margin-bottom:18px;
}
.pick-card {
    background:linear-gradient(145deg,#101010,#180000);
    border:1px solid rgba(255,45,45,.36);
    border-radius:22px;
    padding:20px;
    box-shadow:0 0 26px rgba(255,0,0,.17);
    margin-bottom:16px;
}
.green-card {
    background:linear-gradient(145deg,#001b0e,#07110b);
    border:1px solid rgba(0,255,135,.48);
    border-radius:22px;
    padding:22px;
    box-shadow:0 0 28px rgba(0,255,135,.22);
    margin-bottom:16px;
}
.warn-card {
    background:linear-gradient(145deg,#1c1200,#0f0a00);
    border:1px solid rgba(255,190,60,.45);
    border-radius:22px;
    padding:20px;
    box-shadow:0 0 24px rgba(255,190,60,.13);
    margin-bottom:16px;
}
.small-muted {color:#bdbdbd; font-size:13px;}
.big-title {font-size:42px; font-weight:950; color:#fff; letter-spacing:-1px;}
.sub-title {color:#d3d3d3; font-size:15px; margin-top:-6px;}
.player-name {font-size:23px; font-weight:900; color:#fff;}
.big-number {font-size:42px; font-weight:950; line-height:1.05;}
.green {color:#31e84f;}
.orange {color:#ffbe3c;}
.red {color:#ff5f5f;}
.badge {
    display:inline-block;
    padding:6px 12px;
    border-radius:999px;
    background:#2c0000;
    border:1px solid rgba(255,95,95,.48);
    color:#ffc4c4;
    font-weight:800;
    margin:3px 4px 3px 0;
}
.good-badge {background:#002916;border-color:rgba(0,255,135,.55);color:#b5ffd9;}
.yellow-badge {background:#2b1d00;border-color:rgba(255,210,70,.55);color:#ffe2a1;}
.red-badge {background:#2b0000;border-color:rgba(255,75,75,.55);color:#ffc0c0;}
.kpi-strip {display:grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap:12px; margin:12px 0 18px 0;}
.kpi-box {background:linear-gradient(145deg,#101010,#190000);border:1px solid rgba(255,70,70,.30);border-radius:18px;padding:14px;min-height:92px;}
.kpi-label {font-size:12px;color:#aaa;font-weight:800;letter-spacing:.04em;text-transform:uppercase;}
.kpi-value {font-size:26px;font-weight:900;color:#fff;margin-top:6px;}
.kpi-sub {font-size:12px;color:#cfcfcf;margin-top:5px;}
.progress-wrap {width:100%;height:14px;border-radius:99px;background:#050505;overflow:hidden;border:1px solid rgba(255,255,255,.08);}
.progress-green {height:100%;border-radius:99px;background:linear-gradient(90deg,#00d66b,#46ff9a);}
.progress-orange {height:100%;border-radius:99px;background:linear-gradient(90deg,#ff8c00,#ffbf30);}
.progress-red {height:100%;border-radius:99px;background:linear-gradient(90deg,#ff2d2d,#ff7272);}
.mini-k-bars {display:flex;align-items:flex-end;gap:10px;min-height:76px;margin-top:4px;overflow-x:auto;}
.mini-k-bar-wrap {display:inline-flex;flex-direction:column;align-items:center;justify-content:flex-end;min-width:18px;}
.mini-k-bar {display:block;width:17px;background:#31e84f;border-radius:3px;box-shadow:0 0 10px rgba(49,232,79,.18);}
.mini-k-label {font-size:12px;color:#bdbdbd;margin-top:3px;}
.hr-soft {border-top:1px solid rgba(255,255,255,.12); margin:14px 0;}
.section-title-pro {margin-top:22px;margin-bottom:10px;font-size:24px;font-weight:950;color:#fff;border-left:5px solid #ff3b3b;padding-left:12px;}
.stTabs [data-baseweb="tab"] {color:#b8c3cf;font-weight:850;}
.stTabs [aria-selected="true"] {color:#31e84f!important;border-bottom:3px solid #31e84f;}
@media (max-width: 1100px) {.kpi-strip {grid-template-columns: repeat(2, minmax(0, 1fr));}}
</style>
""", unsafe_allow_html=True)

# =========================
# HELPERS
# =========================
def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def california_now():
    if pytz:
        return datetime.now(pytz.timezone("America/Los_Angeles"))
    return datetime.utcnow() - timedelta(hours=7)

def safe_float(x, default=None):
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default

def safe_int(x, default=None):
    try:
        if x is None or x == "":
            return default
        return int(float(x))
    except Exception:
        return default

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def log_source_request(source, status, message=""):
    rows = load_json(REQUEST_LOG_FILE, [])
    rows.append({
        "time": now_iso(),
        "source": str(source)[:180],
        "status": str(status)[:80],
        "message": str(message)[:350]
    })
    save_json(REQUEST_LOG_FILE, rows[-500:])

def normalize_name(name):
    s = str(name or "").lower().strip()
    for ch in [".", ",", "'", "-", "_", " jr", " sr", " ii", " iii", " iv"]:
        s = s.replace(ch, " ")
    return " ".join(s.split())

def name_score(a, b):
    a_norm, b_norm = normalize_name(a), normalize_name(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    if a_norm in b_norm or b_norm in a_norm:
        return 0.94
    a_parts, b_parts = a_norm.split(), b_norm.split()
    base = 0.76 if a_parts and b_parts and a_parts[-1] == b_parts[-1] else 0.0
    return max(base, difflib.SequenceMatcher(None, a_norm, b_norm).ratio())

def is_pitcher_k_text(text):
    t = str(text or "").lower()
    return (
        "strikeout" in t
        or "strike out" in t
        or "pitcher k" in t
        or t in ["ks", "k", "pitcher strikeouts"]
    ) and not any(bad in t for bad in ["batter", "hitter"])

@st.cache_data(ttl=300, show_spinner=False)
def safe_get_json(url, params=None, timeout=14, headers=None):
    try:
        h = {
            "User-Agent": "Mozilla/5.0 MLBKPropEngine/refresh-save-build",
            "Accept": "application/json,text/plain,*/*",
        }
        if headers:
            h.update(headers)
        r = requests.get(url, params=params, timeout=timeout, headers=h)
        if r.status_code != 200:
            log_source_request(url, f"HTTP {r.status_code}", r.text[:250])
            return None
        try:
            return r.json()
        except Exception as e:
            log_source_request(url, "BAD_JSON", str(e))
            return None
    except Exception as e:
        log_source_request(url, "REQUEST_ERROR", str(e))
        return None

def baseball_ip_to_float(ip):
    if ip is None:
        return None
    try:
        s = str(ip)
        if "." not in s:
            return float(s)
        whole, frac = s.split(".", 1)
        outs = int(frac[:1]) if frac else 0
        if outs not in [0, 1, 2]:
            return float(s)
        return int(whole) + outs / 3
    except Exception:
        return None

def get_first_stat_split(data):
    if not isinstance(data, dict):
        return None
    stats = data.get("stats") or []
    if not stats or not isinstance(stats[0], dict):
        return None
    splits = stats[0].get("splits") or []
    if not splits or not isinstance(splits[0], dict):
        return None
    return splits[0]

def flatten_json(obj):
    items = []
    if isinstance(obj, dict):
        items.append(obj)
        for v in obj.values():
            items.extend(flatten_json(v))
    elif isinstance(obj, list):
        for x in obj:
            items.extend(flatten_json(x))
    return items

def first_value(d, keys):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in [None, ""]:
            return d[k]
    return None

# =========================
# BETTING MATH
# =========================
def poisson_over_probability(lam, line):
    lam = safe_float(lam, 0)
    line = safe_float(line)
    if line is None or lam <= 0:
        return None
    k = int(math.floor(line))
    prob_under_or_equal = sum((lam ** i) * exp(-lam) / factorial(i) for i in range(k + 1))
    return float(clamp(1 - prob_under_or_equal, 0.001, 0.999))

def american_to_implied(price):
    price = safe_float(price)
    if price is None:
        return None
    if price > 0:
        return 100 / (price + 100)
    return abs(price) / (abs(price) + 100)

def decimal_odds(odds):
    odds = safe_float(odds)
    if odds is None:
        return None
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / abs(odds)

def expected_value(prob, odds):
    dec = decimal_odds(odds)
    if prob is None or dec is None:
        return None
    return (prob * (dec - 1)) - (1 - prob)

def kelly_fraction(prob, odds):
    dec = decimal_odds(odds)
    if prob is None or dec is None:
        return 0.0
    b = dec - 1
    q = 1 - prob
    if b <= 0:
        return 0.0
    return float(clamp(((b * prob) - q) / b, 0, 0.25))

def paired_no_vig_probability(rows, target_row):
    price = safe_float(target_row.get("Price"))
    listed = american_to_implied(price)
    if listed is None:
        return None
    provider = str(target_row.get("Provider", target_row.get("Source", ""))).lower()
    line = safe_float(target_row.get("Line"))
    side = str(target_row.get("Side", "")).lower()
    if line is None or not side:
        return listed
    want = "under" if "over" in side else "over" if "under" in side else None
    if not want:
        return listed
    opposite = None
    for r in rows or []:
        if safe_float(r.get("Line")) != line:
            continue
        if str(r.get("Provider", r.get("Source", ""))).lower() != provider:
            continue
        if want in str(r.get("Side", "")).lower():
            opposite = american_to_implied(r.get("Price"))
            break
    if opposite is None:
        return listed
    denom = listed + opposite
    return listed / denom if denom > 0 else listed

# =========================
# LEARNING / CLV / LOGGING
# =========================
def load_learning():
    return load_json(LEARN_FILE, {})

def apply_learning(pid, lam):
    data = load_learning()
    scale = safe_float(data.get(str(pid)), 1.0) or 1.0
    return lam * scale, scale

def pitcher_learning_sample_count(pid):
    """Count previous graded official snapshots for this pitcher before changing learning scale."""
    results = load_json(RESULT_LOG, [])
    return sum(
        1 for r in results
        if str(r.get("pitcher_id")) == str(pid)
        and r.get("actual") is not None
        and r.get("projection") is not None
    )

def update_learning(pid, projected, actual):
    """
    Safer learning:
    - does NOT move from one random outcome
    - waits for prior samples
    - uses a smaller learning rate
    - caps pitcher scale tighter
    """
    data = load_learning()
    projected = safe_float(projected, 0) or 0
    actual = safe_float(actual)
    current = safe_float(data.get(str(pid)), 1.0) or 1.0

    if actual is None or projected <= 0:
        return current

    prior_samples = pitcher_learning_sample_count(pid)
    if prior_samples < LEARNING_MIN_PRIOR_STARTS:
        data[str(pid)] = current
        save_json(LEARN_FILE, data)
        return current

    err = clamp((actual - projected) / max(1.0, projected), -0.35, 0.35)
    new_scale = clamp(current * (1 + LEARNING_RATE * err), LEARNING_SCALE_MIN, LEARNING_SCALE_MAX)
    data[str(pid)] = new_scale
    save_json(LEARN_FILE, data)
    return new_scale

def update_clv_snapshot(player_name, source, line):
    if line is None:
        return None
    data = load_json(CLV_FILE, {})
    today = california_now().strftime("%Y-%m-%d")
    key = f"{today}_{normalize_name(player_name)}_{source}"
    old = data.get(key)
    line = float(line)
    if not old:
        data[key] = {
            "player": player_name,
            "source": source,
            "open_line": line,
            "latest_line": line,
            "last_updated": now_iso()
        }
        save_json(CLV_FILE, data)
        return 0.0
    open_line = safe_float(old.get("open_line"))
    old["latest_line"] = line
    old["last_updated"] = now_iso()
    data[key] = old
    save_json(CLV_FILE, data)
    if open_line is None:
        return 0.0
    return round(line - open_line, 2)

def track_line_delta(player_name, source, line):
    if line is None:
        return None
    hist = load_json(LINE_HISTORY_FILE, {})
    key = f"{normalize_name(player_name)}_{source}"
    rows = hist.get(key, [])
    rows.append({"t": now_iso(), "line": safe_float(line)})
    hist[key] = rows[-30:]
    save_json(LINE_HISTORY_FILE, hist)
    if len(hist[key]) < 2:
        return 0.0
    first = safe_float(hist[key][0].get("line"))
    last = safe_float(hist[key][-1].get("line"))
    if first is None or last is None:
        return None
    return round(last - first, 2)

def log_long_backtest_row(pick):
    rows = load_json(LONG_BACKTEST_FILE, [])
    pid = pick.get("pick_id")
    ids = set(r.get("pick_id") for r in rows)
    if pid not in ids:
        slim = {k: v for k, v in pick.items() if k not in ["prop_rows", "lineup_rows", "pitch_type_rows"]}
        rows.append(slim)
        save_json(LONG_BACKTEST_FILE, rows[-20000:])

def build_model_calibration_profile(results):
    finished = [r for r in results if r.get("actual") is not None and r.get("projection") is not None]
    if not finished:
        return {"samples": 0, "mae": None, "bias": None, "hit_rate": None, "quality_score": 50}
    errs = [safe_float(r.get("actual"), 0) - safe_float(r.get("projection"), 0) for r in finished]
    mae = float(np.mean([abs(e) for e in errs]))
    bias = float(np.mean(errs))
    wins = [1 if r.get("win") else 0 for r in finished if r.get("win") is not None]
    hit_rate = float(np.mean(wins)) if wins else None
    quality = 50
    quality += min(len(finished), 50) * 0.6
    quality -= min(mae, 3) * 8
    quality -= abs(bias) * 4
    quality = int(clamp(quality, 0, 100))
    return {
        "samples": len(finished),
        "mae": round(mae, 2),
        "bias": round(bias, 2),
        "hit_rate": hit_rate,
        "quality_score": quality
    }

def apply_calibration_adjustment(k_rate, calibration_profile, enabled=True):
    if not enabled:
        return k_rate, "Calibration adjustment disabled"
    if not calibration_profile or calibration_profile.get("samples", 0) < 10:
        return k_rate, "Calibration sample too small; no adjustment"
    bias = safe_float(calibration_profile.get("bias"), 0) or 0
    factor = clamp(1 + (bias * 0.01), 0.96, 1.04)
    return clamp(k_rate * factor, 0.08, 0.50), f"Historical calibration adjustment x{factor:.3f}"

# =========================
# MLB DATA
# =========================
def target_dates(day_mode):
    now = california_now()
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    if day_mode == "Today":
        return [today]
    if day_mode == "Tomorrow":
        return [tomorrow]
    return [today, tomorrow]

@st.cache_data(ttl=300, show_spinner=False)
def get_schedule(date_str):
    return safe_get_json(
        f"{MLB_BASE}/schedule",
        params={"sportId": 1, "date": date_str, "hydrate": "probablePitcher,venue,team"}
    ) or {"dates": []}

def extract_probable_pitchers(date_str):
    sched = get_schedule(date_str)
    rows = []
    for d in sched.get("dates", []):
        for g in d.get("games", []):
            game_pk = g.get("gamePk")
            teams = g.get("teams", {})
            away = teams.get("away", {}).get("team", {})
            home = teams.get("home", {}).get("team", {})
            away_pp = teams.get("away", {}).get("probablePitcher")
            home_pp = teams.get("home", {}).get("probablePitcher")
            status = g.get("status", {}).get("abstractGameState", "Preview")
            game_time = g.get("gameDate", "")
            venue = g.get("venue", {}).get("name", "")

            if away_pp:
                rows.append({
                    "date": date_str,
                    "game_pk": game_pk,
                    "game_time": game_time,
                    "status": status,
                    "venue": venue,
                    "pitcher_id": away_pp.get("id"),
                    "pitcher": away_pp.get("fullName"),
                    "hand": away_pp.get("pitchHand", {}).get("code", "R"),
                    "team": away.get("abbreviation", away.get("name")),
                    "team_id": away.get("id"),
                    "opponent": home.get("abbreviation", home.get("name")),
                    "opp_team_id": home.get("id"),
                    "home_team": home.get("name"),
                    "away_team": away.get("name"),
                    "opp_side": "home",
                    "matchup": f"{away.get('abbreviation', away.get('name'))} @ {home.get('abbreviation', home.get('name'))}",
                    "pitcher_confirmed": True
                })
            if home_pp:
                rows.append({
                    "date": date_str,
                    "game_pk": game_pk,
                    "game_time": game_time,
                    "status": status,
                    "venue": venue,
                    "pitcher_id": home_pp.get("id"),
                    "pitcher": home_pp.get("fullName"),
                    "hand": home_pp.get("pitchHand", {}).get("code", "R"),
                    "team": home.get("abbreviation", home.get("name")),
                    "team_id": home.get("id"),
                    "opponent": away.get("abbreviation", away.get("name")),
                    "opp_team_id": away.get("id"),
                    "home_team": home.get("name"),
                    "away_team": away.get("name"),
                    "opp_side": "away",
                    "matchup": f"{away.get('abbreviation', away.get('name'))} @ {home.get('abbreviation', home.get('name'))}",
                    "pitcher_confirmed": True
                })
    return rows

def get_pitcher_profile(pid):
    data = safe_get_json(
        f"{MLB_BASE}/people/{pid}/stats",
        params={"stats": "season", "group": "pitching"}
    )
    default = {"Pitcher K%": LEAGUE_AVG_K, "BF": 0, "SO": 0, "AVG IP": None, "K/9": None, "source": "Fallback league avg"}
    try:
        split = get_first_stat_split(data)
        if not split:
            return default
        stat = split.get("stat", {})
        ip = baseball_ip_to_float(stat.get("inningsPitched"))
        so = safe_float(stat.get("strikeOuts"), 0) or 0
        bf = safe_float(stat.get("battersFaced"), 0) or 0
        gs = safe_float(stat.get("gamesStarted"), None)
        gp = safe_float(stat.get("gamesPlayed"), 0) or 0
        starts = gs if gs and gs > 0 else gp
        k_pct = so / bf if bf > 0 else LEAGUE_AVG_K
        k9 = so / ip * 9 if ip and ip > 0 else None
        avg_ip = ip / starts if starts and starts > 0 and ip else None
        shrunk = ((k_pct * bf) + (LEAGUE_AVG_K * 150)) / max(bf + 150, 1)
        return {"Pitcher K%": float(clamp(shrunk, 0.08, 0.45)), "BF": bf, "SO": so, "AVG IP": avg_ip, "K/9": k9, "source": "Season K/BF with shrink"}
    except Exception:
        return default

def get_recent_logs(pid, n=12):
    data = safe_get_json(f"{MLB_BASE}/people/{pid}/stats", params={"stats": "gameLog", "group": "pitching"})
    rows = []
    try:
        splits = data["stats"][0]["splits"]
    except Exception:
        return rows
    for g in splits[:n]:
        stat = g.get("stat", {})
        ip_float = baseball_ip_to_float(stat.get("inningsPitched"))
        bf = safe_float(stat.get("battersFaced"))
        so = safe_float(stat.get("strikeOuts"))
        pitches = safe_float(stat.get("numberOfPitches"))
        rows.append({
            "Date": g.get("date"),
            "Opponent": g.get("opponent", {}).get("name"),
            "IP": stat.get("inningsPitched"),
            "IP_float": ip_float,
            "Ks": so,
            "BF": bf,
            "Pitches": pitches,
            "K%": None if not bf else round((so or 0) / bf * 100, 1)
        })
    return rows

def build_leash_model(recent_rows):
    """Projected batters faced with a safer pitcher-leash model."""
    if not recent_rows:
        return {
            "expected_bf": DEFAULT_BF,
            "ppb": 3.9,
            "recent_ip": 5.5,
            "last_10_ks": [],
            "leash_risk": "UNKNOWN",
            "source": "Default fallback"
        }

    df = pd.DataFrame(recent_rows)

    def mean_col(col, rows=None):
        try:
            x = df[col] if rows is None else df.head(rows)[col]
            x = pd.to_numeric(x, errors="coerce").dropna()
            return float(x.mean()) if len(x) else None
        except Exception:
            return None

    avg_bf_l10 = mean_col("BF")
    avg_bf_l5 = mean_col("BF", 5)
    avg_bf_l3 = mean_col("BF", 3)
    avg_ip_l3 = mean_col("IP_float", 3)
    avg_pitches_l3 = mean_col("Pitches", 3)
    avg_pitches_l5 = mean_col("Pitches", 5)

    if avg_bf_l3 and avg_bf_l5 and avg_bf_l10:
        expected_bf = avg_bf_l3 * 0.55 + avg_bf_l5 * 0.30 + avg_bf_l10 * 0.15
        source = "Weighted L3/L5/L10 BF"
    elif avg_bf_l3 and avg_bf_l10:
        expected_bf = avg_bf_l3 * 0.65 + avg_bf_l10 * 0.35
        source = "Weighted L3/L10 BF"
    elif avg_bf_l3:
        expected_bf = avg_bf_l3
        source = "Last 3 BF"
    elif avg_bf_l10:
        expected_bf = avg_bf_l10
        source = "Last 10 BF"
    else:
        expected_bf = DEFAULT_BF
        source = "Default fallback"

    ppb = 3.9
    if avg_pitches_l3 and avg_bf_l3 and avg_bf_l3 > 0:
        ppb = avg_pitches_l3 / avg_bf_l3

    leash_risk = "NORMAL"

    # High pitches per batter means fewer expected batters faced.
    if ppb >= 4.25:
        expected_bf -= 1.8
        leash_risk = "HIGH_PITCH_COUNT"
    elif ppb >= 4.05:
        expected_bf -= 0.9
        leash_risk = "MILD_PITCH_COUNT"

    # Recent short starts reduce leash confidence.
    if avg_ip_l3 is not None and avg_ip_l3 < 4.5:
        expected_bf -= 1.4
        leash_risk = "SHORT_RECENT_STARTS"

    # Recent very high pitch workload: small fatigue haircut.
    if avg_pitches_l5 is not None and avg_pitches_l5 > 96:
        expected_bf -= 0.7
        leash_risk = "HIGH_RECENT_WORKLOAD"

    return {
        "expected_bf": float(clamp(expected_bf, 14, 31)),
        "ppb": float(ppb),
        "recent_ip": float(avg_ip_l3 or 5.5),
        "last_10_ks": [safe_int(r.get("Ks"), 0) or 0 for r in recent_rows[:10]],
        "leash_risk": leash_risk,
        "source": source
    }

def blend_pitcher_k_rate(profile_k, recent_rows, pitcher_id):
    profile_k = profile_k if profile_k is not None else LEAGUE_AVG_K
    recent_rates = []
    for r in recent_rows[:5]:
        bf = safe_float(r.get("BF"))
        ks = safe_float(r.get("Ks"))
        if bf and bf > 0 and ks is not None:
            recent_rates.append(ks / bf)
    if recent_rates:
        l5 = float(np.mean(recent_rates))
        base = profile_k * 0.70 + l5 * 0.30
        source = "Season K% + recent-start K% blend"
    else:
        base = profile_k
        source = "Season pitcher K%"
    learned, scale = apply_learning(pitcher_id, base)
    return clamp(learned, 0.08, 0.48), source, scale

def calculate_log5_k_rate(pitcher_k, lineup_k, league_avg_k=LEAGUE_AVG_K):
    pitcher_k = clamp(pitcher_k, 0.01, 0.60)
    lineup_k = clamp(lineup_k, 0.01, 0.60)
    num = (pitcher_k * lineup_k) / league_avg_k
    den = num + ((1 - pitcher_k) * (1 - lineup_k)) / (1 - league_avg_k)
    return float(num / den)

# =========================
# LINEUP / BATTER K
# =========================
@st.cache_data(ttl=600, show_spinner=False)
def get_batter_season_k_rate(player_id):
    data = safe_get_json(f"{MLB_BASE}/people/{player_id}/stats", params={"stats": "season", "group": "hitting"})
    try:
        split = get_first_stat_split(data)
        if not split:
            return None, None, None
        stat = split.get("stat", {})
        so = safe_float(stat.get("strikeOuts"), 0) or 0
        pa = safe_float(stat.get("plateAppearances"), 0) or 0
        ab = safe_float(stat.get("atBats"), 0) or 0
        denom = pa if pa and pa > 0 else ab
        return (so / denom if denom and denom > 0 else None), so, denom
    except Exception:
        return None, None, None

@st.cache_data(ttl=600, show_spinner=False)
def get_batter_k_rate_vs_pitcher_hand(player_id, pitcher_hand):
    if not player_id or pitcher_hand not in ["R", "L"]:
        return None, None, None, "No pitcher hand"
    sit_code = "vrhp" if pitcher_hand == "R" else "vlhp"
    urls = [
        (f"{MLB_BASE}/people/{player_id}/stats", {"stats": "statSplits", "group": "hitting", "sitCodes": sit_code}),
        (f"{MLB_BASE}/people/{player_id}/stats", {"stats": "season", "group": "hitting", "sitCodes": sit_code}),
    ]
    for url, params in urls:
        data = safe_get_json(url, params=params)
        if not isinstance(data, dict):
            continue
        stats = data.get("stats") or []
        for block in stats:
            for split in (block.get("splits") or []):
                stat = split.get("stat") or {}
                so = safe_float(stat.get("strikeOuts"), 0) or 0
                pa = safe_float(stat.get("plateAppearances"), 0) or 0
                ab = safe_float(stat.get("atBats"), 0) or 0
                denom = pa if pa and pa > 0 else ab
                if denom and denom >= 10:
                    return float(so / denom), so, denom, f"Real split vs {'RHP' if pitcher_hand == 'R' else 'LHP'}"
    return None, None, None, "Split unavailable"


@st.cache_data(ttl=21600, show_spinner=False)
def get_batter_rolling_k_rates(player_id, days_list=(14, 30)):
    """Real rolling hitter K rates from MLB game logs.

    Returns only rates supported by real PA/SO game-log rows. Missing data gets no fake weight.
    """
    result = {int(d): None for d in days_list}
    if not player_id:
        return result
    data = safe_get_json(f"{MLB_BASE}/people/{player_id}/stats", params={"stats": "gameLog", "group": "hitting"})
    if not isinstance(data, dict):
        return result
    stats = data.get("stats") or []
    if not stats or not isinstance(stats[0], dict):
        return result
    splits = stats[0].get("splits") or []
    if not splits:
        return result
    today_dt = datetime.utcnow().date()
    for window in days_list:
        so_total, pa_total = 0.0, 0.0
        for g in splits:
            try:
                gdate = datetime.strptime(g.get("date", ""), "%Y-%m-%d").date()
            except Exception:
                continue
            age = (today_dt - gdate).days
            if age < 0 or age > int(window):
                continue
            stat = g.get("stat") or {}
            so = safe_float(stat.get("strikeOuts"), 0) or 0
            pa = safe_float(stat.get("plateAppearances"), 0) or 0
            if pa <= 0:
                pa = safe_float(stat.get("atBats"), 0) or 0
            so_total += so
            pa_total += pa
        if pa_total >= 8:
            result[int(window)] = float(so_total / pa_total)
    return result

def blend_batter_k_inputs(season_k, split_k=None, season_pa=None, split_pa=None, rolling14=None, rolling30=None):
    """Blend only real batter K inputs. Missing parts get zero weight."""
    parts = []
    if split_k is not None:
        # hand split is most matchup-specific, but still sample-sensitive
        split_weight = min(max((split_pa or 25) / 160, 0.20), 0.50)
        parts.append((float(split_k), split_weight, "hand split"))
    if rolling14 is not None:
        parts.append((float(rolling14), 0.25, "rolling 14d"))
    if rolling30 is not None:
        parts.append((float(rolling30), 0.15, "rolling 30d"))
    if season_k is not None:
        season_weight = min(max((season_pa or 50) / 300, 0.25), 0.45)
        parts.append((float(season_k), season_weight, "season"))
    if not parts:
        return None, "No batter K data"
    total_w = sum(w for _, w, _ in parts)
    blended = sum(v * w for v, w, _ in parts) / max(total_w, 1e-9)
    sources = ", ".join(src for _, _, src in parts)
    return clamp(blended, 0.04, 0.55), f"Blended real K inputs: {sources}"


def lineup_cache_key(game_pk, opp_side, pitcher_hand):
    return f"{game_pk}_{opp_side}_{pitcher_hand or 'NA'}"

def get_cached_lineup_rows(game_pk, opp_side, pitcher_hand):
    cache = load_json(LINEUP_CACHE_FILE, {})
    rec = cache.get(lineup_cache_key(game_pk, opp_side, pitcher_hand))
    return rec.get("rows", []) if rec else []

def set_cached_lineup_rows(game_pk, opp_side, pitcher_hand, rows):
    if not rows:
        return
    cache = load_json(LINEUP_CACHE_FILE, {})
    cache[lineup_cache_key(game_pk, opp_side, pitcher_hand)] = {"saved_at": now_iso(), "rows": rows[:9]}
    save_json(LINEUP_CACHE_FILE, cache)

@st.cache_data(ttl=300, show_spinner=False)
def calculate_lineup_k_rate(game_pk, opp_side, pitcher_hand=None):
    box = safe_get_json(f"{MLB_BASE}/game/{game_pk}/boxscore")
    if not box:
        cached_rows = get_cached_lineup_rows(game_pk, opp_side, pitcher_hand)
        valid_cached = [r.get("Raw_K_Rate") for r in cached_rows[:9] if r.get("Raw_K_Rate") is not None]
        if len(valid_cached) >= 5:
            return float(np.mean(valid_cached)), cached_rows[:9], "Using cached locked lineup", True
        return None, [], "Boxscore not available", False
    players = box.get("teams", {}).get(opp_side, {}).get("players", {})
    rows = []
    for _, pdata in players.items():
        order = pdata.get("battingOrder")
        if not order:
            continue
        person = pdata.get("person", {})
        player_id = person.get("id")
        name = person.get("fullName")
        season_k, season_so, season_pa = get_batter_season_k_rate(player_id)
        split_k, split_so, split_pa, split_source = get_batter_k_rate_vs_pitcher_hand(player_id, pitcher_hand) if pitcher_hand else (None, None, None, "No split")
        rolling = get_batter_rolling_k_rates(player_id, days_list=(14, 30))
        rolling14 = rolling.get(14)
        rolling30 = rolling.get(30)
        used_k, used_source = blend_batter_k_inputs(
            season_k,
            split_k=split_k,
            season_pa=season_pa,
            split_pa=split_pa,
            rolling14=rolling14,
            rolling30=rolling30,
        )
        if used_k is None:
            used_k = split_k if split_k is not None else season_k
            used_source = split_source if split_k is not None else "Season batter K%"
        rows.append({
            "Order": int(str(order)[:3]),
            "Batter": name,
            "Player ID": player_id,
            "Season K%": None if season_k is None else round(season_k * 100, 1),
            "Split K%": None if split_k is None else round(split_k * 100, 1),
            "Rolling 14d K%": None if rolling14 is None else round(rolling14 * 100, 1),
            "Rolling 30d K%": None if rolling30 is None else round(rolling30 * 100, 1),
            "Split PA/AB": split_pa,
            "Used K%": None if used_k is None else round(used_k * 100, 1),
            "K Source": used_source,
            "SO": season_so,
            "PA/AB": season_pa,
            "Raw_K_Rate": used_k
        })
    rows = sorted(rows, key=lambda x: x["Order"])
    valid = [r["Raw_K_Rate"] for r in rows[:9] if r["Raw_K_Rate"] is not None]
    if len(valid) >= 5:
        set_cached_lineup_rows(game_pk, opp_side, pitcher_hand, rows[:9])
        lineup_k = float(np.mean(valid))
        split_count = sum(1 for r in rows[:9] if r.get("Split K%") is not None)
        msg = f"Posted lineup K%; splits for {split_count}/9 hitters"
        return lineup_k, rows[:9], msg, len(rows[:9]) >= 8
    cached_rows = get_cached_lineup_rows(game_pk, opp_side, pitcher_hand)
    valid_cached = [r.get("Raw_K_Rate") for r in cached_rows[:9] if r.get("Raw_K_Rate") is not None]
    if len(valid_cached) >= 5:
        return float(np.mean(valid_cached)), cached_rows[:9], "Current lineup thin; using cached locked lineup", True
    return None, rows, "Lineup not posted or not enough hitter K data", False

def team_k_vs_hand(team_id, hand):
    data = safe_get_json(f"{MLB_BASE}/teams/{team_id}/stats", params={"stats": "season", "group": "hitting"})
    try:
        split = get_first_stat_split(data)
        if not split:
            return LEAGUE_AVG_K, "League average fallback"
        stat = split.get("stat", {})
        so = safe_float(stat.get("strikeOuts"), 0) or 0
        pa = safe_float(stat.get("plateAppearances"), 0) or 0
        if pa > 0:
            return float(so / pa), "Team season K/PA fallback"
    except Exception:
        pass
    return LEAGUE_AVG_K, "League average fallback"

# =========================
# STATCAST
# =========================
@st.cache_data(ttl=21600, show_spinner=False)
def get_statcast_pitch_profile(pitcher_id, days=365):
    empty = {"available": False, "message": "No pitcher id", "rows": 0, "csw": None, "whiff": None, "pitch_mix": [], "pitch_type_profile": [], "putaway": None}
    if not pitcher_id:
        return empty
    end = datetime.now()
    start = end - timedelta(days=int(days))
    url = "https://baseballsavant.mlb.com/statcast_search/csv"
    params = {
        "all": "true",
        "player_type": "pitcher",
        "pitchers_lookup[]": str(pitcher_id),
        "game_date_gt": start.strftime("%Y-%m-%d"),
        "game_date_lt": end.strftime("%Y-%m-%d"),
        "type": "details",
    }
    try:
        r = requests.get(url, params=params, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or not r.text.strip():
            empty["message"] = f"Statcast HTTP {r.status_code}"
            return empty
        df = pd.read_csv(io.StringIO(r.text), low_memory=False)
        if df.empty or "description" not in df.columns:
            empty["message"] = "Statcast returned no pitch rows"
            return empty
        desc = df["description"].astype(str).str.lower()
        pitch_count = int(len(df))
        called_mask = desc.eq("called_strike")
        whiff_mask = desc.isin(["swinging_strike", "swinging_strike_blocked", "foul_tip"])
        swing_mask = desc.isin(["swinging_strike", "swinging_strike_blocked", "foul_tip", "foul", "foul_bunt", "missed_bunt", "hit_into_play", "hit_into_play_no_out", "hit_into_play_score"])
        called = int(called_mask.sum())
        whiffs_n = int(whiff_mask.sum())
        swings = int(swing_mask.sum())
        csw = (called + whiffs_n) / pitch_count if pitch_count else None
        whiff = whiffs_n / swings if swings else None
        pitch_mix = []
        pitch_type_profile = []
        if "pitch_type" in df.columns:
            df2 = df.copy()
            df2["pitch_type"] = df2["pitch_type"].fillna("UNK").astype(str)
            df2["_called"] = called_mask.astype(int)
            df2["_whiff"] = whiff_mask.astype(int)
            df2["_swing"] = swing_mask.astype(int)
            total = max(len(df2), 1)
            grouped = df2.groupby("pitch_type").agg(Pitches=("pitch_type", "size"), Called=("_called", "sum"), Whiffs=("_whiff", "sum"), Swings=("_swing", "sum")).reset_index()
            grouped["Usage"] = grouped["Pitches"] / total
            grouped["CSW"] = (grouped["Called"] + grouped["Whiffs"]) / grouped["Pitches"].replace(0, np.nan)
            grouped["WhiffRate"] = grouped["Whiffs"] / grouped["Swings"].replace(0, np.nan)
            grouped = grouped.sort_values("Usage", ascending=False).head(8)
            for _, row in grouped.iterrows():
                pt = str(row["pitch_type"])
                usage = safe_float(row["Usage"], 0) or 0
                wr = safe_float(row["WhiffRate"])
                csw_rate = safe_float(row["CSW"])
                pitch_mix.append({"Pitch Type": pt, "Usage %": round(usage * 100, 1)})
                pitch_type_profile.append({
                    "Pitch Type": pt,
                    "Usage %": round(usage * 100, 1),
                    "Pitcher Whiff%": None if wr is None or pd.isna(wr) else round(wr * 100, 1),
                    "Pitcher CSW%": None if csw_rate is None or pd.isna(csw_rate) else round(csw_rate * 100, 1),
                    "Pitches": int(row["Pitches"]),
                    "Swings": int(row["Swings"]),
                })
        return {"available": True, "message": "Real Statcast pitch-level data loaded", "rows": pitch_count, "csw": None if csw is None else float(csw), "whiff": None if whiff is None else float(whiff), "pitch_mix": pitch_mix, "pitch_type_profile": pitch_type_profile}
    except Exception as e:
        empty["message"] = f"Statcast unavailable: {e}"
        return empty

def apply_statcast_csw_adjustment(pitcher_k, statcast_profile, enabled=True):
    if not enabled or not statcast_profile or not statcast_profile.get("available"):
        return pitcher_k, "No Statcast adjustment"
    csw = statcast_profile.get("csw")
    if csw is None:
        return pitcher_k, "No Statcast CSW available"
    factor = clamp(1 + ((float(csw) - 0.275) * 0.45), 0.93, 1.07)
    return clamp(pitcher_k * factor, 0.08, 0.50), f"Real Statcast CSW adjustment x{factor:.3f}"

def apply_pitch_type_matchup_adjustment(pitcher_k, pitcher_statcast, enabled=True):
    if not enabled or not pitcher_statcast or not pitcher_statcast.get("available"):
        return pitcher_k, "No pitch-type matchup adjustment", False, [], 1.0
    # Conservative simplified pitch-type factor from pitcher whiff vs league ref.
    rows = []
    weighted = 0
    total_w = 0
    for r in pitcher_statcast.get("pitch_type_profile", []):
        pt = r.get("Pitch Type")
        usage = (safe_float(r.get("Usage %"), 0) or 0) / 100
        wr = safe_float(r.get("Pitcher Whiff%"))
        ref = LEAGUE_AVG_WHIFF_BY_PITCH_TYPE.get(pt, 0.25)
        if usage >= 0.03 and wr is not None:
            idx = clamp((wr / 100) / max(ref, 0.01), 0.85, 1.18)
            weighted += usage * idx
            total_w += usage
            rows.append({"Pitch Type": pt, "Usage %": round(usage * 100, 1), "Pitcher Whiff%": wr, "League Ref Whiff%": round(ref * 100, 1), "Index": round(idx, 3)})
    if total_w <= 0:
        return pitcher_k, "Pitch-type rows unavailable", False, rows, 1.0
    combined = weighted / total_w
    factor = clamp(1 + ((combined - 1) * 0.08), 0.97, 1.03)
    return clamp(pitcher_k * factor, 0.08, 0.50), f"Pitch-type whiff mix adjustment x{factor:.3f}", True, rows, factor



@st.cache_data(ttl=21600, show_spinner=False)
def get_batter_statcast_pitch_type_profile(batter_id, days=365, pitcher_hand=None):
    """Real batter whiff profile by pitch type from Baseball Savant.

    This never estimates missing data. If Statcast is unavailable or too thin, no adjustment is applied.
    """
    empty = {"available": False, "message": "No batter id", "rows": 0, "pitch_type_profile": []}
    if not batter_id:
        return empty
    end = datetime.now()
    start = end - timedelta(days=int(days))
    url = "https://baseballsavant.mlb.com/statcast_search/csv"
    params = {
        "all": "true",
        "player_type": "batter",
        "batters_lookup[]": str(batter_id),
        "game_date_gt": start.strftime("%Y-%m-%d"),
        "game_date_lt": end.strftime("%Y-%m-%d"),
        "type": "details",
    }
    try:
        r = requests.get(url, params=params, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or not r.text.strip():
            empty["message"] = f"Batter Statcast HTTP {r.status_code}"
            return empty
        df = pd.read_csv(io.StringIO(r.text), low_memory=False)
        if df.empty or "description" not in df.columns or "pitch_type" not in df.columns:
            empty["message"] = "Batter Statcast returned no pitch-type rows"
            return empty
        # Use hand split only if the split sample is not tiny. Otherwise use all pitcher hands.
        if pitcher_hand in ["R", "L"] and "p_throws" in df.columns:
            hand_df = df[df["p_throws"].astype(str).str.upper() == pitcher_hand].copy()
            if len(hand_df) >= 25:
                df = hand_df
        desc = df["description"].astype(str).str.lower()
        whiff_mask = desc.isin(["swinging_strike", "swinging_strike_blocked", "foul_tip"])
        swing_mask = desc.isin([
            "swinging_strike", "swinging_strike_blocked", "foul_tip", "foul", "foul_bunt",
            "missed_bunt", "hit_into_play", "hit_into_play_no_out", "hit_into_play_score"
        ])
        df2 = df.copy()
        df2["pitch_type"] = df2["pitch_type"].fillna("UNK").astype(str)
        df2["_whiff"] = whiff_mask.astype(int)
        df2["_swing"] = swing_mask.astype(int)
        grouped = df2.groupby("pitch_type").agg(
            Pitches=("pitch_type", "size"),
            Whiffs=("_whiff", "sum"),
            Swings=("_swing", "sum"),
        ).reset_index()
        grouped = grouped[grouped["Swings"] >= 5]
        if grouped.empty:
            empty["message"] = "Batter Statcast has too few swings by pitch type"
            return empty
        grouped["WhiffRate"] = grouped["Whiffs"] / grouped["Swings"].replace(0, np.nan)
        profile = []
        for _, row in grouped.iterrows():
            wr = safe_float(row["WhiffRate"])
            if wr is None or pd.isna(wr):
                continue
            profile.append({
                "Pitch Type": str(row["pitch_type"]),
                "Batter Whiff%": round(wr * 100, 1),
                "Swings": int(row["Swings"]),
                "Pitches Seen": int(row["Pitches"]),
            })
        if not profile:
            empty["message"] = "No batter pitch-type whiff rows passed sample filter"
            return empty
        return {"available": True, "message": "Real batter Statcast pitch-type whiff loaded", "rows": int(len(df)), "pitch_type_profile": profile}
    except Exception as e:
        empty["message"] = f"Batter Statcast unavailable: {e}"
        return empty


def build_pitch_type_matchup_profile(pitcher_statcast, lineup_rows, enabled=True, min_batters=5, pitcher_hand=None):
    """Compare real pitcher pitch mix to real batter whiff by pitch type.

    Applies only when enough real batter Statcast profiles load. Missing pitch types are ignored, not guessed.
    """
    result = {"available": False, "factor": 1.0, "message": "Pitch-type matchup disabled or unavailable", "rows": [], "batters_loaded": 0}
    if not enabled:
        result["message"] = "Pitch-type matchup disabled"
        return result
    if not pitcher_statcast or not pitcher_statcast.get("available"):
        result["message"] = "Pitcher Statcast pitch mix unavailable"
        return result
    pitch_profile = pitcher_statcast.get("pitch_type_profile") or []
    if not pitch_profile:
        result["message"] = "Pitcher pitch-type profile unavailable"
        return result
    if not lineup_rows:
        result["message"] = "No posted lineup for batter pitch-type matching"
        return result

    pitcher_usage = {r.get("Pitch Type"): (safe_float(r.get("Usage %"), 0) or 0) / 100.0 for r in pitch_profile}
    pitcher_whiff = {
        r.get("Pitch Type"): (safe_float(r.get("Pitcher Whiff%")) / 100.0 if safe_float(r.get("Pitcher Whiff%")) is not None else None)
        for r in pitch_profile
    }
    pitch_types = [pt for pt, use in pitcher_usage.items() if pt and use >= 0.03]

    batter_profiles = []
    for r in lineup_rows[:9]:
        bid = r.get("Player ID")
        prof = get_batter_statcast_pitch_type_profile(bid, days=365, pitcher_hand=pitcher_hand)
        if prof.get("available"):
            by_pt = {x.get("Pitch Type"): x for x in prof.get("pitch_type_profile", [])}
            batter_profiles.append({"Batter": r.get("Batter"), "by_pt": by_pt})
    result["batters_loaded"] = len(batter_profiles)
    if len(batter_profiles) < min_batters:
        result["message"] = f"Only {len(batter_profiles)}/9 batter pitch-type profiles loaded; no adjustment applied"
        return result

    rows = []
    weighted_index = 0.0
    used_weight = 0.0
    for pt in pitch_types:
        use = pitcher_usage.get(pt, 0) or 0
        batter_rates = []
        batter_swings = 0
        for bp in batter_profiles:
            row = bp["by_pt"].get(pt)
            if not row:
                continue
            wr = safe_float(row.get("Batter Whiff%"))
            swings = safe_int(row.get("Swings"), 0) or 0
            if wr is not None and swings >= 5:
                batter_rates.append(wr / 100.0)
                batter_swings += swings
        if len(batter_rates) < 3:
            continue
        avg_batter_whiff = float(np.mean(batter_rates))
        league_ref = LEAGUE_AVG_WHIFF_BY_PITCH_TYPE.get(pt, 0.25)
        pitcher_wr = pitcher_whiff.get(pt)
        pitcher_bonus = 1.0
        if pitcher_wr is not None:
            pitcher_bonus = clamp(pitcher_wr / max(league_ref, 0.01), 0.85, 1.18)
        batter_index = avg_batter_whiff / max(league_ref, 0.01)
        combined_index = clamp((batter_index * 0.70) + (pitcher_bonus * 0.30), 0.82, 1.22)
        weighted_index += use * combined_index
        used_weight += use
        rows.append({
            "Pitch Type": pt,
            "Pitcher Usage %": round(use * 100, 1),
            "Avg Batter Whiff%": round(avg_batter_whiff * 100, 1),
            "League Ref Whiff%": round(league_ref * 100, 1),
            "Pitcher Whiff%": None if pitcher_wr is None else round(pitcher_wr * 100, 1),
            "Index": round(combined_index, 3),
            "Batter Profiles Used": len(batter_rates),
            "Batter Swings": batter_swings,
        })
    if used_weight <= 0 or not rows:
        result["message"] = "No overlapping pitcher/batter pitch-type rows passed sample filter"
        return result
    avg_index = weighted_index / used_weight
    factor = clamp(1 + ((avg_index - 1) * 0.10), 0.965, 1.035)
    result.update({
        "available": True,
        "factor": factor,
        "message": f"Real batter-vs-pitch-type matchup x{factor:.3f} ({len(batter_profiles)}/9 batters loaded)",
        "rows": rows,
    })
    return result


def apply_advanced_pitch_type_matchup_adjustment(pitcher_k, matchup_profile, enabled=True):
    if not enabled or not matchup_profile or not matchup_profile.get("available"):
        msg = matchup_profile.get("message", "No batter-vs-pitch-type matchup adjustment") if matchup_profile else "No batter-vs-pitch-type matchup adjustment"
        return pitcher_k, msg
    factor = safe_float(matchup_profile.get("factor"), 1.0) or 1.0
    return clamp(pitcher_k * factor, 0.08, 0.50), matchup_profile.get("message", f"Pitch-type matchup x{factor:.3f}")

# =========================
# SIMULATION
# =========================
def park_k_factor(venue_name):
    """Small, conservative park adjustment. Missing venue stays neutral."""
    v = normalize_name(venue_name)
    park_map = {
        "tropicana field": 1.025,
        "loan depot park": 1.015,
        "oracle park": 1.010,
        "petco park": 1.010,
        "t mobile park": 1.010,
        "coors field": 0.965,
        "great american ball park": 0.985,
        "fenway park": 0.990,
        "citizens bank park": 0.990,
        "globe life field": 1.005,
    }
    for name, factor in park_map.items():
        if name in v:
            return factor
    return 1.00

def umpire_factor(game_pk):
    data = safe_get_json(f"{MLB_LIVE}/game/{game_pk}/feed/live")
    try:
        officials = data["liveData"]["boxscore"].get("officials", [])
        name = officials[0]["official"]["fullName"] if officials else "Unknown"
        high_k = ["Lance Barrett", "Mark Wegner"]
        low_k = ["Bill Miller", "Chris Segal"]
        if name in high_k:
            return 1.06, name
        if name in low_k:
            return 0.97, name
        return 1.00, name
    except Exception:
        return 1.00, "Unknown"

def build_pa_sequence(lineup_rows, bf, fallback_k):
    bf = int(round(bf))
    if lineup_rows:
        rates = [r.get("Raw_K_Rate") for r in lineup_rows[:9] if r.get("Raw_K_Rate") is not None]
        if len(rates) >= 5:
            return [rates[i % len(rates)] for i in range(max(1, bf))], "Batter-by-batter posted lineup"
    return [fallback_k for _ in range(max(1, bf))], "Team/fallback K sequence"

def simulate_matchup(pitcher_k, batter_rates, park=1.0, ump=1.0, sims=12000):
    rates = []
    for br in batter_rates:
        k = calculate_log5_k_rate(pitcher_k, br)
        k *= park * ump
        rates.append(clamp(k, 0.03, 0.60))
    out = np.random.binomial(1, np.array(rates), size=(sims, len(rates))).sum(axis=1)
    return out, rates

def calculate_pick_metrics(sims, line):
    if line is None:
        return {"over_prob": None, "under_prob": None, "fair_prob": None, "pick_side": "NO LINE", "edge": None, "grade": "NO LINE", "ev": None}
    over_prob = float(np.mean(sims > line))
    under_prob = 1 - over_prob
    if over_prob >= under_prob:
        side = "OVER"
        fair = over_prob
    else:
        side = "UNDER"
        fair = under_prob
    edge = (fair - 0.50) * 100
    grade = "S" if fair >= 0.68 else "A" if fair >= 0.60 else "B" if fair >= 0.55 else "C"
    return {"over_prob": over_prob, "under_prob": under_prob, "fair_prob": fair, "pick_side": side, "edge": edge, "grade": grade, "ev": (fair * 100) - ((1 - fair) * 100)}

# =========================
# REAL PROP SOURCES
# =========================
def source_result(source, status, line=None, rows=None, message=""):
    return {"source": source, "status": status, "line": safe_float(line), "rows": rows or [], "message": message}

@st.cache_data(ttl=600, show_spinner=False)
def get_odds_events():
    if not ODDS_API_KEY:
        return []
    data = safe_get_json(f"{ODDS_BASE}/sports/baseball_mlb/events", params={"apiKey": ODDS_API_KEY}, timeout=16)
    return data if isinstance(data, list) else []

@st.cache_data(ttl=600, show_spinner=False)
def get_sportsbook_event_pitcher_k_lines(event_id, player_name):
    if not event_id:
        return source_result("Sportsbook", "NO EVENT", rows=[], message="No matching Odds API event id")
    data = safe_get_json(
        f"{ODDS_BASE}/sports/baseball_mlb/events/{event_id}/odds",
        params={"apiKey": ODDS_API_KEY, "regions": "us,us2,uk,eu,au", "markets": ",".join(SPORTSBOOK_PITCHER_K_MARKETS), "oddsFormat": "american"},
        timeout=16
    )
    if not data or (isinstance(data, dict) and data.get("message")):
        return source_result("Sportsbook", "FAILED", rows=[], message="Event odds call failed or plan has no player props")
    rows = []
    for book in data.get("bookmakers", []):
        book_name = book.get("title") or book.get("key") or "Sportsbook"
        for market in book.get("markets", []):
            if market.get("key") not in SPORTSBOOK_PITCHER_K_MARKETS:
                continue
            for outcome in market.get("outcomes", []):
                desc = outcome.get("description") or outcome.get("player") or outcome.get("participant") or outcome.get("name") or ""
                score = name_score(player_name, desc)
                if score < 0.80:
                    continue
                point = safe_float(outcome.get("point"))
                if point is None:
                    continue
                rows.append({"Source": "OddsAPI", "Provider": book_name, "Player": player_name, "Matched Name": desc, "Match Score": round(score, 3), "Market": market.get("key"), "Line": point, "Side": str(outcome.get("name", "")).upper(), "Price": outcome.get("price"), "Last Update": market.get("last_update") or book.get("last_update")})
    if not rows:
        return source_result("Sportsbook", "NO MATCH", rows=[], message="No sportsbook K prop matched this pitcher")
    line_vals = [safe_float(r["Line"]) for r in rows if safe_float(r.get("Line")) is not None]
    consensus = float(np.median(line_vals)) if line_vals else rows[0]["Line"]
    return source_result("Sportsbook", "FOUND", line=consensus, rows=rows, message=f"Found {len(rows)} sportsbook outcomes")

def get_sportsbook_k_data(game_home, game_away, player_name):
    events = get_odds_events()
    event_id = None
    target_teams = {normalize_name(game_home), normalize_name(game_away)}
    for ev in events:
        home = normalize_name(ev.get("home_team"))
        away = normalize_name(ev.get("away_team"))
        if {home, away} == target_teams or (home in target_teams and away in target_teams):
            event_id = ev.get("id")
            break
    return get_sportsbook_event_pitcher_k_lines(event_id, player_name)

@st.cache_data(ttl=600, show_spinner=False)
def get_prizepicks_k_data(player_name):
    data = safe_get_json(PRIZEPICKS_URL, timeout=16)
    if not data:
        return source_result("PrizePicks", "FAILED", message="API failed or returned no JSON")
    players = {}
    for inc in data.get("included", []):
        inc_type = inc.get("type", "")
        attrs = inc.get("attributes", {}) or {}
        if inc_type in ["new_player", "player"]:
            pid = str(inc.get("id"))
            name = attrs.get("name") or attrs.get("display_name") or attrs.get("full_name")
            league = attrs.get("league") or attrs.get("league_name") or attrs.get("sport") or ""
            team = attrs.get("team") or attrs.get("team_name") or ""
            if pid and name:
                players[pid] = {"name": name, "league": league, "team": team}
    rows = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {}) or {}
        stat_type = attrs.get("stat_type") or attrs.get("stat_display_name") or attrs.get("name") or ""
        if not is_pitcher_k_text(stat_type):
            continue
        line_score = safe_float(attrs.get("line_score") or attrs.get("line") or attrs.get("projection"))
        if line_score is None:
            continue
        rel = item.get("relationships", {}) or {}
        pdata = (rel.get("new_player", {}) or {}).get("data") or (rel.get("player", {}) or {}).get("data") or {}
        pid = str(pdata.get("id", ""))
        info = players.get(pid, {})
        pp_name = info.get("name") or attrs.get("player_name") or attrs.get("description") or ""
        score = name_score(player_name, pp_name)
        if score >= 0.80:
            rows.append({"Source": "PrizePicks", "Provider": "PrizePicks", "Player": player_name, "Matched Name": pp_name, "Team": info.get("team", ""), "League": info.get("league", ""), "Market": stat_type, "Line": line_score, "Side": "OVER/UNDER", "Price": None, "Match Score": round(score, 3), "Start Time": attrs.get("start_time"), "Projection ID": item.get("id")})
    if not rows:
        return source_result("PrizePicks", "NO MATCH", message="No fuzzy pitcher strikeout prop match found")
    rows = sorted(rows, key=lambda r: -r.get("Match Score", 0))
    return source_result("PrizePicks", "FOUND", line=rows[0]["Line"], rows=rows, message=f"Found {len(rows)} PrizePicks matches")

def extract_prop_rows_from_any_json(data, player_name, source_name):
    rows = []
    if not data:
        return rows
    objects = flatten_json(data)
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        blob = json.dumps(obj, default=str).lower()
        if not ("strikeout" in blob or "strike out" in blob or "pitcher k" in blob or "pitcher_k" in blob):
            continue
        candidate_bits = []
        for key in ["player", "player_name", "participant", "participant_name", "name", "description", "display_name", "market_name", "selection", "title"]:
            val = obj.get(key)
            if isinstance(val, dict):
                val = val.get("name") or val.get("full_name") or val.get("display_name")
            if val:
                candidate_bits.append(str(val))
        candidate = " ".join(candidate_bits) or blob[:160]
        score = name_score(player_name, candidate)
        if score < 0.80 and normalize_name(player_name) in normalize_name(blob):
            score = 0.82
        if score < 0.80:
            continue
        line = safe_float(first_value(obj, ["line", "point", "points", "total", "handicap", "stat_value", "target_value", "over_under_line", "line_score", "value"]))
        if line is None:
            continue
        side = first_value(obj, ["side", "label", "name", "selection", "outcome", "bet_type"]) or "Over/Under"
        price = safe_float(first_value(obj, ["price", "odds", "american_odds", "american", "over_price", "under_price"]))
        book = first_value(obj, ["sportsbook", "book", "bookmaker", "operator", "source"]) or source_name
        if isinstance(book, dict):
            book = book.get("name") or source_name
        rows.append({"Source": source_name, "Provider": str(book), "Player": player_name, "Matched Name": candidate[:120], "Match Score": round(score, 3), "Market": first_value(obj, ["market", "market_name", "stat", "stat_type", "prop", "category"]) or "Pitcher Strikeouts", "Side": str(side).upper(), "Line": line, "Price": price})
    dedup = {}
    for r in rows:
        key = (r.get("Provider"), r.get("Source"), str(r.get("Side")).lower(), r.get("Line"), r.get("Price"))
        dedup[key] = r
    return list(dedup.values())

@st.cache_data(ttl=600, show_spinner=False)
def get_underdog_k_data(player_name):
    all_rows = []
    last_msg = ""
    for url in UNDERDOG_URLS:
        data = safe_get_json(url, timeout=16)
        if not data:
            last_msg = f"No JSON from {url}"
            continue
        all_rows.extend(extract_prop_rows_from_any_json(data, player_name, "Underdog"))
    if not all_rows:
        return source_result("Underdog", "NO MATCH", message=last_msg or "No Underdog match")
    lines = [safe_float(r.get("Line")) for r in all_rows if safe_float(r.get("Line")) is not None]
    return source_result("Underdog", "FOUND", line=float(np.median(lines)), rows=all_rows, message=f"Found {len(all_rows)} Underdog rows")

@st.cache_data(ttl=600, show_spinner=False)
def get_sportsgameodds_k_data(player_name):
    if not SPORTSGAMEODDS_API_KEY:
        return source_result("SportsGameOdds", "DISABLED", message="Add SPORTSGAMEODDS_API_KEY to enable")
    endpoints = [f"{SPORTSGAMEODDS_BASE}/events", f"{SPORTSGAMEODDS_BASE}/odds", f"{SPORTSGAMEODDS_BASE}/props"]
    headers = {"X-Api-Key": SPORTSGAMEODDS_API_KEY, "Authorization": f"Bearer {SPORTSGAMEODDS_API_KEY}"}
    all_rows = []
    last_msg = ""
    for url in endpoints:
        data = safe_get_json(url, params={"sport": "baseball", "league": "mlb", "market": "player_pitcher_strikeouts"}, headers=headers, timeout=16)
        if not data:
            last_msg = f"No JSON from {url}"
            continue
        all_rows.extend(extract_prop_rows_from_any_json(data, player_name, "SportsGameOdds"))
    if not all_rows:
        return source_result("SportsGameOdds", "NO MATCH", message=last_msg or "No SportsGameOdds row matched")
    lines = [safe_float(r.get("Line")) for r in all_rows if safe_float(r.get("Line")) is not None]
    return source_result("SportsGameOdds", "FOUND", line=float(np.median(lines)), rows=all_rows, message=f"Found {len(all_rows)} SportsGameOdds rows")

@st.cache_data(ttl=600, show_spinner=False)
def get_opticodds_k_data(player_name):
    if not OPTICODDS_API_KEY:
        return source_result("OpticOdds", "DISABLED", message="Add OPTICODDS_API_KEY to enable")
    endpoints = [f"{OPTICODDS_BASE}/fixtures/odds", f"{OPTICODDS_BASE}/odds", f"{OPTICODDS_BASE}/player-props"]
    headers = {"X-Api-Key": OPTICODDS_API_KEY, "Authorization": f"Bearer {OPTICODDS_API_KEY}"}
    all_rows = []
    last_msg = ""
    for url in endpoints:
        data = safe_get_json(url, params={"sport": "baseball", "league": "mlb", "market": "player_pitcher_strikeouts"}, headers=headers, timeout=16)
        if not data:
            last_msg = f"No JSON from {url}"
            continue
        all_rows.extend(extract_prop_rows_from_any_json(data, player_name, "OpticOdds"))
    if not all_rows:
        return source_result("OpticOdds", "NO MATCH", message=last_msg or "No OpticOdds row matched")
    lines = [safe_float(r.get("Line")) for r in all_rows if safe_float(r.get("Line")) is not None]
    return source_result("OpticOdds", "FOUND", line=float(np.median(lines)), rows=all_rows, message=f"Found {len(all_rows)} OpticOdds rows")

def choose_active_line(sportsbook_data, pp_data, ud_data, sgo_data, optic_data):
    candidates = []
    def add(source, line, weight):
        val = safe_float(line)
        if val is not None:
            candidates.append({"Source": source, "Line": val, "Weight": float(weight)})
    add("Sportsbook", sportsbook_data.get("line"), 3.0)
    add("SportsGameOdds", sgo_data.get("line"), 2.5)
    add("OpticOdds", optic_data.get("line"), 2.5)
    add("PrizePicks", pp_data.get("line"), 1.5)
    add("Underdog", ud_data.get("line"), 1.5)
    if not candidates:
        return None, "No Real Line", {"count": 0, "quality": "NO LINE", "spread": None, "rows": []}
    expanded = []
    for c in candidates:
        expanded.extend([c["Line"]] * max(1, int(round(c["Weight"] * 2))))
    consensus = float(np.median(expanded))
    raw_lines = [c["Line"] for c in candidates]
    spread = float(max(raw_lines) - min(raw_lines)) if len(raw_lines) > 1 else 0.0
    quality = "STRONG" if len(candidates) >= 3 and spread <= 0.5 else "OK" if len(candidates) >= 2 and spread <= 1.0 else "THIN"
    source = "Cross-Source Consensus" if len(candidates) >= 2 else candidates[0]["Source"]
    return consensus, f"{source} ({quality})", {"count": len(candidates), "quality": quality, "spread": round(spread, 2), "rows": candidates}

# =========================
# CONFIDENCE / SIGNAL
# =========================
def data_lock_score(lineup_locked, pitcher_confirmed, active_line, consensus_info, ppb, statcast_available, pitch_type_available):
    score = 38
    if pitcher_confirmed:
        score += 15
    if lineup_locked:
        score += 20
    if active_line is not None:
        score += 15
    if consensus_info.get("count", 0) >= 3 and (consensus_info.get("spread") is None or consensus_info.get("spread") <= 0.5):
        score += 9
    elif consensus_info.get("count", 0) >= 2:
        score += 6
    if ppb and ppb < 4.05:
        score += 3
    elif ppb and ppb >= 4.25:
        score -= 5
    if statcast_available:
        score += 5
    if pitch_type_available:
        score += 3
    return int(clamp(score, 0, 100))

def shrink_probability_to_market(model_prob, score=50, lineup_locked=False, pitcher_confirmed=False):
    p = safe_float(model_prob)
    if p is None:
        return None

    # Tighter shrink: high probabilities only survive if the data is actually locked.
    strength = 0.20 + (float(score or 50) / 100.0) * 0.50
    strength += 0.08 if lineup_locked else -0.10
    strength += 0.06 if pitcher_confirmed else -0.08
    strength = clamp(strength, 0.18, 0.86)

    capped = clamp(0.50 + ((p - 0.50) * strength), 0.01, 0.99)

    if not lineup_locked or not pitcher_confirmed:
        capped = min(capped, 0.74)
    elif score < MIN_CONFIRMED_LINEUP_SCORE:
        capped = min(capped, 0.80)

    return clamp(capped, 0.01, 0.99)

def no_bet_gate(active_line, pick_side, fair_prob, ev, gap, score, lineup_locked, pitcher_confirmed, line_source, consensus_info, leash):
    reasons = []
    if active_line is None:
        reasons.append("no real prop line")
    if pick_side not in ["OVER", "UNDER"]:
        reasons.append("no valid side")
    if fair_prob is None or fair_prob < MIN_BETTABLE_PROB:
        reasons.append(f"probability below {int(MIN_BETTABLE_PROB*100)}%")
    if ev is None or ev < MIN_BETTABLE_EV:
        reasons.append(f"EV below {round(MIN_BETTABLE_EV*100,1)}%")
    if gap is None or gap < MIN_BETTABLE_GAP_KS:
        reasons.append(f"edge below {MIN_BETTABLE_GAP_KS} K")
    if score < MIN_BETTABLE_SCORE:
        reasons.append(f"data score below {MIN_BETTABLE_SCORE}")
    if not pitcher_confirmed:
        reasons.append("pitcher not confirmed")
    if not lineup_locked:
        reasons.append("lineup not locked")
    if consensus_info.get("quality") == "NO LINE":
        reasons.append("no market consensus")
    if leash.get("leash_risk") in ["HIGH_PITCH_COUNT", "SHORT_RECENT_STARTS", "HIGH_RECENT_WORKLOAD"]:
        reasons.append(f"leash risk: {leash.get('leash_risk')}")
    return len(reasons) == 0, reasons

def classify_risk(prob, score, priced, edge_pct, gap, line_source):
    p = safe_float(prob)
    if p is None:
        return "NO MODEL %", "No usable probability"

    pct = p * 100
    if pct >= 85 and score >= 92 and priced and edge_pct >= MIN_ELITE_NO_VIG_EDGE and gap >= 1.0:
        return "ELITE WATCH — VERIFY", "Strict gates passed; still verify lineup, line, and pitcher status"

    if pct >= 75 and score >= 85:
        label = "STRONG WATCH"
    elif pct >= 65 and score >= 78:
        label = "MEDIUM WATCH"
    elif pct >= 55:
        label = "LEAN ONLY"
    else:
        label = "PASS / COINFLIP RISK"

    notes = []
    if score < 75:
        notes.append("data score under 75")
    if not priced:
        notes.append("no real sportsbook price")
    if edge_pct is not None and edge_pct <= 0:
        notes.append("no positive no-vig edge")
    if "No Real Line" in str(line_source):
        notes.append("no real prop line")
    if gap < MIN_BETTABLE_GAP_KS:
        notes.append("gap under 0.70 K")
    return label, "; ".join(notes) if notes else "Strict risk label applied"

def build_signal(proj, line, fair_prob, ev, ppb, score):
    if line is None:
        return "PASS — NO REAL LINE", "pass"
    gap = abs(proj - line)
    side = "OVER" if proj > line else "UNDER"
    if fair_prob >= 0.70 and gap >= 1.0 and ev is not None and ev >= 0.06 and score >= 88 and ppb < 4.10:
        return f"🔥 STRONG WATCH {side}", "good"
    if fair_prob >= 0.62 and gap >= 0.80 and ev is not None and ev >= 0.03 and score >= 80:
        return f"✅ WATCH {side}", "good"
    return f"PASS / LEAN {side}", "pass"



def bullpen_workload_bf_factor(team_id):
    """Conservative team pitching workload proxy for starter leash.

    It only nudges expected batters faced slightly and never creates a fake edge.
    """
    data = safe_get_json(f"{MLB_BASE}/teams/{team_id}/stats", params={"stats": "season", "group": "pitching"})
    try:
        split = get_first_stat_split(data)
        if not split:
            return 1.0, "Bullpen/team workload unavailable"
        stat = split.get("stat", {})
        ip = baseball_ip_to_float(stat.get("inningsPitched"))
        games = safe_float(stat.get("gamesPlayed"), 0) or 0
        if not ip or not games:
            return 1.0, "Bullpen/team workload unavailable"
        ip_per_game = ip / max(games, 1)
        factor = clamp(1.0 + ((ip_per_game - 8.7) * 0.015), 0.97, 1.03)
        return float(factor), f"Conservative bullpen workload BF factor x{factor:.3f}"
    except Exception:
        return 1.0, "Bullpen/team workload unavailable"

# =========================
# PROJECTION ENGINE
# =========================
def make_projection(row, bankroll, default_odds, use_statcast, use_pitch_type, use_calibration, use_sgo=False, use_optic=False):
    pid = row["pitcher_id"]
    pitcher_name = row["pitcher"]
    hand = row["hand"]

    profile = get_pitcher_profile(pid)
    recent_rows = get_recent_logs(pid)
    leash = build_leash_model(recent_rows)

    lineup_k, lineup_rows, lineup_msg, lineup_locked = calculate_lineup_k_rate(row["game_pk"], row["opp_side"], hand)
    if lineup_k is None:
        lineup_k, fallback_msg = team_k_vs_hand(row["opp_team_id"], hand)
        lineup_rows = []
        lineup_msg = fallback_msg
        lineup_locked = False

    pitcher_k, pitcher_k_source, learn_scale = blend_pitcher_k_rate(profile["Pitcher K%"], recent_rows, pid)

    statcast_profile = get_statcast_pitch_profile(pid, days=365)
    pitcher_k, statcast_note = apply_statcast_csw_adjustment(pitcher_k, statcast_profile, enabled=use_statcast)

    # v9.6 upgrade: prefer true batter-vs-pitch-type matchup when lineup is available.
    matchup_profile = build_pitch_type_matchup_profile(
        statcast_profile,
        lineup_rows if lineup_locked else [],
        enabled=use_pitch_type,
        min_batters=5,
        pitcher_hand=hand,
    )
    if matchup_profile.get("available"):
        pitcher_k, pitch_type_note = apply_advanced_pitch_type_matchup_adjustment(pitcher_k, matchup_profile, enabled=use_pitch_type)
        pitch_type_available = True
        pitch_type_rows = matchup_profile.get("rows", [])
        pitch_type_factor = safe_float(matchup_profile.get("factor"), 1.0) or 1.0
    else:
        # fallback to pitcher-only whiff mix when batter Statcast profiles are thin or lineup is not posted
        pitcher_k, pitch_type_note, pitch_type_available, pitch_type_rows, pitch_type_factor = apply_pitch_type_matchup_adjustment(pitcher_k, statcast_profile, enabled=use_pitch_type)
        if not pitch_type_available:
            pitch_type_note = matchup_profile.get("message", pitch_type_note)

    calibration_profile = build_model_calibration_profile(load_json(RESULT_LOG, []))
    pitcher_k, calibration_note = apply_calibration_adjustment(pitcher_k, calibration_profile, enabled=use_calibration)

    matchup_k = calculate_log5_k_rate(pitcher_k, lineup_k)
    ump_mult, ump_name = umpire_factor(row["game_pk"])
    park = park_k_factor(row.get("venue"))

    bf = leash["expected_bf"]
    bullpen_factor, bullpen_note = bullpen_workload_bf_factor(row.get("team_id"))
    bf = float(clamp(bf * bullpen_factor, 14, 31))
    batter_rates, simulation_source = build_pa_sequence(lineup_rows if lineup_locked else [], bf, lineup_k)
    sims, pa_probs = simulate_matchup(matchup_k, batter_rates, park=park, ump=ump_mult, sims=12000)

    mean = float(np.mean(sims))
    median = float(np.median(sims))
    p10 = float(np.percentile(sims, 10))
    p90 = float(np.percentile(sims, 90))

    sportsbook_data = get_sportsbook_k_data(row["home_team"], row["away_team"], pitcher_name)
    pp_data = get_prizepicks_k_data(pitcher_name)
    ud_data = get_underdog_k_data(pitcher_name)
    sgo_data = get_sportsgameodds_k_data(pitcher_name) if use_sgo else source_result("SportsGameOdds", "OFF", message="Optional source turned off")
    optic_data = get_opticodds_k_data(pitcher_name) if use_optic else source_result("OpticOdds", "OFF", message="Optional source turned off")

    active_line, active_source, consensus = choose_active_line(sportsbook_data, pp_data, ud_data, sgo_data, optic_data)

    # NOTE: CLV/line tracking updates on refresh because it tracks market movement.
    # Official pick history is only saved when you press "SAVE OFFICIAL BEFORE-GAME SNAPSHOT".
    line_delta = update_clv_snapshot(pitcher_name, active_source, active_line) if active_line is not None else None
    true_line_delta = track_line_delta(pitcher_name, active_source, active_line) if active_line is not None else None

    metrics = calculate_pick_metrics(sims, active_line)

    score = data_lock_score(
        lineup_locked=lineup_locked,
        pitcher_confirmed=row.get("pitcher_confirmed"),
        active_line=active_line,
        consensus_info=consensus,
        ppb=leash["ppb"],
        statcast_available=statcast_profile.get("available"),
        pitch_type_available=pitch_type_available
    )

    over_prob_raw = metrics.get("over_prob")
    over_prob = shrink_probability_to_market(over_prob_raw, score, lineup_locked, row.get("pitcher_confirmed")) if over_prob_raw is not None else None
    under_prob = 1 - over_prob if over_prob is not None else None

    if active_line is None:
        pick_side = "NO LINE"
        fair_prob = None
        price = None
        no_vig = None
        ev = None
        kelly = 0.0
        edge_pct = None
        gap = None
    else:
        pick_side = "OVER" if mean > active_line else "UNDER"
        fair_prob = over_prob if pick_side == "OVER" else under_prob
        price = default_odds
        priced_rows = []
        for src in [sportsbook_data, sgo_data, optic_data]:
            priced_rows.extend(src.get("rows", []))
        matching_priced = []
        for r in priced_rows:
            if safe_float(r.get("Line")) == safe_float(active_line) and pick_side in str(r.get("Side", "")).upper():
                matching_priced.append(r)
        if matching_priced:
            best = sorted(matching_priced, key=lambda x: expected_value(fair_prob, x.get("Price")) or -999)[-1]
            price = safe_float(best.get("Price"), default_odds)
            no_vig = paired_no_vig_probability(priced_rows, best)
        else:
            no_vig = american_to_implied(price)
        ev = expected_value(fair_prob, price)
        raw_kelly = kelly_fraction(fair_prob, price)
        kelly = min(raw_kelly, MAX_RECOMMENDED_KELLY)
        edge_pct = ((fair_prob - no_vig) * 100) if no_vig is not None and fair_prob is not None else None
        gap = abs(mean - active_line)

    risk_label, risk_notes = classify_risk(
        fair_prob,
        score,
        priced=(active_line is not None),
        edge_pct=edge_pct if edge_pct is not None else -999,
        gap=gap if gap is not None else 0,
        line_source=active_source
    )

    signal, signal_type = build_signal(mean, active_line, fair_prob or 0, ev, leash["ppb"], score)

    bettable, no_bet_reasons = no_bet_gate(
        active_line=active_line,
        pick_side=pick_side,
        fair_prob=fair_prob,
        ev=ev,
        gap=gap,
        score=score,
        lineup_locked=lineup_locked,
        pitcher_confirmed=row.get("pitcher_confirmed"),
        line_source=active_source,
        consensus_info=consensus,
        leash=leash,
    )

    if not bettable:
        signal_type = "pass"
        if pick_side in ["OVER", "UNDER"]:
            signal = f"PASS — {pick_side}"
        else:
            signal = "PASS"
        risk_notes = (risk_notes + "; " if risk_notes else "") + "No-bet gate: " + "; ".join(no_bet_reasons)

    prop_rows = []
    for src in [sportsbook_data, pp_data, ud_data, sgo_data, optic_data]:
        for r in src.get("rows", []):
            rr = dict(r)
            rr["Model Projection"] = round(mean, 2)
            line = safe_float(rr.get("Line"))
            if line is not None:
                raw_p = poisson_over_probability(mean, line)
                cal_p = shrink_probability_to_market(raw_p, score, lineup_locked, row.get("pitcher_confirmed"))
                lean = "OVER" if mean > line else "UNDER"
                lean_prob = cal_p if lean == "OVER" else 1 - cal_p
                rr["Model Lean"] = lean
                rr["Raw Model Prob %"] = round((raw_p if lean == "OVER" else 1 - raw_p) * 100, 1)
                rr["Model Prob %"] = round(lean_prob * 100, 1)
                rr["Hit Risk"], rr["Risk Notes"] = classify_risk(
                    lean_prob,
                    score,
                    priced=safe_float(rr.get("Price")) is not None,
                    edge_pct=0,
                    gap=abs(mean - line),
                    line_source=rr.get("Source")
                )
            rr["All Real"] = "YES"
            prop_rows.append(rr)

    pick_id = f"{row['date']}_{row['game_pk']}_{pid}_{active_line}_{active_source}"

    return {
        "pick_id": pick_id,
        "created_at": now_iso(),
        "date": row["date"],
        "game_pk": row["game_pk"],
        "game_time": row["game_time"],
        "status": row["status"],
        "venue": row.get("venue"),
        "pitcher_id": str(pid),
        "pitcher": pitcher_name,
        "hand": hand,
        "team": row["team"],
        "opponent": row["opponent"],
        "matchup": row["matchup"],
        "home_team": row["home_team"],
        "away_team": row["away_team"],
        "pitcher_confirmed": bool(row.get("pitcher_confirmed")),
        "lineup_locked": bool(lineup_locked),
        "lineup_note": lineup_msg,
        "pitcher_k": round(pitcher_k, 3),
        "pitcher_k_source": pitcher_k_source,
        "opp_k": round(lineup_k, 3),
        "simulation_source": simulation_source,
        "umpire": ump_name,
        "ump_factor": round(ump_mult, 3),
        "expected_bf": round(bf, 1),
        "ppb": round(leash["ppb"], 2),
        "leash_risk": leash.get("leash_risk"),
        "bullpen_bf_factor": round(safe_float(bullpen_factor, 1.0), 3),
        "bullpen_note": bullpen_note,
        "recent_ip": round(leash["recent_ip"], 2),
        "last_10_ks": leash["last_10_ks"],
        "projection": round(mean, 2),
        "median": round(median, 2),
        "p10": round(p10, 2),
        "p90": round(p90, 2),
        "learning_scale": round(learn_scale, 3),
        "line": active_line,
        "line_source": active_source,
        "line_delta": line_delta,
        "true_line_delta": true_line_delta,
        "consensus_count": consensus.get("count"),
        "consensus_quality": consensus.get("quality"),
        "consensus_spread": consensus.get("spread"),
        "leash_risk": leash.get("leash_risk"),
        "bettable": bettable,
        "no_bet_reasons": no_bet_reasons,
        "odds": price,
        "pick_side": pick_side,
        "over_probability": None if over_prob is None else round(over_prob, 4),
        "under_probability": None if under_prob is None else round(under_prob, 4),
        "fair_probability": None if fair_prob is None else round(fair_prob, 4),
        "edge_ks": None if active_line is None else round(mean - active_line, 2),
        "abs_edge": None if active_line is None else round(abs(mean - active_line), 2),
        "edge_pct": None if edge_pct is None else round(edge_pct, 2),
        "ev": None if ev is None else round(ev, 4),
        "kelly": round(kelly, 4),
        "bet_size": round(bankroll * kelly, 2),
        "data_score": score,
        "risk_label": risk_label,
        "risk_notes": risk_notes,
        "signal": signal,
        "signal_type": signal_type,
        "graded": False,
        "actual": None,
        "win": None,
        "statcast_available": statcast_profile.get("available"),
        "statcast_rows": statcast_profile.get("rows"),
        "statcast_csw": None if statcast_profile.get("csw") is None else round(statcast_profile.get("csw") * 100, 1),
        "statcast_whiff": None if statcast_profile.get("whiff") is None else round(statcast_profile.get("whiff") * 100, 1),
        "statcast_note": statcast_note,
        "pitch_type_matchup_available": pitch_type_available,
        "pitch_type_factor": round(safe_float(pitch_type_factor, 1.0), 3),
        "pitch_type_note": pitch_type_note,
        "calibration_note": calibration_note,
        "calibration_quality": calibration_profile.get("quality_score"),
        "calibration_samples": calibration_profile.get("samples"),
        "prop_rows": prop_rows,
        "lineup_rows": lineup_rows,
        "pitch_type_rows": pitch_type_rows,
        "source_status": {
            "sportsbook": sportsbook_data.get("status"),
            "prizepicks": pp_data.get("status"),
            "underdog": ud_data.get("status"),
            "sportsgameodds": sgo_data.get("status"),
            "opticodds": optic_data.get("status"),
        }
    }

def save_many_once(new_picks):
    picks = load_json(PICK_LOG, [])
    ids = set([p.get("pick_id") for p in picks])
    added = 0
    for p in new_picks:
        if p.get("pick_id") not in ids:
            official = dict(p)
            official["official_snapshot_saved_at"] = now_iso()
            official["snapshot_type"] = "OFFICIAL_BEFORE_GAME"
            official["official_quality_gate"] = "PASS" if official.get("data_score", 0) >= MIN_OFFICIAL_SAVE_SCORE else "LOW_DATA_REVIEW"
            picks.append(official)
            log_long_backtest_row(official)
            ids.add(p.get("pick_id"))
            added += 1
    save_json(PICK_LOG, picks[-10000:])
    return added

# =========================
# GRADING
# =========================
def is_game_final(game_pk):
    sched = safe_get_json(f"{MLB_BASE}/schedule", params={"sportId": 1, "gamePk": game_pk})
    try:
        games = (sched.get("dates") or [{}])[0].get("games") or []
        return bool(games and games[0].get("status", {}).get("abstractGameState") == "Final")
    except Exception:
        return False

def get_actual_pitcher_ks(game_pk, pitcher_id):
    box = safe_get_json(f"{MLB_BASE}/game/{game_pk}/boxscore")
    if not box:
        return None
    for side in ["home", "away"]:
        players = box.get("teams", {}).get(side, {}).get("players", {})
        for p in players.values():
            person = p.get("person", {})
            if str(person.get("id")) == str(pitcher_id):
                return p.get("stats", {}).get("pitching", {}).get("strikeOuts", None)
    return None

def grade_finished_games():
    picks = load_json(PICK_LOG, [])
    results = load_json(RESULT_LOG, [])
    result_ids = set([r.get("pick_id") for r in results])
    graded = 0
    for p in picks:
        if p.get("graded"):
            continue
        if not p.get("game_pk") or not p.get("pitcher_id"):
            continue
        if not is_game_final(p["game_pk"]):
            continue
        actual = get_actual_pitcher_ks(p["game_pk"], p["pitcher_id"])
        if actual is None:
            continue
        p["actual"] = actual
        p["graded"] = True
        p["graded_at"] = now_iso()
        line = safe_float(p.get("line"))
        side = p.get("pick_side")
        if line is not None and side in ["OVER", "UNDER"]:
            win = (actual > line) if side == "OVER" else (actual < line)
            p["win"] = bool(win)
            p["graded_result"] = "WIN" if win else "LOSS"
        else:
            p["win"] = None
            p["graded_result"] = "NO LINE"
        p["new_learning_scale"] = round(update_learning(p["pitcher_id"], p.get("projection"), actual), 3)
        if p.get("pick_id") not in result_ids:
            results.append(dict(p))
            result_ids.add(p.get("pick_id"))
        graded += 1
    save_json(PICK_LOG, picks[-10000:])
    save_json(RESULT_LOG, results[-10000:])
    return graded

def build_signal_tracking():
    results = load_json(RESULT_LOG, [])
    finished = [r for r in results if r.get("graded_result") in ["WIN", "LOSS"]]
    buckets = {}
    def add_bucket(key, row):
        if key not in buckets:
            buckets[key] = {"tag": key, "count": 0, "wins": 0}
        buckets[key]["count"] += 1
        buckets[key]["wins"] += 1 if row.get("graded_result") == "WIN" else 0
    for r in finished:
        tags = [
            f"side={r.get('pick_side')}",
            f"risk={r.get('risk_label')}",
            f"line_source={r.get('line_source')}",
            f"consensus={r.get('consensus_quality')}",
            f"lineup_locked={r.get('lineup_locked')}",
            f"statcast={r.get('statcast_available')}",
            f"pitch_type={r.get('pitch_type_matchup_available')}",
            f"data_score={int((r.get('data_score') or 0)//10)*10}s",
        ]
        for tag in tags:
            add_bucket(tag, r)
    rows = []
    for v in buckets.values():
        count = v["count"]
        wins = v["wins"]
        rows.append({"Signal Tag": v["tag"], "Samples": count, "Wins": wins, "Win Rate": round(wins / count * 100, 1) if count else 0})
    df = pd.DataFrame(rows).sort_values(["Samples", "Win Rate"], ascending=[False, False]) if rows else pd.DataFrame()
    save_json(SIGNAL_TRACKING_FILE, rows)
    return df

# =========================
# RENDERING
# =========================
def render_kpis(picks, bankroll):
    valid = [p for p in picks if p.get("ev") is not None]
    best = sorted(valid, key=lambda x: x.get("ev", -999), reverse=True)[0] if valid else None
    real_line_count = len([p for p in picks if p.get("line") is not None])
    strong_count = len([p for p in picks if p.get("signal_type") == "good"])
    no_line_count = len([p for p in picks if p.get("line") is None])
    statcast_count = len([p for p in picks if p.get("statcast_available")])
    pitch_type_count = len([p for p in picks if p.get("pitch_type_matchup_available")])
    st.markdown(f"""
    <div class="kpi-strip">
      <div class="kpi-box"><div class="kpi-label">Board Rows</div><div class="kpi-value">{len(picks)}</div><div class="kpi-sub">Current screen</div></div>
      <div class="kpi-box"><div class="kpi-label">Real Lines</div><div class="kpi-value green">{real_line_count}</div><div class="kpi-sub">No fake prop lines</div></div>
      <div class="kpi-box"><div class="kpi-label">No Line</div><div class="kpi-value orange">{no_line_count}</div><div class="kpi-sub">Projection only</div></div>
      <div class="kpi-box"><div class="kpi-label">Strong Signals</div><div class="kpi-value green">{strong_count}</div><div class="kpi-sub">Strict gates</div></div>
      <div class="kpi-box"><div class="kpi-label">Statcast</div><div class="kpi-value">{statcast_count}/{len(picks)}</div><div class="kpi-sub">Pitch-type {pitch_type_count}</div></div>
      <div class="kpi-box"><div class="kpi-label">Bankroll</div><div class="kpi-value green">${bankroll:,.0f}</div><div class="kpi-sub">{california_now().strftime('%I:%M %p PT')}</div></div>
    </div>
    """, unsafe_allow_html=True)
    if best:
        st.markdown(f"""
        <div class="green-card">
          <div class="small-muted">Best EV Play On Current Board</div>
          <div class="big-number green">{best.get('signal')}</div>
          <div>{best.get('pitcher')} — {best.get('pick_side')} {best.get('line')} Ks | EV {round((best.get('ev') or 0)*100,2)}% | Data {best.get('data_score')}/100</div>
        </div>
        """, unsafe_allow_html=True)

def render_pick_card(p):
    prob = p.get("fair_probability")
    prob_pct = int(round(prob * 100)) if prob is not None else 0
    progress_width = max(3, min(100, prob_pct))
    risk = p.get("risk_label", "")
    signal_type = p.get("signal_type", "pass")
    if "85" in risk or signal_type == "good":
        color_class, progress_class, badge = "green", "progress-green", "good-badge"
    elif "PASS" in risk or "NO" in risk:
        color_class, progress_class, badge = "red", "progress-red", "red-badge"
    else:
        color_class, progress_class, badge = "orange", "progress-orange", "yellow-badge"
    line_display = p.get("line") if p.get("line") is not None else "NO REAL LINE"
    edge_display = p.get("edge_ks") if p.get("edge_ks") is not None else "—"
    ev_display = f"{(p.get('ev') or 0)*100:.2f}%" if p.get("ev") is not None else "—"
    prob_display = f"{prob_pct}%" if prob is not None else "—"
    # Render-safe Last 10 K bars.
    # NOTE: this avoids standalone raw HTML ever being printed by Streamlit/tunnel caching.
    # The full card below is still rendered with unsafe_allow_html=True.
    bars = "<span class='small-muted'>No recent K log</span>"
    last_ks = p.get("last_10_ks", []) or []
    if last_ks:
        max_k = max(max([safe_int(x, 0) or 0 for x in last_ks]), 1)
        bar_parts = []
        for k_raw in last_ks[:10]:
            k = safe_int(k_raw, 0) or 0
            h = int(20 + (k / max_k) * 42)
            bar_parts.append(
                f"<span class='mini-k-bar-wrap'>"
                f"<span class='mini-k-bar' style='height:{h}px;'></span>"
                f"<span class='mini-k-label'>{k}</span>"
                f"</span>"
            )
        bars = "<div class='mini-k-bars'>" + "".join(bar_parts) + "</div>"
    statcast_txt = "YES" if p.get("statcast_available") else "NO"
    pitch_type_txt = "YES" if p.get("pitch_type_matchup_available") else "NO"
    st.markdown(f"""
    <div class="pick-card">
      <div style="display:grid;grid-template-columns:1.3fr .8fr .9fr 1fr 1fr;gap:18px;align-items:center;">
        <div>
          <div class="player-name">{p.get('pitcher')}</div>
          <div class="small-muted">{p.get('matchup')} | {p.get('hand')}HP</div>
          <div class="small-muted">{p.get('team')} vs {p.get('opponent')}</div>
          <span class="badge {badge}">{p.get('risk_label')}</span>
          <span class="badge">{p.get('line_source')}</span>
        </div>
        <div><div class="small-muted">Projection</div><div class="big-number {color_class}">{p.get('projection')}</div><div class="small-muted">BF {p.get('expected_bf')} | PPB {p.get('ppb')}</div></div>
        <div><div class="small-muted">Line</div><div class="big-number">{line_display}</div><div class="small-muted">Edge: {edge_display} K</div></div>
        <div>
          <div class="small-muted">Pick</div><div class="big-number {color_class}">{p.get('pick_side')}</div>
          <div class="small-muted">Fair Prob</div><div class="{color_class}" style="font-size:26px;font-weight:900;">{prob_display}</div>
          <div class="progress-wrap"><div class="{progress_class}" style="width:{progress_width}%;"></div></div>
        </div>
        <div>
          <div class="small-muted">Signal</div><div class="{color_class}" style="font-size:20px;font-weight:950;">{p.get('signal')}</div>
          <div class="small-muted" style="margin-top:8px;">EV</div><div style="font-size:22px;font-weight:900;">{ev_display}</div>
          <div class="small-muted">Bet Size</div><div style="font-size:22px;font-weight:900;">${p.get('bet_size')}</div>
        </div>
      </div>
      <div class="hr-soft"></div>
      <div style="display:grid;grid-template-columns:.7fr .7fr .7fr .7fr .7fr .7fr 2.2fr;gap:14px;align-items:end;">
        <div><div class="small-muted">Data Score</div><div style="font-size:22px;font-weight:900;">{p.get('data_score')}/100</div></div>
        <div><div class="small-muted">Pitcher K%</div><div style="font-size:22px;font-weight:900;">{p.get('pitcher_k')}</div></div>
        <div><div class="small-muted">Opp K%</div><div style="font-size:22px;font-weight:900;">{p.get('opp_k')}</div></div>
        <div><div class="small-muted">Statcast</div><div style="font-size:22px;font-weight:900;">{statcast_txt}</div></div>
        <div><div class="small-muted">Pitch-Type</div><div style="font-size:22px;font-weight:900;">{pitch_type_txt}</div></div>
        <div><div class="small-muted">CLV Δ</div><div style="font-size:22px;font-weight:900;">{p.get('line_delta')}</div></div>
        <div><div class="small-muted">Last 10 Ks</div>{bars}</div>
      </div>
      <div class="small-muted" style="margin-top:12px;">Risk Notes: {p.get('risk_notes')}</div>
      <div class="small-muted">Statcast: {p.get('statcast_note')} | Pitch Type: {p.get('pitch_type_note')} | Calibration: {p.get('calibration_note')}</div>
    </div>
    """, unsafe_allow_html=True)

# =========================
# APP
# =========================
st.markdown("""
<div class="hero-panel">
  <div class="big-title">🔥 MLB STRIKEOUT PROP ENGINE v9.6 FIXED</div>
  <div class="sub-title">Safety Lock: strict no-bet gates, slower learning, leash risk, real lines only → Refresh → Save → Grade</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Controls")
    day_mode = st.radio("Game Feed", ["Today + Tomorrow", "Today", "Tomorrow"], index=0)
    bankroll = st.number_input("Bankroll", min_value=1.0, value=1000.0, step=50.0)
    default_odds = st.number_input("Default Odds if sportsbook price missing", value=-110.0, step=5.0)
    hide_no_line = st.checkbox("Hide No Real Line picks", value=False)
    only_strong = st.checkbox("Show only strong signals", value=False)
    st.divider()
    st.header("Model Upgrades")
    use_statcast = st.checkbox("Use Statcast pitcher CSW/whiff", value=True)
    use_pitch_type = st.checkbox("Use pitch-type whiff mix", value=True)
    use_calibration = st.checkbox("Use historical calibration", value=True)
    use_sgo = st.checkbox("Optional: SportsGameOdds API", value=False)
    use_optic = st.checkbox("Optional: OpticOdds API", value=False)
    st.caption("Refresh does not save official picks. Save only when the board looks right. Optional paid APIs stay OFF unless you have keys.")

dates = target_dates(day_mode)

if "loaded_picks" not in st.session_state:
    st.session_state.loaded_picks = []
if "last_refresh_time" not in st.session_state:
    st.session_state.last_refresh_time = None
if "last_saved_count" not in st.session_state:
    st.session_state.last_saved_count = 0

col_refresh, col_save = st.columns(2)

with col_refresh:
    refresh_btn = st.button("🔄 REFRESH LIVE BOARD — Do Not Save Yet", use_container_width=True)

with col_save:
    save_btn = st.button("💾 SAVE OFFICIAL BEFORE-GAME SNAPSHOT", use_container_width=True)

if refresh_btn:
    all_rows = []
    for d in dates:
        all_rows.extend(extract_probable_pitchers(d))

    projections = []
    progress = st.progress(0)

    for i, row in enumerate(all_rows):
        try:
            projections.append(
                make_projection(
                    row,
                    bankroll=bankroll,
                    default_odds=default_odds,
                    use_statcast=use_statcast,
                    use_pitch_type=use_pitch_type,
                    use_calibration=use_calibration,
                    use_sgo=use_sgo,
                    use_optic=use_optic
                )
            )
        except Exception as e:
            log_source_request("make_projection", "ERROR", f"{row.get('pitcher')}: {e}")
        progress.progress((i + 1) / max(1, len(all_rows)))

    st.session_state.loaded_picks = projections
    st.session_state.last_refresh_time = now_iso()
    st.success(f"Refreshed {len(projections)} pitchers. Nothing officially saved yet.")

if save_btn:
    if not st.session_state.get("loaded_picks"):
        st.warning("Refresh the live board first, inspect the lines, then save the official before-game snapshot.")
    else:
        added = save_many_once(st.session_state.loaded_picks)
        st.session_state.last_saved_count = added
        st.success(f"Saved official before-game snapshot. Added {added} new rows.")

saved = load_json(PICK_LOG, [])

# IMPORTANT:
# - If you have refreshed this session, the screen shows refreshed live board.
# - If not, it shows saved official snapshots for the selected dates.
if st.session_state.get("loaded_picks"):
    board = st.session_state.loaded_picks
    board_status = "LIVE REFRESHED BOARD — NOT OFFICIAL UNLESS SAVED"
else:
    board = [p for p in saved if p.get("date") in dates]
    board_status = "SAVED OFFICIAL SNAPSHOTS"

if hide_no_line:
    board = [p for p in board if p.get("line") is not None]
if only_strong:
    board = [p for p in board if p.get("signal_type") == "good"]

st.info(f"{board_status} | Last refresh: {st.session_state.get('last_refresh_time') or 'Not refreshed this session'} | Last save added: {st.session_state.get('last_saved_count', 0)}")

render_kpis(board, bankroll)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "TOP PLAYS",
    "ALL PLAYERS",
    "REAL PROP BOARD",
    "STATCAST",
    "AFTER GAMES / LEARNING",
    "SETTINGS"
])

with tab1:
    st.markdown('<div class="section-title-pro">Top Plays</div>', unsafe_allow_html=True)
    if not board:
        st.info("Click 🔄 Refresh Live Board first.")
    else:
        top = sorted(
            board,
            key=lambda x: (
                x.get("signal_type") == "good",
                x.get("ev") if x.get("ev") is not None else -999,
                x.get("fair_probability") if x.get("fair_probability") is not None else 0
            ),
            reverse=True
        )
        for p in top:
            render_pick_card(p)

with tab2:
    st.markdown('<div class="section-title-pro">All Players</div>', unsafe_allow_html=True)
    if board:
        show = pd.DataFrame([{k: v for k, v in p.items() if k not in ["prop_rows", "lineup_rows", "pitch_type_rows"]} for p in board])
        cols = [
            "date", "pitcher", "matchup", "hand", "projection", "line", "pick_side",
            "fair_probability", "edge_ks", "ev", "signal", "risk_label",
            "line_source", "data_score", "lineup_locked", "pitcher_confirmed",
            "statcast_available", "pitch_type_matchup_available", "pitch_type_factor", "bettable", "leash_risk"
        ]
        cols = [c for c in cols if c in show.columns]
        st.dataframe(show[cols], use_container_width=True, hide_index=True)
    else:
        st.info("No players loaded.")

with tab3:
    st.markdown('<div class="section-title-pro">Real Prop Rows From Sources</div>', unsafe_allow_html=True)
    rows = []
    for p in board:
        for r in p.get("prop_rows", []):
            rr = dict(r)
            rr["Pitcher"] = p.get("pitcher")
            rr["Projection"] = p.get("projection")
            rr["Data Score"] = p.get("data_score")
            rows.append(rr)
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.warning("No real prop rows found from connected sources yet. No fake line is created.")

with tab4:
    st.markdown('<div class="section-title-pro">Statcast + Pitch-Type</div>', unsafe_allow_html=True)
    if board:
        stat_rows = []
        pitch_rows = []
        lineup_rows = []
        for p in board:
            stat_rows.append({
                "Pitcher": p.get("pitcher"),
                "Statcast Available": p.get("statcast_available"),
                "Statcast Rows": p.get("statcast_rows"),
                "CSW%": p.get("statcast_csw"),
                "Whiff%": p.get("statcast_whiff"),
                "Pitch-Type Available": p.get("pitch_type_matchup_available"),
                "Pitch-Type Factor": p.get("pitch_type_factor"),
                "Pitch-Type Note": p.get("pitch_type_note"),
            })
            for r in p.get("pitch_type_rows", []):
                rr = dict(r)
                rr["Pitcher"] = p.get("pitcher")
                pitch_rows.append(rr)
            for r in p.get("lineup_rows", []):
                rr = dict(r)
                rr["Pitcher"] = p.get("pitcher")
                rr["Matchup"] = p.get("matchup")
                lineup_rows.append(rr)
        st.subheader("Pitcher Statcast Summary")
        st.dataframe(pd.DataFrame(stat_rows), use_container_width=True, hide_index=True)
        st.subheader("Pitch-Type Rows")
        if pitch_rows:
            st.dataframe(pd.DataFrame(pitch_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No pitch-type rows loaded yet.")
        st.subheader("Lineup Batter K Inputs")
        if lineup_rows:
            st.dataframe(pd.DataFrame(lineup_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No posted lineup rows loaded yet.")
    else:
        st.info("Load the board first.")

with tab5:
    st.markdown('<div class="section-title-pro">After Games — Grade + Learn</div>', unsafe_allow_html=True)
    if st.button("✅ AFTER GAMES — Grade Results + Update Learning", use_container_width=True):
        graded = grade_finished_games()
        st.success(f"Graded {graded} finished official snapshots and updated learning.")
    results = load_json(RESULT_LOG, [])
    if results:
        df = pd.DataFrame(results)
        finished = df[df["graded_result"].isin(["WIN", "LOSS"])] if "graded_result" in df.columns else pd.DataFrame()
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Graded", len(finished))
        if not finished.empty:
            c2.metric("Win Rate", f"{(finished['graded_result'].eq('WIN').mean()*100):.1f}%")
            c3.metric("Avg EV", f"{(finished['ev'].dropna().mean()*100 if 'ev' in finished.columns and not finished['ev'].dropna().empty else 0):.2f}%")
            c4.metric("Avg Edge", f"{(finished['abs_edge'].dropna().mean() if 'abs_edge' in finished.columns and not finished['abs_edge'].dropna().empty else 0):.2f}")
            cal = build_model_calibration_profile(results)
            c5.metric("Calibration", f"{cal.get('quality_score', 0)}/100")
        else:
            c2.metric("Win Rate", "N/A")
            c3.metric("Avg EV", "N/A")
            c4.metric("Avg Edge", "N/A")
            c5.metric("Calibration", "N/A")
        st.dataframe(df.tail(200), use_container_width=True)
        st.markdown('<div class="section-title-pro">Signal Tracking</div>', unsafe_allow_html=True)
        sig = build_signal_tracking()
        if not sig.empty:
            st.dataframe(sig, use_container_width=True, hide_index=True)
        else:
            st.info("Signal tracking starts after graded wins/losses.")
    else:
        st.info("No graded history yet. Save official snapshots before games, then grade after games finish.")

with tab6:
    st.markdown('<div class="section-title-pro">Settings / Saved Files</div>', unsafe_allow_html=True)
    st.code(STORAGE_DIR)
    st.write("Pick Log:")
    st.code(PICK_LOG)
    st.write("Result Log:")
    st.code(RESULT_LOG)
    st.write("Learning File:")
    st.code(LEARN_FILE)
    st.write("CLV File:")
    st.code(CLV_FILE)
    st.write("Long Backtest File:")
    st.code(LONG_BACKTEST_FILE)
    st.subheader("Source Status")
    if board:
        src_rows = []
        for p in board:
            rr = {"Pitcher": p.get("pitcher")}
            rr.update(p.get("source_status", {}))
            src_rows.append(rr)
        st.dataframe(pd.DataFrame(src_rows), use_container_width=True, hide_index=True)
    req = load_json(REQUEST_LOG_FILE, [])
    if req:
        st.subheader("Recent Source Requests / Errors")
        st.dataframe(pd.DataFrame(req).tail(75), use_container_width=True)
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("Clear Current Date-Range Official Snapshots"):
            picks = load_json(PICK_LOG, [])
            picks = [p for p in picks if p.get("date") not in dates]
            save_json(PICK_LOG, picks)
            st.warning("Cleared current date-range official snapshots.")
    with col_b:
        if st.button("Clear Request Logs"):
            save_json(REQUEST_LOG_FILE, [])
            st.warning("Request logs cleared.")
    with col_c:
        if st.button("Clear ALL Logs"):
            save_json(PICK_LOG, [])
            save_json(RESULT_LOG, [])
            save_json(LEARN_FILE, {})
            save_json(CLV_FILE, {})
            save_json(SIGNAL_TRACKING_FILE, [])
            save_json(LONG_BACKTEST_FILE, [])
            save_json(LINE_HISTORY_FILE, {})
            save_json(LINEUP_CACHE_FILE, {})
            st.error("All logs cleared.")

st.caption("Workflow: Refresh live board → inspect lines → save official before-game snapshot → after games, grade and learn.")
