import os
import asyncio
import math
from datetime import datetime

import aiohttp
import pandas as pd
from tqdm.asyncio import tqdm_asyncio

API_KEY = "YOUR_POLYGON_API_KEY"
DATA_DIR = "prices_parquet"
os.makedirs(DATA_DIR, exist_ok=True)

BASE_URL = "https://api.polygon.io"


# ---------------------------
# Helpers: HTTP with retries
# ---------------------------
async def fetch_json(session, url, params, max_retries=5, backoff_base=1.5):
    for attempt in range(max_retries):
        try:
            async with session.get(url, params=params, timeout=60) as resp:
                if resp.status == 429:
                    # Rate limit: exponential backoff
                    wait = backoff_base ** attempt
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return await resp.json()
        except Exception:
            if attempt == max_retries - 1:
                return None
            wait = backoff_base ** attempt
            await asyncio.sleep(wait)
    return None


# ---------------------------
# 1. Get all active tickers
# ---------------------------
async def get_all_tickers():
    tickers = []
    url = f"{BASE_URL}/v3/reference/tickers"
    params = {
        "market": "stocks",
        "active": "true",
        "limit": 1000,
        "apiKey": API_KEY,
    }

    async with aiohttp.ClientSession() as session:
        while True:
            data = await fetch_json(session, url, params)
            if not data or "results" not in data:
                break

            for t in data["results"]:
                if t.get("type") == "CS":
                    tickers.append(t["ticker"])

            next_url = data.get("next_url")
            if not next_url:
                break
            url = next_url

    return tickers


# ---------------------------
# 2. Fetch ALL daily bars
# ---------------------------
async def get_all_bars(session, ticker):
    start = datetime(1980, 1, 1)
    end = datetime.today()

    url = f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start:%Y-%m-%d}/{end:%Y-%m-%d}"
    params = {
        "adjusted": "true",
        "limit": 50000,
        "apiKey": API_KEY,
    }

    data = await fetch_json(session, url, params)
    if not data or "results" not in data:
        return None

    df = pd.DataFrame(data["results"])
    if df.empty:
        return None

    df["date"] = pd.to_datetime(df["t"], unit="ms")
    df["dollar_volume"] = df["c"] * df["v"]
    df = df[["date", "c", "v", "dollar_volume"]]
    df.rename(columns={"c": "close", "v": "volume"}, inplace=True)
    return df


# ---------------------------
# 3. Worker: one ticker
# ---------------------------
async def process_ticker(session, ticker):
    df = await get_all_bars(session, ticker)
    if df is None or df.empty:
        return None

    df["ticker"] = ticker

    # Save per‑ticker Parquet
    out_path = os.path.join(DATA_DIR, f"{ticker}.parquet")
    df.to_parquet(out_path, index=False)

    adv = df["dollar_volume"].mean()
    return ticker, adv, df


# ---------------------------
# 4. Orchestrate in batches
# ---------------------------
async def compute_adv_async(tickers, batch_size=64):
    liquidity = []
    all_prices = []

    connector = aiohttp.TCPConnector(limit=batch_size)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Process in chunks to avoid overwhelming API
        for i in tqdm_asyncio(range(0, len(tickers), batch_size), desc="Batches"):
            batch = tickers[i : i + batch_size]
            tasks = [process_ticker(session, t) for t in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if isinstance(res, Exception) or res is None:
                    continue
                ticker, adv, df = res
                liquidity.append((ticker, adv))
                all_prices.append(df)

    if all_prices:
        combined = pd.concat(all_prices, ignore_index=True)
    else:
        combined = pd.DataFrame()

    return (
        pd.DataFrame(liquidity, columns=["ticker", "adv"]),
        combined,
    )


# ---------------------------
# 5. Main
# ---------------------------
async def main():
    print("Downloading ticker list...")
    tickers = await get_all_tickers()
    print(f"Found {len(tickers)} active common stocks")

    print("Computing ADV (async, with retries & rate limiting)...")
    liquidity_df, backtest_df = await compute_adv_async(tickers)

    liquidity_df = liquidity_df.sort_values("adv", ascending=False).reset_index(drop=True)

    # Full liquidity table
    liquidity_df.to_parquet("all_liquidity.parquet", index=False)
    print("Saved full liquidity rankings to all_liquidity.parquet")

    # Backtesting dataset
    backtest_df.to_parquet("backtesting_dataset.parquet", index=False)
    print("Saved backtesting dataset to backtesting_dataset.parquet")

    print("\nTop 100 most liquid stocks:")
    print(liquidity_df.head(100))


if __name__ == "__main__":
    asyncio.run(main())
