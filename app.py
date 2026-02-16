
import streamlit as st
import pandas as pd
import requests

# --- CONFIGURATION ---
API_KEY = "818d64a21306f003ad587fbb0bd5958b"
REGION = "us_dfs" # Force DFS Region check

st.set_page_config(page_title="SharpStake Debugger", layout="wide")
st.title("🛠️ SharpStake Data Inspector")

# --- CONTROLS ---
sport = st.selectbox("Sport", ["icehockey_nhl", "basketball_ncaab", "soccer_epl"])
market = st.selectbox("Market", ["player_points", "player_goals_scored"])

if st.button("Fetch Raw Data"):
    st.info(f"Fetching raw JSON for {sport} / {market}...")
    
    # 1. Get Events
    events = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport}/events", params={"apiKey": API_KEY}).json()
    
    if not events:
        st.error("❌ No games found in API response.")
    else:
        st.success(f"✅ Found {len(events)} games.")
        
        all_lines = []
        
        # Check first 3 games
        for event in events[:3]:
            game_label = f"{event['home_team']} vs {event['away_team']}"
            game_id = event['id']
            
            # 2. Get Odds (NO FILTERING)
            odds = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport}/events/{game_id}/odds",
                params={
                    "apiKey": API_KEY,
                    "regions": REGION, # Check DFS region specifically
                    "markets": market,
                    "oddsFormat": "american",
                }
            ).json()
            
            # 3. Parse and Dump Everything
            if 'bookmakers' in odds:
                for book in odds['bookmakers']:
                    book_name = book['title']
                    for mkt in book['markets']:
                        for outcome in mkt['outcomes']:
                            all_lines.append({
                                "Game": game_label,
                                "Book": book_name,
                                "Player": outcome['name'], # Or description
                                "Line": outcome.get('point', 'N/A'),
                                "Price": outcome.get('price', 'N/A')
                            })
                            
        if all_lines:
            st.write(f"### Found {len(all_lines)} Raw Lines")
            df = pd.DataFrame(all_lines)
            st.dataframe(df, use_container_width=True)
            
            # Check specifically for PrizePicks
            pp_lines = df[df['Book'].str.contains("PrizePicks", case=False)]
            if not pp_lines.empty:
                st.success(f"🎉 FOUND {len(pp_lines)} PRIZEPICKS LINES!")
                st.dataframe(pp_lines)
            else:
                st.warning("⚠️ No PrizePicks lines found in this batch.")
        else:
            st.warning("⚠️ API returned valid game, but 'bookmakers' list was empty.")
