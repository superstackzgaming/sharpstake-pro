import streamlit as st
import pandas as pd
import requests

# --- CONFIGURATION ---
API_KEY = "818d64a21306f003ad587fbb0bd5958b"
REGION = "us"
DFS_REGION = "us_dfs"

st.set_page_config(page_title="SharpStake Optimizer", layout="wide")

# --- CUSTOM CSS (Make it look like OddsJam) ---
st.markdown("""
<style>
    .stDataFrame { font-size: 14px; }
    div[data-testid="stMetricValue"] { font-size: 18px; }
    .ev-green { color: #00ff00; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ SharpStake Fantasy Optimizer")

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("⚙️ Settings")
    sport_key = st.selectbox("Sport", ["basketball_nba", "icehockey_nhl", "soccer_epl"], index=1)
    dfs_site = st.selectbox("DFS Site", ["PrizePicks", "Underdog Fantasy"])
    
    # Dynamic Break-Even Rates
    break_even = 54.34 if dfs_site == "PrizePicks" else 55.0
    st.caption(f"Break-Even Win %: **{break_even}%**")
    
    min_ev = st.slider("Min EV %", 0.0, 15.0, 1.5)
    
    # Market Filter
    market_map = {
        "basketball_nba": "player_points",
        "icehockey_nhl": "player_points", 
        "soccer_epl": "player_goals_scored"
    }
    market_key = market_map.get(sport_key, "player_points")

# --- ENGINE ---
def get_optimizer_data():
    all_rows = []
    
    # 1. Get Games
    events = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/events", params={"apiKey": API_KEY}).json()
    if not events: return pd.DataFrame()

    # Progress Bar
    progress_text = "Scanning Sharps..."
    my_bar = st.progress(0, text=progress_text)
    
    # SCAN FIRST 5 GAMES
    for i, event in enumerate(events[:5]):
        game_id = event['id']
        game_label = f"{event['home_team']} vs {event['away_team']}"
        my_bar.progress((i + 1) * 20, text=f"Checking {game_label}...")

        # 2. Get DFS & Sharp Odds in Parallel
        # (For speed, we'd use async, but this is simple sync code)
        
        # A. DFS Lines
        dfs_resp = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{game_id}/odds",
            params={"apiKey": API_KEY, "regions": DFS_REGION, "markets": market_key, "oddsFormat": "american", "bookmakers": dfs_site.lower().replace(" ", "")}
        ).json()
        
        # B. Sharp Lines (Pinnacle/DK)
        sharp_resp = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{game_id}/odds",
            params={"apiKey": API_KEY, "regions": REGION, "markets": market_key, "oddsFormat": "american", "bookmakers": "pinnacle,draftkings"}
        ).json()

        if not dfs_resp.get('bookmakers'): continue

        # 3. MATCH LOGIC
        dfs_book = dfs_resp['bookmakers'][0]
        for mkt in dfs_book.get('markets', []):
            for outcome in mkt.get('outcomes', []):
                player = outcome['name']
                line = outcome.get('point', 0)
                
                # Find Sharp Odds for this specific line
                best_side, win_prob, sharp_odds_str = find_sharp_edge(sharp_resp, player, line)
                
                if win_prob > 0:
                    ev = (win_prob * 100) - break_even
                    
                    if ev >= min_ev:
                        all_rows.append({
                            "Player": player,
                            "Game": game_label,
                            "Prop": market_key.replace("player_", "").title(),
                            "Line": line,
                            "Pick": best_side.upper(),
                            "Sharp Odds": sharp_odds_str,
                            "Win %": win_prob * 100, # Keep as number for sorting
                            "EV %": ev               # Keep as number for sorting
                        })
    
    my_bar.empty()
    return pd.DataFrame(all_rows)

def find_sharp_edge(sharp_data, player, target_line):
    # Search for matching player + line
    # Returns: (Best Side, Win %, Sharp Odds String)
    
    for book in sharp_data.get('bookmakers', []):
        for mkt in book.get('markets', []):
            for outcome in mkt.get('outcomes', []):
                # Loose Match
                if outcome['name'] == player or outcome.get('description') == player:
                    if abs(outcome.get('point', 0) - target_line) < 0.1:
                        
                        # We found the line! Now check price.
                        price = outcome.get('price', 0)
                        side = outcome.get('name', 'Over') # Usually 'Over' or 'Under'
                        
                        # Calculate Prob
                        if price > 0: prob = 100 / (price + 100)
                        else: prob = (-price) / (-price + 100)
                        
                        # Format "Sharp Odds" text
                        sharp_str = f"{book['title']}: {price}"
                        
                        return side, prob, sharp_str

    return None, 0.0, ""

# --- MAIN UI ---
if st.button("🔄 Refresh Optimizer"):
    df = get_optimizer_data()
    
    if not df.empty:
        # Sort by EV
        df = df.sort_values(by="EV %", ascending=False)
        
        # Metric Cards at Top
        top_play = df.iloc[0]
        col1, col2, col3 = st.columns(3)
        col1.metric("Top Play", top_play['Player'])
        col2.metric("Pick", f"{top_play['Pick']} {top_play['Line']}")
        col3.metric("EV", f"{top_play['EV %']:.1f}%")
        
        st.divider()
        
        # THE OPTIMIZER TABLE
        st.dataframe(
            df,
            column_config={
                "Player": st.column_config.TextColumn("Player", width="medium"),
                "Game": st.column_config.TextColumn("Matchup", width="small"),
                "Prop": st.column_config.TextColumn("Prop", width="small"),
                "Line": st.column_config.NumberColumn("Line", format="%.1f"),
                "Pick": st.column_config.TextColumn("Pick", width="small"),
                "Sharp Odds": st.column_config.TextColumn("Sharp Odds", width="medium"),
                
                "Win %": st.column_config.ProgressColumn(
                    "Win %",
                    format="%.1f%%",
                    min_value=50,
                    max_value=75,
                ),
                "EV %": st.column_config.ProgressColumn(
                    "Edge (EV)",
                    format="%.1f%%",
                    min_value=0,
                    max_value=15,
                ),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning(f"No +EV plays found for {sport_key} on {dfs_site}.")
        st.info("Try lowering the Min EV % or switching sports.")
