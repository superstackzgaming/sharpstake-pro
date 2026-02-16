import streamlit as st
import pandas as pd
import requests

# --- CONFIGURATION ---
API_KEY = "818d64a21306f003ad587fbb0bd5958b" # Your Key
REGION = "us"
DFS_REGION = "us_dfs"

SPORTS = {
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "NHL": "icehockey_nhl",
    "College Basketball": "basketball_ncaab",
    "Soccer (EPL)": "soccer_epl"
}

# ONLY Player Props (No Match Winners)
MARKETS = {
    "NBA": {"Points": "player_points", "Rebounds": "player_rebounds", "Assists": "player_assists", "Threes": "player_threes"},
    "NFL": {"Pass Yds": "player_pass_yds", "Rush Yds": "player_rush_yds", "Rec Yds": "player_reception_yds", "TD": "player_anytime_td"},
    "NHL": {"Points": "player_points", "Goals": "player_goals_scored", "Assists": "player_assists", "Shots": "player_shots_on_goal"},
    "College Basketball": {"Points": "player_points"},
    "Soccer (EPL)": {"Goals": "player_goals_scored", "Assists": "player_assists"}
}

st.set_page_config(page_title="SharpStake Pro", layout="wide")
st.title("🎯 SharpStake Pro: Player Props Engine")

# --- SIDEBAR ---
sport_name = st.sidebar.selectbox("Select Sport", list(SPORTS.keys()))
sport_key = SPORTS[sport_name]

avail_markets = MARKETS.get(sport_name, {})
market_name = st.sidebar.selectbox("Select Prop", list(avail_markets.keys()))
market_key = avail_markets[market_name]

dfs_site = st.sidebar.selectbox("Select DFS Site", ["PrizePicks", "Underdog Fantasy", "Betr"])
min_ev = st.sidebar.slider("Min EV %", 0.0, 10.0, 1.5)

# --- ENGINE ---
def get_ev_data():
    st.toast(f"Scanning {dfs_site} for {market_name}...", icon="🔍")
    
    # 1. Get Games
    events = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/events", params={"apiKey": API_KEY}).json()
    if not events: return pd.DataFrame()

    all_data = []
    
    # CHECK FIRST 5 GAMES
    for event in events[:5]:
        game_id = event['id']
        game_label = f"{event['home_team']} vs {event['away_team']}"
        
        # 2. GET DFS LINES (Primary Source)
        dfs_resp = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{game_id}/odds",
            params={
                "apiKey": API_KEY,
                "regions": DFS_REGION,
                "markets": market_key,
                "oddsFormat": "american",
                "bookmakers": dfs_site.lower().replace(" ", "") # 'prizepicks'
            }
        ).json()
        
        # Skip if DFS site has no lines
        if not dfs_resp.get('bookmakers'): continue
        
        # 3. GET SHARP ODDS (Comparison Source)
        sharp_resp = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{game_id}/odds",
            params={
                "apiKey": API_KEY,
                "regions": REGION,
                "markets": market_key,
                "oddsFormat": "american",
                "bookmakers": "pinnacle,draftkings,fanduel"
            }
        ).json()

        # 4. MATCH PLAYERS
        dfs_book = dfs_resp['bookmakers'][0]
        for mkt in dfs_book.get('markets', []):
            for outcome in mkt.get('outcomes', []):
                player = outcome['name']
                line = outcome.get('point', 0)
                
                # Find Sharp Match
                sharp_prob = find_sharp_prob(sharp_resp, player, line)
                
                if sharp_prob > 0:
                    # EV Calc (PrizePicks Implied = 54.34%)
                    ev = (sharp_prob * 100) - 54.34
                    
                    all_data.append({
                        "Game": game_label,
                        "Player": player,
                        "Line": line,
                        "Sharp Win%": round(sharp_prob * 100, 1),
                        "EV%": round(ev, 1)
                    })
    
    return pd.DataFrame(all_data)

def find_sharp_prob(sharp_data, player, target_line):
    probs = []
    for book in sharp_data.get('bookmakers', []):
        for mkt in book.get('markets', []):
            for outcome in mkt.get('outcomes', []):
                # Check Name Match
                if outcome['name'] == player or outcome.get('description') == player:
                    # Check Line Match (within 0.1)
                    if abs(outcome.get('point', 0) - target_line) < 0.1:
                        # Convert Price to Prob
                        price = outcome.get('price', 0)
                        if price != 0:
                            if price > 0: prob = 100 / (price + 100)
                            else: prob = (-price) / (-price + 100)
                            probs.append(prob)
    
    if probs: return sum(probs) / len(probs)
    return 0.0

if st.button("🚀 Find Plays"):
    df = get_ev_data()
    if not df.empty:
        df = df[df['EV%'] >= min_ev].sort_values(by="EV%", ascending=False)
        st.success(f"Found {len(df)} Plays on {dfs_site}!")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning(f"No {market_name} lines found on {dfs_site} for these games yet.")
