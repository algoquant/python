import requests

# Alpaca API credentials
API_KEY = "your_api_key"
BASE_URL = "https://broker-api.alpaca.markets/v2/options/contracts"

# Define parameters
params = {
    "underlying_symbols": "AAPL",  # Fetch options for Apple Inc.
    "expiration_date_lte": "2025-06-30",  # Options expiring on or before June 30, 2025
    "limit": 50  # Limit the number of contracts returned
}

# Make the request
headers = {"APCA-API-KEY-ID": API_KEY}
response = requests.get(BASE_URL, params=params, headers=headers)

# Parse and display the response
if response.status_code == 200:
    contracts = response.json()
    print(contracts)
else:
    print(f"Error: {response.status_code} - {response.text}")
