import streamlit as st
import pandas as pd
import requests

# --- CONFIGURATION ---
# ⚠️ SECURITY: Replace with your key or st.secrets["ODDS_API_KEY"]
API_KEY = "818d64a21306f003ad587fbb0bd5958b"

REGION = "us"
DFS_REGION = "us_dfs"

# 1. SPORTS MAPPING
SPORTS = {
    "Basketball (NBA)": "basketball_nba",
    "Football (NFL)": "americanfootball_nfl",
    "Ice Hockey (NHL)": "icehockey_nhl",
    "Tennis (ATP)": "tennis_atp_wta_all", # Check availability
    "Golf (PGA)": "golf_pga_tour",
    "Soccer (EPL)": "soccer_epl"
}

# 2. MARKETS MAPPING (Strictly Player Props)
MARKETS = {
    "Basketball (NBA)": {
        "Points": "player_points",
        "Rebounds": "player_rebounds",
        "Assists": "player_assists",
        "Threes Made": "player_threes",
        "Blocks": "player_blocks",
        "Steals": "player_steals",
        "Turnovers": "player_turnovers"
    },
    "Football (NFL)": {
        "Passing Yards": "player_pass_yds",
        "Pass TDs": "player_pass_tds",
        "Rush Yards": "player_rush_yds",
        "Rec Yards": "player_reception_yds",
        "Anytime TD": "player_anytime_td_scorer"
    },
    "Ice Hockey (NHL)": {
        "Goals": "player_goals_scored",
        "Assists": "player_assists",
        "Points": "player_points",
        "Shots on Goal": "player_shots_on_goal",
        "Power Play Points": "player_power_play_points"
    },
    "Tennis (ATP)": {
        "Total Aces": "player_aces", # Note: Odds API support varies
        "Double Faults": "player_double_faults"
    },
    "Golf (PGA)": {
        "Round Score": "player_round_score", # Note: Odds API support varies
        "Birdies": "player_birdies"
    },
    "Soccer (EPL)": {
        "Goals": "player_goals_scored",
        "Assists": "player_assists",
        "Shots on Target": "player_shots_on_target"
    }
}

st.set_page_config(page_title="SharpStake Pro | Props Only", layout="wide")
st.title("🎯 SharpStake Pro: Player Props Engine")

# --- SIDEBAR ---
selected_sport_name = st.sidebar.selectbox("Select Sport", list(SPORTS.keys()))
sport_key = SPORTS[selected_sport_name]

# Dynamic Markets Dropdown
available_markets = MARKETS.get(selected_sport_name, {})
if not available_markets:
    st.error("No player props configured for this sport yet.")
    st.stop()

selected_market_name = st.sidebar.selectbox("Select Prop Type", list(available_markets.keys()))
market_key = available_markets[selected_market_name]

dfs_sites = st.sidebar.multiselect("Select DFS Apps", ["PrizePicks", "Underdog Fantasy", "Betr", "DraftKings Pick6"], default=["PrizePicks"])
min_ev = st.sidebar.slider("Minimum EV %", 0.0, 15.0, 2.0)

# --- THE ENGINE ---
def get_ev_data(sport, market):
    st.info(f"Scanning {sport} for {selected_market_name} lines...")
    
    # 1. Fetch Games
    events_url = f"https://api.the-odds-api.com/v4/sports/{sport}/events"
    events = requests.get(events_url, params={"apiKey": API_KEY}).json()
    
    if not events or 'message' in events:
        st.warning("No games found (or API limit reached).")
        return pd.DataFrame()

    all_data = []
    
    # LIMIT: Check first 3 games to save quota
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
        sb_params['bookmakers'] = "draftkings,fanduel,pinnacle,caesars"
        sb_resp = requests.get(dfs_url, params=sb_params)
        sb_data = sb_resp.json()

        # 4. Match Logic
        for dfs_book in dfs_data.get('bookmakers', []):
            dfs_name = dfs_book['title']
            if dfs_name not in dfs_sites: continue

            for mkt in dfs_book.get('markets', []):
                for outcome in mkt.get('outcomes', []):
                    player = outcome['name']
                    line = outcome.get('point', 0)
                    
                    # Find Sharp Odds
                    sharp_prob = find_sharp_prob(sb_data, player, line)
                    
                    if sharp_prob > 0:
                        # EV Calc (PrizePicks -119 implied = 54.34%)
                        ev = (sharp_prob * 100) - 54.34
                        
                        all_data.append({
                            "Game": game_name,
                            "Player": player,
                            "Prop": selected_market_name,
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
                    # Logic: Must match line EXACTLY or be "Anytime TD" (no line)
                    is_line_match = abs(outcome.get('point', 0) - target_line) < 0.1
                    is_anytime_prop = target_line == 0 # e.g. Anytime TD
                    
                    if is_line_match or is_anytime_prop:
                         # Assume 'Over' or 'Yes' is what we want
                         if outcome.get('name') in ['Over', 'Yes']:
                             odds = outcome['price']
                             probs.append(american_to_prob(odds))
    
    if probs: return sum(probs) / len(probs)
    return 0.0

def american_to_prob(odds):
    if odds > 0: return 100 / (odds + 100)
    else: return (-odds) / (-odds + 100)

# --- RUN BUTTON ---
if st.button("🚀 Find +EV Props"):
    with st.spinner("Analyzing Markets..."):
        df = get_ev_data(sport_key, market_key)
        
        if not df.empty:
            # Filter & Sort
            df_filtered = df[df['EV%'] >= min_ev].sort_values(by="EV%", ascending=False)
            
            st.success(f"Found {len(df_filtered)} Props!")
            st.dataframe(
                df_filtered,
                column_config={
                    "EV%": st.column_config.ProgressColumn(
                        "Expected Value",
                        format="%.1f%%",
                        min_value=-5,
                        max_value=15,
                    ),
                },
                use_container_width=True
            )
        else:
            st.error("No matching props found. (API limit or no lines available)")
