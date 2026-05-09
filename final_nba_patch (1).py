# ============================================================
# NBA FINAL PROP ENGINE FIX PATCH
# ============================================================

# ADD THIS NEAR YOUR HELPER FUNCTIONS
# ============================================================

def flatten_json(y):

    out = {}

    def flatten(x, name=''):

        if isinstance(x, dict):

            for a in x:
                flatten(x[a], f'{name}{a}_')

        elif isinstance(x, list):

            i = 0

            for a in x:
                flatten(a, f'{name}{i}_')
                i += 1

        else:
            out[name[:-1]] = x

    flatten(y)

    return out


# ============================================================
# THEN FIND THIS:
# ============================================================

event_id = match_event_id(game)
markets = sorted(set(PROP_CONFIG[p]["market"] for p in prop_types))
prop_rows = get_event_player_props(event_id, ",".join(markets)) if event_id else []

# ============================================================
# DELETE IT
# ============================================================


# ============================================================
# REPLACE WITH THIS:
# ============================================================

# ============================================================
# STANDALONE PROP ENGINE
# Props NO LONGER depend on game matching
# ============================================================

markets = sorted(
    set(PROP_CONFIG[p]["market"] for p in prop_types)
)

prop_rows = []

# ------------------------------------------------------------
# Try sportsbook event props FIRST
# ------------------------------------------------------------

try:

    event_id = match_event_id(game)

    if event_id:

        odds_rows = get_event_player_props(
            event_id,
            ",".join(markets)
        )

        if odds_rows:
            prop_rows.extend(odds_rows)

except Exception as e:

    log_request(
        "event_prop_pull",
        "ERROR",
        str(e)
    )

# ------------------------------------------------------------
# DIRECT UNDERDOG / DIRECT PROP FEED
# ------------------------------------------------------------

try:

    direct_rows = get_direct_nba_prop_feed()

    if direct_rows:

        for r in direct_rows:

            if r.get("Market") in markets:
                prop_rows.append(r)

except Exception as e:

    log_request(
        "direct_prop_feed",
        "ERROR",
        str(e)
    )

# ------------------------------------------------------------
# HARD DEDUPE
# ------------------------------------------------------------

deduped = []
seen = set()

for r in prop_rows:

    key = (
        normalize_name(r.get("Player")),
        r.get("Market"),
        safe_float(r.get("Line"))
    )

    if key in seen:
        continue

    seen.add(key)
    deduped.append(r)

prop_rows = deduped


# ============================================================
# ADD THIS BELOW get_event_player_props(...)
# ============================================================

@st.cache_data(ttl=180, show_spinner=False)
def get_direct_nba_prop_feed():

    rows = []

    try:

        ud = safe_get_json(
            "https://api.underdogfantasy.com/beta/v5/over_under_lines"
        )

        if isinstance(ud, dict):

            appearances = {}

            for inc in ud.get("included", []):

                if inc.get("type") == "appearance":

                    aid = inc.get("id")

                    appearances[aid] = (
                        inc.get("attributes", {})
                    )

            for item in ud.get("over_under_lines", []):

                stat = (
                    item.get("stat_value")
                    or item.get("over_under", {})
                    .get("appearance_stat", {})
                    .get("display_stat")
                )

                line = safe_float(
                    item.get("stat_value")
                )

                rel = (
                    item.get("over_under", {})
                    .get("appearance_stat", {})
                    .get("appearance_id")
                )

                app = appearances.get(rel, {})

                player = (
                    app.get("player_name")
                    or app.get("display_name")
                )

                market_map = {
                    "points": "player_points",
                    "rebounds": "player_rebounds",
                    "assists": "player_assists",
                    "pts_rebs_asts":
                        "player_points_rebounds_assists"
                }

                mapped = market_map.get(
                    str(stat).lower()
                )

                if not mapped:
                    continue

                if player and line is not None:

                    rows.append({
                        "Book": "Underdog",
                        "Market": mapped,
                        "Player": player,
                        "Side": "OVER",
                        "Line": line,
                        "Price": -110,
                    })

    except Exception as e:

        log_request(
            "underdog_direct",
            "ERROR",
            str(e)
        )

    return rows
