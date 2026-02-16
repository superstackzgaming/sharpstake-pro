import streamlit as st
import pandas as pd
import requests

# --- CONFIGURATION ---
# SECURITY WARNING: Ideally use st.secrets for this key!
API_KEY = "818d64a21306f003ad587fbb0bd5958b"  # <--- PASTE YOUR KEY
REGION = "us"
DFS_REGION = "us_dfs"

# Sports Mapping
SPORTS = {
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "NHL": "icehockey_nhl",
    "Tennis": "tennis_atp_wta_all",
    "Golf": "golf_pga_tour",
    "Soccer (EPL)": "soccer_epl"
}

# Supported Markets
MARKETS = {
    "Points": "player_points",
    "Rebounds": "player_rebounds",
    "Assists": "player_assists",
    "Goals (NHL/Soccer)": "player_goals_scored"
}

st.set_page_config(page_title="SharpStake Pro", layout="wide")
st.title("🚀 SharpStake Pro: Multi-Sport EV Finder")

# --- SIDEBAR CONTROLS ---
selected_sport_name = st.sidebar.selectbox("Select Sport", list(SPORTS.keys()))
selected_market_name = st.sidebar.selectbox("Select Market", list(MARKETS.keys()))
sport_key = SPORTS[selected_sport_name]
market_key = MARKETS[selected_market_name]

# DFS Site Filter
dfs_sites = st.sidebar.multiselect("Select DFS Apps", ["PrizePicks", "Underdog Fantasy", "Betr", "DraftKings Pick6"], default=["PrizePicks"])

# EV Threshold
min_ev = st.sidebar.slider("Minimum EV %", 0.0, 10.0, 2.0)

# --- THE ENGINE (FUNCTIONS) ---
def get_ev_data(sport, market):
    # 1. Fetch Games
    st.info(f"Scanning {sport} games...")
    events_url = f"https://api.the-odds-api.com/v4/sports/{sport}/events"
    events = requests.get(events_url, params={"apiKey": API_KEY}).json()
    
    if not events:
        st.warning("No games found for this sport today.")
        return pd.DataFrame()

    all_data = []
    
    # LIMIT to first 3 games to save API quota
    for event in events[:3]:
        game_id = event['id']
        game_name = f"{event['home_team']} vs {event['away_team']}"
        
        # 2. Get DFS Lines
        dfs_url = f"https://api.the-odds-api.com/v4/sports/{sport}/events/{game_id}/odds"
        dfs_params = {
            "apiKey": API_KEY,
            "regions": DFS_REGION,
            "markets": market,
            "oddsFormat": "american",
            "bookmakers": "prizepicks,underdog,betr"
        }
        dfs_resp = requests.get(dfs_url, params=dfs_params)
        dfs_data = dfs_resp.json()
        
        # 3. Get Sharp Odds
        sb_params = dfs_params.copy()
        sb_params['regions'] = REGION
        sb_params['bookmakers'] = "draftkings,fanduel,pinnacle"
        sb_resp = requests.get(dfs_url, params=sb_params)
        sb_data = sb_resp.json()

        # 4. Match Them Up
        for dfs_book in dfs_data.get('bookmakers', []):
            dfs_name = dfs_book['title']
            if dfs_name not in dfs_sites: continue

            for mkt in dfs_book.get('markets', []):
                for outcome in mkt.get('outcomes', []):
                    player = outcome['name']
                    line = outcome['point']
                    
                    # Find Sharp Odds for this Player + Line
                    sharp_prob = find_sharp_prob(sb_data, player, line)
                    
                    if sharp_prob > 0:
                        ev = (sharp_prob * 100) - 54.34
                        all_data.append({
                            "Game": game_name,
                            "Player": player,
                            "Line": line,
                            "DFS Site": dfs_name,
                            "Sharp Win%": round(sharp_prob * 100, 1),
                            "EV%": round(ev, 1)
                        })

    return pd.DataFrame(all_data)

def find_sharp_prob(sb_data, player_name, target_line):
    probs = []
    for book in sb_data.get('bookmakers', []):
        for mkt in book.get('markets', []):
            for outcome in mkt.get('outcomes', []):
                if outcome['name'] == player_name:
                    if abs(outcome.get('point', 0) - target_line) < 0.1:
                        if outcome.get('name') == 'Over':
                             odds = outcome['price']
                             probs.append(american_to_prob(odds))
    if probs:
        return sum(probs) / len(probs)
    return 0.0

def american_to_prob(odds):
    if odds > 0: return 100 / (odds + 100)
    else: return (-odds) / (-odds + 100)

if st.button("🚀 Find +EV Plays"):
    with st.spinner("Analyzing Markets..."):
        df = get_ev_data(sport_key, market_key)
        if not df.empty:
            df_filtered = df[df['EV%'] >= min_ev].sort_values(by="EV%", ascending=False)
            st.success(f"Found {len(df_filtered)} Plays!")
            st.dataframe(df_filtered, use_container_width=True)
        else:
            st.error("No matching plays found.")
