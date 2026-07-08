import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("POLYGON_API_KEY", "")
DATA_DIR = os.getenv("POLYGON_LEGACY_DATA_DIR", "prices")
os.makedirs(DATA_DIR, exist_ok=True)

if not API_KEY:
    raise ValueError("Missing POLYGON_API_KEY in environment")

# ---------------------------------------------------------
# 1. Get all active US stock tickers
# ---------------------------------------------------------
def get_all_tickers():
    url = "https://api.polygon.io/v3/reference/tickers"
    params = {
        "market": "stocks",
        "active": "true",
        "limit": 1000,
        "apiKey": API_KEY
    }

    tickers = []
    while True:
        r = requests.get(url, params=params).json()
        tickers.extend([t["ticker"] for t in r["results"] if t["type"] == "CS"])

        if "next_url" not in r:
            break
        url = r["next_url"]

    return tickers


# ---------------------------------------------------------
# 2. Fetch 3 years of daily bars for a ticker
# ---------------------------------------------------------
def get_3yr_bars(ticker):
    end = datetime.today()
    start = end - timedelta(days=365 * 3)

    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start:%Y-%m-%d}/{end:%Y-%m-%d}"
    params = {"adjusted": "true", "limit": 50000, "apiKey": API_KEY}

    r = requests.get(url, params=params).json()
    if "results" not in r:
        return None

    df = pd.DataFrame(r["results"])
    df["date"] = pd.to_datetime(df["t"], unit="ms")
    df["dollar_volume"] = df["c"] * df["v"]
    df = df[["date", "c", "v", "dollar_volume"]]
    df.rename(columns={"c": "close", "v": "volume"}, inplace=True)

    return df



# ---------------------------------------------------------
# 2. Fetch all available years of daily bars for a ticker
# ---------------------------------------------------------
def get_all_bars(ticker):
    # Earliest possible date Polygon supports
    start = datetime(1980, 1, 1)   # safely before any modern ticker existed
    end = datetime.today()

    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start:%Y-%m-%d}/{end:%Y-%m-%d}"
    params = {"adjusted": "true", "limit": 50000, "apiKey": API_KEY}

    r = requests.get(url, params=params).json()
    if "results" not in r:
        return None

    df = pd.DataFrame(r["results"])
    df["date"] = pd.to_datetime(df["t"], unit="ms")
    df["dollar_volume"] = df["c"] * df["v"]
    df = df[["date", "c", "v", "dollar_volume"]]
    df.rename(columns={"c": "close", "v": "volume"}, inplace=True)

    return df




# ---------------------------------------------------------
# 3. Worker: compute ADV + save individual CSV + return data
# ---------------------------------------------------------
def process_ticker(ticker):
    df = get_3yr_bars(ticker)
    if df is None or df.empty:
        return None

    # Save individual price history
    df.to_csv(f"{DATA_DIR}/{ticker}.csv", index=False)

    # Compute ADV
    adv = df["dollar_volume"].mean()

    # Return for liquidity table + backtesting dataset
    df["ticker"] = ticker
    return ticker, adv, df


# ---------------------------------------------------------
# 4. Parallel ADV computation
# ---------------------------------------------------------
def compute_adv_parallel(tickers, max_workers=12):
    liquidity = []
    all_prices = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_ticker, t): t for t in tickers}

        for future in as_completed(futures):
            result = future.result()
            if result is None:
                continue

            ticker, adv, df = result
            liquidity.append((ticker, adv))
            all_prices.append(df)

    # Combine all price histories into one backtesting dataset
    if all_prices:
        combined = pd.concat(all_prices, ignore_index=True)
    else:
        combined = pd.DataFrame()

    return (
        pd.DataFrame(liquidity, columns=["ticker", "adv"]),
        combined
    )


# ---------------------------------------------------------
# 5. Main workflow
# ---------------------------------------------------------
if __name__ == "__main__":
    print("Downloading ticker list...")
    tickers = get_all_tickers()
    print(f"Found {len(tickers)} active common stocks")

    print("Computing 3-year ADV in parallel...")
    liquidity_df, backtest_df = compute_adv_parallel(tickers)

    # Sort by liquidity
    liquidity_df = liquidity_df.sort_values("adv", ascending=False).reset_index(drop=True)

    # Save full liquidity table
    liquidity_df.to_csv("all_liquidity.csv", index=False)
    print("Saved full liquidity rankings to all_liquidity.csv")

    # Save backtesting-ready dataset
    backtest_df.to_csv("backtesting_dataset.csv", index=False)
    print("Saved backtesting dataset to backtesting_dataset.csv")

    print("\nTop 100 most liquid stocks:")
    print(liquidity_df.head(100))



