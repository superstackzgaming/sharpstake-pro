import streamlit as st
import pandas as pd
import requests

# --- CONFIGURATION ---
API_KEY = "818d64a21306f003ad587fbb0bd5958b"  # <--- PASTE YOUR KEY
REGION = "us" 
DFS_REGION = "us_dfs"

# Sports Mapping
SPORTS = {
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "NHL": "icehockey_nhl",
    "College Basketball": "basketball_ncaab",
    "Tennis": "tennis_atp_wta_all",
    "Soccer (EPL)": "soccer_epl"
}

# Markets Mapping
MARKETS = {
    "NBA": ["player_points", "player_rebounds", "player_assists", "player_threes", "player_points_rebounds_assists"],
    "NFL": ["player_pass_yds", "player_rush_yds", "player_reception_yds", "player_anytime_td"],
    "NHL": ["player_points", "player_goals", "player_assists", "player_shots_on_goal"],
    "College Basketball": ["player_points", "player_rebounds", "player_assists"],
    "Tennis": ["h2h_winner"], # Limited props for tennis in API
    "Soccer (EPL)": ["player_goals_scored"]
}

# Sharp Books for "True Odds"
SHARP_BOOKS = ["pinnacle", "bookmaker", "betonlineag", "draftkings", "fanduel", "bovada"]

st.set_page_config(page_title="SharpStake | OddsJam Clone", layout="wide")
st.title("🔥 SharpStake: The Fantasy Optimizer")

# --- SIDEBAR ---
sport_name = st.sidebar.selectbox("Select Sport", list(SPORTS.keys()))
sport_key = SPORTS[sport_name]

# Market Selection
avail_markets = MARKETS.get(sport_name, [])
market_key = st.sidebar.selectbox("Select Prop Market", avail_markets)

# DFS Site Selection
dfs_site = st.sidebar.selectbox("Select DFS Site", ["PrizePicks", "Underdog", "ParlayPlay"])

# IMPLIED PROBABILITIES (Break-even %)
# PrizePicks 5-Flex = -119 (54.34%)
# Underdog 5-Pick = -122 (54.95%)
IMPLIED_PROBS = {
    "PrizePicks": 54.34,
    "Underdog": 54.95,
    "ParlayPlay": 53.22
}
break_even = IMPLIED_PROBS.get(dfs_site, 54.34)
st.sidebar.markdown(f"**Break-Even to Beat:** {break_even}%")

min_ev = st.sidebar.slider("Min EV (%)", 0.0, 10.0, 1.5)

# --- MATH FUNCTIONS ---
def devig_odds(over_price, under_price):
    """
    Calculates Fair Win Probability by removing the vig.
    Input: American Odds (e.g. -140, +110)
    Output: Decimal Probability (e.g. 0.568)
    """
    # Convert to Implied Prob
    def to_prob(odd):
        if odd > 0: return 100 / (odd + 100)
        else: return (-odd) / (-odd + 100)
    
    p_over = to_prob(over_price)
    p_under = to_prob(under_price)
    
    # Remove Vig (Proportional Method)
    total_vig = p_over + p_under
    fair_prob = p_over / total_vig
    return fair_prob

# --- DATA ENGINE ---
def get_optimizer_data():
    st.toast(f"Scanning {sport_name} for +EV plays...", icon="⚡")
    
    # 1. Fetch Events
    events = requests.get(
        f"https://api.the-odds-api.com/v4/sports/{sport_key}/events", 
        params={"apiKey": API_KEY}
    ).json()
    
    if not events or 'message' in events:
        return pd.DataFrame() # Return empty if no games

    data = []
    
    # Check first 5 games
    for event in events[:5]:
        game_id = event['id']
        game_label = f"{event['home_team']} vs {event['away_team']}"
        
        # 2. Get Odds from ALL Books (DFS + Sharps)
        # We fetch "us" region (Sharps) and "us_dfs" (PrizePicks) separately? 
        # Actually, let's fetch 'us' and 'us_dfs' if possible, or make 2 calls.
        # To save quota, we make 2 specific calls per game.
        
        # Call A: DFS Lines
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
        
        # Call B: Sharp Odds
        sharp_resp = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{game_id}/odds",
            params={
                "apiKey": API_KEY,
                "regions": REGION,
                "markets": market_key,
                "oddsFormat": "american",
                "bookmakers": ",".join(SHARP_BOOKS)
            }
        ).json()

        # 3. Find Matches
        # Iterate through DFS lines
        for book in dfs_resp.get('bookmakers', []):
            for mkt in book.get('markets', []):
                for outcome in mkt.get('outcomes', []):
                    player = outcome['name']
                    line = outcome.get('point', 0)
                    side = outcome.get('name') # 'Over' or 'Under' usually not labeled in DFS, assumed 'Line'
                    
                    # DFS sites just give a number (e.g. 24.5). We must check BOTH Over and Under against Sharps.
                    
                    # Find matching Sharp Market
                    best_ev = -100
                    best_side = ""
                    sharp_details = ""
                    
                    # Look for this player in Sharp Data
                    for s_book in sharp_resp.get('bookmakers', []):
                        for s_mkt in s_book.get('markets', []):
                             # Check if it's the same player/prop
                             # (The Odds API structure groups by market, so we are good on prop type)
                             
                             # Find the outcome for this player
                             # Note: API structure for props is: Market -> Outcomes [Player Over, Player Under]? 
                             # Actually it's usually: Market (Player Points) -> Outcomes [Over, Under] 
                             # BUT for "player_points", the 'key' is the prop, and outcomes has 'name'="Over", 'point'=24.5
                             
                             # Wait, for Player Props, the 'outcomes' list usually contains MULTIPLE players?
                             # NO. The market key is 'player_points'. The outcomes are 'Over' and 'Under' for a specific player?
                             # Actually, The Odds API v4 returns outcomes as: Name="LeBron James", Point=24.5?
                             # Let's assume standard structure:
                             
                             # Find outcomes matching our player
                             s_outcomes = [o for o in s_mkt['outcomes'] if o['name'] == player]
                             
                             # Check if we have Over/Under odds
                             # (This part depends heavily on API response structure for the specific sport)
                             # Let's try to match by Point Line
                             
                             # Filter for exact line match (Sharps must have same line 24.5)
                             matched_outcomes = [o for o in mkt['outcomes'] if o['name'] == player] 
                             # Wait, s_outcomes is from Sharp Book.
                             pass 
                             
                    # --- SIMPLIFIED MATCHING LOGIC ---
                    # We need to find the specific Sharp Market for this player
                    # API v4: Market = 'player_points'. Outcomes = [{'name': 'Over', 'point': 24.5, 'price': -110}, ...]
                    # Actually, usually 'description' or 'name' holds the player name in some formats, 
                    # OR the market key includes the player ID. 
                    # For The Odds API, 'outcomes' usually has 'description' = Player Name? 
                    # Let's assume we find the player in the outcomes list.

                    # REAL LOGIC:
                    # We will loop through Sharp Books. If we find the Player + Line (24.5), we get the Over/Under price.
                    
                    # (Placeholder for complex JSON parsing loop - simplified for this script)
                    # Let's assume we found Pinnacle Odds: Over -140, Under +110
                    
                    # If we found it:
                    # fair_prob = devig_odds(-140, 110) # 56.8%
                    # ev = fair_prob * 100 - break_even
                    
                    # Since I cannot see the live JSON to parse perfectly, 
                    # I will add a "Mock" EV calculation here so the app RUNS 
                    # and you can see the UI. You will need to tweak the parsing 
                    # once you see the real data structure.
                    
                    pass

    return pd.DataFrame() 

# --- RUN ---
st.error("⚠️ LOGIC UPDATE NEEDED: To parse Player Props correctly, we need to inspect the exact JSON structure of the API response for 'player_points'.")
st.info("The structure varies by sport. Please run the 'Check Player Props' script from earlier to see the JSON, then we can map the 'Over/Under' prices.")

