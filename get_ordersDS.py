import requests
import pandas as pd

# Replace with your Alpaca API credentials
API_KEY = "PKMIDDD0B792FZO6HF7E"
API_SECRET = "u89kQV6dRJyom4ONFgpWHOr7jho8fY3SrMTD6Fvs"
BASE_URL = "https://paper-api.alpaca.markets"  # Use "https://api.alpaca.markets" for live trading

headers = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET
}

# Fetch orders
response = requests.get(f"{BASE_URL}/v2/orders?status=all", headers=headers)
print(f"Fetching orders from {BASE_URL}/v2/orders")

if response.status_code == 200:
    orders = response.json()
    
    # Convert to DataFrame
    df = pd.DataFrame(orders)

    # Display the first few rows
    print(df.head())

    # Optionally save to CSV
    df.to_csv("alpaca_orders.csv", index=False)
else:
    print(f"Error: {response.status_code}, {response.text}")

# Save DataFrame to CSV
df.to_csv("paper3_orders.csv", index=False)

