import streamlit as st
import pandas as pd
import requests

# --- CONFIGURATION ---
API_KEY = "818d64a21306f003ad587fbb0bd5958b" # Your Key
REGION = "us"
DFS_REGION = "us_dfs"

SPORTS = {
    "All Sports": "all",
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "NHL": "icehockey_nhl",
    "College Basketball": "basketball_ncaab",
    "Soccer (EPL)": "soccer_epl"
}

MARKETS = {
    "Points": "player_points",
    "Rebounds": "player_rebounds",
    "Assists": "player_assists",
    "Goals": "player_goals_scored",
    "Shots": "player_shots_on_goal"
}

st.set_page_config(page_title="SharpStake Pro", layout="wide")
st.title("🔥 SharpStake: The EV Board")

# --- SIDEBAR ---
sport_name = st.sidebar.selectbox("Sport", list(SPORTS.keys()))
dfs_site = st.sidebar.selectbox("DFS Site", ["PrizePicks", "Underdog Fantasy", "Betr"])
min_ev = st.sidebar.slider("Min EV %", 0.0, 10.0, 1.5)

# --- ENGINE ---
def get_ev_data():
    all_plays = []
    
    # Determine which sports to scan
    sports_to_scan = [SPORTS[sport_name]] if sport_name != "All Sports" else [v for k,v in SPORTS.items() if v != "all"]
    
    for sport_key in sports_to_scan:
        # 1. Get Games
        events = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/events", params={"apiKey": API_KEY}).json()
        if not events: continue

        # CHECK FIRST 3 GAMES PER SPORT
        for event in events[:3]:
            game_id = event['id']
            game_label = f"{event['home_team']} vs {event['away_team']}"
            
            # Check MAIN props (Points/Goals)
            market_key = "player_points" if "basketball" in sport_key else "player_goals_scored"
            
            # 2. GET DFS LINES
            dfs_resp = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{game_id}/odds",
                params={
                    "apiKey": API_KEY,
                    "regions": DFS_REGION,
                    "markets": market_key,
                    "oddsFormat": "american",
                    "bookmakers": dfs_site.lower().replace(" ", "")
                }
            ).json()
            
            if not dfs_resp.get('bookmakers'): continue
            
            # 3. GET SHARP ODDS
            sharp_resp = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{game_id}/odds",
                params={
                    "apiKey": API_KEY,
                    "regions": REGION,
                    "markets": market_key,
                    "oddsFormat": "american",
                    "bookmakers": "draftkings,fanduel"
                }
            ).json()

            # 4. MATCH & BUILD CARDS
            dfs_book = dfs_resp['bookmakers'][0]
            for mkt in dfs_book.get('markets', []):
                for outcome in mkt.get('outcomes', []):
                    player = outcome['name']
                    line = outcome.get('point', 0)
                    
                    # Find Sharp Odds for BOTH sides
                    over_prob, under_prob = find_sharp_probs(sharp_resp, player, line)
                    
                    # Calculate EV
                    over_ev = (over_prob * 100) - 54.34
                    under_ev = (under_prob * 100) - 54.34
                    
                    if over_ev > min_ev or under_ev > min_ev:
                        all_plays.append({
                            "Sport": sport_key,
                            "Game": game_label,
                            "Player": player,
                            "Line": line,
                            "Prop": market_key,
                            "Over EV": over_ev,
                            "Under EV": under_ev
                        })
    
    return sorted(all_plays, key=lambda x: max(x['Over EV'], x['Under EV']), reverse=True)

def find_sharp_probs(sharp_data, player, target_line):
    over_probs = []
    under_probs = []
    
    for book in sharp_data.get('bookmakers', []):
        for mkt in book.get('markets', []):
            for outcome in mkt.get('outcomes', []):
                if outcome['name'] == player or outcome.get('description') == player:
                    if abs(outcome.get('point', 0) - target_line) < 0.1:
                        price = outcome.get('price', 0)
                        prob = 100 / (price + 100) if price > 0 else (-price) / (-price + 100)
                        
                        if outcome.get('name') == 'Over': over_probs.append(prob)
                        elif outcome.get('name') == 'Under': under_probs.append(prob)
    
    avg_over = sum(over_probs)/len(over_probs) if over_probs else 0
    avg_under = sum(under_probs)/len(under_probs) if under_probs else 0
    return avg_over, avg_under

# --- DISPLAY (The PrizePicks Layout) ---
if st.button("🚀 Find Best Plays"):
    with st.spinner("Scanning Market..."):
        plays = get_ev_data()
        
        if not plays:
            st.warning("No +EV plays found right now.")
        else:
            for p in plays:
                # Create a "Card" for each player
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 1, 2, 2])
                    
                    with col1:
                        st.markdown(f"**{p['Player']}**")
                        st.caption(f"{p['Game']}")
                    
                    with col2:
                        st.metric("Line", f"{p['Line']}")
                    
                    with col3:
                        # Color code EV
                        over_color = "green" if p['Over EV'] > 0 else "red"
                        st.markdown(f":{over_color}[**OVER**] {p['Over EV']:.1f}% EV")
                        
                    with col4:
                        under_color = "green" if p['Under EV'] > 0 else "red"
                        st.markdown(f":{under_color}[**UNDER**] {p['Under EV']:.1f}% EV")
                    
                    st.divider()
