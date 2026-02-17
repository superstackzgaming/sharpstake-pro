import requests
import pandas as pd

# --- CONFIGURATION ---
API_KEY = "818d64a21306f003ad587fbb0bd5958b"  # Paste your key inside these quotes
SPORT = "basketball_ncaab" # The sport we want
MARKETS = "player_points,player_rebounds,player_assists" # The props we want
BOOKMAKERS = "draftkings,fanduel,mgm" # The books we want

def fetch_player_props():
    print(f"Fetching {MARKETS} for {SPORT}...")
    
    # 1. Build the URL
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": MARKETS,
        "oddsFormat": "american", # Returns -110 instead of 1.91
        "bookmakers": BOOKMAKERS
    }

    # 2. Call the API
    response = requests.get(url, params=params)
    
    # 3. Check for errors
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return pd.DataFrame() # Return empty table

    # 4. Process the Data
    data = response.json()
    prop_list = []

    for game in data:
        game_title = f"{game['home_team']} vs {game['away_team']}"
        
        for book in game['bookmakers']:
            book_name = book['title']
            
            for market in book['markets']:
                market_name = market['key'] # e.g. "player_points"
                
                for outcome in market['outcomes']:
                    # Extract the data
                    player_name = outcome['description']
                    wager_type = outcome['name'] # "Over" or "Under"
                    line = outcome.get('point') # The number (e.g. 20.5)
                    odds = outcome['price'] # The price (e.g. -110)
                    
                    if line: # Only keep if there is a line
                        prop_list.append({
                            "Game": game_title,
                            "Player": player_name,
                            "Market": market_name,
                            "Book": book_name,
                            "Type": wager_type,
                            "Line": line,
                            "Odds": odds
                        })

    return pd.DataFrame(prop_list)

# --- RUN IT ---
if __name__ == "__main__":
    df = fetch_player_props()
    
    if not df.empty:
        print("\nSUCCESS! Here are the first 10 props found:")
        print(df.head(10).to_markdown(index=False))
        
        # Save to CSV so you can open in Excel
        df.to_csv("my_props.csv", index=False)
        print("\nSaved all props to 'my_props.csv'")
    else:
        print("\nNo props found. (Check your API key or try a different sport)")
