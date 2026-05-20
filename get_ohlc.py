# ---------------------------------------------------------
# Download from Tiingo the OHLCV bars for stocks or ETFs, 
# and save in individual Parquet files.
# Usage: python3 get_ohlc.py stocks | etfs
# ---------------------------------------------------------

import os
import sys
import asyncio
from datetime import date
import aiohttp
import pandas as pd
from tqdm.asyncio import tqdm_asyncio

API_KEY = "d84fc2a9c5bde2d68e33034f65a838092c6b9f10"

BASE_URL = "https://api.tiingo.com"

STOCKS_METADATA = "/Users/jerzy/Develop/data/stock_metadata.csv"
ETFS_METADATA   = "/Users/jerzy/Develop/data/etf_metadata.csv"

STOCKS_DATA_DIR     = "/Users/jerzy/Develop/data/daily/"
ETFS_DATA_DIR       = "/Users/jerzy/Develop/data/daily/"
STOCKS_LIQUIDITY    = "/Users/jerzy/Develop/data/all_liquidity.parquet"
ETFS_LIQUIDITY      = "/Users/jerzy/Develop/data/all_liquidity_etf.parquet"


def _parse_mode() -> str:
    """Accept 'stocks' or 'etfs' as the first CLI argument with partial matching."""
    choices = {"stocks", "etfs"}
    raw = sys.argv[1].lower().strip() if len(sys.argv) > 1 else ""
    if not raw:
        print("Usage: python get_ohlc.py stocks|etfs", file=sys.stderr)
        sys.exit(1)
    matches = [c for c in choices if c.startswith(raw)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous argument {raw!r}. Did you mean: {', '.join(sorted(matches))}?", file=sys.stderr)
        sys.exit(1)
    print(f"Unknown argument {raw!r}. Expected 'stocks' or 'etfs'.", file=sys.stderr)
    sys.exit(1)


def _resolve_paths(mode: str) -> tuple[str, str, str]:
    """Return (metadata_file, data_dir, liquidity_path) for the given mode."""
    if mode == "stocks":
        return STOCKS_METADATA, STOCKS_DATA_DIR, STOCKS_LIQUIDITY
    return ETFS_METADATA, ETFS_DATA_DIR, ETFS_LIQUIDITY


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
# 1. Get all tickers from the appropriate metadata file
# ---------------------------------------------------------
def get_all_tickers(metadata_file: str) -> list[str]:
    if not os.path.exists(metadata_file):
        raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

    metadata_df = pd.read_csv(metadata_file)
    if "ticker" not in metadata_df.columns:
        raise ValueError(f"Expected 'ticker' column in {metadata_file}")

    tickers = (
        metadata_df["ticker"]
        .dropna()
        .astype(str)
        .str.upper()
        .str.strip()
    )
    return list(dict.fromkeys(tickers.tolist()))


# ---------------------------------------------------------
# 2. Fetch ALL daily bars for a ticker
# ---------------------------------------------------------
async def get_all_bars(session, ticker):
    url = f"{BASE_URL}/tiingo/daily/{ticker}/prices"
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

    # Prefer split-adjusted OHLCV when Tiingo provides it.
    adjusted_map = {
        "open": "adjOpen",
        "high": "adjHigh",
        "low": "adjLow",
        "close": "adjClose",
        "volume": "adjVolume",
    }
    for base_col, adj_col in adjusted_map.items():
        if adj_col in df.columns:
            df[base_col] = df[adj_col]

    # Ignore today's partial session and any rows that still lack OHLCV data.
    df = df[pd.to_datetime(df["date"]).dt.date < date.today()]
    df = df.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    if df.empty:
        return None

    df["dollar_volume"] = df["close"] * df["volume"]
    df["ticker"] = ticker

    return df[["date", "open", "high", "low", "close", "volume", "dollar_volume", "ticker"]]


# ---------------------------------------------------------
# 3. Worker: fetch + save + compute volume
# ---------------------------------------------------------
async def process_ticker(session, ticker):
    df = await get_all_bars(session, ticker)
    if df is None or df.empty:
        return None

    volume = df["dollar_volume"].mean()

    # Output format requested: TICKER.Field columns and no plain ticker column.
    prefixed_df = df[["date", "open", "high", "low", "close", "volume", "dollar_volume"]].rename(
        columns={
            "open": f"{ticker}.Open",
            "high": f"{ticker}.High",
            "low": f"{ticker}.Low",
            "close": f"{ticker}.Close",
            "volume": f"{ticker}.Volume",
            "dollar_volume": f"{ticker}.VolumeD",
        }
    )

    # Save per-ticker Parquet (data_dir injected via closure from main)
    prefixed_df.to_parquet(f"{_CURRENT_DATA_DIR}/{ticker}.parquet", index=False)

    return ticker, volume, prefixed_df


# ---------------------------------------------------------
# 4. Async orchestration with batching + tqdm
# ---------------------------------------------------------
async def compute_volume(tickers, batch_size=64):
    liquidity = []

    connector = aiohttp.TCPConnector(limit=batch_size)

    async with aiohttp.ClientSession(connector=connector) as session:
        for i in tqdm_asyncio(range(0, len(tickers), batch_size), desc="Batches"):
            batch = tickers[i : i + batch_size]
            tasks = [process_ticker(session, t) for t in batch]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if isinstance(res, Exception) or res is None:
                    continue
                ticker, volume, df = res
                liquidity.append((ticker, volume))

    return pd.DataFrame(liquidity, columns=["ticker", "volume"])


# ---------------------------------------------------------
# 5. Main
# ---------------------------------------------------------

# Module-level variable set by main() so process_ticker can resolve the data dir.
_CURRENT_DATA_DIR: str = STOCKS_DATA_DIR


async def main():
    global _CURRENT_DATA_DIR

    mode = _parse_mode()
    metadata_file, data_dir, liquidity_path = _resolve_paths(mode)
    _CURRENT_DATA_DIR = data_dir
    os.makedirs(data_dir, exist_ok=True)

    label = "stocks" if mode == "stocks" else "ETFs"
    print(f"Mode: {mode}  |  Metadata: {metadata_file}")

    try:
        tickers = get_all_tickers(metadata_file)
    except Exception as exc:
        print(f"Ticker load failed: {exc}")
        return

    if not tickers:
        print("No tickers returned. Aborting without writing empty outputs.")
        return

    print(f"Found {len(tickers)} {label}")
    print(f"Saving per-ticker OHLCV Parquets to: {data_dir}")

    print("Downloading all historical bars (async)...")
    liquidity_df = await compute_volume(tickers)

    liquidity_df = liquidity_df.sort_values("volume", ascending=False).reset_index(drop=True)

    liquidity_df.to_parquet(liquidity_path, index=False)
    print(f"Saved {liquidity_path}")

    print(f"\nTop 20 most liquid {label}:")
    print(liquidity_df.head(20))


if __name__ == "__main__":
    asyncio.run(main())
