"""Reusable security-metadata loading and enrichment helpers."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from pathlib import Path
import time
from typing import Any

import aiohttp
import pandas as pd

try:
    import yfinance as yf

    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
except ImportError:
    yf = None


UNAVAILABLE_FREE_TEXT = "field not available for free/evaluation"
CLASSIFICATION_COLUMNS = ("sector", "industry", "sicCode", "sicSector", "sicIndustry")
YAHOO_CACHE_COLUMNS = ("ticker", "sector_yahoo", "industry_yahoo", "quote_type_yahoo")
ETF_DETAIL_COLUMNS = (
    "etf_name",
    "category",
    "net_assets",
    "beta_5y",
    "sharpe_ratio",
    "treynor_ratio",
)
OTC_MARKERS = frozenset(
    {
        "OTC",
        "OTCBB",
        "OTCQB",
        "OTCQX",
        "OTCM",
        "OTCMKTS",
        "PINK",
        "GREY",
    }
)


class TiingoQuotaError(RuntimeError):
    """Indicate that Tiingo rejected a metadata request due to quota limits."""


def normalize_ticker_column(df: pd.DataFrame, column: str = "ticker") -> pd.DataFrame:
    """Return a copy with a required ticker column normalized to uppercase."""
    if column not in df.columns:
        raise ValueError(f"Expected '{column}' column")

    normalized = df.copy()
    normalized[column] = normalized[column].astype(str).str.upper().str.strip()
    return normalized


def load_normalized_parquet(path: Path, ticker_column: str = "ticker") -> pd.DataFrame:
    """Load a Parquet table and normalize its required ticker column."""
    if not path.exists():
        raise FileNotFoundError(f"Parquet file not found: {path}")

    try:
        return normalize_ticker_column(pd.read_parquet(path), ticker_column)
    except ValueError as exc:
        raise ValueError(f"Expected '{ticker_column}' column in {path}") from exc


def is_otc_exchange(exchange_code: str) -> bool:
    """Return whether an exchange code contains a recognized OTC marker."""
    exchange = str(exchange_code or "").upper().strip()
    return bool(exchange) and (
        exchange in OTC_MARKERS or any(marker in exchange for marker in OTC_MARKERS)
    )


async def fetch_tiingo_json(
    session: aiohttp.ClientSession,
    url: str,
    api_key: str,
    params: dict[str, Any] | None = None,
    max_retries: int = 5,
    backoff: float = 1.5,
    timeout_seconds: int = 60,
    raise_on_failure: bool = False,
) -> Any | None:
    """Fetch authenticated Tiingo JSON, retrying transient failures."""
    request_params = dict(params or {})
    request_headers = {"Authorization": f"Token {api_key}"}

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            async with session.get(
                url,
                params=request_params,
                headers=request_headers,
                timeout=timeout_seconds,
            ) as response:
                if response.status in (429, 503):
                    last_error = RuntimeError(
                        f"Tiingo request failed with HTTP {response.status}"
                    )
                    await asyncio.sleep(backoff**attempt)
                    continue
                response.raise_for_status()
                return await response.json()
        except Exception as exc:
            last_error = exc
            if attempt == max_retries - 1:
                break
            await asyncio.sleep(backoff**attempt)

    if raise_on_failure and last_error is not None:
        raise RuntimeError(f"Tiingo request failed: {last_error}") from last_error
    return None


async def get_tiingo_ticker_profile(
    session: aiohttp.ClientSession,
    ticker: str,
    api_key: str,
    base_url: str,
) -> dict[str, Any]:
    """Fetch searchable attributes and exchange metadata for one ticker."""
    search_data = await fetch_tiingo_json(
        session,
        f"{base_url}/tiingo/utilities/search",
        api_key,
        params={"query": ticker, "limit": 10},
    )
    asset_type = ""
    country_code = ""
    is_active = True

    if isinstance(search_data, list):
        exact = next(
            (
                row
                for row in search_data
                if str(row.get("ticker") or "").upper().strip() == ticker
            ),
            search_data[0] if search_data else None,
        )
        if exact:
            asset_type = str(exact.get("assetType", "")).upper().strip()
            country_code = str(exact.get("countryCode", "")).upper().strip()
            is_active = bool(exact.get("isActive", True))

    daily_metadata = await fetch_tiingo_json(
        session,
        f"{base_url}/tiingo/daily/{ticker}",
        api_key,
    )
    exchange_code = ""
    if isinstance(daily_metadata, dict):
        exchange_code = str(daily_metadata.get("exchangeCode", "")).upper().strip()

    return {
        "asset_type": asset_type,
        "country_code": country_code,
        "is_active": is_active,
        "exchange_code": exchange_code,
        "is_otc": is_otc_exchange(exchange_code),
    }


async def exclude_otc_stocks(
    liquidity_df: pd.DataFrame,
    api_key: str,
    base_url: str,
    concurrency: int = 40,
) -> pd.DataFrame:
    """Remove rows whose Tiingo ticker profile identifies an OTC exchange."""
    tickers = sorted(set(liquidity_df["ticker"].dropna().astype(str).str.upper().str.strip()))
    if not tickers:
        return liquidity_df

    connector = aiohttp.TCPConnector(limit=concurrency)
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_fetch(
        session: aiohttp.ClientSession,
        ticker: str,
    ) -> tuple[str, bool]:
        async with semaphore:
            profile = await get_tiingo_ticker_profile(session, ticker, api_key, base_url)
            return ticker, bool(profile.get("is_otc", False))

    async with aiohttp.ClientSession(connector=connector) as session:
        results = await asyncio.gather(
            *(bounded_fetch(session, ticker) for ticker in tickers),
            return_exceptions=True,
        )

    otc_tickers = {
        ticker
        for result in results
        if not isinstance(result, BaseException)
        for ticker, is_otc in [result]
        if is_otc
    }
    if not otc_tickers:
        print("OTC filter: no OTC tickers detected.")
        return liquidity_df

    filtered = liquidity_df[~liquidity_df["ticker"].isin(otc_tickers)].copy()
    print(f"OTC filter: removed {len(otc_tickers)} tickers; {len(filtered)} rows remain.")
    return filtered


async def fetch_tiingo_metadata(api_key: str, base_url: str) -> pd.DataFrame:
    """Download and normalize Tiingo's fundamentals metadata catalog."""
    url = f"{base_url}/tiingo/fundamentals/meta"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params={"token": api_key}, timeout=90) as response:
                if response.status == 429:
                    detail = await response.text()
                    raise TiingoQuotaError(
                        "Tiingo API quota exceeded while loading ticker metadata. "
                        f"Response: {detail}"
                    )
                response.raise_for_status()
                data = await response.json()
        except TiingoQuotaError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to load ticker metadata from Tiingo: {exc}") from exc

    if not isinstance(data, list) or not data:
        raise RuntimeError("Tiingo metadata response was empty or not a list.")

    metadata = pd.DataFrame(data)
    try:
        metadata = normalize_ticker_column(metadata)
    except ValueError as exc:
        raise RuntimeError("Tiingo metadata did not include a 'ticker' column.") from exc
    return metadata[metadata["ticker"] != ""]


def clean_classification_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with absent, blank, and redacted classifications set to NA."""
    cleaned = df.copy()
    for column in CLASSIFICATION_COLUMNS:
        if column not in cleaned.columns:
            cleaned[column] = pd.NA
            continue

        values = cleaned[column].astype("string")
        redacted = values.str.lower().str.contains(UNAVAILABLE_FREE_TEXT, na=False)
        empty = values.str.strip().eq("")
        cleaned.loc[redacted | empty, column] = pd.NA
    return cleaned


def fetch_yahoo_sector_industry(ticker: str) -> dict[str, str | None]:
    """Fetch sector, industry, and quote type from Yahoo with rate-limit retries."""
    if yf is None:
        return {
            "ticker": ticker,
            "sector_yahoo": None,
            "industry_yahoo": None,
            "quote_type_yahoo": None,
        }

    info: dict[str, Any] = {}
    quote_type = None
    for attempt in range(4):
        try:
            ticker_object = yf.Ticker(ticker)
            try:
                fast_info = ticker_object.fast_info
                quote_type = getattr(fast_info, "quote_type", None)
                if quote_type is None and isinstance(fast_info, dict):
                    quote_type = fast_info.get("quoteType")
            except Exception:
                quote_type = None

            response = ticker_object.get_info()
            info = response if isinstance(response, dict) else {}
            quote_type = quote_type or info.get("quoteType")
            break
        except Exception as exc:
            if attempt < 3 and "rate" in str(exc).lower():
                time.sleep(2**attempt * 2)
                continue
            break

    time.sleep(0.2)
    return {
        "ticker": ticker,
        "sector_yahoo": info.get("sector") or info.get("sectorDisp"),
        "industry_yahoo": info.get("industry") or info.get("industryDisp"),
        "quote_type_yahoo": quote_type,
    }


def load_yahoo_cache(cache_file: Path) -> pd.DataFrame:
    """Load and normalize the shared Yahoo classification and quote-type cache."""
    if not cache_file.exists():
        return pd.DataFrame(columns=YAHOO_CACHE_COLUMNS)

    cache_df = pd.read_parquet(cache_file)
    for column in YAHOO_CACHE_COLUMNS:
        if column not in cache_df.columns:
            cache_df[column] = pd.NA
    cache_df = normalize_ticker_column(cache_df)
    quote_types = cache_df["quote_type_yahoo"].astype("string").str.strip()
    none_like = quote_types.str.lower().isin(("", "none", "nan", "null", "na", "<na>"))
    cache_df.loc[none_like, "quote_type_yahoo"] = pd.NA
    return cache_df[list(YAHOO_CACHE_COLUMNS)]


def save_yahoo_cache(df: pd.DataFrame, cache_file: Path) -> None:
    """Replace the Yahoo classification Parquet cache."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_file, index=False)


def backfill_sector_industry_from_yahoo(
    df: pd.DataFrame,
    cache_file: Path,
    max_workers: int = 4,
    max_fetch_per_batch: int = 300,
    pause_seconds: float = 5.0,
    progress_every: int = 25,
) -> pd.DataFrame:
    """Fill missing classifications from Yahoo and persist attempted lookups."""
    if max_workers < 1 or max_fetch_per_batch < 1 or progress_every < 1:
        raise ValueError("Yahoo worker, batch, and progress values must be positive")

    enriched = clean_classification_fields(df)
    missing_mask = enriched["sector"].isna() | enriched["industry"].isna()
    missing_tickers = sorted(set(enriched.loc[missing_mask, "ticker"].dropna().tolist()))

    if not missing_tickers:
        enriched["classification_source"] = "tiingo"
        return enriched
    if yf is None:
        print("yfinance not installed; skipping Yahoo backfill for missing sector/industry.")
        enriched["classification_source"] = "tiingo"
        return enriched

    cache_df = load_yahoo_cache(cache_file)
    total_missing = len(missing_tickers)
    print(f"Yahoo backfill target tickers: {total_missing}")

    batch_number = 0
    while True:
        cached_tickers = set(cache_df["ticker"].tolist())
        remaining_tickers = [ticker for ticker in missing_tickers if ticker not in cached_tickers]
        if not remaining_tickers:
            print("Yahoo backfill complete: all missing tickers have been processed.")
            break

        batch_number += 1
        to_fetch = remaining_tickers[:max_fetch_per_batch]
        print(
            f"Batch {batch_number}: fetching {len(to_fetch)} tickers "
            f"({len(remaining_tickers)} remaining of {total_missing})"
        )

        newly_fetched = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(fetch_yahoo_sector_industry, ticker): ticker
                for ticker in to_fetch
            }
            for completed, future in enumerate(as_completed(futures), start=1):
                newly_fetched.append(future.result())
                if completed % progress_every == 0 or completed == len(to_fetch):
                    print(f"  Batch progress: {completed}/{len(to_fetch)}")

        cache_df = pd.concat(
            [cache_df, pd.DataFrame(newly_fetched)],
            ignore_index=True,
        ).drop_duplicates("ticker")
        save_yahoo_cache(cache_df, cache_file)

        cached_tickers = set(cache_df["ticker"].tolist())
        processed = total_missing - sum(ticker not in cached_tickers for ticker in missing_tickers)
        percentage = processed / total_missing * 100 if total_missing else 100.0
        print(
            f"Updated cache: {cache_file} | "
            f"processed {processed}/{total_missing} ({percentage:.1f}%)"
        )

        if pause_seconds > 0 and processed < total_missing:
            print(f"Pausing {pause_seconds:.1f}s before next batch...")
            time.sleep(pause_seconds)

    yahoo_df = cache_df[cache_df["ticker"].isin(missing_tickers)].copy()
    if yahoo_df.empty:
        enriched["classification_source"] = "tiingo"
        return enriched

    enriched = enriched.merge(yahoo_df, on="ticker", how="left")
    sector_missing = enriched["sector"].isna()
    industry_missing = enriched["industry"].isna()
    yahoo_filled = (
        (sector_missing & enriched["sector_yahoo"].notna())
        | (industry_missing & enriched["industry_yahoo"].notna())
    )
    enriched["sector"] = enriched["sector"].combine_first(enriched["sector_yahoo"])
    enriched["industry"] = enriched["industry"].combine_first(enriched["industry_yahoo"])
    enriched["classification_source"] = "tiingo"
    enriched.loc[yahoo_filled, "classification_source"] = "yahoo"
    return enriched


def fetch_yahoo_quote_type(ticker: str) -> dict[str, str | None]:
    """Fetch Yahoo's instrument type for one ticker with rate-limit retries."""
    if yf is None:
        return {"ticker": ticker, "quote_type_yahoo": None}

    quote_type = None
    for attempt in range(4):
        try:
            ticker_object = yf.Ticker(ticker)
            fast_info = ticker_object.fast_info
            quote_type = getattr(fast_info, "quote_type", None)
            if quote_type is None and isinstance(fast_info, dict):
                quote_type = fast_info.get("quoteType")
            if not quote_type:
                info = ticker_object.get_info()
                quote_type = info.get("quoteType") if isinstance(info, dict) else None
            break
        except Exception as exc:
            if attempt < 3 and "rate" in str(exc).lower():
                time.sleep(2**attempt * 2)
                continue
            break

    time.sleep(0.1)
    return {"ticker": ticker, "quote_type_yahoo": quote_type}


def filter_to_etfs_using_yahoo_quote_type(
    df: pd.DataFrame,
    cache_file: Path,
    max_workers: int = 8,
    max_fetch_per_batch: int = 500,
    pause_seconds: float = 3.0,
    progress_every: int = 50,
) -> pd.DataFrame:
    """Return only rows Yahoo identifies as exchange-traded funds.

    Cached quote types are reused. Missing quote types are attempted once per
    run in bounded thread-pool batches and persisted to the shared Yahoo cache.
    Unknown and non-ETF instruments are excluded from the returned DataFrame.
    """
    if yf is None:
        raise RuntimeError(
            "yfinance is required to enforce ETF-only output. Install yfinance and rerun."
        )
    if max_workers < 1 or max_fetch_per_batch < 1 or progress_every < 1:
        raise ValueError("Yahoo worker, batch, and progress values must be positive")

    filtered = normalize_ticker_column(df)
    tickers = sorted(set(filtered["ticker"].dropna()))
    if not tickers:
        return filtered.iloc[0:0].copy()

    cache_df = load_yahoo_cache(cache_file)
    attempted_this_run: set[str] = set()
    batch_number = 0
    while True:
        known_types = cache_df.drop_duplicates("ticker").set_index("ticker")[
            "quote_type_yahoo"
        ]
        remaining = [
            ticker
            for ticker in tickers
            if ticker not in attempted_this_run
            and (ticker not in known_types.index or pd.isna(known_types.get(ticker)))
        ]
        if not remaining:
            break

        batch_number += 1
        batch = remaining[:max_fetch_per_batch]
        attempted_this_run.update(batch)
        print(
            f"Quote-type batch {batch_number}: fetching {len(batch)} tickers "
            f"({len(remaining)} remaining)"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(fetch_yahoo_quote_type, ticker): ticker for ticker in batch
            }
            newly_fetched = []
            for completed, future in enumerate(as_completed(futures), start=1):
                newly_fetched.append(future.result())
                if completed % progress_every == 0 or completed == len(batch):
                    print(f"  Quote-type progress: {completed}/{len(batch)}")

        updates = pd.DataFrame(newly_fetched)
        cache_df = cache_df.merge(updates, on="ticker", how="outer", suffixes=("", "_new"))
        cache_df["quote_type_yahoo"] = cache_df["quote_type_yahoo"].combine_first(
            cache_df["quote_type_yahoo_new"]
        )
        cache_df = cache_df.drop(columns=["quote_type_yahoo_new"])
        save_yahoo_cache(cache_df, cache_file)

        if pause_seconds > 0 and len(attempted_this_run) < len(tickers):
            print(f"Pausing {pause_seconds:.1f}s before next quote-type batch...")
            time.sleep(pause_seconds)

    quote_types = cache_df[["ticker", "quote_type_yahoo"]].drop_duplicates("ticker")
    quote_types = quote_types.rename(columns={"quote_type_yahoo": "quote_type_yahoo_cache"})
    filtered = filtered.merge(quote_types, on="ticker", how="left")
    if "quote_type_yahoo" in filtered.columns:
        filtered["quote_type_yahoo"] = filtered["quote_type_yahoo"].combine_first(
            filtered["quote_type_yahoo_cache"]
        )
    else:
        filtered["quote_type_yahoo"] = filtered["quote_type_yahoo_cache"]
    filtered = filtered.drop(columns=["quote_type_yahoo_cache"])
    is_etf = filtered["quote_type_yahoo"].astype("string").str.upper().eq("ETF")
    return filtered.loc[is_etf].copy()


def fetch_yahoo_etf_details(ticker: str) -> dict[str, Any]:
    """Fetch descriptive and risk fields for one ETF from Yahoo Finance."""
    result = {"ticker": ticker, **dict.fromkeys(ETF_DETAIL_COLUMNS)}
    if yf is None:
        return result

    for attempt in range(3):
        try:
            info = yf.Ticker(ticker).get_info()
            info = info if isinstance(info, dict) else {}
            result.update(
                {
                    "etf_name": info.get("longName") or info.get("shortName"),
                    "category": info.get("category"),
                    "net_assets": info.get("totalAssets"),
                    "beta_5y": info.get("beta"),
                    "sharpe_ratio": info.get("sharpeRatio"),
                    "treynor_ratio": info.get("treynorRatio") or info.get("treynoRatio"),
                }
            )
            break
        except Exception as exc:
            if attempt < 2 and "rate" in str(exc).lower():
                time.sleep(2**attempt * 2)
                continue
            break

    time.sleep(0.1)
    return result


def enrich_etf_details_from_yahoo(
    df: pd.DataFrame,
    max_workers: int = 8,
    max_fetch_per_batch: int = 500,
    pause_seconds: float = 2.0,
    progress_every: int = 50,
) -> pd.DataFrame:
    """Fetch and merge Yahoo descriptive and risk fields for every ETF row."""
    if yf is None:
        print("yfinance not available; skipping ETF details enrichment.")
        return df
    if max_workers < 1 or max_fetch_per_batch < 1 or progress_every < 1:
        raise ValueError("Yahoo worker, batch, and progress values must be positive")

    enriched = normalize_ticker_column(df)
    remaining = sorted(set(enriched["ticker"].dropna()))
    if not remaining:
        return enriched

    print(f"Fetching detailed ETF data from Yahoo for {len(remaining)} tickers...")
    all_details = []
    batch_number = 0
    while remaining:
        batch_number += 1
        batch = remaining[:max_fetch_per_batch]
        remaining = remaining[max_fetch_per_batch:]
        print(f"ETF details batch {batch_number}: fetching {len(batch)} tickers")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(fetch_yahoo_etf_details, ticker): ticker for ticker in batch
            }
            for completed, future in enumerate(as_completed(futures), start=1):
                all_details.append(future.result())
                if completed % progress_every == 0 or completed == len(batch):
                    print(f"  ETF details progress: {completed}/{len(batch)}")

        if pause_seconds > 0 and remaining:
            print(f"Pausing {pause_seconds:.1f}s before next ETF details batch...")
            time.sleep(pause_seconds)

    return enriched.merge(pd.DataFrame(all_details), on="ticker", how="left")


def pick_liquidity_sort_column(df: pd.DataFrame) -> str | None:
    """Return the preferred available liquidity column for descending sorting."""
    for column in ("volume", "adv", "avg_dollar_volume", "dollar_volume"):
        if column in df.columns:
            return column
    return None


__all__ = [
    "TiingoQuotaError",
    "backfill_sector_industry_from_yahoo",
    "clean_classification_fields",
    "enrich_etf_details_from_yahoo",
    "exclude_otc_stocks",
    "fetch_tiingo_json",
    "fetch_tiingo_metadata",
    "fetch_yahoo_etf_details",
    "fetch_yahoo_quote_type",
    "fetch_yahoo_sector_industry",
    "filter_to_etfs_using_yahoo_quote_type",
    "get_tiingo_ticker_profile",
    "is_otc_exchange",
    "load_normalized_parquet",
    "load_yahoo_cache",
    "normalize_ticker_column",
    "pick_liquidity_sort_column",
    "save_yahoo_cache",
]