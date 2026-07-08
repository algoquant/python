# ---------------------------------------------------------
# Download OHLCV data for most liquid ETFs from Tiingo,
# compute average volumes, and save in individual Parquet files.
# ---------------------------------------------------------

import os
import asyncio
import aiohttp
import pandas as pd
import re
from datetime import datetime, timedelta
from functools import reduce
from dotenv import load_dotenv
from tqdm.asyncio import tqdm_asyncio

load_dotenv()

API_KEY = os.getenv("API_KEY", "")
if not API_KEY:
    raise ValueError("Missing API_KEY in environment")

DATA_DIR = os.getenv("ETF_DATA_DIR", "/Users/jerzy/Develop/data/daily/")
os.makedirs(DATA_DIR, exist_ok=True)

LIQUIDITY_PATH = os.getenv("ETF_LIQUIDITY_PATH", "/Users/jerzy/Develop/data/all_liquidity_etf.parquet")
BACKTEST_PATH = os.getenv("ETF_BACKTEST_PATH", "/Users/jerzy/Develop/data/backtesting_dataset_etf.parquet")

BASE_URL = os.getenv("TIINGO_BASE_URL", "https://api.tiingo.com")
FETCH_TIMEOUT_SECONDS = int(os.getenv("TIINGO_FETCH_TIMEOUT_SECONDS", "60"))
FETCH_MAX_RETRIES = int(os.getenv("TIINGO_FETCH_MAX_RETRIES", "5"))
FETCH_BACKOFF = float(os.getenv("TIINGO_FETCH_BACKOFF", "1.5"))
HISTORY_START_DATE = os.getenv("TIINGO_HISTORY_START_DATE", "1900-01-01")
RESAMPLE_FREQ = os.getenv("TIINGO_RESAMPLE_FREQ", "daily")
RANKING_LOOKBACK_DAYS = int(os.getenv("ETF_RANKING_LOOKBACK_DAYS", "365"))
RANKING_BATCH_SIZE = int(os.getenv("ETF_RANKING_BATCH_SIZE", "64"))
DOWNLOAD_BATCH_SIZE = int(os.getenv("ETF_DOWNLOAD_BATCH_SIZE", "64"))
RANKING_PATH = os.getenv("ETF_RANKING_PATH", "/Users/jerzy/Develop/data/etf_candidate_ranking.parquet")

REQUIRED_ETFS = [
    "SPY", "VTI", "QQQ", "VEU", "EEM", "XLY", "XLP", "XLE", "XLF", "XLV",
    "XLI", "XLB", "XLK", "XLU", "VYM", "IVW", "IWB", "IWD", "IWF", "IEF",
    "TLT", "VNQ", "DBC", "GLD", "USO", "VXX", "SVXY", "MTUM", "IVE", "VLUE",
    "QUAL", "VTV", "USMV", "AIEQ", "DYNF",
]

SEARCH_QUERIES = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


class TiingoQuotaError(RuntimeError):
    """Raised when Tiingo daily request quota has been exhausted."""


# ---------------------------------------------------------
# HTTP helper with retry + backoff
# ---------------------------------------------------------
async def fetch_json(session, url, params=None, max_retries=FETCH_MAX_RETRIES, backoff=FETCH_BACKOFF):
    params = params or {}
    params["token"] = API_KEY

    for attempt in range(max_retries):
        try:
            async with session.get(url, params=params, timeout=FETCH_TIMEOUT_SECONDS) as resp:
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


def _normalize_ticker(value: str) -> str:
    return (value or "").strip().upper().replace('"', "")


# ---------------------------------------------------------
# 1. Discover ETF candidate universe from Tiingo search
# ---------------------------------------------------------
async def discover_etf_candidates() -> list[str]:
    url = f"{BASE_URL}/tiingo/utilities/search"
    etfs: set[str] = set()

    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_json(session, url, params={"query": query, "limit": 100})
            for query in SEARCH_QUERIES
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception) or not isinstance(result, list):
            continue

        for row in result:
            ticker = _normalize_ticker(row.get("ticker", ""))
            asset_type = str(row.get("assetType", "")).upper()
            country = str(row.get("countryCode", "")).upper()
            is_active = bool(row.get("isActive", True))

            if asset_type != "ETF":
                continue
            if country and country != "US":
                continue
            if not is_active:
                continue
            if not re.fullmatch(r"[A-Z][A-Z0-9.\-]*", ticker):
                continue

            etfs.add(ticker)

    # Always include required ETFs even if search endpoint misses some.
    etfs.update(_normalize_ticker(t) for t in REQUIRED_ETFS)
    return sorted(etfs)


# ---------------------------------------------------------
# 2. Fetch daily bars for a ticker (full history by default)
# ---------------------------------------------------------
async def get_bars(session, ticker, start_date: str = HISTORY_START_DATE):
    url = f"{BASE_URL}/tiingo/daily/{ticker}/prices"
    params = {
        "startDate": start_date,
        "resampleFreq": RESAMPLE_FREQ,
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

    df["dollar_volume"] = df["close"] * df["volume"]
    df["ticker"] = ticker

    return df[["date", "open", "high", "low", "close", "volume", "dollar_volume", "ticker"]]


# ---------------------------------------------------------
# 3. Compute recent volume for ETF ranking
# ---------------------------------------------------------
async def compute_volume(session, ticker, lookback_days: int = RANKING_LOOKBACK_DAYS):
    start_date = (datetime.utcnow().date() - timedelta(days=lookback_days)).isoformat()
    df = await get_bars(session, ticker, start_date=start_date)
    if df is None or df.empty:
        return None

    return ticker, float(df["dollar_volume"].mean())


# ---------------------------------------------------------
# 4. Worker: fetch full history + save + return dataframe
# ---------------------------------------------------------
async def process_ticker(session, ticker):
    df = await get_bars(session, ticker)
    if df is None or df.empty:
        return None

    volume = df["dollar_volume"].mean()

    # Requested format: TICKER.Field columns with no plain ticker column.
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

    # Save per‑ticker Parquet
    prefixed_df.to_parquet(f"{DATA_DIR}/{ticker}.parquet", index=False)

    return ticker, volume, prefixed_df


# ---------------------------------------------------------
# 5. Rank candidate ETFs by recent volume and select top 100
# ---------------------------------------------------------
async def select_top_100_etfs(candidates: list[str], batch_size: int = RANKING_BATCH_SIZE) -> tuple[list[str], pd.DataFrame]:
    volume_rows: list[tuple[str, float]] = []
    connector = aiohttp.TCPConnector(limit=batch_size)

    async with aiohttp.ClientSession(connector=connector) as session:
        for i in tqdm_asyncio(range(0, len(candidates), batch_size), desc="Ranking batches"):
            batch = candidates[i : i + batch_size]
            tasks = [compute_volume(session, t) for t in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if isinstance(res, Exception) or res is None:
                    continue
                volume_rows.append(res)

    volume_df = pd.DataFrame(volume_rows, columns=["ticker", "volume"]).sort_values("volume", ascending=False)
    if volume_df.empty:
        return [], volume_df

    selected = volume_df["ticker"].head(100).tolist()
    required_set = {_normalize_ticker(t) for t in REQUIRED_ETFS}
    ranked = volume_df["ticker"].tolist()

    # Force required ETFs into final top-100 selection when available.
    for req in REQUIRED_ETFS:
        req = _normalize_ticker(req)
        if req not in ranked or req in selected:
            continue

        # Replace the lowest-ranked non-required ticker.
        for i in range(len(selected) - 1, -1, -1):
            if selected[i] not in required_set:
                selected[i] = req
                break

    selected = list(dict.fromkeys(selected))
    if len(selected) < 100:
        for ticker in ranked:
            if ticker not in selected:
                selected.append(ticker)
            if len(selected) == 100:
                break

    return selected[:100], volume_df


# ---------------------------------------------------------
# 6. Download full OHLCV for selected ETFs
# ---------------------------------------------------------
async def compute_volume(tickers, batch_size=DOWNLOAD_BATCH_SIZE):
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
                ticker, volume, df = res
                liquidity.append((ticker, volume))
                all_prices.append(df)

    # Wide date-joined dataset with one set of TICKER.Field columns per symbol.
    if all_prices:
        combined = reduce(
            lambda left, right: pd.merge(left, right, on="date", how="outer"),
            all_prices,
        ).sort_values("date").reset_index(drop=True)
    else:
        combined = pd.DataFrame()

    return pd.DataFrame(liquidity, columns=["ticker", "volume"]), combined


# ---------------------------------------------------------
# 7. Main
# ---------------------------------------------------------
async def main():
    print("Discovering ETF candidates from Tiingo search...")
    try:
        candidates = await discover_etf_candidates()
    except TiingoQuotaError as exc:
        print(str(exc))
        return
    except Exception as exc:
        print(f"ETF discovery failed: {exc}")
        return

    if not candidates:
        print("No ETF candidates returned. Aborting without writing empty outputs.")
        return

    print(f"Discovered {len(candidates)} ETF candidates")
    print("Ranking ETF candidates by recent volume...")
    selected, ranking_df = await select_top_100_etfs(candidates)

    if not selected:
        print("Unable to rank ETFs from Tiingo data.")
        return

    missing_required = [t for t in REQUIRED_ETFS if _normalize_ticker(t) not in selected]
    if missing_required:
        print(f"Warning: required ETFs unavailable from ranking data: {missing_required}")

    print(f"Selected {len(selected)} ETFs for full OHLCV download")
    print(f"Saving per-ticker full OHLCV files to: {DATA_DIR}")

    print("Downloading all historical bars (async)...")
    liquidity_df, backtest_df = await compute_volume(selected)

    liquidity_df = liquidity_df.sort_values("volume", ascending=False).reset_index(drop=True)

    # Save full liquidity table
    liquidity_df.to_parquet(LIQUIDITY_PATH, index=False)
    print(f"Saved {LIQUIDITY_PATH}")

    # Save combined backtesting dataset
    backtest_df.to_parquet(BACKTEST_PATH, index=False)
    print(f"Saved {BACKTEST_PATH}")

    ranking_df.to_parquet(RANKING_PATH, index=False)
    print(f"Saved {RANKING_PATH}")

    print("\nTop 100 most liquid ETFs in target universe:")
    print(liquidity_df.head(100))


if __name__ == "__main__":
    asyncio.run(main())
