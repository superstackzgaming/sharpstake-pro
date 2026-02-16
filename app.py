import streamlit as st
import pandas as pd
import requests

# --- CONFIGURATION ---
API_KEY = "818d64a21306f003ad587fbb0bd5958b"
REGION = "us"
DFS_REGION = "us_dfs"

st.set_page_config(page_title="SharpStake Pro", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stDataFrame { font-size: 14px; }
    div[data-testid="stMetricValue"] { font-size: 18px; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ SharpStake: Auto-Scan Optimizer")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    # 1. Select Sport
    sport_map = {
        "NBA": "basketball_nba",
        "NHL": "icehockey_nhl", 
        "College Basketball": "basketball_ncaab",
        "Soccer (EPL)": "soccer_epl"
    }
    sport_name = st.selectbox("Sport", list(sport_map.keys()))
    sport_key = sport_map[sport_name]
    
    # 2. Select DFS Site
    dfs_site = st.selectbox("DFS Site", ["PrizePicks", "Underdog Fantasy"])
    
    # 3. EV Filter
    min_ev = st.slider("Min EV %", 0.0, 10.0, 1.5)
    
    # Break-Even Logic
    break_even = 54.34 if dfs_site == "PrizePicks" else 55.0
    st.caption(f"Break-Even: **{break_even}%**")

# --- MARKETS TO SCAN (AUTO) ---
# When you pick a sport, we automatically scan ALL these props
MARKETS_CONFIG = {
    "basketball_nba": ["player_points", "player_rebounds", "player_assists", "player_threes"],
    "icehockey_nhl": ["player_points", "player_goals_scored", "player_assists"],
    "basketball_ncaab": ["player_points"],
    "soccer_epl": ["player_goals_scored"]
}

# --- ENGINE ---
def scan_all_markets():
    all_rows = []
    markets_to_scan = MARKETS_CONFIG.get(sport_key, [])
    
    # 1. Get Games (Once)
    events = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/events", params={"apiKey": API_KEY}).json()
    if not events: return pd.DataFrame()
    
    # Progress Bar
    progress_bar = st.progress(0, text="Starting Scan...")
    total_steps = len(events[:3]) * len(markets_to_scan) # Limit to 3 games for speed
    current_step = 0
    
    # 2. Loop through Games
    for game in events[:3]: # Limit 3 games
        game_label = f"{game['home_team']} vs {game['away_team']}"
        game_id = game['id']
        
        # 3. Loop through ALL Markets (Points, Rebs, Asts)
        for market in markets_to_scan:
            current_step += 1
            progress_bar.progress(int((current_step / total_steps) * 90), text=f"Scanning {market} in {game_label}...")
            
            # A. Get DFS Lines
            dfs_resp = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{game_id}/odds",
                params={"apiKey": API_KEY, "regions": DFS_REGION, "markets": market, "oddsFormat": "american", "bookmakers": dfs_site.lower().replace(" ", "")}
            ).json()
            
            # Skip if no lines
            if not dfs_resp.get('bookmakers'): continue
            
            # B. Get Sharp Odds (Only if DFS lines exist)
            sharp_resp = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{game_id}/odds",
                params={"apiKey": API_KEY, "regions": REGION, "markets": market, "oddsFormat": "american", "bookmakers": "pinnacle,draftkings"}
            ).json()
            
            # C. Match & Calculate
            dfs_book = dfs_resp['bookmakers'][0]
            for mkt in dfs_book.get('markets', []):
                for outcome in mkt.get('outcomes', []):
                    player = outcome['name']
                    line = outcome.get('point', 0)
                    
                    # Find Sharp Edge
                    best_side, win_prob, sharp_str = find_sharp_edge(sharp_resp, player, line)
                    
                    if win_prob > 0:
                        ev = (win_prob * 100) - break_even
                        if ev >= min_ev:
                            all_rows.append({
                                "Player": player,
                                "Prop": market.replace("player_", "").title().replace("_scored", ""),
                                "Line": line,
                                "Pick": best_side, # Over/Under
                                "Game": game_label,
                                "EV %": ev,
                                "Win %": win_prob * 100,
                                "Sharp Odds": sharp_str
                            })
    
    progress_bar.empty()
    return pd.DataFrame(all_rows)

def find_sharp_edge(sharp_data, player, target_line):
    # Search for matching player + line
    for book in sharp_data.get('bookmakers', []):
        for mkt in book.get('markets', []):
            for outcome in mkt.get('outcomes', []):
                if outcome['name'] == player or outcome.get('description') == player:
                    if abs(outcome.get('point', 0) - target_line) < 0.1:
                        price = outcome.get('price', 0)
                        side = outcome.get('name', 'Over')
                        
                        # Convert to Prob
                        if price > 0: prob = 100 / (price + 100)
                        else: prob = (-price) / (-price + 100)
                        
                        # Only return if this side is the "Favorite" (Prob > 50%)?
                        # Or return whatever side we found. 
                        # For simplicity, let's return this side.
                        return side, prob, f"{book['title']}: {price}"
    return None, 0.0, ""

# --- AUTO-RUN LOGIC ---
# We use session state to run once on load, or when button clicked
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame()

if st.button("🔄 Scan All Markets"):
    st.session_state.data = scan_all_markets()

# Display Data
df = st.session_state.data
if not df.empty:
    # Sort by EV
    df = df.sort_values(by="EV %", ascending=False)
    
    # Top Plays Metrics
    top = df.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Top Player", top['Player'])
    c2.metric("Prop", f"{top['Prop']} {top['Line']}")
    c3.metric("Pick", top['Pick'])
    c4.metric("EV", f"{top['EV %']:.1f}%", delta_color="normal")
    
    st.dataframe(
        df,
        column_config={
            "Win %": st.column_config.ProgressColumn("Win %", format="%.1f%%", min_value=50, max_value=70),
            "EV %": st.column_config.ProgressColumn("EV %", format="%.1f%%", min_value=0, max_value=15),
        },
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Click 'Scan All Markets' to start.")
