# -*- coding: utf-8 -*-
"""
DEVIL PICKS — NBA ONLY CLEAN MARKET + PLAYER PROPS ENGINE
Streamlit Community Cloud / Colab / local ready.

What this version fixes:
- NBA only. No WNBA endpoints, labels, folders, files, or filters.
- Player props show in their own raw table even when projections cannot be made yet.
- Underdog direct public prop parsing added as fallback.
- PrizePicks public projection parsing added as fallback when available.
- The Odds API NBA props supported when ODDS_API_KEY is set.
- Removed deprecated datetime.utcnow().
- Removed deprecated use_container_width=True. Uses width="stretch".
- Added caching and source diagnostics so blank prop pages are easier to debug.
- Added API key override, injury/lineup adjustments, closing-line tracking, auto grading, and longer history.

Optional secret/environment variable:
ODDS_API_KEY = your The Odds API key
"""

import os
import re
import json
import math
import difflib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import streamlit as st

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

# ============================================================
# CONFIG
# ============================================================
APP_TITLE = "DEVIL PICKS — NBA CLEAN ENGINE"
SPORT_KEY = "basketball_nba"
CURRENT_SEASON = "2025-26"
DEFAULT_ODDS = -110
MAX_KELLY = 0.03

LOCAL_DIR = "devil_picks_nba_clean"
DRIVE_DIR = "/content/drive/MyDrive/devil_picks_nba_clean"

try:
    from google.colab import drive  # type: ignore
    if not os.path.exists("/content/drive/MyDrive"):
        drive.mount("/content/drive", force_remount=False)
    os.makedirs(DRIVE_DIR, exist_ok=True)
    STORAGE_DIR = DRIVE_DIR
except Exception:
    os.makedirs(LOCAL_DIR, exist_ok=True)
    STORAGE_DIR = LOCAL_DIR

REQUEST_LOG_FILE = os.path.join(STORAGE_DIR, "request_log.json")
PROP_SNAPSHOT_FILE = os.path.join(STORAGE_DIR, "nba_prop_snapshot.json")
MARKET_SNAPSHOT_FILE = os.path.join(STORAGE_DIR, "nba_market_snapshot.json")
BET_TRACKER_FILE = os.path.join(STORAGE_DIR, "nba_bet_tracker.json")
EDGE_HISTORY_FILE = os.path.join(STORAGE_DIR, "nba_edge_history.json")
CLOSING_LINE_FILE = os.path.join(STORAGE_DIR, "nba_closing_line_history.json")
INJURY_LINEUP_FILE = os.path.join(STORAGE_DIR, "nba_injury_lineup_adjustments.json")
GRADED_HISTORY_FILE = os.path.join(STORAGE_DIR, "nba_graded_history.json")

NBA_SCOREBOARD = "https://cdn.nba.com/static/json/liveData/scoreboard/scoreboard_00.json"
NBA_TODAY_SCOREBOARD = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
NBA_BOXSCORE = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
NBA_COMMON_PLAYERS = "https://stats.nba.com/stats/commonallplayers"
NBA_PLAYER_GAMELOG = "https://stats.nba.com/stats/playergamelog"
ODDS_BASE = "https://api.the-odds-api.com/v4"
PRIZEPICKS_URL = "https://api.prizepicks.com/projections"
ESPN_NBA_TEAMS = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"

UNDERDOG_URLS = [
    "https://api.underdogfantasy.com/beta/v5/over_under_lines",
    "https://api.underdogfantasy.com/v1/over_under_lines",
]

TEAM_ID_TO_ABBR = {
    1610612737: "ATL", 1610612738: "BOS", 1610612751: "BKN", 1610612766: "CHA", 1610612741: "CHI",
    1610612739: "CLE", 1610612742: "DAL", 1610612743: "DEN", 1610612765: "DET", 1610612744: "GSW",
    1610612745: "HOU", 1610612754: "IND", 1610612746: "LAC", 1610612747: "LAL", 1610612763: "MEM",
    1610612748: "MIA", 1610612749: "MIL", 1610612750: "MIN", 1610612740: "NOP", 1610612752: "NYK",
    1610612760: "OKC", 1610612753: "ORL", 1610612755: "PHI", 1610612756: "PHX", 1610612757: "POR",
    1610612758: "SAC", 1610612759: "SAS", 1610612761: "TOR", 1610612762: "UTA", 1610612764: "WAS",
}

ABBR_TO_NAME = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets", "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers", "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons", "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies", "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves", "NOP": "New Orleans Pelicans", "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder", "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs", "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}

PROP_CONFIG = {
    "PTS": {"label": "Points", "markets": ["player_points"], "cols": ["PTS"], "min_edge": 1.8, "limits": (3.5, 45.5)},
    "REB": {"label": "Rebounds", "markets": ["player_rebounds"], "cols": ["REB"], "min_edge": 1.5, "limits": (1.5, 22.5)},
    "AST": {"label": "Assists", "markets": ["player_assists"], "cols": ["AST"], "min_edge": 1.5, "limits": (0.5, 17.5)},
    "PRA": {"label": "PRA", "markets": ["player_points_rebounds_assists"], "cols": ["PTS", "REB", "AST"], "min_edge": 2.5, "limits": (8.5, 65.5)},
    "PR": {"label": "Points + Rebounds", "markets": ["player_points_rebounds"], "cols": ["PTS", "REB"], "min_edge": 2.2, "limits": (6.5, 58.5)},
    "PA": {"label": "Points + Assists", "markets": ["player_points_assists"], "cols": ["PTS", "AST"], "min_edge": 2.2, "limits": (6.5, 58.5)},
    "RA": {"label": "Rebounds + Assists", "markets": ["player_rebounds_assists"], "cols": ["REB", "AST"], "min_edge": 2.0, "limits": (2.5, 34.5)},
    "3PM": {"label": "3PM", "markets": ["player_threes"], "cols": ["FG3M"], "min_edge": 0.65, "limits": (0.5, 8.5)},
}

# ============================================================
# PAGE / STYLE
# ============================================================
st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root {--red:#ff344f; --green:#38f063; --orange:#ffb02e; --bg:#050812; --panel:#0b1220; --muted:#aeb7c9;}
.stApp {background: radial-gradient(circle at top left,#21000a 0%,#070b13 38%,#02040a 100%); color:#f7f8fb;}
.block-container {padding-top:1rem; max-width:1650px;}
section[data-testid="stSidebar"] {background:linear-gradient(180deg,#050912,#02040a); border-right:1px solid rgba(255,52,79,.28);}
h1,h2,h3 {color:#fff;}
.hero {border:1px solid rgba(255,255,255,.16); background:linear-gradient(135deg,rgba(12,19,34,.96),rgba(5,8,18,.96)); border-radius:24px; padding:22px; box-shadow:0 0 34px rgba(255,52,79,.11); margin-bottom:16px;}
.logo-title {font-size:31px; font-weight:950; letter-spacing:-.5px;}
.sub {color:#aeb7c9; font-size:13px;}
.card {border:1px solid rgba(255,255,255,.14); background:linear-gradient(145deg,#0a111f,#080d18); border-radius:19px; padding:18px; box-shadow:0 0 22px rgba(0,0,0,.28); margin-bottom:14px;}
.card-green {border:1px solid rgba(56,240,99,.45); background:linear-gradient(145deg,rgba(0,42,18,.70),rgba(8,13,24,.94)); border-radius:19px; padding:18px; box-shadow:0 0 24px rgba(56,240,99,.14); margin-bottom:14px;}
.card-orange {border:1px solid rgba(255,176,46,.45); background:linear-gradient(145deg,rgba(54,32,0,.70),rgba(8,13,24,.94)); border-radius:19px; padding:18px; box-shadow:0 0 24px rgba(255,176,46,.12); margin-bottom:14px;}
.metric-grid {display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:10px 0 16px 0;}
.metric-box {border:1px solid rgba(255,255,255,.14); background:linear-gradient(145deg,#0a111f,#080d18); border-radius:16px; padding:14px; min-height:88px;}
.metric-label {font-size:12px; color:#aeb7c9; text-transform:uppercase; font-weight:800; letter-spacing:.05em;}
.metric-value {font-size:28px; color:#fff; font-weight:950; margin-top:5px;}
.metric-sub {font-size:12px; color:#aeb7c9; margin-top:4px;}
.team-row {display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:20px;}
.team-name {font-size:25px; font-weight:950;}
.vs-pill {border:1px solid rgba(255,255,255,.18); padding:10px 16px; border-radius:999px; color:#dce4f5; font-weight:900; background:#0a111f; text-align:center;}
.green {color:#38f063;} .red {color:#ff344f;} .orange {color:#ffb02e;} .muted {color:#aeb7c9;}
.badge {display:inline-block; padding:7px 12px; border-radius:999px; font-weight:900; font-size:12px; margin:3px 5px 3px 0; border:1px solid rgba(255,255,255,.18); background:#101827; color:#dce4f5;}
.badge-green {background:#002c16; border-color:rgba(56,240,99,.55); color:#b9ffd0;}
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
# BASIC HELPERS
# ============================================================
def get_secret(key: str, default: str = "") -> str:
    try:
        value = st.secrets.get(key, default)
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(key, default)

ODDS_API_KEY = get_secret("ODDS_API_KEY", "")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat(timespec="seconds")


def app_now() -> datetime:
    if ZoneInfo:
        return datetime.now(ZoneInfo("America/New_York"))
    return datetime.now(timezone.utc) - timedelta(hours=5)


def safe_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def load_json(path: str, default: Any) -> Any:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_json(path: str, data: Any) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


def log_request(source: str, status: str, message: str = "") -> None:
    rows = load_json(REQUEST_LOG_FILE, [])
    rows.append({"time": now_iso(), "source": source[:160], "status": status[:80], "message": str(message)[:500]})
    save_json(REQUEST_LOG_FILE, rows[-700:])


def normalize_name(name: Any) -> str:
    s = str(name or "").lower().strip()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(s.split())


def name_score(a: Any, b: Any) -> float:
    aa, bb = normalize_name(a), normalize_name(b)
    if not aa or not bb:
        return 0.0
    if aa == bb:
        return 1.0
    if aa in bb or bb in aa:
        return 0.94
    return difflib.SequenceMatcher(None, aa, bb).ratio()


def flatten_json(obj: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        out.append(obj)
        for v in obj.values():
            out.extend(flatten_json(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(flatten_json(v))
    return out


def american_to_decimal(odds: Optional[float]) -> Optional[float]:
    odds = safe_float(odds)
    if odds is None:
        return None
    return 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)


def expected_value(prob: Optional[float], odds: Optional[float]) -> Optional[float]:
    dec = american_to_decimal(odds)
    if prob is None or dec is None:
        return None
    return (prob * (dec - 1)) - (1 - prob)


def kelly_fraction(prob: Optional[float], odds: Optional[float]) -> float:
    dec = american_to_decimal(odds)
    if prob is None or dec is None:
        return 0.0
    b = dec - 1
    q = 1 - prob
    if b <= 0:
        return 0.0
    return clamp(((b * prob) - q) / b, 0.0, MAX_KELLY)


def odds_display(o: Optional[float]) -> str:
    o = safe_float(o)
    if o is None:
        return "N/A"
    return f"+{int(o)}" if o > 0 else str(int(o))


def valid_prop_line(prop: str, line: Any) -> bool:
    val = safe_float(line)
    if val is None or prop not in PROP_CONFIG:
        return False
    lo, hi = PROP_CONFIG[prop]["limits"]
    return lo <= val <= hi


def prop_from_market_text(text: Any) -> Optional[str]:
    t = normalize_name(text)
    if not t:
        return None
    if any(bad in t for bad in ["wnba", "fantasy score", "turnover", "steals", "blocks", "double double"]):
        return None
    if "points rebounds assists" in t or "pts rebs asts" in t or t == "pra":
        return "PRA"
    if "points rebounds" in t or "pts rebs" in t:
        return "PR"
    if "points assists" in t or "pts ast" in t:
        return "PA"
    if "rebounds assists" in t or "rebs ast" in t:
        return "RA"
    if any(x in t for x in ["3 pointers", "three pointers", "threes", "3pt", "three point", "3 pm"]):
        return "3PM"
    if "points" in t or t in ["pts", "point"]:
        return "PTS"
    if "rebounds" in t or t in ["reb", "rebs", "boards"]:
        return "REB"
    if "assists" in t or t in ["ast", "asts"]:
        return "AST"
    for code, cfg in PROP_CONFIG.items():
        for mk in cfg["markets"]:
            if t == normalize_name(mk):
                return code
    return None

# ============================================================
# HTTP
# ============================================================
@st.cache_data(ttl=300, show_spinner=False)
def safe_get_json(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15) -> Any:
    headers = {
        "User-Agent": "Mozilla/5.0 DevilPicksNBA/clean",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nba.com/",
        "Origin": "https://www.nba.com",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        if r.status_code != 200:
            log_request(url, f"HTTP {r.status_code}", r.text[:300])
            return None
        return r.json()
    except Exception as e:
        log_request(url, "REQUEST_ERROR", str(e))
        return None

# ============================================================
# NBA SCHEDULE / BOXSCORE
# ============================================================
def date_for_mode(day_mode: str) -> str:
    d = app_now()
    if day_mode == "Tomorrow":
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


@st.cache_data(ttl=180, show_spinner=False)
def get_scoreboard(date_str: str) -> Dict[str, Any]:
    data = safe_get_json(NBA_SCOREBOARD, params={"GameDate": date_str}, timeout=15)
    if not data or "scoreboard" not in data:
        data = safe_get_json(NBA_TODAY_SCOREBOARD, timeout=15)
    return data or {"scoreboard": {"games": []}}


def extract_games(date_str: str) -> List[Dict[str, Any]]:
    data = get_scoreboard(date_str)
    games = data.get("scoreboard", {}).get("games", []) or []
    rows = []
    for g in games:
        home = g.get("homeTeam", {}) or {}
        away = g.get("awayTeam", {}) or {}
        home_id = home.get("teamId")
        away_id = away.get("teamId")
        home_abbr = home.get("teamTricode") or TEAM_ID_TO_ABBR.get(home_id, "HOME")
        away_abbr = away.get("teamTricode") or TEAM_ID_TO_ABBR.get(away_id, "AWAY")
        rows.append({
            "date": date_str,
            "game_id": str(g.get("gameId") or g.get("gameCode") or f"{date_str}_{away_abbr}_{home_abbr}"),
            "status": g.get("gameStatusText") or str(g.get("gameStatus") or "Scheduled"),
            "game_time": g.get("gameTimeUTC") or g.get("gameEt") or "",
            "arena": g.get("arenaName") or "",
            "home": home_abbr,
            "away": away_abbr,
            "home_name": ABBR_TO_NAME.get(home_abbr, home_abbr),
            "away_name": ABBR_TO_NAME.get(away_abbr, away_abbr),
            "home_score": home.get("score"),
            "away_score": away.get("score"),
            "home_record": f"{home.get('wins','')}-{home.get('losses','')}" if home.get("wins") is not None else "",
            "away_record": f"{away.get('wins','')}-{away.get('losses','')}" if away.get("wins") is not None else "",
        })
    return rows


@st.cache_data(ttl=300, show_spinner=False)
def get_boxscore(game_id: str) -> Dict[str, Any]:
    return safe_get_json(NBA_BOXSCORE.format(game_id=game_id), timeout=15) or {}


# ============================================================
# LIVE INJURY / LINEUP + CLOSING LINE / GRADING HELPERS
# ============================================================
@st.cache_data(ttl=1800, show_spinner=False)
def get_espn_injury_feed() -> List[Dict[str, Any]]:
    """Best-effort public injury feed. If ESPN changes the endpoint, app keeps running and manual adjustments still work."""
    rows: List[Dict[str, Any]] = []
    teams = safe_get_json(ESPN_NBA_TEAMS, timeout=15) or {}
    try:
        for item in (((teams.get("sports") or [{}])[0].get("leagues") or [{}])[0].get("teams") or []):
            team = (item.get("team") or {})
            abbr = str(team.get("abbreviation") or "").upper()
            tid = team.get("id")
            if not abbr or not tid:
                continue
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{tid}/injuries"
            data = safe_get_json(url, timeout=10) or {}
            for inj in data.get("injuries", []) or []:
                athlete = inj.get("athlete") or {}
                rows.append({
                    "Team": abbr,
                    "Player": athlete.get("displayName") or athlete.get("fullName") or "",
                    "Status": inj.get("status") or inj.get("type") or "",
                    "Detail": inj.get("details") or inj.get("shortComment") or inj.get("description") or "",
                    "Updated": inj.get("date") or "",
                    "Source": "ESPN best-effort",
                })
    except Exception as e:
        log_request("ESPN Injuries", "ERROR", str(e)[:250])
    if not rows:
        log_request("ESPN Injuries", "EMPTY", "No public injury rows returned. Use manual injury/lineup adjustments.")
    return rows


def parse_manual_adjustments(text: str) -> Dict[str, float]:
    """Format: BOS:-2.5 on one line, LAL:+1.0 on another. Negative hurts a team rating."""
    out: Dict[str, float] = {}
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        team, val = line.split(":", 1)
        team = team.strip().upper()
        adj = safe_float(val.strip())
        if team in ABBR_TO_NAME and adj is not None:
            out[team] = float(adj)
    return out


def injury_team_adjustments(injuries: List[Dict[str, Any]], manual_text: str) -> Dict[str, float]:
    """Convert injury/lineup feed into conservative point adjustments by team."""
    adj: Dict[str, float] = parse_manual_adjustments(manual_text)
    for r in injuries:
        team = str(r.get("Team") or "").upper()
        if team not in ABBR_TO_NAME:
            continue
        blob = normalize_name(f"{r.get('Status','')} {r.get('Detail','')}")
        # Conservative automatic adjustment. Manual text should be used for star-level news.
        delta = 0.0
        if any(x in blob for x in ["out", "doubtful", "inactive", "will not play"]):
            delta -= 0.75
        elif any(x in blob for x in ["questionable", "game time", "gtd"]):
            delta -= 0.30
        elif "probable" in blob:
            delta -= 0.05
        if delta:
            adj[team] = adj.get(team, 0.0) + delta
    return adj


def save_closing_snapshot(game_rows: List[Dict[str, Any]], prop_rows: List[Dict[str, Any]], label: str) -> int:
    hist = load_json(CLOSING_LINE_FILE, [])
    stamp = now_iso()
    for g in game_rows:
        hist.append({
            "saved_at": stamp, "label": label, "Type": "Game Market", "date": g.get("date"), "game_id": g.get("game_id"),
            "Game": f"{g.get('away')} @ {g.get('home')}", "home": g.get("home"), "away": g.get("away"),
            "home_ml": g.get("home_ml"), "away_ml": g.get("away_ml"), "spread": g.get("spread"), "total": g.get("total"), "quality": g.get("quality")
        })
    for p in prop_rows[:500]:
        hist.append({
            "saved_at": stamp, "label": label, "Type": "Player Prop", "Player": p.get("Player"), "Prop": p.get("Prop"),
            "Line": p.get("Line"), "Book": p.get("Book"), "Source": p.get("Source"), "Side": p.get("Side"), "Price": p.get("Price")
        })
    save_json(CLOSING_LINE_FILE, hist[-20000:])
    return len(game_rows) + min(len(prop_rows), 500)


def find_final_game_for_tracker(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    key = str(row.get("Tracker Key") or "")
    parts = key.split("|")
    date = parts[0] if len(parts) >= 2 else app_now().strftime("%Y-%m-%d")
    game_id = parts[1] if len(parts) >= 2 else ""
    # Search saved date, plus nearby days for late games / timezone shifts.
    dates = [date]
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        dates += [(dt + timedelta(days=1)).strftime("%Y-%m-%d"), (dt - timedelta(days=1)).strftime("%Y-%m-%d")]
    except Exception:
        pass
    for d in dict.fromkeys(dates):
        for g in extract_games(d):
            if game_id and str(g.get("game_id")) == game_id:
                return g
            if str(row.get("Game") or "") == f"{g.get('away')} @ {g.get('home')}":
                return g
    return None


def grade_game_market_bet(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    if out.get("Result") in ["WIN", "LOSS", "PUSH"]:
        return out
    if out.get("Type") != "Game Market":
        out.setdefault("Result", "PENDING")
        out.setdefault("Grade Note", "Auto grading for props needs final player boxscore match; game markets grade automatically.")
        return out
    g = find_final_game_for_tracker(out)
    if not g:
        out["Result"] = "PENDING"
        out["Grade Note"] = "Final score not found yet."
        return out
    status = normalize_name(g.get("status"))
    if "final" not in status:
        out["Result"] = "PENDING"
        out["Grade Note"] = f"Game not final: {g.get('status')}"
        return out
    home_score = safe_float(g.get("home_score"))
    away_score = safe_float(g.get("away_score"))
    if home_score is None or away_score is None:
        out["Result"] = "PENDING"
        out["Grade Note"] = "Final score missing."
        return out
    home, away = g.get("home"), g.get("away")
    market = out.get("Market")
    pick = str(out.get("Pick") or "")
    result = "PENDING"
    if market == "Moneyline":
        winner = home if home_score > away_score else away
        result = "WIN" if winner in pick else "LOSS"
    elif market == "Spread":
        # Pick looks like "BOS -4.5" or "LAL +4.5".
        m = re.search(r"\b([A-Z]{2,3})\s*([+-]\d+(?:\.\d+)?)", pick)
        if m:
            team, spr = m.group(1), float(m.group(2))
            if team == home:
                val = home_score + spr - away_score
            else:
                val = away_score + spr - home_score
            result = "PUSH" if abs(val) < 1e-9 else ("WIN" if val > 0 else "LOSS")
    elif market == "Total":
        line = safe_float(out.get("Line"))
        if line is not None:
            val = home_score + away_score - line
            if abs(val) < 1e-9:
                result = "PUSH"
            elif "OVER" in pick.upper():
                result = "WIN" if val > 0 else "LOSS"
            elif "UNDER" in pick.upper():
                result = "WIN" if val < 0 else "LOSS"
    out["Result"] = result
    out["Final Score"] = f"{away} {int(away_score)} - {home} {int(home_score)}"
    out["Grade Note"] = "Auto graded from NBA final score."
    out["Graded At"] = now_iso() if result in ["WIN", "LOSS", "PUSH"] else ""
    return out


def auto_grade_tracker() -> Tuple[int, int]:
    tracker = load_json(BET_TRACKER_FILE, [])
    if not tracker:
        return 0, 0
    graded = []
    changed = 0
    for r in tracker:
        before = r.get("Result")
        nr = grade_game_market_bet(r)
        if nr.get("Result") != before and nr.get("Result") in ["WIN", "LOSS", "PUSH"]:
            changed += 1
        graded.append(nr)
    save_json(BET_TRACKER_FILE, graded[-10000:])
    finished = [r for r in graded if r.get("Result") in ["WIN", "LOSS", "PUSH"]]
    save_json(GRADED_HISTORY_FILE, finished[-10000:])
    return changed, len(finished)

# ============================================================
# THE ODDS API MARKET ODDS
# ============================================================
@st.cache_data(ttl=360, show_spinner=False)
def get_market_odds() -> List[Dict[str, Any]]:
    if not ODDS_API_KEY:
        log_request("The Odds API", "NO_KEY", "ODDS_API_KEY missing. Market and book prop odds limited.")
        return []
    url = f"{ODDS_BASE}/sports/{SPORT_KEY}/odds"
    data = safe_get_json(url, params={
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
    }, timeout=20)
    return data if isinstance(data, list) else []


@st.cache_data(ttl=600, show_spinner=False)
def get_odds_events() -> List[Dict[str, Any]]:
    if not ODDS_API_KEY:
        return []
    url = f"{ODDS_BASE}/sports/{SPORT_KEY}/events"
    data = safe_get_json(url, params={"apiKey": ODDS_API_KEY}, timeout=20)
    return data if isinstance(data, list) else []


def match_odds_event_for_game(game: Dict[str, Any]) -> Tuple[Optional[str], float]:
    best_id, best_score = None, 0.0
    for ev in get_odds_events():
        h, a = ev.get("home_team", ""), ev.get("away_team", "")
        normal = (name_score(game["home_name"], h) + name_score(game["away_name"], a)) / 2
        swapped = (name_score(game["home_name"], a) + name_score(game["away_name"], h)) / 2
        score = max(normal, swapped)
        if score > best_score:
            best_score = score
            best_id = ev.get("id")
    return (best_id if best_score >= 0.70 else None), best_score


def market_summary_for_game(game: Dict[str, Any]) -> Dict[str, Any]:
    result = {"home_ml": None, "away_ml": None, "spread": None, "total": None, "quality": "NO ODDS", "source": "No Odds"}
    events = get_market_odds()
    if not events:
        return result
    chosen, best_score = None, 0.0
    for ev in events:
        h, a = ev.get("home_team", ""), ev.get("away_team", "")
        normal = (name_score(game["home_name"], h) + name_score(game["away_name"], a)) / 2
        swapped = (name_score(game["home_name"], a) + name_score(game["away_name"], h)) / 2
        score = max(normal, swapped)
        if score > best_score:
            chosen, best_score = ev, score
    if not chosen or best_score < 0.70:
        return result

    home_ml, away_ml, spreads, totals = [], [], [], []
    for book in chosen.get("bookmakers", []) or []:
        for market in book.get("markets", []) or []:
            key = market.get("key")
            for out in market.get("outcomes", []) or []:
                nm = out.get("name", "")
                price = safe_float(out.get("price"))
                point = safe_float(out.get("point"))
                if key == "h2h" and price is not None:
                    if name_score(nm, game["home_name"]) >= 0.70 or name_score(nm, game["home"]) >= 0.90:
                        home_ml.append(price)
                    elif name_score(nm, game["away_name"]) >= 0.70 or name_score(nm, game["away"]) >= 0.90:
                        away_ml.append(price)
                elif key == "spreads" and point is not None:
                    if name_score(nm, game["home_name"]) >= 0.70 or name_score(nm, game["home"]) >= 0.90:
                        spreads.append(point)
                elif key == "totals" and point is not None:
                    totals.append(point)
    if home_ml:
        result["home_ml"] = float(np.median(home_ml))
    if away_ml:
        result["away_ml"] = float(np.median(away_ml))
    if spreads:
        result["spread"] = float(np.median(spreads))
    if totals:
        result["total"] = float(np.median(totals))
    found = sum(x is not None for x in [result["home_ml"], result["away_ml"], result["spread"], result["total"]])
    result["quality"] = "STRONG" if found >= 4 else "OK" if found >= 2 else "THIN" if found else "NO ODDS"
    result["source"] = "Sportsbook Consensus" if found else "No Odds"
    return result


# ============================================================
# GAME MARKET SIGNALS — MONEYLINE / SPREAD / TOTALS
# ============================================================
def implied_prob_from_american(odds: Optional[float]) -> Optional[float]:
    o = safe_float(odds)
    if o is None:
        return None
    if o < 0:
        return abs(o) / (abs(o) + 100.0)
    return 100.0 / (o + 100.0)


def remove_vig_two_way(p1: Optional[float], p2: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    if p1 is None or p2 is None or (p1 + p2) <= 0:
        return p1, p2
    s = p1 + p2
    return p1 / s, p2 / s


def market_confidence_label(score: float) -> str:
    if score >= 82:
        return "STRONG"
    if score >= 68:
        return "LEAN"
    if score >= 55:
        return "WATCH"
    return "PASS"


def get_team_live_stats_from_scoreboard(games: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Tiny same-day fallback power rating from records shown by NBA scoreboard."""
    stats: Dict[str, Dict[str, float]] = {}
    for g in games:
        for side in ["home", "away"]:
            abbr = g.get(side)
            rec = str(g.get(f"{side}_record") or "")
            wins, losses = 0, 0
            if "-" in rec:
                try:
                    wins, losses = [int(x) for x in rec.split("-", 1)]
                except Exception:
                    wins, losses = 0, 0
            games_played = wins + losses
            win_pct = wins / games_played if games_played else 0.50
            stats[abbr] = {"wins": wins, "losses": losses, "win_pct": win_pct}
    return stats


def build_game_market_signals(markets: List[Dict[str, Any]], team_adjustments: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    team_stats = get_team_live_stats_from_scoreboard(markets)
    team_adjustments = team_adjustments or {}
    rows: List[Dict[str, Any]] = []
    for g in markets:
        home = g.get("home")
        away = g.get("away")
        h_ml = safe_float(g.get("home_ml"))
        a_ml = safe_float(g.get("away_ml"))
        spread = safe_float(g.get("spread"))
        total = safe_float(g.get("total"))
        h_imp = implied_prob_from_american(h_ml)
        a_imp = implied_prob_from_american(a_ml)
        h_nv, a_nv = remove_vig_two_way(h_imp, a_imp)

        h_wp = team_stats.get(home, {}).get("win_pct", 0.50)
        a_wp = team_stats.get(away, {}).get("win_pct", 0.50)
        # Conservative model: mostly market-derived, small record/home-court tilt.
        adj_points = float(team_adjustments.get(home, 0.0)) - float(team_adjustments.get(away, 0.0))
        raw_home_model = 0.50 + ((h_wp - a_wp) * 0.18) + 0.025 + (adj_points / 100.0)
        if h_nv is not None:
            home_model = (h_nv * 0.72) + (raw_home_model * 0.28)
        else:
            home_model = raw_home_model
        home_model = clamp(float(home_model), 0.08, 0.92)
        away_model = 1.0 - home_model

        home_ev = expected_value(home_model, h_ml) if h_ml is not None else None
        away_ev = expected_value(away_model, a_ml) if a_ml is not None else None
        ml_pick = home if (home_ev or -9) >= (away_ev or -9) else away
        ml_prob = home_model if ml_pick == home else away_model
        ml_price = h_ml if ml_pick == home else a_ml
        ml_ev = home_ev if ml_pick == home else away_ev
        ml_score = 50 + abs((ml_prob - 0.50) * 100) + max(0.0, (ml_ev or 0) * 100)
        ml_signal = market_confidence_label(ml_score)
        if ml_ev is not None and ml_ev < -0.015:
            ml_signal = "PASS"

        # Spread estimate: convert moneyline strength to rough point margin.
        expected_margin_home = (home_model - 0.50) * 16.0 + 2.0 + adj_points
        spread_edge = None
        spread_pick = "PASS"
        spread_prob = None
        spread_signal = "PASS"
        if spread is not None:
            # The Odds API point is usually home team's spread in this summary.
            spread_edge = expected_margin_home + spread
            spread_pick = f"{home} {spread:+.1f}" if spread_edge > 0 else f"{away} {(-spread):+.1f}"
            spread_prob = clamp(0.50 + abs(spread_edge) / 18.0, 0.50, 0.68)
            spread_score = 50 + abs(spread_edge) * 6 + (spread_prob - 0.50) * 100
            spread_signal = market_confidence_label(spread_score)

        # Total estimate fallback: no player/team pace model here, so make it conservative.
        total_edge = None
        total_pick = "PASS"
        total_prob = None
        total_signal = "PASS"
        if total is not None:
            # A neutral NBA baseline plus competitiveness adjustment. Conservative unless edge is material.
            estimated_total = 226.0 + (8.0 * (1.0 - abs(home_model - 0.50) * 2.0))
            total_edge = estimated_total - total
            total_pick = "OVER" if total_edge > 0 else "UNDER"
            total_prob = clamp(0.50 + abs(total_edge) / 28.0, 0.50, 0.66)
            total_score = 50 + abs(total_edge) * 3.8 + (total_prob - 0.50) * 100
            total_signal = market_confidence_label(total_score)

        rows.append({
            **g,
            "Home Model Prob": home_model,
            "Away Model Prob": away_model,
            "ML Pick": ml_pick,
            "ML Price": ml_price,
            "ML Prob": ml_prob,
            "ML EV": ml_ev,
            "ML Kelly": kelly_fraction(ml_prob, ml_price),
            "ML Signal": ml_signal,
            "Spread Pick": spread_pick,
            "Spread Edge": spread_edge,
            "Spread Prob": spread_prob,
            "Spread Signal": spread_signal,
            "Total Pick": total_pick,
            "Total Edge": total_edge,
            "Total Prob": total_prob,
            "Total Signal": total_signal,
            "Injury/Lineup Adj": adj_points,
            "Game Rating": round(max(ml_score if 'ml_score' in locals() else 0, 50), 1),
        })
    return rows


def fmt_pct(x: Any) -> str:
    v = safe_float(x)
    return "N/A" if v is None else f"{v*100:.1f}%"


def fmt_num(x: Any, digits: int = 2, signed: bool = False) -> str:
    v = safe_float(x)
    if v is None:
        return "N/A"
    return f"{v:+.{digits}f}" if signed else f"{v:.{digits}f}"

# ============================================================
# PLAYER DATABASE / LOGS
# ============================================================
@st.cache_data(ttl=86400, show_spinner=False)
def get_current_nba_players() -> pd.DataFrame:
    params = {"LeagueID": "00", "Season": CURRENT_SEASON, "IsOnlyCurrentSeason": "1"}
    data = safe_get_json(NBA_COMMON_PLAYERS, params=params, timeout=20)
    try:
        rs = data.get("resultSets", [])[0]
        df = pd.DataFrame(rs.get("rowSet", []), columns=rs.get("headers", []))
        if "PERSON_ID" in df.columns:
            df["PERSON_ID"] = pd.to_numeric(df["PERSON_ID"], errors="coerce")
        if "DISPLAY_FIRST_LAST" not in df.columns and "DISPLAY_LAST_COMMA_FIRST" in df.columns:
            df["DISPLAY_FIRST_LAST"] = df["DISPLAY_LAST_COMMA_FIRST"]
        df["norm"] = df["DISPLAY_FIRST_LAST"].map(normalize_name)
        return df
    except Exception:
        return pd.DataFrame()


def find_player_id(player_name: str) -> Tuple[Optional[int], float, str]:
    df = get_current_nba_players()
    if df.empty or "DISPLAY_FIRST_LAST" not in df.columns:
        return None, 0.0, ""
    target = normalize_name(player_name)
    best_id, best_name, best = None, "", 0.0
    for _, row in df.iterrows():
        nm = row.get("DISPLAY_FIRST_LAST", "")
        score = name_score(target, nm)
        if score > best:
            best = score
            best_name = str(nm)
            pid = safe_float(row.get("PERSON_ID"))
            best_id = int(pid) if pid is not None else None
    return (best_id if best >= 0.82 else None), best, best_name


@st.cache_data(ttl=3600, show_spinner=False)
def get_player_logs(player_id: int) -> pd.DataFrame:
    params = {"PlayerID": str(player_id), "Season": CURRENT_SEASON, "SeasonType": "Regular Season", "LeagueID": "00"}
    data = safe_get_json(NBA_PLAYER_GAMELOG, params=params, timeout=20)
    try:
        rs = data.get("resultSets", [])[0]
        df = pd.DataFrame(rs.get("rowSet", []), columns=rs.get("headers", []))
        for col in ["PTS", "REB", "AST", "FG3M", "MIN"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def project_prop(player: str, prop: str) -> Dict[str, Any]:
    pid, score, matched = find_player_id(player)
    if not pid:
        return {"projection": None, "std": None, "games": 0, "note": "No NBA player ID match", "matched_name": matched, "match_score": score}
    logs = get_player_logs(pid)
    if logs.empty:
        return {"projection": None, "std": None, "games": 0, "note": "No game logs yet", "matched_name": matched, "match_score": score}
    cols = PROP_CONFIG[prop]["cols"]
    missing = [c for c in cols if c not in logs.columns]
    if missing:
        return {"projection": None, "std": None, "games": 0, "note": f"Missing log columns: {missing}", "matched_name": matched, "match_score": score}
    values = logs[cols].sum(axis=1).dropna().astype(float)
    if len(values) < 3:
        return {"projection": None, "std": None, "games": int(len(values)), "note": "Not enough games", "matched_name": matched, "match_score": score}
    recent = values.head(min(10, len(values)))
    season = values
    projection = (recent.mean() * 0.65) + (season.mean() * 0.35)
    std = float(max(recent.std(ddof=0), season.std(ddof=0), 1.0))
    return {
        "projection": float(projection),
        "std": std,
        "games": int(len(values)),
        "note": f"Matched {matched} | recent+season blend",
        "matched_name": matched,
        "match_score": score,
    }

# ============================================================
# PROP SOURCES
# ============================================================
def clean_player_candidate(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    v = value.strip()
    low = normalize_name(v)
    if len(v.split()) < 2:
        return ""
    if any(bad in low for bad in ["over", "under", "points", "rebounds", "assists", "fantasy", "basketball", "nba", "wnba"]):
        return ""
    return v


def extract_line_info(obj: Dict[str, Any]) -> Tuple[Optional[float], str]:
    """
    Extract the actual sportsbook/fantasy prop line.

    IMPORTANT FIX:
    The old parser also checked generic keys like `value` and `points`.
    Some feeds use those fields for unrelated numbers, IDs, fantasy scoring, or prices,
    which can make prop lines look wrong. This version only trusts known line fields.
    """
    trusted_keys = [
        "stat_value", "statValue",
        "line_score", "lineScore",
        "line",
        "point",
        "over_under_value", "overUnderValue",
        "display_line", "displayLine",
    ]
    for key in trusted_keys:
        if key in obj:
            val = safe_float(obj.get(key))
            if val is not None:
                return val, key

    # Some APIs nest the line inside an option/outcome object. Still avoid generic `value`.
    for nested_key in ["over", "under", "outcome", "option", "selection"]:
        nested = obj.get(nested_key)
        if isinstance(nested, dict):
            val, field = extract_line_info(nested)
            if val is not None:
                return val, f"{nested_key}.{field}"
    return None, ""


def guess_line(obj: Dict[str, Any]) -> Optional[float]:
    val, _field = extract_line_info(obj)
    return val


def line_quality_note(prop: str, line: Any, source: str = "") -> str:
    val = safe_float(line)
    if val is None:
        return "BAD — missing line"
    if not valid_prop_line(prop, val):
        return "BAD — outside expected NBA range"
    # Most fantasy lines are .5 increments; sportsbook alt lines may be whole numbers too.
    frac = abs(val - round(val))
    if frac not in [0.0, 0.5] and min(abs(frac - 0.5), abs(frac - 0.0)) > 0.01:
        return "CHECK — unusual increment"
    if source in ["The Odds API", "PrizePicks", "Underdog"]:
        return "OK — direct feed line"
    return "OK"


def guess_player(obj: Dict[str, Any]) -> str:
    keys = ["player_name", "playerName", "participant_name", "participantName", "display_name", "displayName", "full_name", "fullName", "name", "title"]
    for key in keys:
        cand = clean_player_candidate(obj.get(key))
        if cand:
            return cand
    for nested in ["player", "athlete", "participant", "appearance"]:
        v = obj.get(nested)
        if isinstance(v, dict):
            cand = guess_player(v)
            if cand:
                return cand
    first = obj.get("first_name") or obj.get("firstName")
    last = obj.get("last_name") or obj.get("lastName")
    if first and last:
        return f"{first} {last}".strip()
    return ""


def guess_stat_text(obj: Dict[str, Any]) -> str:
    texts = []
    for key in ["stat_type", "statType", "stat", "stat_name", "statName", "display_stat", "displayStat", "appearance_stat", "over_under_type", "overUnderType", "market", "market_name", "title", "name", "label"]:
        v = obj.get(key)
        if isinstance(v, str):
            texts.append(v)
        elif isinstance(v, dict):
            texts.append(guess_stat_text(v))
    return " ".join([t for t in texts if t])


@st.cache_data(ttl=300, show_spinner=False)
def get_underdog_props() -> List[Dict[str, Any]]:
    """
    Underdog NBA props parser — STRUCTURED ONLY.

    This is the important line fix:
    - Do NOT flatten the whole JSON and guess random numbers.
    - Read each over_under_line object.
    - Use its related over_under object's `stat_value` / `line_score` as the true Underdog line.
    - Attach the related appearance/player and appearance_stat through the included maps.

    This keeps the displayed line matching Underdog instead of accidentally using IDs,
    option prices, fantasy values, or unrelated nested values.
    """
    rows: List[Dict[str, Any]] = []
    seen = set()

    def _included_maps(data: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        maps: Dict[str, Dict[str, Dict[str, Any]]] = {}
        included = data.get("included", []) if isinstance(data, dict) else []
        if isinstance(included, list):
            for item in included:
                if not isinstance(item, dict):
                    continue
                typ = str(item.get("type") or "")
                iid = str(item.get("id") or "")
                if typ and iid:
                    maps.setdefault(typ, {})[iid] = item
        return maps

    def _rel_id(obj: Dict[str, Any], rel_name: str) -> str:
        rel = (obj.get("relationships") or {}).get(rel_name) or {}
        data = rel.get("data")
        if isinstance(data, dict):
            return str(data.get("id") or "")
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return str(data[0].get("id") or "")
        return ""

    def _rel_ids(obj: Dict[str, Any], rel_name: str) -> List[str]:
        rel = (obj.get("relationships") or {}).get(rel_name) or {}
        data = rel.get("data")
        out: List[str] = []
        if isinstance(data, dict):
            iid = str(data.get("id") or "")
            if iid:
                out.append(iid)
        elif isinstance(data, list):
            for x in data:
                if isinstance(x, dict):
                    iid = str(x.get("id") or "")
                    if iid:
                        out.append(iid)
        return out

    def _attrs(obj: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(obj, dict):
            return {}
        a = obj.get("attributes")
        return a if isinstance(a, dict) else {}

    def _player_from_appearance(appearance: Optional[Dict[str, Any]], maps: Dict[str, Dict[str, Dict[str, Any]]]) -> str:
        aa = _attrs(appearance)
        for k in ["display_name", "displayName", "name", "full_name", "fullName", "title"]:
            cand = clean_player_candidate(aa.get(k))
            if cand:
                return cand
        # Appearance often points to player.
        if isinstance(appearance, dict):
            pid = _rel_id(appearance, "player")
            player = maps.get("player", {}).get(pid) or maps.get("players", {}).get(pid)
            pa = _attrs(player)
            first = pa.get("first_name") or pa.get("firstName")
            last = pa.get("last_name") or pa.get("lastName")
            if first and last:
                return f"{first} {last}".strip()
            for k in ["display_name", "displayName", "name", "full_name", "fullName"]:
                cand = clean_player_candidate(pa.get(k))
                if cand:
                    return cand
        return ""

    def _prop_from_appearance_stat(app_stat: Optional[Dict[str, Any]], over_under: Optional[Dict[str, Any]]) -> Optional[str]:
        parts: List[str] = []
        for obj in [app_stat, over_under]:
            a = _attrs(obj)
            for k in ["display_stat", "displayStat", "stat", "stat_type", "statType", "name", "title", "label"]:
                v = a.get(k)
                if isinstance(v, str):
                    parts.append(v)
        return prop_from_market_text(" ".join(parts))

    def _true_line_from_over_under(line_obj: Dict[str, Any], over_under: Optional[Dict[str, Any]]) -> Tuple[Optional[float], str]:
        # Underdog's real prop line lives on over_under.attributes most often.
        for source_name, obj in [("over_under", over_under), ("over_under_line", line_obj)]:
            a = _attrs(obj)
            for key in ["stat_value", "statValue", "line_score", "lineScore", "line"]:
                if key in a:
                    val = safe_float(a.get(key))
                    if val is not None:
                        return val, f"{source_name}.attributes.{key}"
            # Some payloads put attributes at top-level after transforms.
            if isinstance(obj, dict):
                for key in ["stat_value", "statValue", "line_score", "lineScore", "line"]:
                    if key in obj:
                        val = safe_float(obj.get(key))
                        if val is not None:
                            return val, f"{source_name}.{key}"
        return None, ""

    for url in UNDERDOG_URLS:
        data = safe_get_json(url, timeout=20)
        if not data or not isinstance(data, dict):
            log_request("Underdog", "FAILED", url)
            continue

        maps = _included_maps(data)
        entries = data.get("data", [])
        if not isinstance(entries, list):
            entries = []

        count_before = len(rows)
        for line_obj in entries:
            if not isinstance(line_obj, dict):
                continue

            # Only parse actual over_under_line rows, not every nested object.
            typ = str(line_obj.get("type") or "").lower()
            if typ and "over_under_line" not in typ and "over_under" not in typ:
                continue

            ou_id = _rel_id(line_obj, "over_under")
            over_under = maps.get("over_under", {}).get(ou_id) or maps.get("over_under_lines", {}).get(ou_id)
            if not over_under and typ == "over_under":
                over_under = line_obj

            # Sport filter: reject anything that explicitly says WNBA. Keep NBA / basketball.
            combined_blob = json.dumps([line_obj, over_under], default=str).lower()
            if "wnba" in combined_blob or "women" in combined_blob:
                continue
            if not any(x in combined_blob for x in ["nba", "basketball"]):
                continue

            # Related stat and appearance.
            app_stat_id = ""
            appearance_id = ""
            if isinstance(over_under, dict):
                app_stat_id = _rel_id(over_under, "appearance_stat") or _rel_id(over_under, "appearanceStat")
                appearance_id = _rel_id(over_under, "appearance") or _rel_id(over_under, "participant")
            app_stat = maps.get("appearance_stat", {}).get(app_stat_id) or maps.get("appearance_stats", {}).get(app_stat_id)
            appearance = maps.get("appearance", {}).get(appearance_id) or maps.get("appearances", {}).get(appearance_id)

            prop = _prop_from_appearance_stat(app_stat, over_under)
            line, raw_line_field = _true_line_from_over_under(line_obj, over_under)
            player = _player_from_appearance(appearance, maps)

            # Last resort for player name only, never for line.
            if not player:
                player = guess_player(_attrs(over_under)) or guess_player(_attrs(line_obj))

            if not prop or not player or not valid_prop_line(prop, line):
                continue

            # Pull over/under prices when available, but never use option fields as the line.
            side = "OVER/UNDER"
            price = None
            option_ids = _rel_ids(line_obj, "options") or _rel_ids(over_under or {}, "options")
            option_bits = []
            for oid in option_ids:
                opt = maps.get("over_under_option", {}).get(oid) or maps.get("over_under_options", {}).get(oid) or maps.get("option", {}).get(oid)
                oa = _attrs(opt)
                choice = str(oa.get("choice") or oa.get("type") or oa.get("side") or oa.get("description") or "").upper()
                payout = safe_float(oa.get("payout_multiplier") or oa.get("payoutMultiplier") or oa.get("odds") or oa.get("price"))
                if choice:
                    option_bits.append(choice)
                if price is None and payout is not None:
                    price = payout
            if option_bits:
                side = "/".join(sorted(set([b for b in option_bits if "OVER" in b or "UNDER" in b]))) or "OVER/UNDER"

            key = (normalize_name(player), prop, float(line), url)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "Source": "Underdog",
                "Book": "Underdog",
                "Player": player,
                "Prop": prop,
                "Prop Label": PROP_CONFIG[prop]["label"],
                "Line": float(line),
                "Raw Line": float(line),
                "Line Field": raw_line_field,
                "Line Quality": "OK — Underdog structured stat_value",
                "Side": side if side else "OVER/UNDER",
                "Price": price,
                "Market": f"underdog_{prop}",
                "Last Update": _attrs(line_obj).get("updated_at") or _attrs(line_obj).get("updatedAt") or _attrs(over_under).get("updated_at") or _attrs(over_under).get("updatedAt"),
            })

        log_request("Underdog", "FOUND" if len(rows) > count_before else "NO_ROWS", f"{url} structured -> +{len(rows)-count_before}")

    return rows


@st.cache_data(ttl=300, show_spinner=False)
def get_prizepicks_props() -> List[Dict[str, Any]]:
    data = safe_get_json(PRIZEPICKS_URL, timeout=20)
    if not data:
        log_request("PrizePicks", "FAILED", "No JSON returned")
        return []
    included = data.get("included", []) if isinstance(data, dict) else []
    names: Dict[str, str] = {}
    for inc in included:
        if not isinstance(inc, dict):
            continue
        attrs = inc.get("attributes", {}) or {}
        name = attrs.get("name") or attrs.get("display_name")
        if name:
            names[str(inc.get("id"))] = name
    rows, seen = [], set()
    for item in data.get("data", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        attrs = item.get("attributes", {}) or {}
        rel = item.get("relationships", {}) or {}
        league = normalize_name(attrs.get("league") or attrs.get("league_id") or attrs.get("sport") or "")
        blob = json.dumps(item, default=str).lower()
        if "wnba" in blob:
            continue
        if "nba" not in blob and league not in ["nba"]:
            continue
        stat_type = attrs.get("stat_type") or attrs.get("statType") or attrs.get("market") or ""
        prop = prop_from_market_text(stat_type)
        line = safe_float(attrs.get("line_score") or attrs.get("line"))
        raw_line_field = "line_score" if attrs.get("line_score") is not None else ("line" if attrs.get("line") is not None else "")
        if not prop or not valid_prop_line(prop, line):
            continue
        player = attrs.get("description") or attrs.get("name") or ""
        if not clean_player_candidate(player):
            player_id = None
            try:
                player_id = rel.get("new_player", {}).get("data", {}).get("id") or rel.get("player", {}).get("data", {}).get("id")
            except Exception:
                player_id = None
            player = names.get(str(player_id), player)
        if not clean_player_candidate(player):
            continue
        key = (normalize_name(player), prop, float(line), "PrizePicks")
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "Source": "PrizePicks",
            "Book": "PrizePicks",
            "Player": player,
            "Prop": prop,
            "Prop Label": PROP_CONFIG[prop]["label"],
            "Line": float(line),
            "Raw Line": float(line),
            "Line Field": raw_line_field,
            "Line Quality": line_quality_note(prop, line, "PrizePicks"),
            "Side": "OVER/UNDER",
            "Price": None,
            "Market": f"prizepicks_{prop}",
            "Last Update": attrs.get("updated_at") or attrs.get("start_time"),
        })
    log_request("PrizePicks", "FOUND" if rows else "NO_ROWS", f"{len(rows)} NBA rows")
    return rows


@st.cache_data(ttl=360, show_spinner=False)
def get_odds_api_props_for_event(event_id: str, markets_csv: str) -> List[Dict[str, Any]]:
    if not ODDS_API_KEY or not event_id:
        return []
    url = f"{ODDS_BASE}/sports/{SPORT_KEY}/events/{event_id}/odds"
    data = safe_get_json(url, params={
        "apiKey": ODDS_API_KEY,
        "regions": "us,us2",
        "markets": markets_csv,
        "oddsFormat": "american",
    }, timeout=20)
    if not isinstance(data, dict):
        return []
    rows = []
    for book in data.get("bookmakers", []) or []:
        book_name = book.get("title") or book.get("key") or "Book"
        for market in book.get("markets", []) or []:
            mkey = market.get("key")
            prop = prop_from_market_text(mkey)
            if not prop:
                continue
            for out in market.get("outcomes", []) or []:
                player = out.get("description") or out.get("player") or out.get("participant") or ""
                line = safe_float(out.get("point"))
                raw_line_field = "outcome.point"
                if not clean_player_candidate(player) or not valid_prop_line(prop, line):
                    continue
                rows.append({
                    "Source": "The Odds API",
                    "Book": book_name,
                    "Player": player,
                    "Prop": prop,
                    "Prop Label": PROP_CONFIG[prop]["label"],
                    "Line": float(line),
                    "Raw Line": float(line),
                    "Line Field": raw_line_field,
                    "Line Quality": line_quality_note(prop, line, "The Odds API"),
                    "Side": str(out.get("name", "")).upper() or "OVER/UNDER",
                    "Price": safe_float(out.get("price")),
                    "Market": mkey,
                    "Last Update": market.get("last_update") or book.get("last_update"),
                })
    return rows


def get_all_live_props(games: List[Dict[str, Any]], selected_props: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    selected_markets = []
    for p in selected_props:
        selected_markets.extend(PROP_CONFIG[p]["markets"])
    markets_csv = ",".join(sorted(set(selected_markets)))

    # Direct public fantasy sources first. Default is Underdog only so lines match the Underdog board.
    source_mode = globals().get("prop_source_mode", "Underdog only")
    rows.extend(get_underdog_props())
    if source_mode in ["Underdog + PrizePicks", "All sources"]:
        rows.extend(get_prizepicks_props())

    # Sportsbook player props when ODDS_API_KEY exists and the user asks for all sources.
    if source_mode == "All sources" and ODDS_API_KEY and games:
        for game in games:
            event_id, score = match_odds_event_for_game(game)
            if event_id:
                fetched = get_odds_api_props_for_event(event_id, markets_csv)
                for r in fetched:
                    r["Game"] = f"{game['away']} @ {game['home']}"
                rows.extend(fetched)
            else:
                log_request("The Odds API Props", "NO_EVENT_MATCH", f"{game['away']} @ {game['home']} score={score:.2f}")

    # Filter + dedupe.
    final, seen = [], set()
    for r in rows:
        prop = r.get("Prop")
        if prop not in selected_props:
            continue
        line = safe_float(r.get("Line"))
        if not valid_prop_line(prop, line):
            continue
        key = (r.get("Source"), r.get("Book"), normalize_name(r.get("Player")), prop, line, r.get("Side"))
        if key in seen:
            continue
        seen.add(key)
        r["Line"] = float(line)
        r.setdefault("Raw Line", float(line))
        r.setdefault("Line Field", "verified")
        r["Line Quality"] = line_quality_note(prop, line, str(r.get("Source") or ""))
        final.append(r)
    return final

# ============================================================
# PROP SIGNALS / SIMULATION
# ============================================================
def estimated_prop_std(prop: str, line: float) -> float:
    """Reasonable NBA prop volatility fallback when live NBA logs are unavailable."""
    base = {
        "PTS": 5.8,
        "REB": 3.2,
        "AST": 2.8,
        "PRA": 7.8,
        "PR": 6.8,
        "PA": 6.8,
        "RA": 4.6,
        "3PM": 1.25,
    }.get(prop, 4.0)
    return float(max(0.85, base + (abs(float(line)) * 0.035)))


def build_prop_market_indexes(raw_props: List[Dict[str, Any]]) -> Tuple[Dict[Tuple[str, str], List[float]], Dict[Tuple[str, str, str, float, str], float]]:
    """Build consensus lines and side prices from all books/sources before scoring."""
    consensus: Dict[Tuple[str, str], List[float]] = {}
    side_prices: Dict[Tuple[str, str, str, float, str], float] = {}
    for r in raw_props:
        player_key = normalize_name(r.get("Player"))
        prop = str(r.get("Prop") or "")
        line = safe_float(r.get("Line"))
        if not player_key or not prop or line is None:
            continue
        consensus.setdefault((player_key, prop), []).append(float(line))
        side = str(r.get("Side") or "").upper()
        price = safe_float(r.get("Price"))
        if price is not None and side in ["OVER", "UNDER"]:
            side_prices[(player_key, prop, str(r.get("Book") or ""), float(line), side)] = float(price)
    return consensus, side_prices


def market_consensus_projection(r: Dict[str, Any], consensus_index: Dict[Tuple[str, str], List[float]]) -> Tuple[Optional[float], str]:
    """Use multi-source consensus as a projection fallback when NBA logs fail."""
    player_key = normalize_name(r.get("Player"))
    prop = str(r.get("Prop") or "")
    line = safe_float(r.get("Line"))
    lines = consensus_index.get((player_key, prop), [])
    if line is None or not lines:
        return None, "No consensus fallback"
    unique_lines = sorted(set(round(float(x), 2) for x in lines))
    if len(unique_lines) >= 2:
        # Multiple books/sources disagreeing gives real directional information.
        avg_line = float(np.mean(lines))
        return avg_line, f"Market consensus fallback from {len(lines)} lines"
    return None, "Only one market line; no directional consensus"


def choose_price_for_pick(r: Dict[str, Any], pick: str, side_price_index: Dict[Tuple[str, str, str, float, str], float], default_odds: int) -> float:
    player_key = normalize_name(r.get("Player"))
    prop = str(r.get("Prop") or "")
    book = str(r.get("Book") or "")
    line = safe_float(r.get("Line"))
    if line is None:
        return float(default_odds)
    side = str(pick or "").upper()
    return float(side_price_index.get((player_key, prop, book, float(line), side), safe_float(r.get("Price"), float(default_odds)) or float(default_odds)))


def score_projection_vs_line(projection: float, line: float, std: float, price: float, prop: str, min_edge: float, min_prob: float) -> Dict[str, Any]:
    edge = float(projection - line)
    if abs(edge) < 0.01:
        side = "NO PLAY"
    else:
        side = "OVER" if edge > 0 else "UNDER"
    abs_edge = abs(edge)
    z = abs_edge / max(float(std), 0.75)
    prob = float(0.5 + min(0.47, (math.erf(z / math.sqrt(2)) * 0.5)))
    ev = expected_value(prob, price) if side in ["OVER", "UNDER"] else 0.0
    kelly = kelly_fraction(prob, price) if side in ["OVER", "UNDER"] else 0.0
    cfg_edge = max(float(PROP_CONFIG[prop]["min_edge"]), float(min_edge))

    if side == "NO PLAY":
        signal = "PASS"
    elif abs_edge >= cfg_edge and prob >= max(float(min_prob), 0.56) and (ev is None or ev >= -0.01):
        signal = "STRONG" if prob >= 0.60 and abs_edge >= cfg_edge * 1.25 else "LEAN"
    elif abs_edge >= max(0.20, cfg_edge * 0.40) and prob >= 0.515:
        # This still tells OVER/UNDER, but marks it WATCH instead of forcing a bet.
        signal = "WATCH"
    else:
        signal = "PASS"
    return {"edge": edge, "side": side, "prob": prob, "ev": ev, "kelly": kelly, "signal": signal}


def make_prop_signals(raw_props: List[Dict[str, Any]], default_odds: int, min_edge: float, min_prob: float) -> List[Dict[str, Any]]:
    """
    Every prop row now gets a visible projection path:
    1) NBA player-game-log projection when available.
    2) Multi-source market consensus fallback.
    3) Neutral simulation label when no directional data exists.

    The Pick column will show OVER/UNDER only when the model has directional information.
    Otherwise it shows NO PLAY, so the app does not fake a pick.
    """
    signals = []
    consensus_index, side_price_index = build_prop_market_indexes(raw_props)

    for r in raw_props:
        prop = r["Prop"]
        line = safe_float(r["Line"])
        if line is None:
            continue

        proj = project_prop(r["Player"], prop)
        projection = proj.get("projection")
        std = proj.get("std")
        note = proj.get("note") or ""
        projection_source = "NBA logs"

        if projection is None:
            fallback_projection, fallback_note = market_consensus_projection(r, consensus_index)
            if fallback_projection is not None:
                projection = float(fallback_projection)
                std = estimated_prop_std(prop, float(line))
                note = f"SIM + {fallback_note}; NBA log note: {note}"
                projection_source = "Market simulation"
            else:
                projection = float(line)
                std = estimated_prop_std(prop, float(line))
                note = f"Neutral SIM: {fallback_note}; NBA log note: {note}"
                projection_source = "Neutral simulation"

        price_for_initial = choose_price_for_pick(r, "OVER", side_price_index, default_odds)
        scored = score_projection_vs_line(float(projection), float(line), float(std or estimated_prop_std(prop, float(line))), price_for_initial, prop, min_edge, min_prob)
        pick = scored["side"]
        price = choose_price_for_pick(r, pick if pick in ["OVER", "UNDER"] else "OVER", side_price_index, default_odds)
        scored = score_projection_vs_line(float(projection), float(line), float(std or estimated_prop_std(prop, float(line))), price, prop, min_edge, min_prob)
        pick = scored["side"]

        # Human-facing instruction: distinguish a model lean from an actual take.
        if scored["signal"] in ["STRONG", "LEAN"]:
            take_text = f"TAKE {pick}"
        elif scored["signal"] == "WATCH" and pick in ["OVER", "UNDER"]:
            take_text = f"WATCH {pick}"
        elif pick in ["OVER", "UNDER"]:
            take_text = f"MODEL LEANS {pick} — PASS"
        else:
            take_text = "NO PLAY — no edge"

        out = dict(r)
        consensus_lines = consensus_index.get((normalize_name(r.get("Player")), prop), [])
        consensus_line = float(np.median(consensus_lines)) if consensus_lines else float(line)
        out.update({
            "Projection": float(projection),
            "Consensus Line": consensus_line,
            "Line Check": line_quality_note(prop, line, str(r.get("Source") or "")),
            "Projection Source": projection_source,
            "Sim Std": float(std or estimated_prop_std(prop, float(line))),
            "Edge": scored["edge"],
            "Pick": pick,
            "Take": take_text,
            "Pick Prob": scored["prob"],
            "EV": scored["ev"],
            "Kelly": scored["kelly"],
            "Signal": scored["signal"],
            "Projection Note": note,
            "Matched Name": proj.get("matched_name"),
            "Games": proj.get("games"),
            "Price": price,
        })
        signals.append(out)

    def sort_key(x: Dict[str, Any]) -> Tuple[int, float, float]:
        rank = {"STRONG": 0, "LEAN": 1, "WATCH": 2, "PASS": 3, "NO PROJECTION": 4}.get(x.get("Signal"), 5)
        prob = x.get("Pick Prob") or 0
        edge = abs(x.get("Edge") or 0)
        return (rank, -prob, -edge)
    return sorted(signals, key=sort_key)

# ============================================================
# UI HELPERS
# ============================================================
def save_snapshot(path: str, rows: List[Dict[str, Any]]) -> int:
    payload = {"saved_at": now_iso(), "rows": rows}
    save_json(path, payload)
    return len(rows)


def dataframe_width_kwargs() -> Dict[str, Any]:
    return {"width": "stretch", "hide_index": True}


def signal_strength(signal: Any) -> int:
    return {"STRONG": 3, "LEAN": 2, "WATCH": 1, "PASS": 0, "NO PROJECTION": 0}.get(str(signal or "").upper(), 0)

def confidence_grade(prob: Any, ev: Any, edge: Any, signal: Any) -> str:
    p = safe_float(prob, 0.0) or 0.0
    e = safe_float(ev, 0.0) or 0.0
    ed = abs(safe_float(edge, 0.0) or 0.0)
    score = (signal_strength(signal) * 22) + max(0, (p - 0.50) * 160) + max(0, e * 170) + min(16, ed * 3)
    if score >= 82:
        return "A+"
    if score >= 72:
        return "A"
    if score >= 62:
        return "B+"
    if score >= 52:
        return "B"
    if score >= 42:
        return "C"
    return "PASS"

def stake_units(kelly: Any, signal: Any, confidence: Any, max_units: float) -> float:
    k = safe_float(kelly, 0.0) or 0.0
    base = min(float(max_units), max(0.0, k * 100.0))
    if signal == "STRONG":
        mult = 1.00
    elif signal == "LEAN":
        mult = 0.55
    else:
        mult = 0.0
    if confidence in ["A+", "A"]:
        mult *= 1.05
    elif confidence in ["C", "PASS"]:
        mult *= 0.55
    return round(clamp(base * mult, 0.0, float(max_units)), 2)

def recommended_dollars(units: Any, unit_size: float) -> float:
    return round((safe_float(units, 0.0) or 0.0) * float(unit_size), 2)

def add_tracker_rows(new_rows: List[Dict[str, Any]]) -> int:
    tracker = load_json(BET_TRACKER_FILE, [])
    seen = {str(r.get("Tracker Key")) for r in tracker}
    added = 0
    for r in new_rows:
        key = str(r.get("Tracker Key") or "")
        if key and key not in seen:
            tracker.append(r)
            seen.add(key)
            added += 1
    save_json(BET_TRACKER_FILE, tracker[-10000:])
    return added

def build_best_bets(game_rows: List[Dict[str, Any]], prop_rows: List[Dict[str, Any]], unit_size: float, max_units: float, max_cards: int = 12) -> List[Dict[str, Any]]:
    bets: List[Dict[str, Any]] = []
    for g in game_rows:
        for market, sig_key, pick_key, prob_key, ev_key, edge_key, kelly_key in [
            ("Moneyline", "ML Signal", "ML Pick", "ML Prob", "ML EV", "Home Model Prob", "ML Kelly"),
            ("Spread", "Spread Signal", "Spread Pick", "Spread Prob", None, "Spread Edge", None),
            ("Total", "Total Signal", "Total Pick", "Total Prob", None, "Total Edge", None),
        ]:
            signal = g.get(sig_key)
            if signal not in ["STRONG", "LEAN"]:
                continue
            prob = g.get(prob_key)
            ev = g.get(ev_key) if ev_key else None
            edge = g.get(edge_key)
            conf = confidence_grade(prob, ev, edge, signal)
            kelly = g.get(kelly_key) if kelly_key else (0.012 if signal == "STRONG" else 0.007)
            units = stake_units(kelly, signal, conf, max_units)
            bets.append({
                "Type": "Game Market", "Market": market, "Game": f"{g.get('away')} @ {g.get('home')}", "Pick": g.get(pick_key),
                "Signal": signal, "Confidence": conf, "Prob": prob, "EV": ev, "Edge": edge, "Units": units, "Stake $": recommended_dollars(units, unit_size),
                "Source": g.get("source"), "Line": g.get("spread") if market == "Spread" else (g.get("total") if market == "Total" else g.get("ML Price")), "Home": g.get("home"), "Away": g.get("away"), "Injury/Lineup Adj": g.get("Injury/Lineup Adj"), "Tracker Key": f"{g.get('date')}|{g.get('game_id')}|{market}|{g.get(pick_key)}"
            })
    for p in prop_rows:
        if p.get("Signal") not in ["STRONG", "LEAN"]:
            continue
        conf = confidence_grade(p.get("Pick Prob"), p.get("EV"), p.get("Edge"), p.get("Signal"))
        units = stake_units(p.get("Kelly"), p.get("Signal"), conf, max_units)
        bets.append({
            "Type": "Player Prop", "Market": p.get("Prop Label") or p.get("Prop"), "Game": p.get("Game", ""),
            "Pick": f"{p.get('Player')} {p.get('Pick')} {p.get('Line')} {p.get('Prop')}", "Signal": p.get("Signal"), "Confidence": conf,
            "Prob": p.get("Pick Prob"), "EV": p.get("EV"), "Edge": p.get("Edge"), "Units": units, "Stake $": recommended_dollars(units, unit_size),
            "Source": p.get("Source"), "Player": p.get("Player"), "Prop": p.get("Prop"), "Line": p.get("Line"), "Side": p.get("Pick"), "Book": p.get("Book"), "Projection": p.get("Projection"), "Tracker Key": f"{p.get('Source')}|{normalize_name(p.get('Player'))}|{p.get('Prop')}|{p.get('Line')}|{p.get('Pick')}"
        })
    return sorted(bets, key=lambda x: (-(signal_strength(x.get("Signal"))), str(x.get("Confidence")), -(safe_float(x.get("Prob"), 0) or 0), -(abs(safe_float(x.get("Edge"), 0) or 0))))[:max_cards]

def append_edge_history(games_count: int, props_count: int, best_count: int) -> None:
    hist = load_json(EDGE_HISTORY_FILE, [])
    today = app_now().strftime("%Y-%m-%d")
    row = {"date": today, "time": now_iso(), "games": games_count, "qualified_props": props_count, "best_bets": best_count}
    if not hist or hist[-1].get("date") != today or hist[-1].get("best_bets") != best_count:
        hist.append(row)
        save_json(EDGE_HISTORY_FILE, hist[-3000:])

# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.markdown("""
<div style='padding:12px 4px 18px 4px;'>
  <div style='font-size:28px;font-weight:950;'>😈 DEVIL PICKS</div>
  <div style='color:#ff344f;font-weight:900;'>NBA FULL ENGINE</div>
  <div style='color:#aeb7c9;font-size:12px;margin-top:4px;'>Moneyline • Spread • Totals • Player Props</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Board Controls")
    day_mode = st.radio("Game Day", ["Today", "Tomorrow", "Both"], index=0)
    selected_props = st.multiselect("NBA props to scan", list(PROP_CONFIG.keys()), default=["PTS", "REB", "AST", "PRA", "3PM"])
    prop_source_mode = st.selectbox("Prop line source", ["Underdog only", "Underdog + PrizePicks", "All sources"], index=0, help="Use Underdog only when comparing lines to the Underdog app.")
    default_odds = st.number_input("Default prop odds when price missing", value=int(DEFAULT_ODDS), step=5)
    min_edge = st.number_input("Extra minimum prop edge", value=0.0, min_value=0.0, step=0.25)
    min_prob = st.slider("Minimum prop probability", 0.50, 0.70, 0.56, 0.01)
    st.markdown("---")
    st.markdown("### Bankroll / Risk Controls")
    bankroll = st.number_input("Bankroll $", value=100.0, min_value=1.0, step=10.0)
    unit_size = st.number_input("1 unit = $", value=5.0, min_value=0.25, step=0.25)
    max_units = st.slider("Max units per play", 0.25, 5.0, 1.5, 0.25)
    st.caption("The app sizes plays conservatively. PASS rows get $0.")
    st.markdown("---")
    st.markdown("### 10/10 Safety Filters")
    hide_passes = st.checkbox("Hide PASS rows in top pages", value=True)
    show_raw = st.checkbox("Show raw prop table", value=True)
    st.markdown("---")
    st.markdown("### Live Data Upgrades")
    api_override = st.text_input("Odds API key override", value="", type="password", help="Optional. Better: put ODDS_API_KEY in Streamlit Secrets.")
    if api_override.strip():
        ODDS_API_KEY = api_override.strip()
    manual_injury_text = st.text_area("Manual injury/lineup adjustments", value="", height=90, help="Optional format: BOS:-2.5 or LAL:+1.0. Negative hurts team projection.")
    auto_grade_now = st.button("✅ Auto Grade Finished Games", width="stretch")
    save_opening_lines = st.button("📌 Save Opening Line Snapshot", width="stretch")
    save_closing_lines = st.button("🔒 Save Closing Line Snapshot", width="stretch")
    st.markdown("---")
    st.markdown("### Source Status")
    st.markdown(f"<span class='badge {'badge-green' if ODDS_API_KEY else 'badge-orange'}'>Odds API: {'KEY SET' if ODDS_API_KEY else 'NO KEY'}</span>", unsafe_allow_html=True)
    st.caption("Moneyline/spread/totals need ODDS_API_KEY. Player props default to Underdog direct so lines match the Underdog board.")

# ============================================================
# MAIN
# ============================================================
st.markdown("""
<div class='hero'>
  <div class='logo-title'>😈 DEVIL PICKS — NBA Full Betting Engine</div>
  <div class='sub'>NBA only. Moneyline, spreads, and totals stay separate from player props. No WNBA logic.</div>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1:
    refresh = st.button("🔄 Refresh NBA Board", width="stretch")
with c2:
    save_props = st.button("💾 Save Prop Snapshot", width="stretch")
with c3:
    save_markets = st.button("💾 Save Game Market Snapshot", width="stretch")
with c4:
    save_tracker = st.button("🧾 Add Best Bets To Tracker", width="stretch")

if refresh:
    st.cache_data.clear()
    st.success("Cache cleared. Board refreshed.")

# Load games and markets.
dates = [date_for_mode("Today"), date_for_mode("Tomorrow")] if day_mode == "Both" else [date_for_mode(day_mode)]
games: List[Dict[str, Any]] = []
for d in dates:
    games.extend(extract_games(d))

markets: List[Dict[str, Any]] = []
for g in games:
    m = market_summary_for_game(g)
    markets.append({**g, **m})

injury_rows = get_espn_injury_feed()
team_adjustments = injury_team_adjustments(injury_rows, manual_injury_text if 'manual_injury_text' in globals() else "")
game_signals = build_game_market_signals(markets, team_adjustments)
raw_props = get_all_live_props(games, selected_props)
prop_signals = make_prop_signals(raw_props, default_odds=int(default_odds), min_edge=float(min_edge), min_prob=float(min_prob))
qualified_props = [p for p in prop_signals if p.get("Signal") in ["STRONG", "LEAN"]]
watch_props = [p for p in prop_signals if p.get("Signal") == "WATCH"]
qualified_ml = [g for g in game_signals if g.get("ML Signal") in ["STRONG", "LEAN"]]
qualified_spread = [g for g in game_signals if g.get("Spread Signal") in ["STRONG", "LEAN"]]
qualified_total = [g for g in game_signals if g.get("Total Signal") in ["STRONG", "LEAN"]]
best_bets = build_best_bets(game_signals, prop_signals, float(unit_size), float(max_units))
append_edge_history(len(games), len(qualified_props), len(best_bets))

if save_props:
    n = save_snapshot(PROP_SNAPSHOT_FILE, prop_signals)
    st.success(f"Saved {n} NBA prop rows to {PROP_SNAPSHOT_FILE}")
if save_markets:
    n = save_snapshot(MARKET_SNAPSHOT_FILE, game_signals)
    st.success(f"Saved {n} NBA game-market rows to {MARKET_SNAPSHOT_FILE}")
if save_tracker:
    n = add_tracker_rows(best_bets)
    st.success(f"Added {n} new best-bet rows to tracker.")
if 'save_opening_lines' in globals() and save_opening_lines:
    n = save_closing_snapshot(game_signals, raw_props, "OPENING")
    st.success(f"Saved {n} opening-line rows.")
if 'save_closing_lines' in globals() and save_closing_lines:
    n = save_closing_snapshot(game_signals, raw_props, "CLOSING")
    st.success(f"Saved {n} closing-line rows.")
if 'auto_grade_now' in globals() and auto_grade_now:
    changed, total = auto_grade_tracker()
    st.success(f"Auto grading complete: {changed} newly graded, {total} total graded rows.")

best_prop = qualified_props[0] if qualified_props else (prop_signals[0] if prop_signals else None)
best_game = None
if game_signals:
    ordered_games = sorted(game_signals, key=lambda x: (x.get("ML Signal") not in ["STRONG", "LEAN"], -(x.get("ML Prob") or 0)))
    best_game = ordered_games[0]

st.markdown(f"""
<div class='metric-grid'>
  <div class='metric-box'><div class='metric-label'>NBA Games Loaded</div><div class='metric-value'>{len(games)}</div><div class='metric-sub'>{day_mode}</div></div>
  <div class='metric-box'><div class='metric-label'>Game Market Plays</div><div class='metric-value'>{len(qualified_ml)+len(qualified_spread)+len(qualified_total)}</div><div class='metric-sub'>ML + spread + totals</div></div>
  <div class='metric-box'><div class='metric-label'>Raw Prop Lines</div><div class='metric-value'>{len(raw_props)}</div><div class='metric-sub'>Underdog direct by default</div></div>
  <div class='metric-box'><div class='metric-label'>Best Bets</div><div class='metric-value'>{len(best_bets)}</div><div class='metric-sub'>Separated game markets + player props</div></div>
</div>
""", unsafe_allow_html=True)

st.info("Closer to 10/10+: NBA-only, separated markets/props, real Odds API wiring, injury/lineup adjustments, closing-line snapshots, auto grading, longer saved history, EV/Kelly sizing, diagnostics, and safer PASS gates.")

tab_best, tab_games, tab_ml, tab_spread, tab_totals, tab_top_props, tab_prop_table, tab_raw, tab_tracker, tab_injuries, tab_closing, tab_logs = st.tabs([
    "🔥 Best Bets",
    "🏀 Game Board",
    "💰 Moneyline",
    "📏 Spreads",
    "🔢 Totals",
    "😈 Top Player Props",
    "🎯 Prop Signals",
    "📋 Raw Props",
    "🧾 Tracker",
    "🚑 Injuries/Lineups",
    "📈 Closing/CLV",
    "🔌 Diagnostics",
])

with tab_best:
    st.markdown("<div class='section-title'>Best Bets Board — Game Markets Separate From Player Props</div>", unsafe_allow_html=True)
    if not best_bets:
        st.warning("No best bets passed the safer 10/10 gates. That is better than forcing weak plays.")
    else:
        st.dataframe(pd.DataFrame(best_bets), **dataframe_width_kwargs())
        for b in best_bets[:8]:
            cls = "card-green" if b.get("Signal") == "STRONG" else "card-orange"
            st.markdown(f"""
            <div class='{cls}'>
              <div style='display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap;'>
                <div>
                  <div class='team-name'>{b.get('Pick')}</div>
                  <div class='sub'>{b.get('Type')} • {b.get('Market')} • {b.get('Game')} • {b.get('Source')}</div>
                </div>
                <div style='font-size:24px;font-weight:950;' class='green'>{b.get('Confidence')}</div>
              </div>
              <span class='badge {'badge-green' if b.get('Signal') == 'STRONG' else 'badge-orange'}'>{b.get('Signal')}</span>
              <span class='badge'>Prob {fmt_pct(b.get('Prob'))}</span>
              <span class='badge'>EV {fmt_pct(b.get('EV'))}</span>
              <span class='badge'>Edge {fmt_num(b.get('Edge'),2,True)}</span>
              <span class='badge'>Units {fmt_num(b.get('Units'),2)}</span>
              <span class='badge'>Stake ${fmt_num(b.get('Stake $'),2)}</span>
            </div>
            """, unsafe_allow_html=True)

with tab_games:
    st.markdown("<div class='section-title'>NBA Game Board — Separated From Props</div>", unsafe_allow_html=True)
    if not game_signals:
        st.warning("No NBA games loaded for the selected date. Try Tomorrow or Both.")
    for g in game_signals:
        st.markdown(f"""
        <div class='card'>
          <div class='team-row'>
            <div><div class='team-name'>{g['away']}</div><div class='muted'>{g.get('away_name','')}</div></div>
            <div class='vs-pill'>{g.get('status','Scheduled')}<br>{g.get('game_time','')}</div>
            <div style='text-align:right;'><div class='team-name'>{g['home']}</div><div class='muted'>{g.get('home_name','')}</div></div>
          </div>
          <span class='badge'>Home ML {odds_display(g.get('home_ml'))}</span>
          <span class='badge'>Away ML {odds_display(g.get('away_ml'))}</span>
          <span class='badge'>Spread {fmt_num(g.get('spread'),1,True)}</span>
          <span class='badge'>Total {fmt_num(g.get('total'),1)}</span>
          <span class='badge {'badge-green' if g.get('quality') == 'STRONG' else 'badge-orange'}'>{g.get('quality')}</span>
        </div>
        """, unsafe_allow_html=True)

with tab_ml:
    st.markdown("<div class='section-title'>Moneyline Picks</div>", unsafe_allow_html=True)
    rows = [g for g in game_signals if (not hide_passes or g.get("ML Signal") != "PASS")]
    if not rows:
        st.warning("No moneyline rows. Add ODDS_API_KEY or select a day with games.")
    for g in rows:
        cls = "card-green" if g.get("ML Signal") in ["STRONG", "LEAN"] else "card-orange"
        st.markdown(f"""
        <div class='{cls}'>
          <div style='display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap;'>
            <div>
              <div class='team-name'>{g.get('away')} @ {g.get('home')}</div>
              <div class='sub'>{g.get('away_name')} vs {g.get('home_name')} • {g.get('source')}</div>
            </div>
            <div style='font-size:27px;font-weight:950;' class='green'>{g.get('ML Pick')}</div>
          </div>
          <span class='badge {'badge-green' if g.get('ML Signal') in ['STRONG','LEAN'] else 'badge-orange'}'>{g.get('ML Signal')}</span>
          <span class='badge'>Price {odds_display(g.get('ML Price'))}</span>
          <span class='badge'>Model Prob {fmt_pct(g.get('ML Prob'))}</span>
          <span class='badge'>EV {fmt_pct(g.get('ML EV'))}</span>
          <span class='badge'>Kelly {fmt_pct(g.get('ML Kelly'))}</span>
        </div>
        """, unsafe_allow_html=True)
    if game_signals:
        df = pd.DataFrame(game_signals)
        keep = ["away", "home", "ML Signal", "ML Pick", "ML Price", "ML Prob", "ML EV", "ML Kelly", "Game Rating", "home_ml", "away_ml", "quality"]
        st.dataframe(df[[c for c in keep if c in df.columns]], **dataframe_width_kwargs())

with tab_spread:
    st.markdown("<div class='section-title'>Spread Picks</div>", unsafe_allow_html=True)
    rows = [g for g in game_signals if (not hide_passes or g.get("Spread Signal") != "PASS")]
    if not rows:
        st.warning("No spread rows. Add ODDS_API_KEY or select a day with games.")
    for g in rows:
        cls = "card-green" if g.get("Spread Signal") in ["STRONG", "LEAN"] else "card-orange"
        st.markdown(f"""
        <div class='{cls}'>
          <div class='team-name'>{g.get('away')} @ {g.get('home')} — {g.get('Spread Pick')}</div>
          <div class='sub'>Consensus home spread: {fmt_num(g.get('spread'),1,True)} • Market quality: {g.get('quality')}</div>
          <span class='badge {'badge-green' if g.get('Spread Signal') in ['STRONG','LEAN'] else 'badge-orange'}'>{g.get('Spread Signal')}</span>
          <span class='badge'>Edge {fmt_num(g.get('Spread Edge'),2,True)}</span>
          <span class='badge'>Prob {fmt_pct(g.get('Spread Prob'))}</span>
        </div>
        """, unsafe_allow_html=True)
    if game_signals:
        df = pd.DataFrame(game_signals)
        keep = ["away", "home", "Spread Signal", "Spread Pick", "spread", "Spread Edge", "Spread Prob", "quality"]
        st.dataframe(df[[c for c in keep if c in df.columns]], **dataframe_width_kwargs())

with tab_totals:
    st.markdown("<div class='section-title'>Total Points Over/Under</div>", unsafe_allow_html=True)
    rows = [g for g in game_signals if (not hide_passes or g.get("Total Signal") != "PASS")]
    if not rows:
        st.warning("No totals rows. Add ODDS_API_KEY or select a day with games.")
    for g in rows:
        cls = "card-green" if g.get("Total Signal") in ["STRONG", "LEAN"] else "card-orange"
        st.markdown(f"""
        <div class='{cls}'>
          <div class='team-name'>{g.get('away')} @ {g.get('home')} — {g.get('Total Pick')} {fmt_num(g.get('total'),1)}</div>
          <div class='sub'>Total model is conservative unless there is a real edge.</div>
          <span class='badge {'badge-green' if g.get('Total Signal') in ['STRONG','LEAN'] else 'badge-orange'}'>{g.get('Total Signal')}</span>
          <span class='badge'>Edge {fmt_num(g.get('Total Edge'),2,True)}</span>
          <span class='badge'>Prob {fmt_pct(g.get('Total Prob'))}</span>
        </div>
        """, unsafe_allow_html=True)
    if game_signals:
        df = pd.DataFrame(game_signals)
        keep = ["away", "home", "Total Signal", "Total Pick", "total", "Total Edge", "Total Prob", "quality"]
        st.dataframe(df[[c for c in keep if c in df.columns]], **dataframe_width_kwargs())

with tab_top_props:
    st.markdown("<div class='section-title'>Best NBA Player Props — Separate From Game Markets</div>", unsafe_allow_html=True)
    if not prop_signals:
        st.warning("No NBA props loaded yet. Open Diagnostics to see which source is failing or empty.")
    else:
        show = qualified_props[:12] if qualified_props else (watch_props[:12] if watch_props else prop_signals[:12])
        if not qualified_props:
            st.info("Props are showing. None passed the TAKE gates yet, so this page shows WATCH / model-lean rows with projections instead of going blank.")
        for p in show:
            cls = "card-green" if p.get("Signal") in ["STRONG", "LEAN"] else "card-orange"
            projection = p.get("Projection")
            edge = p.get("Edge")
            prob = p.get("Pick Prob")
            ev = p.get("EV")
            st.markdown(f"""
            <div class='{cls}'>
              <div style='display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap;'>
                <div>
                  <div class='team-name'>{p.get('Player')} — {p.get('Prop Label')}</div>
                  <div class='sub'>{p.get('Source')} • {p.get('Book')} • Line {p.get('Line')} • {p.get('Projection Note') or ''}</div>
                </div>
                <div style='font-size:27px;font-weight:950;' class='{'green' if p.get('Signal') in ['STRONG','LEAN'] else 'orange'}'>{p.get('Take') or p.get('Pick')}</div>
              </div>
              <span class='badge {'badge-green' if p.get('Signal') in ['STRONG','LEAN'] else 'badge-orange'}'>{p.get('Signal')}</span>
              <span class='badge'>Proj {'N/A' if projection is None else f'{projection:.2f}'}</span>
              <span class='badge'>{p.get('Projection Source','')}</span>
              <span class='badge'>Edge {'N/A' if edge is None else f'{edge:+.2f}'}</span>
              <span class='badge'>Prob {'N/A' if prob is None else f'{prob*100:.1f}%'}</span>
              <span class='badge'>Price {odds_display(p.get('Price') if p.get('Price') is not None else default_odds)}</span>
              <span class='badge'>EV {'N/A' if ev is None else f'{ev*100:.1f}%'}</span>
            </div>
            """, unsafe_allow_html=True)

with tab_prop_table:
    st.markdown("<div class='section-title'>NBA Prop Signals Table</div>", unsafe_allow_html=True)
    if prop_signals:
        df = pd.DataFrame(prop_signals)
        if hide_passes:
            df = df[df["Signal"].isin(["STRONG", "LEAN", "WATCH"])]
        keep = ["Signal", "Take", "Pick", "Player", "Prop", "Prop Label", "Line", "Projection", "Projection Source", "Sim Std", "Edge", "Pick Prob", "EV", "Kelly", "Source", "Book", "Price", "Games", "Projection Note"]
        keep = [c for c in keep if c in df.columns]
        st.dataframe(df[keep], **dataframe_width_kwargs())
    else:
        st.info("No prop signals because no raw prop lines were loaded.")

with tab_raw:
    st.markdown("<div class='section-title'>Raw NBA Player Prop Lines</div>", unsafe_allow_html=True)
    if raw_props and show_raw:
        df = pd.DataFrame(raw_props)
        keep = ["Source", "Book", "Player", "Prop", "Prop Label", "Line", "Side", "Price", "Market", "Last Update"]
        keep = [c for c in keep if c in df.columns]
        st.dataframe(df[keep], **dataframe_width_kwargs())
    elif raw_props:
        st.info("Raw table is hidden from the sidebar.")
    else:
        st.warning("No raw NBA prop rows came back from Underdog, PrizePicks, or The Odds API. Check Diagnostics.")

with tab_tracker:
    st.markdown("<div class='section-title'>Bet Tracker + Edge History</div>", unsafe_allow_html=True)
    st.write("Click **Add Best Bets To Tracker** at the top to save today’s separated picks. You can export this table later for grading.")
    tracker = load_json(BET_TRACKER_FILE, [])
    if tracker:
        st.dataframe(pd.DataFrame(tracker).iloc[::-1], **dataframe_width_kwargs())
    else:
        st.info("No tracked bets yet.")
    hist = load_json(EDGE_HISTORY_FILE, [])
    if hist:
        st.markdown("### Edge history")
        st.dataframe(pd.DataFrame(hist).iloc[::-1], **dataframe_width_kwargs())

with tab_injuries:
    st.markdown("<div class='section-title'>Injury / Lineup Feed + Adjustments</div>", unsafe_allow_html=True)
    st.write("ESPN public injuries are best-effort. Manual adjustments in the sidebar are the strongest control for confirmed lineup news.")
    adj_rows = [{"Team": k, "Point Adjustment": v, "Meaning": "Negative hurts team projection; positive helps."} for k, v in sorted(team_adjustments.items())]
    if adj_rows:
        st.markdown("### Active team adjustments")
        st.dataframe(pd.DataFrame(adj_rows), **dataframe_width_kwargs())
    else:
        st.info("No active injury/lineup point adjustments yet.")
    if injury_rows:
        st.markdown("### ESPN best-effort injury rows")
        st.dataframe(pd.DataFrame(injury_rows), **dataframe_width_kwargs())
    else:
        st.warning("No public injury feed rows returned. Add manual adjustments like BOS:-2.5 in the sidebar when news matters.")

with tab_closing:
    st.markdown("<div class='section-title'>Opening / Closing Line Tracking</div>", unsafe_allow_html=True)
    st.write("Save an opening snapshot early and a closing snapshot near tipoff. This tracks CLV and keeps a long history.")
    clos = load_json(CLOSING_LINE_FILE, [])
    if clos:
        df = pd.DataFrame(clos).iloc[::-1]
        st.dataframe(df, **dataframe_width_kwargs())
    else:
        st.info("No line snapshots yet. Use the sidebar buttons to save opening or closing lines.")
    graded = load_json(GRADED_HISTORY_FILE, [])
    if graded:
        st.markdown("### Graded history")
        st.dataframe(pd.DataFrame(graded).iloc[::-1], **dataframe_width_kwargs())

with tab_logs:
    st.markdown("<div class='section-title'>Source Diagnostics + 10/10 Checklist</div>", unsafe_allow_html=True)
    st.write("Use this tab when player props, moneylines, spreads, or totals do not show.")
    logs = load_json(REQUEST_LOG_FILE, [])
    status_rows = [
        {"Check": "NBA only", "Status": "OK", "Detail": "This file uses SPORT_KEY=basketball_nba and no WNBA endpoints."},
        {"Check": "ODDS_API_KEY", "Status": "SET" if ODDS_API_KEY else "MISSING", "Detail": "Needed for true sportsbook moneyline/spread/totals and book player props."},
        {"Check": "Games loaded", "Status": str(len(games)), "Detail": f"Dates: {', '.join(dates)}"},
        {"Check": "Game markets", "Status": str(len(game_signals)), "Detail": "Moneyline/spread/totals stay separated from props."},
        {"Check": "Raw props loaded", "Status": str(len(raw_props)), "Detail": "Displayed even when projection is missing. Default source is Underdog structured feed."},
        {"Check": "Qualified prop signals", "Status": str(len(qualified_props)), "Detail": "TAKE rows only. WATCH rows still show Over/Under lean and simulation."},
        {"Check": "Best-bet tracker", "Status": str(len(load_json(BET_TRACKER_FILE, []))), "Detail": "Saves top market and prop picks separately for later review; keeps up to 10,000 rows."},
        {"Check": "Injury/lineup feed", "Status": str(len(injury_rows)), "Detail": f"Manual team adjustments active: {len(team_adjustments)}."},
        {"Check": "Closing-line history", "Status": str(len(load_json(CLOSING_LINE_FILE, []))), "Detail": "Use opening/closing snapshot buttons for real CLV tracking."},
        {"Check": "Auto grading", "Status": str(len(load_json(GRADED_HISTORY_FILE, []))), "Detail": "Game markets auto-grade from NBA final scores; props are saved for manual/advanced grading."},
        {"Check": "Risk controls", "Status": "OK", "Detail": f"Unit=${unit_size}, max units={max_units}, bankroll=${bankroll}."},
        {"Check": "Still missing for true 10/10", "Status": "NEXT", "Detail": "True confirmed starting lineups/minutes, referee/rest/travel, paid-grade injury source, and full player-prop boxscore matching."},
    ]
    st.dataframe(pd.DataFrame(status_rows), **dataframe_width_kwargs())
    if logs:
        st.markdown("### Latest request log")
        st.dataframe(pd.DataFrame(logs[-150:]).iloc[::-1], **dataframe_width_kwargs())
    else:
        st.info("No request logs yet.")

st.caption("NBA-only 10/10 upgrade version. Moneyline, spreads, totals, and player props are separated. This is a model dashboard, not guaranteed betting advice.")
