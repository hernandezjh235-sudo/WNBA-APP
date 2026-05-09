# -*- coding: utf-8 -*-
# ============================================================
# DEVIL PICKS — WNBA FULL MARKET + PLAYER PROP ENGINE — ONE FILE v1.0
# Streamlit + Colab ready
# Moneyline + Spread + Totals + Player Props
# Refresh first, save official snapshots, grade after games, persistent learning.
# ============================================================

import os
import json
from collections import defaultdict
import math
import time
import difflib
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st

try:
    import pytz
except Exception:
    pytz = None

# ============================================================
# STORAGE
# ============================================================
DRIVE_DIR = "/content/drive/MyDrive/devil_picks_wnba"
LOCAL_DIR = "devil_picks_wnba"

try:
    from google.colab import drive
    if not os.path.exists("/content/drive/MyDrive"):
        drive.mount("/content/drive", force_remount=False)
    os.makedirs(DRIVE_DIR, exist_ok=True)
    STORAGE_DIR = DRIVE_DIR
except Exception:
    os.makedirs(LOCAL_DIR, exist_ok=True)
    STORAGE_DIR = LOCAL_DIR

MARKET_PICK_LOG = os.path.join(STORAGE_DIR, "wnba_market_pick_log.json")
MARKET_RESULT_LOG = os.path.join(STORAGE_DIR, "wnba_market_result_log.json")
MARKET_LEARN_FILE = os.path.join(STORAGE_DIR, "wnba_market_learning.json")
PROP_PICK_LOG = os.path.join(STORAGE_DIR, "wnba_prop_pick_log.json")
PROP_RESULT_LOG = os.path.join(STORAGE_DIR, "wnba_prop_result_log.json")
PROP_LEARN_FILE = os.path.join(STORAGE_DIR, "wnba_prop_learning.json")
CLV_FILE = os.path.join(STORAGE_DIR, "wnba_clv.json")
REQUEST_LOG_FILE = os.path.join(STORAGE_DIR, "request_log.json")
MARKET_SNAPSHOT_FILE = os.path.join(STORAGE_DIR, "latest_market_board.json")
PROP_SNAPSHOT_FILE = os.path.join(STORAGE_DIR, "latest_prop_board.json")

# ============================================================
# API / CONSTANTS
# ============================================================
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"
ESPN_SUMMARY = "https://site.web.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"
ODDS_BASE = "https://api.the-odds-api.com/v4"
SPORT_KEY = "basketball_wnba"

WNBA_ABBR_TO_NAME = {
    "ATL": "Atlanta Dream",
    "CHI": "Chicago Sky",
    "CONN": "Connecticut Sun",
    "DAL": "Dallas Wings",
    "GS": "Golden State Valkyries",
    "IND": "Indiana Fever",
    "LA": "Los Angeles Sparks",
    "LV": "Las Vegas Aces",
    "MIN": "Minnesota Lynx",
    "NY": "New York Liberty",
    "PHX": "Phoenix Mercury",
    "SEA": "Seattle Storm",
    "WAS": "Washington Mystics",
}
NAME_TO_ABBR = {v.lower(): k for k, v in WNBA_ABBR_TO_NAME.items()}

DEFAULT_HOME_COURT = 1.7
DEFAULT_TOTAL = 162.5
DEFAULT_SPREAD = 0.0
DEFAULT_ODDS = -110
MAX_KELLY = 0.025

MIN_MARKET_EDGE_PROB = 0.030
MIN_MARKET_DATA_SCORE = 72
MIN_MARKET_BET_SCORE = 80

MIN_PROP_EDGE = {
    "PTS": 1.8,
    "REB": 1.2,
    "AST": 1.1,
    "PRA": 2.8,
    "PR": 2.3,
    "PA": 2.4,
    "RA": 1.8,
    "3PM": 0.55,
}
MIN_PROP_PROB = 0.58
MIN_PROP_DATA_SCORE = 74
MIN_PROP_BET_SCORE = 80

MARKET_SIMS = 18000
PROP_SIMS = 10000


PACE_BASE = 79.5
PACE_WEIGHT = 0.42
REST_ADVANTAGE = 1.1
BACK_TO_BACK_PENALTY = -1.8

BLOWOUT_SPREAD_THRESHOLD = 11
BLOWOUT_MINUTES_REDUCTION = 2

MAX_PROP_EDGE = 7.0
MAX_PROP_PROB = 0.80

POSITION_DEFENSE_WEIGHTS = {
    "G": {"PTS": 1.00, "AST": 1.08, "3PM": 1.10},
    "W": {"PTS": 1.02, "REB": 0.96, "3PM": 1.04},
    "F": {"PTS": 1.01, "REB": 1.05, "PRA": 1.03},
    "C": {"REB": 1.12, "PTS": 0.97, "RA": 1.08},
}

PROP_CONFIG = {
    "PTS": {"label": "Points", "markets": ["player_points"], "default_std": 5.8},
    "REB": {"label": "Rebounds", "markets": ["player_rebounds"], "default_std": 3.2},
    "AST": {"label": "Assists", "markets": ["player_assists"], "default_std": 2.8},
    "PRA": {"label": "PRA", "markets": ["player_points_rebounds_assists"], "default_std": 7.5},
    "PR": {"label": "Points + Rebounds", "markets": ["player_points_rebounds"], "default_std": 6.7},
    "PA": {"label": "Points + Assists", "markets": ["player_points_assists"], "default_std": 6.5},
    "RA": {"label": "Rebounds + Assists", "markets": ["player_rebounds_assists"], "default_std": 4.8},
    "3PM": {"label": "3PM", "markets": ["player_threes"], "default_std": 1.25},
}

# ============================================================
# SECRETS
# ============================================================
def get_secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

ODDS_API_KEY = get_secret("ODDS_API_KEY", "")

# ============================================================
# PAGE + UI
# ============================================================
st.set_page_config(page_title="Devil Picks — WNBA Engine", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root {--red:#ff344f; --green:#38f063; --orange:#ffb02e; --bg:#050812; --panel:#0b1220; --muted:#aeb7c9;}
.stApp {background: radial-gradient(circle at top left,#230012 0%,#070b13 38%,#02040a 100%); color:#f7f8fb;}
.block-container {padding-top:1rem; max-width:1600px;}
section[data-testid="stSidebar"] {background:linear-gradient(180deg,#050912,#02040a); border-right:1px solid rgba(255,52,79,.28);}
h1,h2,h3 {color:#fff;}
.hero {border:1px solid rgba(255,255,255,.16); background:linear-gradient(135deg,rgba(12,19,34,.96),rgba(5,8,18,.96)); border-radius:22px; padding:22px; box-shadow:0 0 32px rgba(255,52,79,.10); margin-bottom:16px;}
.logo-title {font-size:30px; font-weight:950; letter-spacing:-.5px;}
.sub {color:#aeb7c9; font-size:13px;}
.card {border:1px solid rgba(255,255,255,.14); background:linear-gradient(145deg,#0a111f,#080d18); border-radius:18px; padding:18px; box-shadow:0 0 22px rgba(0,0,0,.28); margin-bottom:14px;}
.card-red {border:1px solid rgba(255,52,79,.55); background:linear-gradient(145deg,rgba(80,10,22,.85),rgba(8,13,24,.94)); border-radius:18px; padding:18px; box-shadow:0 0 24px rgba(255,52,79,.15); margin-bottom:14px;}
.card-green {border:1px solid rgba(56,240,99,.45); background:linear-gradient(145deg,rgba(0,42,18,.70),rgba(8,13,24,.94)); border-radius:18px; padding:18px; box-shadow:0 0 24px rgba(56,240,99,.14); margin-bottom:14px;}
.card-orange {border:1px solid rgba(255,176,46,.45); background:linear-gradient(145deg,rgba(54,32,0,.70),rgba(8,13,24,.94)); border-radius:18px; padding:18px; box-shadow:0 0 24px rgba(255,176,46,.12); margin-bottom:14px;}
.metric-grid {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:10px 0 16px 0;}
.metric-box {border:1px solid rgba(255,255,255,.14); background:linear-gradient(145deg,#0a111f,#080d18); border-radius:16px; padding:14px; min-height:88px;}
.metric-label {font-size:12px; color:#aeb7c9; text-transform:uppercase; font-weight:800; letter-spacing:.05em;}
.metric-value {font-size:28px; color:#fff; font-weight:950; margin-top:5px;}
.metric-sub {font-size:12px; color:#aeb7c9; margin-top:4px;}
.team-row {display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:20px;}
.team-name {font-size:26px; font-weight:950;}
.team-record {color:#aeb7c9; font-size:13px;}
.vs-pill {border:1px solid rgba(255,255,255,.18); padding:10px 16px; border-radius:999px; color:#dce4f5; font-weight:900; background:#0a111f; text-align:center;}
.big-prob {font-size:44px; font-weight:950; line-height:1;}
.green {color:#38f063;} .red {color:#ff344f;} .orange {color:#ffb02e;} .muted {color:#aeb7c9;}
.badge {display:inline-block; padding:7px 12px; border-radius:999px; font-weight:900; font-size:12px; margin:3px 5px 3px 0; border:1px solid rgba(255,255,255,.18); background:#101827; color:#dce4f5;}
.badge-green {background:#002c16; border-color:rgba(56,240,99,.55); color:#b9ffd0;}
.badge-red {background:#3a0710; border-color:rgba(255,52,79,.55); color:#ffc2cb;}
.badge-orange {background:#362000; border-color:rgba(255,176,46,.55); color:#ffe1a3;}
.section-title {font-size:22px; font-weight:950; margin:18px 0 10px; border-left:5px solid #ff344f; padding-left:12px;}
[data-testid="stMetric"] {background:#0a111f; border:1px solid rgba(255,255,255,.14); border-radius:16px; padding:14px;}
.stButton button {border-radius:14px; font-weight:900; border:1px solid rgba(255,255,255,.18);}
.stTabs [data-baseweb="tab"] {color:#b8c3cf; font-weight:900;}
.stTabs [aria-selected="true"] {color:#ff344f!important; border-bottom:3px solid #ff344f;}
@media (max-width: 1100px) {.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.team-row{grid-template-columns:1fr; text-align:center;}}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HELPERS
# ============================================================
def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def eastern_now():
    if pytz:
        return datetime.now(pytz.timezone("America/New_York"))
    return datetime.utcnow() - timedelta(hours=5)

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
    """Atomic JSON save with a backup copy. Safer on Streamlit Cloud restarts."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        bak = path + ".bak"
        if os.path.exists(path):
            try:
                with open(path, "r") as src, open(bak, "w") as dst:
                    dst.write(src.read())
            except Exception:
                pass
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass

def log_request(source, status, message=""):
    rows = load_json(REQUEST_LOG_FILE, [])
    rows.append({"time": now_iso(), "source": str(source)[:180], "status": str(status)[:80], "message": str(message)[:350]})
    save_json(REQUEST_LOG_FILE, rows[-500:])

def normalize_name(name):
    s = str(name or "").lower().strip()
    for ch in [".", ",", "'", "-", "_", "  "]:
        s = s.replace(ch, " ")
    return " ".join(s.split())

def name_score(a, b):
    a, b = normalize_name(a), normalize_name(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.94
    return difflib.SequenceMatcher(None, a, b).ratio()

@st.cache_data(ttl=240, show_spinner=False)
def safe_get_json(url, params=None, headers=None, timeout=18):
    try:
        h = {
            "User-Agent": "Mozilla/5.0 DevilPicksWNBA/1.0",
            "Accept": "application/json,text/plain,*/*",
        }
        if headers:
            h.update(headers)
        r = requests.get(url, params=params, headers=h, timeout=timeout)
        if r.status_code != 200:
            log_request(url, f"HTTP {r.status_code}", r.text[:250])
            return None
        return r.json()
    except Exception as e:
        log_request(url, "REQUEST_ERROR", str(e))
        return None

def american_to_implied(price):
    price = safe_float(price)
    if price is None:
        return None
    return 100/(price+100) if price > 0 else abs(price)/(abs(price)+100)

def decimal_odds(odds):
    odds = safe_float(odds)
    if odds is None:
        return None
    return 1 + odds/100 if odds > 0 else 1 + 100/abs(odds)

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
    if b <= 0:
        return 0.0
    q = 1 - prob
    return float(clamp(((b * prob) - q) / b, 0, MAX_KELLY))

def odds_display(o):
    o = safe_float(o)
    if o is None:
        return "N/A"
    return f"+{int(o)}" if o > 0 else str(int(o))

def price_to_market_prob(price):
    imp = american_to_implied(price)
    return imp if imp is not None else 0.50

def side_class(side):
    if side in ["OVER", "UNDER", "BET", "LEAN"]:
        return "green"
    if side == "PASS":
        return "orange"
    return ""


@st.cache_data(ttl=3600, show_spinner=False)
def build_minutes_projection(player, prop, game_context=None):
    base_minutes = 28
    elite_players = [
        "aja wilson","breanna stewart","napheesa collier",
        "caitlin clark","sabrina ionescu","jackie young",
        "kahleah copper","jewell loyd"
    ]
    key = normalize_name(player)
    if any(x in key for x in elite_players):
        base_minutes += 6

    if game_context:
        spread = abs(safe_float(game_context.get("projected_home_margin"), 0) or 0)
        if spread >= BLOWOUT_SPREAD_THRESHOLD:
            base_minutes -= BLOWOUT_MINUTES_REDUCTION

    return clamp(base_minutes, 18, 40)

def build_pace_projection(home_team, away_team, home_rating, away_rating):
    rating_factor = ((home_rating + away_rating) / 2) * PACE_WEIGHT
    projected_pace = PACE_BASE + rating_factor
    return clamp(projected_pace, 74, 90)

def get_player_position(player_name):
    name = normalize_name(player_name)

    guards = ["clark","ionescu","loyd","young","diggins"]
    wings = ["plum","mitchell","cloud"]
    forwards = ["stewart","collier","bonner"]
    centers = ["wilson","griner","cardoso"]

    if any(x in name for x in guards):
        return "G"
    if any(x in name for x in wings):
        return "W"
    if any(x in name for x in forwards):
        return "F"
    if any(x in name for x in centers):
        return "C"

    return "W"

def confidence_tier(prob, edge, ev_val):
    score = 0
    score += prob * 100
    score += edge * 4
    score += max(ev_val or 0, 0) * 100

    if score >= 82:
        return "ELITE"
    if score >= 72:
        return "HIGH"
    if score >= 62:
        return "MEDIUM"
    return "LOW"

def clv_quality_score(clv):
    clv = safe_float(clv, 0) or 0

    if clv >= 2:
        return "ELITE"
    if clv >= 1:
        return "GOOD"
    if clv >= 0:
        return "NEUTRAL"
    return "NEGATIVE"


# ============================================================
# WNBA DATA
# ============================================================
def date_for_mode(day_mode):
    now = eastern_now()
    if day_mode == "Tomorrow":
        now += timedelta(days=1)
    return now.strftime("%Y-%m-%d")

def espn_date(date_str):
    return date_str.replace("-", "")

def canonical_abbr(abbr, name=""):
    a = str(abbr or "").upper().strip()
    if a in WNBA_ABBR_TO_NAME:
        return a
    n = normalize_name(name)
    for team_name, short in NAME_TO_ABBR.items():
        if team_name in n or n in team_name:
            return short
    if a == "CON":
        return "CONN"
    if a == "LAS":
        return "LV"
    if a == "LOS":
        return "LA"
    return a or name[:3].upper()

@st.cache_data(ttl=180, show_spinner=False)
def get_wnba_scoreboard(date_str):
    data = safe_get_json(ESPN_SCOREBOARD, params={"dates": espn_date(date_str), "limit": 100})
    return data or {"events": []}

def extract_games(date_str):
    data = get_wnba_scoreboard(date_str)
    rows = []
    for ev in data.get("events", []) or []:
        comp = (ev.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []
        home_c = None
        away_c = None
        for c in competitors:
            if c.get("homeAway") == "home":
                home_c = c
            elif c.get("homeAway") == "away":
                away_c = c
        if not home_c or not away_c:
            continue
        ht = home_c.get("team") or {}
        at = away_c.get("team") or {}
        home_abbr = canonical_abbr(ht.get("abbreviation"), ht.get("displayName") or ht.get("name"))
        away_abbr = canonical_abbr(at.get("abbreviation"), at.get("displayName") or at.get("name"))
        rows.append({
            "date": date_str,
            "game_id": str(ev.get("id") or comp.get("id") or f"{date_str}_{away_abbr}_{home_abbr}"),
            "status": ((comp.get("status") or {}).get("type") or {}).get("description") or ev.get("status", {}).get("type", {}).get("description") or "Scheduled",
            "status_state": ((comp.get("status") or {}).get("type") or {}).get("state") or "",
            "game_time": ev.get("date") or comp.get("date") or "",
            "arena": ((comp.get("venue") or {}).get("fullName")) or "",
            "home": home_abbr, "away": away_abbr,
            "home_name": ht.get("displayName") or WNBA_ABBR_TO_NAME.get(home_abbr, home_abbr),
            "away_name": at.get("displayName") or WNBA_ABBR_TO_NAME.get(away_abbr, away_abbr),
            "home_score": safe_int(home_c.get("score")),
            "away_score": safe_int(away_c.get("score")),
            "home_record": (home_c.get("records") or [{}])[0].get("summary", ""),
            "away_record": (away_c.get("records") or [{}])[0].get("summary", ""),
        })
    return rows

@st.cache_data(ttl=3600, show_spinner=False)
def get_team_power_index():
    """Lightweight WNBA team rating from ESPN scoreboard records.

    This is intentionally conservative. If deeper WNBA stats are not available, the model stays near neutral.
    """
    # Pull a 30-day window around today to gather records from scoreboard events.
    today = eastern_now().date()
    ratings = {}
    for delta in range(-8, 3):
        d = (today + timedelta(days=delta)).strftime("%Y-%m-%d")
        data = get_wnba_scoreboard(d)
        for ev in data.get("events", []) or []:
            comp = (ev.get("competitions") or [{}])[0]
            for c in comp.get("competitors") or []:
                team = c.get("team") or {}
                abbr = canonical_abbr(team.get("abbreviation"), team.get("displayName") or team.get("name"))
                rec = (c.get("records") or [{}])[0].get("summary", "")
                w_pct = 0.50
                try:
                    if "-" in rec:
                        w, l = rec.split("-")[:2]
                        w, l = int(w), int(l)
                        w_pct = w / max(w + l, 1)
                except Exception:
                    pass
                ratings[abbr] = {"win_pct": w_pct, "rating": (w_pct - .500) * 11.0}
    return ratings

@st.cache_data(ttl=240, show_spinner=False)
def get_espn_summary(game_id):
    return safe_get_json(ESPN_SUMMARY, params={"event": game_id}, timeout=18) or {}

def boxscore_players(game):
    """Return player rows from ESPN summary if available.

    Used for player prop actual grading and a basic player universe. Projections are only made when a real prop line exists.
    """
    data = get_espn_summary(game["game_id"])
    rows = []
    box = data.get("boxscore", {}) or {}
    teams = box.get("players") or []
    for team_block in teams:
        team = team_block.get("team", {}) or {}
        team_abbr = canonical_abbr(team.get("abbreviation"), team.get("displayName") or team.get("name"))
        for stat_group in team_block.get("statistics", []) or []:
            labels = stat_group.get("labels") or []
            for athlete in stat_group.get("athletes", []) or []:
                a = athlete.get("athlete", {}) or {}
                vals = athlete.get("stats") or []
                stat_map = {}
                for lab, val in zip(labels, vals):
                    stat_map[str(lab).upper()] = val
                rows.append({
                    "player_id": str(a.get("id") or a.get("uid") or a.get("displayName")),
                    "player": a.get("displayName") or a.get("shortName") or "",
                    "team": team_abbr,
                    "stats": stat_map
                })
    return rows

# ============================================================
# ODDS / MARKET
# ============================================================
@st.cache_data(ttl=360, show_spinner=False)
def get_market_odds():
    if not ODDS_API_KEY:
        return []
    url = f"{ODDS_BASE}/sports/{SPORT_KEY}/odds"
    data = safe_get_json(
        url,
        params={
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american"
        },
        timeout=20
    )
    return data if isinstance(data, list) else []

@st.cache_data(ttl=360, show_spinner=False)
def get_odds_events():
    if not ODDS_API_KEY:
        return []
    data = safe_get_json(f"{ODDS_BASE}/sports/{SPORT_KEY}/events", params={"apiKey": ODDS_API_KEY}, timeout=18)
    return data if isinstance(data, list) else []

def match_event(game, events):
    if not events:
        return None
    home = WNBA_ABBR_TO_NAME.get(game["home"], game["home_name"])
    away = WNBA_ABBR_TO_NAME.get(game["away"], game["away_name"])
    best = None
    best_score = 0
    for ev in events:
        h = ev.get("home_team", "")
        a = ev.get("away_team", "")
        score = max(
            (name_score(home, h) + name_score(away, a)) / 2,
            (name_score(home, a) + name_score(away, h)) / 2
        )
        if score > best_score:
            best_score = score
            best = ev
    return best if best_score >= 0.70 else None

def match_market_odds_for_game(game, market_events):
    home_name = WNBA_ABBR_TO_NAME.get(game["home"], game["home_name"])
    away_name = WNBA_ABBR_TO_NAME.get(game["away"], game["away_name"])
    best = {
        "home_price": None, "away_price": None,
        "home_spread": None, "away_spread": None,
        "spread_home_price": None, "spread_away_price": None,
        "total": None, "over_price": None, "under_price": None,
        "rows": [], "quality": "NO ODDS", "source": "No Odds"
    }
    if not market_events:
        return best
    chosen = match_event(game, market_events)
    if not chosen:
        return best

    home_prices, away_prices = [], []
    home_spreads, away_spreads = [], []
    sp_home_prices, sp_away_prices = [], []
    totals, over_prices, under_prices = [], [], []
    rows = []

    for book in chosen.get("bookmakers", []) or []:
        book_name = book.get("title") or book.get("key") or "Book"
        rec = {"Book": book_name, "Home ML": None, "Away ML": None, "Home Spread": None, "Away Spread": None, "Total": None}
        for market in book.get("markets", []) or []:
            key = market.get("key")
            outcomes = market.get("outcomes", []) or []
            if key == "h2h":
                for out in outcomes:
                    nm = out.get("name", "")
                    price = safe_float(out.get("price"))
                    if price is None:
                        continue
                    if name_score(nm, home_name) >= 0.70 or name_score(nm, game["home"]) >= 0.85:
                        home_prices.append(price); rec["Home ML"] = price
                    elif name_score(nm, away_name) >= 0.70 or name_score(nm, game["away"]) >= 0.85:
                        away_prices.append(price); rec["Away ML"] = price
            elif key == "spreads":
                for out in outcomes:
                    nm = out.get("name", "")
                    price = safe_float(out.get("price"))
                    point = safe_float(out.get("point"))
                    if point is None:
                        continue
                    if name_score(nm, home_name) >= 0.70 or name_score(nm, game["home"]) >= 0.85:
                        home_spreads.append(point); sp_home_prices.append(price); rec["Home Spread"] = point
                    elif name_score(nm, away_name) >= 0.70 or name_score(nm, game["away"]) >= 0.85:
                        away_spreads.append(point); sp_away_prices.append(price); rec["Away Spread"] = point
            elif key == "totals":
                for out in outcomes:
                    name = str(out.get("name", "")).lower()
                    price = safe_float(out.get("price"))
                    point = safe_float(out.get("point"))
                    if point is not None:
                        totals.append(point); rec["Total"] = point
                    if "over" in name and price is not None:
                        over_prices.append(price)
                    if "under" in name and price is not None:
                        under_prices.append(price)
        rows.append(rec)

    if home_prices and away_prices:
        best["home_price"] = float(np.median(home_prices))
        best["away_price"] = float(np.median(away_prices))
    if home_spreads:
        best["home_spread"] = float(np.median(home_spreads))
        best["spread_home_price"] = float(np.median([x for x in sp_home_prices if x is not None])) if any(x is not None for x in sp_home_prices) else DEFAULT_ODDS
    if away_spreads:
        best["away_spread"] = float(np.median(away_spreads))
        best["spread_away_price"] = float(np.median([x for x in sp_away_prices if x is not None])) if any(x is not None for x in sp_away_prices) else DEFAULT_ODDS
    if totals:
        best["total"] = float(np.median(totals))
        best["over_price"] = float(np.median(over_prices)) if over_prices else DEFAULT_ODDS
        best["under_price"] = float(np.median(under_prices)) if under_prices else DEFAULT_ODDS

    count = sum([
        best["home_price"] is not None and best["away_price"] is not None,
        best["home_spread"] is not None,
        best["total"] is not None,
    ])
    best["rows"] = rows
    best["quality"] = "STRONG" if count >= 3 and len(rows) >= 2 else "OK" if count >= 1 else "NO ODDS"
    best["source"] = "Sportsbook Consensus" if count else "No Odds"
    return best


# ============================================================
# PROP MARKET SAFETY / DIAGNOSTICS
# ============================================================
def valid_prop_line(prop, line):
    """Reject obvious bad mappings but keep real WNBA lines flexible."""
    line = safe_float(line)
    if line is None:
        return False, "missing line"
    limits = {
        "PTS": (3.5, 40.5),
        "REB": (1.5, 18.5),
        "AST": (0.5, 14.5),
        "PRA": (8.5, 55.5),
        "PR": (6.5, 48.5),
        "PA": (6.5, 48.5),
        "RA": (2.5, 28.5),
        "3PM": (0.5, 6.5),
    }
    lo, hi = limits.get(prop, (0.5, 60.5))
    if line < lo or line > hi:
        return False, f"line {line} outside expected {prop} range {lo}-{hi}"
    return True, "valid line"


def get_prop_code_from_market(market_key):
    for code, cfg in PROP_CONFIG.items():
        if market_key in cfg["markets"]:
            return code
    return None


def set_prop_diagnostics(rows):
    st.session_state["wnba_prop_diagnostics"] = rows[-200:]


def get_prop_diagnostics():
    return st.session_state.get("wnba_prop_diagnostics", [])

@st.cache_data(ttl=420, show_spinner=False)
def get_event_prop_odds(event_id, markets_csv):
    """Fetch WNBA player props from The Odds API with safer fallback behavior.

    Important fix: if one market in a big CSV is unavailable, some API responses can
    return thin/empty results. We first try the CSV, then retry market-by-market.
    """
    if not ODDS_API_KEY or not event_id:
        return []

    def fetch(markets):
        url = f"{ODDS_BASE}/sports/{SPORT_KEY}/events/{event_id}/odds"
        data = safe_get_json(
            url,
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us,us2",
                "markets": markets,
                "oddsFormat": "american"
            },
            timeout=22
        )
        rows = []
        if not data or not isinstance(data, dict):
            return rows
        for book in data.get("bookmakers", []) or []:
            book_name = book.get("title") or book.get("key") or "Book"
            for market in book.get("markets", []) or []:
                mkey = market.get("key")
                if not get_prop_code_from_market(mkey):
                    continue
                for out in market.get("outcomes", []) or []:
                    side_raw = str(out.get("name") or "").upper()
                    # The Odds API usually stores player in description for props.
                    player = (
                        out.get("description")
                        or out.get("player")
                        or out.get("participant")
                        or out.get("participant_name")
                        or ""
                    )
                    # If name is the player and side is elsewhere, keep it only if side exists.
                    if not player and side_raw not in ["OVER", "UNDER"]:
                        player = side_raw.title()
                    line = safe_float(out.get("point"))
                    price = safe_float(out.get("price"))
                    if not player or line is None:
                        continue
                    if side_raw not in ["OVER", "UNDER"]:
                        # Avoid misreading team/player names as betting side.
                        continue
                    prop_code = get_prop_code_from_market(mkey)
                    ok, reason = valid_prop_line(prop_code, line)
                    if not ok:
                        log_request("WNBA_PROP_REJECT", "BAD_LINE", f"{player} {mkey} {line}: {reason}")
                        continue
                    rows.append({
                        "Book": book_name,
                        "Market": mkey,
                        "Prop": prop_code,
                        "Player": player,
                        "Side": side_raw,
                        "Line": line,
                        "Price": price,
                        "Last Update": market.get("last_update") or book.get("last_update"),
                        "Validation": "VALID_REAL_PROP_LINE",
                    })
        return rows

    # Try all selected markets first.
    rows = fetch(markets_csv)
    if rows:
        return rows

    # Fallback: retry one-by-one so one unsupported market does not blank the whole board.
    all_rows = []
    for m in [x.strip() for x in str(markets_csv).split(",") if x.strip()]:
        try:
            all_rows.extend(fetch(m))
        except Exception as e:
            log_request("WNBA_PROP_MARKET_RETRY", "ERROR", f"{m}: {e}")
    return all_rows

# ============================================================
# LEARNING / CLV
# ============================================================
def load_market_learning():
    return load_json(MARKET_LEARN_FILE, {"samples": 0, "team_bias": {}})

def apply_market_learning(prob, team_abbr):
    data = load_market_learning()
    if (data.get("samples", 0) or 0) < 8:
        return prob, "Learning sample too small"
    bias = safe_float((data.get("team_bias") or {}).get(team_abbr), 0.0) or 0.0
    return clamp(prob + bias, 0.02, 0.98), f"Team calibration {bias:+.3f}"

def update_market_learning(results):
    data = load_market_learning()
    graded = [r for r in results if r.get("actual_winner") and r.get("market_type") == "MONEYLINE"]
    team_bias = data.get("team_bias") or {}
    if len(graded) >= 8:
        for r in graded[-80:]:
            pick = r.get("pick")
            won = 1 if r.get("win") else 0
            prob = safe_float(r.get("pick_prob"), 0.5) or 0.5
            err = clamp(won - prob, -0.35, 0.35)
            old = safe_float(team_bias.get(pick), 0.0) or 0.0
            team_bias[pick] = clamp(old + 0.003 * err, -0.035, 0.035)
    data["samples"] = len(graded)
    data["team_bias"] = team_bias
    save_json(MARKET_LEARN_FILE, data)
    return data

def load_prop_learning():
    return load_json(PROP_LEARN_FILE, {"samples": 0, "player_bias": {}, "prop_bias": {}})

def apply_prop_learning(player, prop, projection):
    data = load_prop_learning()
    if (data.get("samples", 0) or 0) < 12:
        return projection, "Learning sample too small"
    pb = safe_float((data.get("player_bias") or {}).get(normalize_name(player)), 0.0) or 0.0
    prb = safe_float((data.get("prop_bias") or {}).get(prop), 0.0) or 0.0
    adj = clamp(pb + prb, -2.5, 2.5)
    return projection + adj, f"Prop calibration {adj:+.2f}"

def update_prop_learning(results):
    data = load_prop_learning()
    graded = [r for r in results if r.get("actual") is not None]
    player_bias = data.get("player_bias") or {}
    prop_bias = data.get("prop_bias") or {}
    if len(graded) >= 12:
        for r in graded[-120:]:
            err = clamp(safe_float(r.get("actual"), 0) - safe_float(r.get("projection"), 0), -6, 6)
            pkey = normalize_name(r.get("player"))
            prop = r.get("prop")
            player_bias[pkey] = clamp((safe_float(player_bias.get(pkey), 0) or 0) + 0.015 * err, -2.0, 2.0)
            prop_bias[prop] = clamp((safe_float(prop_bias.get(prop), 0) or 0) + 0.006 * err, -1.25, 1.25)
    data["samples"] = len(graded)
    data["player_bias"] = player_bias
    data["prop_bias"] = prop_bias
    save_json(PROP_LEARN_FILE, data)
    return data

def update_clv(key, price_or_line):
    if price_or_line is None:
        return None
    data = load_json(CLV_FILE, {})
    val = float(price_or_line)
    if key not in data:
        data[key] = {"open": val, "latest": val, "created_at": now_iso(), "updated_at": now_iso()}
        save_json(CLV_FILE, data)
        return 0.0
    old = data[key]
    open_val = safe_float(old.get("open"), val)
    old["latest"] = val
    old["updated_at"] = now_iso()
    data[key] = old
    save_json(CLV_FILE, data)
    return round(val - open_val, 2)

# ============================================================
# MARKET MODEL
# ============================================================
def team_strength(abbr, ratings):
    d = ratings.get(abbr, {})
    return float(d.get("rating", 0.0) or 0.0), float(d.get("win_pct", 0.50) or 0.50)

def model_market_game(game, bankroll, default_odds, use_market=True, use_learning=True, injury_home_adj=0.0, injury_away_adj=0.0):
    ratings = get_team_power_index()
    h_rating, h_wp = team_strength(game["home"], ratings)
    a_rating, a_wp = team_strength(game["away"], ratings)

    rating_diff = (h_rating - a_rating) + DEFAULT_HOME_COURT + injury_home_adj - injury_away_adj
    volatility = 11.0
    sims = np.random.normal(loc=rating_diff, scale=volatility, size=MARKET_SIMS)

    raw_home_prob = float(np.mean(sims > 0))
    home_prob = raw_home_prob
    if use_learning:
        home_prob, learning_note = apply_market_learning(home_prob, game["home"])
    else:
        learning_note = "Learning off"

    odds = match_market_odds_for_game(game, get_market_odds()) if use_market else {
        "home_price": None, "away_price": None, "home_spread": None, "away_spread": None,
        "total": None, "rows": [], "quality": "OFF", "source": "Market off"
    }

    home_price = odds.get("home_price") if odds.get("home_price") is not None else default_odds
    away_price = odds.get("away_price") if odds.get("away_price") is not None else default_odds

    # Moneyline safety: when real ML odds exist, blend model probability with no-vig market probability.
    # This reduces weird ML outputs from the lightweight WNBA team rating model without touching props.
    market_blend_note = "No real ML market blend"
    h_imp = american_to_implied(odds.get("home_price"))
    a_imp = american_to_implied(odds.get("away_price"))
    if h_imp is not None and a_imp is not None and (h_imp + a_imp) > 0:
        market_home_prob = h_imp / (h_imp + a_imp)
        home_prob = clamp((home_prob * 0.70) + (market_home_prob * 0.30), 0.02, 0.98)
        market_blend_note = f"ML blended 70% model / 30% no-vig market ({market_home_prob:.3f})"

    away_prob = 1 - home_prob

    model_pick = game["home"] if home_prob >= away_prob else game["away"]
    pick_prob = max(home_prob, away_prob)
    pick_price = home_price if model_pick == game["home"] else away_price
    implied = american_to_implied(pick_price) or 0.50
    ml_ev = expected_value(pick_prob, pick_price)
    ml_edge_prob = pick_prob - implied
    ml_kelly = kelly_fraction(pick_prob, pick_price)
    ml_clv = update_clv(f"{game['game_id']}_ML_{model_pick}", pick_price)

    # Spread projection from simulated margin.
    projected_home_margin = float(np.mean(sims))
    market_home_spread = safe_float(odds.get("home_spread"))
    if market_home_spread is not None:
        spread_edge = projected_home_margin + market_home_spread
        spread_pick = f"{game['home']} {market_home_spread:+.1f}" if spread_edge > 0 else f"{game['away']} {safe_float(odds.get('away_spread'), -market_home_spread):+.1f}"
        spread_side = game["home"] if spread_edge > 0 else game["away"]
        spread_prob = float(np.mean(sims + market_home_spread > 0)) if spread_edge > 0 else float(np.mean(sims + market_home_spread < 0))
    else:
        spread_edge = None
        spread_pick = "NO SPREAD LINE"
        spread_side = None
        spread_prob = None

    # Total projection. Uses conservative WNBA baseline plus pace/rating lift.
    pace = build_pace_projection(
        game["home"], game["away"], h_rating, a_rating
    )

    projected_total = (
        DEFAULT_TOTAL
        + (h_rating + a_rating) * 0.55
        + ((pace - PACE_BASE) * 1.15)
    )
    total_line = safe_float(odds.get("total"))
    total_std = 13.5
    total_sims = np.random.normal(projected_total, total_std, size=MARKET_SIMS)
    if total_line is not None:
        over_prob = float(np.mean(total_sims > total_line))
        under_prob = 1 - over_prob
        total_side = "OVER" if over_prob >= under_prob else "UNDER"
        total_prob = max(over_prob, under_prob)
        total_edge = abs(projected_total - total_line)
        total_pick = f"{total_side} {total_line:.1f}"
    else:
        over_prob = under_prob = total_prob = total_edge = None
        total_side = None
        total_pick = "NO TOTAL LINE"

    home_score = int(round((projected_total + projected_home_margin) / 2))
    away_score = int(round((projected_total - projected_home_margin) / 2))

    data_score = 45
    if odds.get("home_price") is not None and odds.get("away_price") is not None:
        data_score += 18
    if odds.get("home_spread") is not None:
        data_score += 10
    if odds.get("total") is not None:
        data_score += 10
    if odds.get("quality") == "STRONG":
        data_score += 7
    if ratings:
        data_score += 8
    if use_learning and (load_market_learning().get("samples", 0) or 0) >= 8:
        data_score += 5
    data_score = int(clamp(data_score, 0, 100))

    ml_reasons = []
    if pick_prob < 0.55:
        ml_reasons.append("model probability under 55%")
    if ml_edge_prob < MIN_MARKET_EDGE_PROB:
        ml_reasons.append("edge vs implied too small")
    if ml_ev is None or ml_ev < 0.012:
        ml_reasons.append("EV too low")
    if data_score < MIN_MARKET_BET_SCORE:
        ml_reasons.append("data score too low")

    ml_qualified = len(ml_reasons) == 0
    market_confidence = confidence_tier(
        pick_prob,
        ml_edge_prob,
        ml_ev,
    )

    ml_signal = "PASS"

    if ml_qualified and pick_prob >= 0.62 and ml_ev is not None and ml_ev >= 0.04:
        ml_signal = f"😈 STRONG {model_pick} ML"
    elif ml_qualified:
        ml_signal = f"✅ LEAN {model_pick} ML"

    spread_signal = "PASS"

    if (
        spread_prob is not None
        and data_score >= 76
        and abs(spread_edge or 0) >= 1.2
        and spread_prob >= 0.55
    ):
        spread_signal = (
            f"{'😈' if spread_prob >= .60 else '✅'} {spread_pick}"
        )

    total_signal = "PASS"

    if (
        total_prob is not None
        and data_score >= 76
        and (total_edge or 0) >= 2.0
        and total_prob >= 0.55
    ):
        total_signal = (
            f"{'😈' if total_prob >= .60 else '✅'} {total_pick}"
        )

    return {
        **game,
        "home_prob": home_prob, "away_prob": away_prob, "model_pick": model_pick, "pick_prob": pick_prob,
        "home_price": home_price, "away_price": away_price, "pick_price": pick_price,
        "implied": implied, "ml_ev": ml_ev, "ml_kelly": ml_kelly, "ml_edge_prob": ml_edge_prob, "ml_signal": ml_signal,
        "ml_qualified": ml_qualified, "ml_reasons": ml_reasons, "ml_clv": ml_clv,
        "projected_home_margin": projected_home_margin, "market_home_spread": market_home_spread,
        "spread_edge": spread_edge, "spread_pick": spread_pick, "spread_side": spread_side, "spread_prob": spread_prob, "spread_signal": spread_signal,
        "projected_total": projected_total, "total_line": total_line, "total_side": total_side, "total_prob": total_prob,
        "total_edge": total_edge, "total_signal": total_signal,
        "pred_home_score": home_score, "pred_away_score": away_score,
        "home_rating": h_rating, "away_rating": a_rating, "home_wp": h_wp, "away_wp": a_wp,
        "data_score": data_score, "odds_quality": odds.get("quality"), "market_source": odds.get("source"),
        "odds_rows": odds.get("rows", []), "learning_note": learning_note,
        "market_blend_note": market_blend_note, "raw_home_prob": raw_home_prob,
        "market_confidence": market_confidence,
    }

# ============================================================
# PROP MODEL
# ============================================================
def paired_price(rows, market, player, line, wanted_side):
    best = None
    best_score = 0
    for r in rows:
        if r.get("Market") != market:
            continue
        if safe_float(r.get("Line")) != safe_float(line):
            continue
        side = str(r.get("Side", "")).upper()
        if wanted_side not in side:
            continue
        score = name_score(player, r.get("Player"))
        if score > best_score:
            best_score = score
            best = r
    return safe_float(best.get("Price")) if best else None

def build_prop_board(games, selected_props, bankroll, default_odds, max_players_per_game=26):
    events = get_odds_events()
    market_events = get_market_odds()
    all_market_keys = sorted(set(m for p in selected_props for m in PROP_CONFIG[p]["markets"]))
    out = []
    diagnostics = []

    for game in games:
        ev = match_event(game, events) or match_event(game, market_events)
        if not ev:
            diagnostics.append({
                "Game": f"{game.get('away')} @ {game.get('home')}",
                "Stage": "event_match",
                "Status": "NO ODDS EVENT MATCH",
                "Details": "Market board can still work, but player prop event id was not matched.",
            })
            continue

        prop_rows = get_event_prop_odds(ev.get("id"), ",".join(all_market_keys))
        diagnostics.append({
            "Game": f"{game.get('away')} @ {game.get('home')}",
            "Stage": "prop_fetch",
            "Status": f"{len(prop_rows)} rows",
            "Details": f"Event {ev.get('id')} | markets {','.join(all_market_keys)}",
        })
        if not prop_rows:
            continue

        # Build candidates from real prop rows only. No fake player list, no fake lines.
        candidates = {}
        rejected = 0
        for r in prop_rows:
            player = r.get("Player")
            market = r.get("Market")
            line = safe_float(r.get("Line"))
            prop = get_prop_code_from_market(market)
            if not player or line is None or prop not in selected_props:
                rejected += 1
                continue
            ok, reason = valid_prop_line(prop, line)
            if not ok:
                rejected += 1
                diagnostics.append({
                    "Game": f"{game.get('away')} @ {game.get('home')}",
                    "Stage": "line_validation",
                    "Status": "REJECTED",
                    "Details": f"{player} {prop} {line}: {reason}",
                })
                continue
            candidates.setdefault((normalize_name(player), player, market, line), []).append(r)

        diagnostics.append({
            "Game": f"{game.get('away')} @ {game.get('home')}",
            "Stage": "candidate_build",
            "Status": f"{len(candidates)} candidates",
            "Details": f"Rejected {rejected} invalid/missing rows",
        })

        count = 0
        for (pkey, player, market, line), rows in candidates.items():
            prop = get_prop_code_from_market(market)
            if prop not in selected_props:
                continue
            if count >= max_players_per_game:
                break
            count += 1

            over_price = paired_price(prop_rows, market, player, line, "OVER")
            under_price = paired_price(prop_rows, market, player, line, "UNDER")
            over_price = over_price if over_price is not None else default_odds
            under_price = under_price if under_price is not None else default_odds

            over_imp = price_to_market_prob(over_price)
            under_imp = price_to_market_prob(under_price)
            denom = max(over_imp + under_imp, 1e-9)
            no_vig_over = over_imp / denom
            no_vig_under = under_imp / denom

            # Market-implied projection: line nudged by no-vig pressure. This uses real prop lines only.
            cfg = PROP_CONFIG[prop]
            std = cfg["default_std"]
            market_bias = clamp((no_vig_over - no_vig_under) * std * 0.62, -cfg["default_std"] * .45, cfg["default_std"] * .45)
            minutes_proj = build_minutes_projection(player, prop, game)
            position = get_player_position(player)
            pos_weight = POSITION_DEFENSE_WEIGHTS.get(position, {}).get(prop, 1.0)
            minutes_factor = (minutes_proj - 28) * 0.12

            projection = float(line + market_bias + minutes_factor)
            projection *= pos_weight
            projection, learn_note = apply_prop_learning(player, prop, projection)

            sims = np.random.normal(projection, std, PROP_SIMS)
            over_prob = float(np.mean(sims > line))
            under_prob = 1 - over_prob
            side = "OVER" if over_prob >= under_prob else "UNDER"
            pick_prob = max(over_prob, under_prob)
            price = over_price if side == "OVER" else under_price
            ev_val = expected_value(pick_prob, price)
            edge = abs(projection - line)
            kelly = kelly_fraction(pick_prob, price)

            data_score = 55
            data_score += 18 if over_price is not None and under_price is not None else 0
            data_score += 7 if len(rows) >= 2 else 3
            data_score += 8 if ev and game else 0
            data_score = int(clamp(data_score, 0, 100))

            reasons = []
            if edge < MIN_PROP_EDGE[prop]:
                reasons.append("edge below prop threshold")
            if pick_prob < MIN_PROP_PROB:
                reasons.append("probability below threshold")
            if ev_val is None or ev_val < 0.01:
                reasons.append("EV too low")
            if data_score < MIN_PROP_BET_SCORE:
                reasons.append("data score too low")
            if edge >= MAX_PROP_EDGE:
                reasons.append("projection spike too large — possible bad line")
            if pick_prob >= MAX_PROP_PROB:
                reasons.append("probability unrealistically high")

            qualified = len(reasons) == 0
            prop_confidence = confidence_tier(pick_prob, edge, ev_val)

            signal = "PASS"
            if qualified and pick_prob >= .64 and edge >= MIN_PROP_EDGE[prop] * 1.2:
                signal = f"😈 STRONG {side}"
            elif qualified:
                signal = f"✅ LEAN {side}"

            clv = update_clv(f"{game['game_id']}_{pkey}_{prop}", line)

            out.append({
                **game,
                "player": player, "player_key": pkey, "prop": prop, "prop_label": cfg["label"],
                "market": market, "line": line, "projection": projection, "std": std,
                "side": side, "pick_prob": pick_prob, "over_prob": over_prob, "under_prob": under_prob,
                "over_price": over_price, "under_price": under_price, "price": price,
                "ev": ev_val, "edge": edge, "kelly": kelly, "data_score": data_score,
                "qualified": qualified, "reasons": reasons, "signal": signal, "clv": clv,
                "line_source": "Real sportsbook prop line", "projection_note": "Market-implied + learning calibration",
                "learning_note": learn_note, "prop_rows": rows[:12],
                "prop_confidence": prop_confidence,
                "books_count": len(set(r.get("Book") for r in rows)),
            })

    set_prop_diagnostics(diagnostics)
    out = sorted(out, key=lambda x: (not x["qualified"], -safe_float(x.get("ev"), -9), -x.get("pick_prob", 0)))
    return out

# ============================================================
# GRADING
# ============================================================
def get_actual_winner(game_id, date_str, home, away):
    games = extract_games(date_str)
    for g in games:
        if str(g.get("game_id")) == str(game_id) or (g.get("home") == home and g.get("away") == away):
            hs, aw = safe_int(g.get("home_score")), safe_int(g.get("away_score"))
            status = str(g.get("status", ""))
            if hs is None or aw is None:
                return None, status
            if "Final" not in status and g.get("status_state") != "post" and hs == 0 and aw == 0:
                return None, status
            return (home if hs > aw else away), status
    return None, "not found"

def actual_prop_value(game, player, prop):
    rows = boxscore_players(game)
    best = None
    best_score = 0
    for r in rows:
        s = name_score(player, r.get("player"))
        if s > best_score:
            best_score = s
            best = r
    if not best or best_score < 0.80:
        return None
    stats = best.get("stats") or {}

    def get_stat(*names):
        for n in names:
            if n in stats:
                return safe_float(stats.get(n), 0) or 0
        return 0

    pts = get_stat("PTS", "POINTS")
    reb = get_stat("REB", "REBOUNDS")
    ast = get_stat("AST", "ASSISTS")
    threes = get_stat("3PM", "3PTM", "3PT FG", "3PT")
    if prop == "PTS": return pts
    if prop == "REB": return reb
    if prop == "AST": return ast
    if prop == "PRA": return pts + reb + ast
    if prop == "PR": return pts + reb
    if prop == "PA": return pts + ast
    if prop == "RA": return reb + ast
    if prop == "3PM": return threes
    return None

def save_market_snapshot(board):
    picks = load_json(MARKET_PICK_LOG, [])
    existing = set(p.get("pick_id") for p in picks)
    saved = 0
    for p in board:
        # Save moneyline, spread, total as separate records if signal is not no line.
        records = [
            ("MONEYLINE", p["model_pick"], p["ml_signal"], p["pick_prob"], p["pick_price"], p["ml_ev"], p["ml_kelly"]),
            ("SPREAD", p.get("spread_side"), p.get("spread_signal"), p.get("spread_prob"), None, None, None),
            ("TOTAL", p.get("total_side"), p.get("total_signal"), p.get("total_prob"), None, None, None),
        ]
        for market_type, pick, signal, prob, price, ev_val, kelly in records:
            if not pick or not signal or signal == "PASS" or "NO" in str(signal):
                continue
            pick_id = f"{p['date']}_{p['game_id']}_{market_type}_{pick}"
            if pick_id in existing:
                continue
            rec = {
                "pick_id": pick_id, "saved_at": now_iso(), "market_type": market_type,
                "date": p["date"], "game_id": p["game_id"], "home": p["home"], "away": p["away"],
                "pick": pick, "signal": signal, "pick_prob": None if prob is None else round(float(prob), 4),
                "price": price, "ev": None if ev_val is None else round(float(ev_val), 4),
                "kelly": None if kelly is None else round(float(kelly), 4),
                "data_score": p["data_score"], "pred_home_score": p["pred_home_score"], "pred_away_score": p["pred_away_score"],
                "graded": False,
            }
            picks.append(rec); existing.add(pick_id); saved += 1
    save_json(MARKET_PICK_LOG, picks)
    return saved

def save_prop_snapshot(board):
    picks = load_json(PROP_PICK_LOG, [])
    existing = set(p.get("pick_id") for p in picks)
    saved = 0
    for p in board:
        if p.get("signal") == "PASS":
            continue
        pick_id = f"{p['date']}_{p['game_id']}_{p['player_key']}_{p['prop']}_{p['side']}_{p['line']}"
        if pick_id in existing:
            continue
        rec = {
            "pick_id": pick_id, "saved_at": now_iso(), "date": p["date"], "game_id": p["game_id"],
            "home": p["home"], "away": p["away"], "player": p["player"], "prop": p["prop"],
            "side": p["side"], "line": p["line"], "projection": round(float(p["projection"]), 3),
            "pick_prob": round(float(p["pick_prob"]), 4), "price": p["price"],
            "ev": None if p["ev"] is None else round(float(p["ev"]), 4),
            "kelly": round(float(p["kelly"]), 4), "data_score": p["data_score"],
            "qualified": p["qualified"], "signal": p["signal"], "graded": False,
        }
        picks.append(rec); existing.add(pick_id); saved += 1
    save_json(PROP_PICK_LOG, picks)
    return saved

def grade_market_results():
    picks = load_json(MARKET_PICK_LOG, [])
    results = load_json(MARKET_RESULT_LOG, [])
    ids = set(r.get("pick_id") for r in results)
    graded = 0
    for p in picks:
        if p.get("graded"):
            continue
        winner, status = get_actual_winner(p["game_id"], p["date"], p["home"], p["away"])
        if not winner:
            continue
        win = None
        if p["market_type"] == "MONEYLINE":
            win = winner == p["pick"]
        elif p["market_type"] == "SPREAD":
            # Spread grading is conservative here. If saved spread line details are missing, skip hard grading.
            continue
        elif p["market_type"] == "TOTAL":
            # Total grading requires final score and line. Keep conservative if not stored.
            continue
        p["graded"] = True
        p["actual_winner"] = winner
        p["win"] = bool(win)
        p["graded_at"] = now_iso()
        if p["pick_id"] not in ids:
            results.append(dict(p)); ids.add(p["pick_id"])
        graded += 1
    save_json(MARKET_PICK_LOG, picks)
    save_json(MARKET_RESULT_LOG, results)
    update_market_learning(results)
    return graded

def grade_prop_results():
    picks = load_json(PROP_PICK_LOG, [])
    results = load_json(PROP_RESULT_LOG, [])
    ids = set(r.get("pick_id") for r in results)
    graded = 0
    game_cache = {}
    for p in picks:
        if p.get("graded"):
            continue
        gkey = (p["date"], p["game_id"], p["home"], p["away"])
        if gkey not in game_cache:
            game_cache[gkey] = {"date": p["date"], "game_id": p["game_id"], "home": p["home"], "away": p["away"]}
        actual = actual_prop_value(game_cache[gkey], p["player"], p["prop"])
        if actual is None:
            continue
        win = actual > p["line"] if p["side"] == "OVER" else actual < p["line"]
        p["graded"] = True
        p["actual"] = actual
        p["win"] = bool(win)
        p["graded_at"] = now_iso()
        if p["pick_id"] not in ids:
            results.append(dict(p)); ids.add(p["pick_id"])
        graded += 1
    save_json(PROP_PICK_LOG, picks)
    save_json(PROP_RESULT_LOG, results)
    update_prop_learning(results)
    return graded

def performance_summary():
    market = load_json(MARKET_RESULT_LOG, [])
    props = load_json(PROP_RESULT_LOG, [])
    ml = [r for r in market if r.get("market_type") == "MONEYLINE" and r.get("win") is not None]
    prop_bets = [r for r in props if r.get("win") is not None and r.get("qualified")]
    return {
        "market_graded": len(ml),
        "market_hit": (sum(1 for r in ml if r.get("win")) / len(ml)) if ml else None,
        "prop_graded": len(prop_bets),
        "prop_hit": (sum(1 for r in prop_bets if r.get("win")) / len(prop_bets)) if prop_bets else None,
    }

# ============================================================
# SIDEBAR / CONTROLS
# ============================================================
st.sidebar.markdown("""
<div style='padding:12px 4px 18px 4px;'>
  <div style='font-size:28px;font-weight:950;'>😈 DEVIL PICKS</div>
  <div style='color:#ff344f;font-weight:900;'>WNBA FULL ENGINE</div>
  <div style='color:#aeb7c9;font-size:12px;margin-top:4px;'>Moneyline • Spread • Total • Props</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Board Controls")
    day_mode = st.radio("Game Day", ["Today", "Tomorrow", "Both"], index=0)
    bankroll = st.number_input("Bankroll", min_value=10.0, value=1000.0, step=25.0)
    default_odds = st.number_input("Default Odds if price missing", value=float(DEFAULT_ODDS), step=5.0)
    use_market = st.checkbox("Use sportsbook odds", value=True)
    use_learning = st.checkbox("Use learning calibration", value=True)
    st.markdown("### Props")
    selected_props = st.multiselect("Props to scan", list(PROP_CONFIG.keys()), default=["PTS", "REB", "AST", "PRA", "3PM"])
    max_players = st.slider("Max prop players per game", 6, 40, 22, 2)
    st.caption("WNBA props only appear when real sportsbook prop lines are available.")
    st.markdown("### Manual Injury / News Adjustment")
    injury_home_adj = st.number_input("Home team adjustment", value=0.0, step=0.5)
    injury_away_adj = st.number_input("Away team adjustment", value=0.0, step=0.5)
    st.markdown("---")
    perf = performance_summary()
    st.markdown("### Model Status")
    st.markdown(f"<span class='badge badge-green'>ML Samples: {perf['market_graded']}</span>", unsafe_allow_html=True)
    st.markdown(f"<span class='badge badge-green'>Prop Samples: {perf['prop_graded']}</span>", unsafe_allow_html=True)

# ============================================================
# MAIN APP
# ============================================================
st.markdown("""
<div class='hero'>
  <div class='logo-title'>😈 DEVIL PICKS — WNBA Full Market + Props Engine</div>
  <div class='sub'>Moneyline • Spread • Totals • Player Props • OVER/UNDER/PASS • Snapshots • After-game learning</div>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1:
    refresh = st.button("🔄 REFRESH FULL WNBA BOARD", use_container_width=True)
with c2:
    save_market = st.button("💾 SAVE MARKET SNAPSHOT", use_container_width=True)
with c3:
    save_props = st.button("💾 SAVE PROP SNAPSHOT", use_container_width=True)
with c4:
    grade_all = st.button("✅ GRADE + LEARN", use_container_width=True)

if grade_all:
    gm = grade_market_results()
    gp = grade_prop_results()
    st.success(f"Graded {gm} market picks and {gp} prop picks. Learning updated.")

if refresh or "wnba_market_board" not in st.session_state:
    dates = [date_for_mode("Today"), date_for_mode("Tomorrow")] if day_mode == "Both" else [date_for_mode(day_mode)]
    games = []
    for d in dates:
        games.extend(extract_games(d))

    with st.spinner("Building WNBA market board..."):
        market_board = []
        for g in games:
            try:
                market_board.append(model_market_game(g, bankroll, default_odds, use_market, use_learning, injury_home_adj, injury_away_adj))
            except Exception as e:
                log_request("model_market_game", "ERROR", f"{g}: {e}")

    with st.spinner("Building WNBA player prop board with OVER/UNDER/PASS..."):
        try:
            prop_board = build_prop_board(games, selected_props, bankroll, default_odds, max_players)
        except Exception as e:
            log_request("build_prop_board", "ERROR", str(e))
            prop_board = []

    market_board = sorted(market_board, key=lambda x: (not x.get("ml_qualified"), -safe_float(x.get("ml_ev"), -9), -x.get("pick_prob", 0)))
    prop_board = sorted(prop_board, key=lambda x: (not x.get("qualified"), -safe_float(x.get("ev"), -9), -x.get("pick_prob", 0)))

    st.session_state["wnba_market_board"] = market_board
    st.session_state["wnba_prop_board"] = prop_board
    save_json(MARKET_SNAPSHOT_FILE, market_board)
    save_json(PROP_SNAPSHOT_FILE, prop_board)

market_board = st.session_state.get("wnba_market_board", [])
prop_board = st.session_state.get("wnba_prop_board", [])

if save_market:
    n = save_market_snapshot(market_board)
    st.success(f"Saved {n} official WNBA market snapshots.")

if save_props:
    n = save_prop_snapshot(prop_board)
    st.success(f"Saved {n} official WNBA prop snapshots.")

qualified_markets = [x for x in market_board if x.get("ml_qualified")]
qualified_props = [x for x in prop_board if x.get("qualified")]
best_market = market_board[0] if market_board else None
best_prop = prop_board[0] if prop_board else None

st.markdown(f"""
<div class='metric-grid'>
  <div class='metric-box'><div class='metric-label'>Games Loaded</div><div class='metric-value'>{len(market_board)}</div><div class='metric-sub'>WNBA slate</div></div>
  <div class='metric-box'><div class='metric-label'>Market Plays</div><div class='metric-value'>{len(qualified_markets)}</div><div class='metric-sub'>ML gates passed</div></div>
  <div class='metric-box'><div class='metric-label'>Prop Plays</div><div class='metric-value'>{len(qualified_props)}</div><div class='metric-sub'>Props gates passed</div></div>
  <div class='metric-box'><div class='metric-label'>Best Signal</div><div class='metric-value' style='font-size:20px;'>{best_market['ml_signal'] if best_market else 'No Games'}</div><div class='metric-sub'>{best_prop['signal'] + ' — ' + best_prop['player'] if best_prop else 'Props wait for real lines'}</div></div>
</div>
""", unsafe_allow_html=True)

if not market_board:
    st.warning("No WNBA games loaded. Try Tomorrow/Both, or the WNBA slate may not be posted yet.")
    st.stop()

tab_markets, tab_props, tab_all, tab_tracker, tab_learn, tab_logs = st.tabs([
    "🏀 Markets", "😈 Player Props", "📋 All Boards", "📈 Tracker", "🧠 Learning", "🔌 Source Logs"
])

with tab_markets:
    st.markdown("<div class='section-title'>WNBA Moneyline + Spread + Total</div>", unsafe_allow_html=True)
    for p in market_board:
        card_class = "card-green" if p["ml_qualified"] else "card"
        reasons = ", ".join(p.get("ml_reasons", [])) or "All moneyline gates passed"
        st.markdown(f"""
        <div class='{card_class}'>
          <div class='team-row'>
            <div><div class='team-name'>{p['away']}</div><div class='team-record'>{p.get('away_record','')}</div><div class='muted'>Away • Pred {p['pred_away_score']}</div></div>
            <div class='vs-pill'>{p.get('status','Scheduled')}<br>{p.get('game_time','')}</div>
            <div style='text-align:right;'><div class='team-name'>{p['home']}</div><div class='team-record'>{p.get('home_record','')}</div><div class='muted'>Home • Pred {p['pred_home_score']}</div></div>
          </div>
          <div class='metric-grid' style='grid-template-columns:repeat(5,minmax(0,1fr));'>
            <div><div class='metric-label'>Moneyline</div><div class='metric-value green'>{p['model_pick']} ML</div><div class='metric-sub'>{p['ml_signal']}</div></div>
            <div><div class='metric-label'>Win Prob</div><div class='metric-value'>{p['pick_prob']*100:.1f}%</div><div class='metric-sub'>{odds_display(p['pick_price'])}</div></div>
            <div><div class='metric-label'>Spread</div><div class='metric-value'>{p['spread_signal']}</div><div class='metric-sub'>Proj margin {p['projected_home_margin']:+.1f}</div></div>
            <div><div class='metric-label'>Total</div><div class='metric-value'>{p['total_signal']}</div><div class='metric-sub'>Proj {p['projected_total']:.1f}</div></div>
            <div><div class='metric-label'>EV / Kelly</div><div class='metric-value'>{(p['ml_ev'] or 0)*100:.1f}%</div><div class='metric-sub'>Kelly {p['ml_kelly']*100:.1f}%</div></div>
          </div>
          <span class='badge {'badge-green' if p['ml_qualified'] else 'badge-orange'}'>Data {p['data_score']}/100</span>
          <span class='badge'>Market: {p['odds_quality']}</span>
          <span class='badge'>Predicted Final: {p['away']} {p['pred_away_score']} — {p['home']} {p['pred_home_score']}</span>
          <div class='sub' style='margin-top:8px;'>Moneyline Gate Notes: {reasons}</div>
          <div class='sub' style='margin-top:4px;'>ML Safety: {p.get('market_blend_note','')}</div>
        </div>
        """, unsafe_allow_html=True)
        with st.expander(f"Details — {p['away']} @ {p['home']}"):
            c1, c2, c3 = st.columns(3)
            c1.metric(f"{p['home']} Prob", f"{p['home_prob']*100:.1f}%", odds_display(p['home_price']))
            c2.metric(f"{p['away']} Prob", f"{p['away_prob']*100:.1f}%", odds_display(p['away_price']))
            c3.metric("Home Rating Diff", f"{p['projected_home_margin']:+.2f}", "home perspective")
            if p.get("odds_rows"):
                st.dataframe(pd.DataFrame(p["odds_rows"]), use_container_width=True, hide_index=True)

with tab_props:
    st.markdown("<div class='section-title'>WNBA Player Props — OVER / UNDER / PASS</div>", unsafe_allow_html=True)
    show_props = qualified_props if qualified_props else prop_board[:30]
    if not show_props:
        st.info("No WNBA player prop lines available yet. This version now shows diagnostics below so you can see whether the issue is event matching, API access, or no posted prop rows.")
        diag = get_prop_diagnostics()
        if diag:
            st.dataframe(pd.DataFrame(diag), use_container_width=True, hide_index=True)
    else:
        diag = get_prop_diagnostics()
        if diag:
            with st.expander("Prop source diagnostics"):
                st.dataframe(pd.DataFrame(diag), use_container_width=True, hide_index=True)
    for p in show_props[:60]:
        card_class = "card-green" if p["qualified"] else "card-orange"
        reasons = ", ".join(p.get("reasons", [])) or "All prop gates passed"
        st.markdown(f"""
        <div class='{card_class}'>
          <div style='display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap;'>
            <div>
              <div class='team-name'>{p['player']} — {p['prop_label']}</div>
              <div class='sub'>{p['away']} @ {p['home']} • {p['line_source']} • {p['projection_note']}</div>
            </div>
            <div class='big-prob {'green' if p['qualified'] else 'orange'}'>{p['side']}</div>
          </div>
          <div class='metric-grid' style='grid-template-columns:repeat(6,minmax(0,1fr));'>
            <div><div class='metric-label'>Projection</div><div class='metric-value'>{p['projection']:.2f}</div></div>
            <div><div class='metric-label'>Line</div><div class='metric-value'>{p['line']:.1f}</div></div>
            <div><div class='metric-label'>Pick %</div><div class='metric-value'>{p['pick_prob']*100:.1f}%</div></div>
            <div><div class='metric-label'>Edge</div><div class='metric-value'>{p['edge']:.2f}</div></div>
            <div><div class='metric-label'>Price</div><div class='metric-value'>{odds_display(p['price'])}</div></div>
            <div><div class='metric-label'>EV</div><div class='metric-value'>{(p['ev'] or 0)*100:.1f}%</div></div>
          </div>
          <span class='badge {'badge-green' if p['qualified'] else 'badge-orange'}'>{p['signal']}</span>
          <span class='badge'>Data {p['data_score']}/100</span>
          <span class='badge'>Over {p['over_prob']*100:.1f}%</span>
          <span class='badge'>Under {p['under_prob']*100:.1f}%</span>
          <span class='badge'>CLV {p['clv']}</span>
          <div class='sub' style='margin-top:8px;'>Gate Notes: {reasons}</div>
        </div>
        """, unsafe_allow_html=True)
        with st.expander(f"Book rows — {p['player']} {p['prop']}"):
            st.dataframe(pd.DataFrame(p.get("prop_rows", [])), use_container_width=True, hide_index=True)

with tab_all:
    st.markdown("<div class='section-title'>All Market Rows</div>", unsafe_allow_html=True)
    market_rows = []
    for p in market_board:
        market_rows.append({
            "Game": f"{p['away']} @ {p['home']}",
            "ML Pick": p["model_pick"],
            "ML Prob": round(p["pick_prob"]*100, 1),
            "ML Price": odds_display(p["pick_price"]),
            "ML Signal": p["ml_signal"],
            "Spread Signal": p["spread_signal"],
            "Total Signal": p["total_signal"],
            "Pred Final": f"{p['away']} {p['pred_away_score']} - {p['home']} {p['pred_home_score']}",
            "Data": p["data_score"],
        })
    st.dataframe(pd.DataFrame(market_rows), use_container_width=True, hide_index=True)

    st.markdown("<div class='section-title'>All Prop Rows</div>", unsafe_allow_html=True)
    if prop_board:
        prop_rows = [{
            "Game": f"{p['away']} @ {p['home']}",
            "Player": p["player"], "Prop": p["prop"], "Projection": round(p["projection"], 2),
            "Line": p["line"], "Side": p["side"], "Pick %": round(p["pick_prob"]*100, 1),
            "EV %": None if p["ev"] is None else round(p["ev"]*100, 1), "Signal": p["signal"], "Qualified": p["qualified"]
        } for p in prop_board]
        st.dataframe(pd.DataFrame(prop_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No prop rows loaded.")

with tab_tracker:
    st.markdown("<div class='section-title'>Market Snapshot Tracker</div>", unsafe_allow_html=True)
    mp = load_json(MARKET_PICK_LOG, [])
    mr = load_json(MARKET_RESULT_LOG, [])
    st.dataframe(pd.DataFrame(mp), use_container_width=True, hide_index=True) if mp else st.info("No market snapshots saved yet.")
    st.markdown("<div class='section-title'>Market Results</div>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(mr), use_container_width=True, hide_index=True) if mr else st.info("No market results graded yet.")

    st.markdown("<div class='section-title'>Prop Snapshot Tracker</div>", unsafe_allow_html=True)
    pp = load_json(PROP_PICK_LOG, [])
    pr = load_json(PROP_RESULT_LOG, [])
    st.dataframe(pd.DataFrame(pp), use_container_width=True, hide_index=True) if pp else st.info("No prop snapshots saved yet.")
    st.markdown("<div class='section-title'>Prop Results</div>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(pr), use_container_width=True, hide_index=True) if pr else st.info("No prop results graded yet.")

with tab_learn:
    st.markdown("<div class='section-title'>Learning + Calibration</div>", unsafe_allow_html=True)
    perf = performance_summary()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ML Graded", perf["market_graded"])
    c2.metric("ML Hit Rate", "N/A" if perf["market_hit"] is None else f"{perf['market_hit']*100:.1f}%")
    c3.metric("Prop Graded", perf["prop_graded"])
    c4.metric("Prop Hit Rate", "N/A" if perf["prop_hit"] is None else f"{perf['prop_hit']*100:.1f}%")
    st.subheader("Market Learning")
    st.json(load_market_learning())
    st.subheader("Prop Learning")
    st.json(load_prop_learning())

with tab_logs:
    logs = load_json(REQUEST_LOG_FILE, [])
    if logs:
        st.dataframe(pd.DataFrame(logs[-300:]), use_container_width=True, hide_index=True)
    else:
        st.success("No source errors logged.")

st.caption("Educational analytics only. No model can guarantee betting outcomes. WNBA props depend on real sportsbook prop availability.")
