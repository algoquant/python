# ---------------------------------------------------------
# Merge the stock liquidity data with Tiingo classification metadata 
# and export CSV.
# ---------------------------------------------------------

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import logging
import time

import aiohttp
import pandas as pd

try:
    import yfinance as yf
    # Suppress yfinance's verbose 404/401 noise for missing/delisted tickers.
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
except ImportError:
    yf = None

API_KEY = "d84fc2a9c5bde2d68e33034f65a838092c6b9f10"

INPUT_FILE = Path("/Users/jerzy/Develop/data/all_liquidity.parquet")
OUTPUT_FILE = Path("/Users/jerzy/Develop/data/stock_metadata.csv")
YAHOO_CACHE_FILE = Path("/Users/jerzy/Develop/data/yahoo_sector_cache.parquet")

BASE_URL = "https://api.tiingo.com"
UNAVAILABLE_FREE_TEXT = "field not available for free/evaluation"
OTC_MARKERS = {
    "OTC",
    "OTCBB",
    "OTCQB",
    "OTCQX",
    "OTCM",
    "OTCMKTS",
    "PINK",
    "GREY",
}


class TiingoQuotaError(RuntimeError):
    """Raised when Tiingo daily request quota has been exhausted."""


def _is_otc_exchange(exchange_code: str) -> bool:
    exchange = (exchange_code or "").upper().strip()
    if not exchange:
        return False
    if exchange in OTC_MARKERS:
        return True
    return any(marker in exchange for marker in OTC_MARKERS)


async def get_ticker_profile(session: aiohttp.ClientSession, ticker: str) -> dict:
    """Resolve asset type and exchange so callers can filter Tiingo symbols consistently."""
    search_url = f"{BASE_URL}/tiingo/utilities/search"
    daily_url = f"{BASE_URL}/tiingo/daily/{ticker}"

    search_data = await fetch_json(session, search_url, params={"query": ticker, "limit": 10})
    asset_type = ""
    country_code = ""
    is_active = True

    if isinstance(search_data, list):
        exact = None
        for row in search_data:
            if (row.get("ticker") or "").upper().strip() == ticker:
                exact = row
                break
        if exact is None and search_data:
            exact = search_data[0]

        if exact:
            asset_type = str(exact.get("assetType", "")).upper().strip()
            country_code = str(exact.get("countryCode", "")).upper().strip()
            is_active = bool(exact.get("isActive", True))

    daily_meta = await fetch_json(session, daily_url, params={})
    exchange_code = ""
    if isinstance(daily_meta, dict):
        exchange_code = str(daily_meta.get("exchangeCode", "")).upper().strip()

    return {
        "asset_type": asset_type,
        "country_code": country_code,
        "is_active": is_active,
        "exchange_code": exchange_code,
        "is_otc": _is_otc_exchange(exchange_code),
    }


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


async def exclude_otc_stocks(liquidity_df: pd.DataFrame, concurrency: int = 40) -> pd.DataFrame:
    """Exclude tickers whose Tiingo exchangeCode indicates OTC markets."""
    tickers = sorted(set(liquidity_df["ticker"].dropna().astype(str).str.upper().str.strip()))
    if not tickers:
        return liquidity_df

    connector = aiohttp.TCPConnector(limit=concurrency)
    sem = asyncio.Semaphore(concurrency)

    async def _bounded_fetch(session: aiohttp.ClientSession, ticker: str) -> tuple[str, str]:
        async with sem:
            profile = await get_ticker_profile(session, ticker)
            if not profile:
                return ticker, ""
            return ticker, "" if profile["is_otc"] else profile["exchange_code"]

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [_bounded_fetch(session, ticker) for ticker in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    otc_tickers: set[str] = set()
    for item in results:
        if isinstance(item, Exception):
            continue
        ticker, exchange_code = item
        if _is_otc_exchange(exchange_code):
            otc_tickers.add(ticker)

    if not otc_tickers:
        print("OTC filter: no OTC tickers detected.")
        return liquidity_df

    filtered = liquidity_df[~liquidity_df["ticker"].isin(otc_tickers)].copy()
    print(f"OTC filter: removed {len(otc_tickers)} tickers; {len(filtered)} rows remain.")
    return filtered


async def fetch_tiingo_metadata() -> pd.DataFrame:
    """Download Tiingo fundamentals metadata and return as DataFrame."""
    url = f"{BASE_URL}/tiingo/fundamentals/meta"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params={"token": API_KEY}, timeout=90) as resp:
                if resp.status == 429:
                    detail = await resp.text()
                    raise TiingoQuotaError(
                        "Tiingo API quota exceeded while loading ticker metadata. "
                        f"Response: {detail}"
                    )
                resp.raise_for_status()
                data = await resp.json()
        except TiingoQuotaError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to load ticker metadata from Tiingo: {exc}") from exc

    if not isinstance(data, list) or not data:
        raise RuntimeError("Tiingo metadata response was empty or not a list.")

    md = pd.DataFrame(data)
    if "ticker" not in md.columns:
        raise RuntimeError("Tiingo metadata did not include a 'ticker' column.")

    md["ticker"] = md["ticker"].astype(str).str.upper().str.strip()
    md = md[md["ticker"] != ""]
    return md


def load_liquidity() -> pd.DataFrame:
    """Load liquidity parquet and normalize ticker field."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Liquidity file not found: {INPUT_FILE}")

    df = pd.read_parquet(INPUT_FILE)
    if "ticker" not in df.columns:
        raise ValueError(f"Expected 'ticker' column in {INPUT_FILE}")

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    return df


def _clean_classification_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize empty/redacted classification fields to NA."""
    cleaned = df.copy()
    classification_cols = ["sector", "industry", "sicCode", "sicSector", "sicIndustry"]

    for col in classification_cols:
        if col not in cleaned.columns:
            cleaned[col] = pd.NA
            continue

        s = cleaned[col].astype("string")
        redacted = s.str.lower().str.contains(UNAVAILABLE_FREE_TEXT, na=False)
        empty = s.str.strip().eq("")
        cleaned.loc[redacted | empty, col] = pd.NA
    return cleaned


def _fetch_yahoo_sector_industry(ticker: str) -> dict:
    """Fetch sector/industry from Yahoo Finance with retry on rate-limit."""
    if yf is None:
        return {"ticker": ticker, "sector_yahoo": None, "industry_yahoo": None}

    max_attempts = 4
    for attempt in range(max_attempts):
        try:
            info = yf.Ticker(ticker).get_info()
            if not isinstance(info, dict):
                info = {}
            break
        except Exception as exc:
            # Rate limited — back off exponentially before retrying.
            if attempt < max_attempts - 1 and "rate" in str(exc).lower():
                time.sleep(2 ** attempt * 2)  # 2s, 4s, 8s
                continue
            info = {}
            break
    else:
        info = {}

    time.sleep(0.2)  # Polite delay between requests
    sector = info.get("sector") or info.get("sectorDisp")
    industry = info.get("industry") or info.get("industryDisp")
    return {
        "ticker": ticker,
        "sector_yahoo": sector,
        "industry_yahoo": industry,
    }


def _load_yahoo_cache() -> pd.DataFrame:
    """Load previously fetched Yahoo sector/industry results from local cache."""
    if YAHOO_CACHE_FILE.exists():
        return pd.read_parquet(YAHOO_CACHE_FILE)
    return pd.DataFrame(columns=["ticker", "sector_yahoo", "industry_yahoo"])


def _save_yahoo_cache(df: pd.DataFrame) -> None:
    """Persist Yahoo results cache to disk."""
    YAHOO_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(YAHOO_CACHE_FILE, index=False)


def backfill_sector_industry_from_yahoo(
    df: pd.DataFrame,
    max_workers: int = 4,
    max_fetch_per_batch: int = 300,
    pause_seconds: float = 5.0,
    progress_every: int = 25,
) -> pd.DataFrame:
    """Fill missing sector/industry values using Yahoo Finance until all are processed."""
    enriched = _clean_classification_fields(df)

    missing_mask = enriched["sector"].isna() | enriched["industry"].isna()
    missing_tickers = sorted(set(enriched.loc[missing_mask, "ticker"].dropna().tolist()))

    if not missing_tickers:
        enriched["classification_source"] = "tiingo"
        return enriched

    if yf is None:
        print("yfinance not installed; skipping Yahoo backfill for missing sector/industry.")
        enriched["classification_source"] = "tiingo"
        return enriched

    # Load existing cache and keep looping until all missing tickers are attempted.
    cache_df = _load_yahoo_cache()
    total_missing = len(missing_tickers)
    print(f"Yahoo backfill target tickers: {total_missing}")

    batch_num = 0
    while True:
        cached_tickers = set(cache_df["ticker"].tolist())
        to_fetch_all = [t for t in missing_tickers if t not in cached_tickers]
        remaining = len(to_fetch_all)

        if remaining == 0:
            print("Yahoo backfill complete: all missing tickers have been processed.")
            break

        batch_num += 1
        to_fetch = to_fetch_all[:max_fetch_per_batch]
        print(
            f"Batch {batch_num}: fetching {len(to_fetch)} tickers "
            f"({remaining} remaining of {total_missing})"
        )

        newly_fetched = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_yahoo_sector_industry, t): t for t in to_fetch}
            completed = 0
            for fut in as_completed(futures):
                newly_fetched.append(fut.result())
                completed += 1
                if completed % progress_every == 0 or completed == len(to_fetch):
                    print(f"  Batch progress: {completed}/{len(to_fetch)}")

        new_df = pd.DataFrame(newly_fetched)
        cache_df = pd.concat([cache_df, new_df], ignore_index=True).drop_duplicates("ticker")
        _save_yahoo_cache(cache_df)

        processed = total_missing - len([t for t in missing_tickers if t not in set(cache_df["ticker"].tolist())])
        pct = (processed / total_missing) * 100 if total_missing else 100.0
        print(
            f"Updated cache: {YAHOO_CACHE_FILE} | "
            f"processed {processed}/{total_missing} ({pct:.1f}%)"
        )

        # Pause between batches to reduce rate limiting pressure.
        if pause_seconds > 0:
            print(f"Pausing {pause_seconds:.1f}s before next batch...")
            time.sleep(pause_seconds)

    yahoo_df = cache_df[cache_df["ticker"].isin(missing_tickers)].copy()

    if yahoo_df.empty:
        enriched["classification_source"] = "tiingo"
        return enriched

    before_sector_missing = enriched["sector"].isna()
    before_industry_missing = enriched["industry"].isna()

    enriched = enriched.merge(yahoo_df, on="ticker", how="left")
    enriched["sector"] = enriched["sector"].combine_first(enriched["sector_yahoo"])
    enriched["industry"] = enriched["industry"].combine_first(enriched["industry_yahoo"])

    yahoo_filled = (
        (before_sector_missing & enriched["sector_yahoo"].notna())
        | (before_industry_missing & enriched["industry_yahoo"].notna())
    )
    enriched["classification_source"] = "tiingo"
    enriched.loc[yahoo_filled, "classification_source"] = "yahoo"
    return enriched


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build stock_metadata.csv from liquidity + Tiingo + Yahoo fallback")
    parser.add_argument(
        "--max-yahoo-batch",
        type=int,
        default=300,
        help="Maximum number of uncached Yahoo tickers to fetch per batch.",
    )
    parser.add_argument(
        "--yahoo-workers",
        type=int,
        default=4,
        help="Number of Yahoo worker threads.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=5.0,
        help="Pause duration between Yahoo batches.",
    )
    return parser.parse_args()


def _pick_liquidity_sort_column(df: pd.DataFrame) -> str | None:
    """Pick the best available liquidity column for descending sort."""
    for col in ("volume", "adv", "avg_dollar_volume", "dollar_volume"):
        if col in df.columns:
            return col
    return None


async def main(max_yahoo_batch: int, yahoo_workers: int, pause_seconds: float) -> None:
    print(f"Loading liquidity data: {INPUT_FILE}")
    liquidity_df = load_liquidity()
    liquidity_df = await exclude_otc_stocks(liquidity_df)

    print("Downloading Tiingo classification metadata...")
    metadata_df = pd.DataFrame(columns=["ticker"])
    try:
        metadata_df = await fetch_tiingo_metadata()
    except TiingoQuotaError as exc:
        print(f"Tiingo quota warning: {exc}")
        print("Continuing with Yahoo fallback for sector/industry.")
    except Exception as exc:
        print(f"Tiingo metadata warning: {exc}")
        print("Continuing with Yahoo fallback for sector/industry.")

    tickers = set(liquidity_df["ticker"].dropna().tolist())
    metadata_subset = metadata_df[metadata_df["ticker"].isin(tickers)].copy()

    merged = liquidity_df.merge(metadata_subset, on="ticker", how="left")
    merged = backfill_sector_industry_from_yahoo(
        merged,
        max_workers=yahoo_workers,
        max_fetch_per_batch=max_yahoo_batch,
        pause_seconds=pause_seconds,
    )
    sort_col = _pick_liquidity_sort_column(merged)
    if sort_col is not None:
        merged = merged.sort_values(sort_col, ascending=False).reset_index(drop=True)
    else:
        merged = merged.reset_index(drop=True)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT_FILE, index=False)

    matched = merged["name"].notna().sum() if "name" in merged.columns else 0
    sector_count = merged["sector"].notna().sum() if "sector" in merged.columns else 0
    industry_count = merged["industry"].notna().sum() if "industry" in merged.columns else 0
    print(f"Saved merged stock data: {OUTPUT_FILE}")
    print(f"Rows: {len(merged)} | Metadata matched: {matched}")
    print(f"Sector filled: {sector_count} | Industry filled: {industry_count}")


if __name__ == "__main__":
    args = parse_arguments()
    asyncio.run(
        main(
            max_yahoo_batch=args.max_yahoo_batch,
            yahoo_workers=args.yahoo_workers,
            pause_seconds=args.pause_seconds,
        )
    )
