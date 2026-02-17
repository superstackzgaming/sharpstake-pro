import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# --- CONFIGURATION ---
st.set_page_config(page_title="SmartStake Clone", layout="wide")
st.title("🏀 Player Prop Analyzer")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter API Key", type="password")
    sport = st.selectbox("Select Sport", ["basketball_ncaab", "icehockey_nhl", "basketball_nba"])
    markets = st.multiselect("Select Markets", 
                             ["player_points", "player_rebounds", "player_assists", "player_threes"],
                             default=["player_points"])

# --- FUNCTION TO FETCH DATA ---
@st.cache_data(ttl=3600) # Cache data for 1 hour to save API calls
def fetch_data(api_key, sport, markets):
    if not api_key:
        return pd.DataFrame() # Return empty if no key
    
    # Construct the API URL
    market_string = ",".join(markets)
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": market_string,
        "oddsFormat": "american",
        "bookmakers": "draftkings,fanduel,mgm,caesars"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

    # Process the JSON into a DataFrame
    all_props = []
    for game in data:
        game_title = f"{game['home_team']} vs {game['away_team']}"
        for book in game['bookmakers']:
            book_name = book['title']
            for market in book['markets']:
                market_key = market['key']
                for outcome in market['outcomes']:
                    if 'point' in outcome: # Only keep props with lines
                        all_props.append({
                            "Game": game_title,
                            "Player": outcome['description'],
                            "Market": market_key,
                            "Book": book_name,
                            "Type": outcome['name'], # Over/Under
                            "Line": outcome['point'],
                            "Odds": outcome['price']
                        })
    
    return pd.DataFrame(all_props)

# --- MAIN APP LOGIC ---
if st.button("Fetch Latest Odds"):
    if not api_key:
        st.warning("Please enter an API Key in the sidebar.")
    else:
        with st.spinner("Fetching data from Vegas..."):
            df = fetch_data(api_key, sport, markets)
        
        if df.empty:
            st.warning("No props found. Try a different sport or check your key.")
        else:
            st.success(f"Found {len(df)} player props!")
            
            # 1. Show Summary Metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Props", len(df))
            col2.metric("Unique Players", df['Player'].nunique())
            col3.metric("Sportsbooks", df['Book'].nunique())
            
            # 2. Interactive Data Table
            st.subheader("📋 Prop Search")
            search = st.text_input("Search for a Player (e.g., 'Edey')")
            
            if search:
                filtered_df = df[df['Player'].str.contains(search, case=False)]
            else:
                filtered_df = df
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # 3. Visual Analysis (Optional)
            st.subheader("📊 Odds Distribution")
            fig = px.histogram(df, x="Odds", color="Book", nbins=20, title="Odds Distribution by Sportsbook")
            st.plotly_chart(fig, use_container_width=True)
            
            # 4. Download Button
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "props.csv", "text/csv")

