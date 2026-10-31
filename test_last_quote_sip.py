import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv


# Load .env from this folder first, then parent folder as fallback.
script_dir = Path(__file__).resolve().parent
load_dotenv(script_dir / ".env")
load_dotenv(script_dir.parent / ".env")

API_KEY = (
    os.getenv("ALPACA_DATA_KEY")
    or os.getenv("DATA_KEY")
    or os.getenv("API_KEY")
    or ""
).strip().strip('"').strip("'")
API_SECRET = (
    os.getenv("ALPACA_DATA_SECRET")
    or os.getenv("DATA_SECRET")
    or os.getenv("API_SECRET")
    or ""
).strip().strip('"').strip("'")

if not API_KEY or not API_SECRET:
    print("Missing API credentials in .env")
    print("Set DATA_KEY/DATA_SECRET or API_KEY/API_SECRET")
    sys.exit(1)

symbol = "SPY"
url = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest"
headers = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET,
}
params = {"feed": "sip"}

try:
    response = requests.get(url, headers=headers, params=params, timeout=15)
    if response.status_code != 200:
        print(f"Request failed: HTTP {response.status_code}")
        print(response.text)
        sys.exit(1)

    payload = response.json()
    quote = payload.get("quote")

    if not quote:
        print("No quote payload returned")
        print(payload)
        sys.exit(1)

    print("Latest SPY quote (feed=sip)")
    print(f"Bid price: {quote.get('bp')}")
    print(f"Bid size : {quote.get('bs')}")
    print(f"Ask price: {quote.get('ap')}")
    print(f"Ask size : {quote.get('as')}")
    print(f"Timestamp: {quote.get('t')}")

except requests.RequestException as exc:
    print(f"Network/API error: {exc}")
    sys.exit(1)
