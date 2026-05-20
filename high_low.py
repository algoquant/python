import requests
from datetime import date

API_KEY = "d84fc2a9c5bde2d68e33034f65a838092c6b9f10"
TICKER = "SPY"
TODAY = date.today().isoformat()

# Try real-time IEX quote first (includes today's high/low during market hours)
url = f"https://api.tiingo.com/iex/{TICKER}"
params = {"token": API_KEY}

response = requests.get(url, params=params)
response.raise_for_status()
data = response.json()

if data and isinstance(data, list):
    quote = data[0]
elif data and isinstance(data, dict):
    quote = data
else:
    quote = None

if quote and quote.get("high") is not None:
    print(f"Date : {TODAY}")
    print(f"High : {quote['high']}")
    print(f"Low  : {quote['low']}")
else:
    # Fallback: most recent daily bar
    url = f"https://api.tiingo.com/tiingo/daily/{TICKER}/prices"
    params = {"token": API_KEY}
    response = requests.get(url, params=params)
    response.raise_for_status()
    bars = response.json()
    if bars:
        bar = bars[-1]
        print(f"Date : {bar.get('date', '')[:10]} (most recent close)")
        print(f"High : {bar['high']}")
        print(f"Low  : {bar['low']}")
    else:
        print(f"No data available for {TICKER}")



