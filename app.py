import requests
import pandas as pd
import time

API_KEY = "YOUR_API_KEY_HERE"  # Paste your key here

# The list of markets we want to fetch (Comma separated string)
# Note: The API allows multiple markets in one call, but keep it reasonable.
MARKETS_STRING = "player_points,player_rebounds,player_assists,player_threes"

def get_player_props(sport):
    print(f"Fetching props for {sport}...")
    
    # 1. Get the odds
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",  # "us" for US books, "us2" for more
        "markets": MARKETS_STRING, 
        "oddsFormat": "decimal",
        "bookmakers": "draftkings,fanduel,mgm,caesars" # Limit to major books to save data size
    }

    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return []

    data = response.json()
    
    # 2. Parse the complex JSON into a flat list
    all_props = []

    for game in data:
        game_title = f"{game['home_team']} vs {game['away_team']}"
        commence_time = game['commence_time']
        
        for bookmaker in game['bookmakers']:
            book_name = bookmaker['title']
            
            for market in bookmaker['markets']:
                market_key = market['key'] # e.g., "player_points"
                
                for outcome in market['outcomes']:
                    # This is where the actual line is
                    player_name = outcome['description']
                    bet_name = outcome['name'] # "Over" or "Under"
                    line = outcome.get('point') # The handicap (e.g., 20.5)
                    price = outcome['price'] # The odds (e.g., 1.91)
                    
                    if line is not None: # Only keep lines with a point value
                        all_props.append({
                            "Sport": sport,
                            "Game": game_title,
                            "Date": commence_time,
                            "Player": player_name,
                            "Market": market_key,
                            "Book": book_name,
                            "Type": bet_name,
                            "Line": line,
                            "Odds": price
                        })
    
    return all_props

# --- MAIN EXECUTION ---
final_data = []

# Loop through sports (NCAAB is the priority today)
for sport in ["basketball_ncaab", "icehockey_nhl"]:
    props = get_player_props(sport)
    final_data.extend(props)
    time.sleep(1) # Be polite to the API

# Convert to DataFrame
df = pd.DataFrame(final_data)

if not df.empty:
    print(f"Successfully scraped {len(df)} lines!")
    # Show top 5 rows
    print(df.head())
    
    # Optional: Save to CSV
    df.to_csv("todays_player_props.csv", index=False)
else:
    print("No props found. Are games posted yet? (Try again around 11 AM ET)")
