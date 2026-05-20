# ---------------------------------------------------------
# Download OHLCV data for all common stocks from Polygon, 
# compute average volumes, and save in individual Parquet files.
# ---------------------------------------------------------

import os
import asyncio
import aiohttp
import pandas as pd
import re
from tqdm.asyncio import tqdm_asyncio

# Polygon API key (get your own free key at https://polygon.io/)
API_KEY = "0Q2f8j8CwAbdY4M8VYt_8pwdP0V4TunxbvRVC_"

DATA_DIR = "/Users/jerzy/Develop/data/daily/"
os.makedirs(DATA_DIR, exist_ok=True)

LIQUIDITY_PATH = "/Users/jerzy/Develop/data/all_liquidity.parquet"
BACKTEST_PATH = "/Users/jerzy/Develop/data/backtesting_dataset.parquet"

BASE_URL = "https://api.polygon.io"


class PolygonQuotaError(RuntimeError):
    """Raised when Polygon daily request quota has been exhausted."""


# ---------------------------------------------------------
# HTTP helper with retry + backoff
# ---------------------------------------------------------
async def fetch_json(session, url, params=None, max_retries=5, backoff=1.5):
    params = params or {}
    params["token"] = API_KEY

    for attempt in range(max_retries):
        try:
            async with session.get(url, params=params, timeout=60) as resp:
                if resp.status in (429, 503):
                    await asyncio.sleep(backoff ** attempt)
                    continue
                resp.raise_for_status()
                return await resp.json()
        except Exception:
            if attempt == max_retries - 1:
                return None
            await asyncio.sleep(backoff ** attempt)

    return None


# ---------------------------------------------------------
# 1. Get all Polygon tickers
# ---------------------------------------------------------
async def get_all_tickers():
    # Polygon /stocks/list endpoint returns 404; use fundamentals metadata.
    url = f"{BASE_URL}/stocks/meta"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params={"token": API_KEY}, timeout=60) as resp:
                if resp.status == 429:
                    detail = await resp.text()
                    raise PolygonQuotaError(
                        "Polygon API quota exceeded while loading ticker metadata. "
                        f"Response: {detail}"
                    )
                resp.raise_for_status()
                data = await resp.json()
        except PolygonQuotaError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to load ticker metadata from Polygon: {exc}") from exc

        tickers = []
        for row in data:
            ticker = (row.get("ticker") or "").strip().upper()

            # Heuristic for common stocks:
            # - active listing
            # - not ADR
            # - has sector + industry classification
            # - valid symbol format
            if not ticker:
                continue
            if not row.get("isActive", False):
                continue
            if row.get("isADR", False):
                continue
            if not row.get("sector") or not row.get("industry"):
                continue
            if not re.fullmatch(r"[A-Z][A-Z0-9.\-]*", ticker):
                continue

            tickers.append(ticker)

        # Stable order + uniqueness
        return sorted(set(tickers))


# ---------------------------------------------------------
# 2. Fetch ALL daily bars for a ticker
# ---------------------------------------------------------
async def get_all_bars(session, ticker):
    url = f"{BASE_URL}/stocks/{ticker}/prices"
    params = {
        "startDate": "1900-01-01",
        "resampleFreq": "daily",
    }

    data = await fetch_json(session, url, params=params)
    if not data:
        return None

    df = pd.DataFrame(data)
    if df.empty:
        return None

    df["date"] = pd.to_datetime(df["date"])
    if not {"open", "high", "low", "close", "volume"}.issubset(df.columns):
        return None

    df["dollar_volume"] = df["close"] * df["volume"]
    df["ticker"] = ticker

    return df[["date", "open", "high", "low", "close", "volume", "dollar_volume", "ticker"]]


# ---------------------------------------------------------
# 3. Worker: fetch + save + compute ADV
# ---------------------------------------------------------
async def process_ticker(session, ticker):
    df = await get_all_bars(session, ticker)
    if df is None or df.empty:
        return None

    # Save per‑ticker Parquet
    df.to_parquet(f"{DATA_DIR}/{ticker}.parquet", index=False)

    adv = df["dollar_volume"].mean()
    return ticker, adv, df


# ---------------------------------------------------------
# 4. Async orchestration with batching + tqdm
# ---------------------------------------------------------
async def compute_adv_async(tickers, batch_size=64):
    liquidity = []
    all_prices = []

    connector = aiohttp.TCPConnector(limit=batch_size)

    async with aiohttp.ClientSession(connector=connector) as session:
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

    combined = pd.concat(all_prices, ignore_index=True) if all_prices else pd.DataFrame()
    return pd.DataFrame(liquidity, columns=["ticker", "adv"]), combined


# ---------------------------------------------------------
# 5. Main
# ---------------------------------------------------------
async def main():
    print("Downloading Polygon ticker list...")
    try:
        tickers = await get_all_tickers()
    except PolygonQuotaError as exc:
        print(str(exc))
        return
    except Exception as exc:
        print(f"Ticker load failed: {exc}")
        return

    if not tickers:
        print("No tickers returned. Aborting without writing empty outputs.")
        return

    print(f"Found {len(tickers)} common stocks")
    print(f"Saving per-ticker full OHLCV files to: {DATA_DIR}")

    print("Downloading all historical bars (async)...")
    liquidity_df, backtest_df = await compute_adv_async(tickers)

    liquidity_df = liquidity_df.sort_values("adv", ascending=False).reset_index(drop=True)

    # Save full liquidity table
    liquidity_df.to_parquet(LIQUIDITY_PATH, index=False)
    print(f"Saved {LIQUIDITY_PATH}")

    # Save combined backtesting dataset
    backtest_df.to_parquet(BACKTEST_PATH, index=False)
    print(f"Saved {BACKTEST_PATH}")

    print("\nTop 100 most liquid stocks:")
    print(liquidity_df.head(100))


if __name__ == "__main__":
    asyncio.run(main())
