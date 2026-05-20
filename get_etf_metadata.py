# ---------------------------------------------------------
# Merge the ETF liquidity data with Tiingo classification metadata 
# Scrape popular ETFs across multiple categories, and export to a CSV file.
# ---------------------------------------------------------

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import logging
import time
import requests
from bs4 import BeautifulSoup

import aiohttp
import pandas as pd

try:
    import yfinance as yf
    # Suppress yfinance's verbose 404/401 noise for missing/delisted tickers.
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
except ImportError:
    yf = None

API_KEY = "d84fc2a9c5bde2d68e33034f65a838092c6b9f10"

INPUT_FILE = Path("/Users/jerzy/Develop/data/all_liquidity_etf.parquet")
OUTPUT_FILE = Path("/Users/jerzy/Develop/data/etf_metadata.csv")
YAHOO_CACHE_FILE = Path("/Users/jerzy/Develop/data/yahoo_sector_cache.parquet")

BASE_URL = "https://api.tiingo.com"
UNAVAILABLE_FREE_TEXT = "field not available for free/evaluation"


class TiingoQuotaError(RuntimeError):
    """Raised when Tiingo daily request quota has been exhausted."""


def get_popular_etfs_by_category() -> dict:
    """
    Return a curated list of popular ETF tickers across multiple categories.
    This combines well-known ETFs with those likely discoverable via web scraping.
    """
    return {
        # Broad US Market
        "Large Cap": ["SPY", "VOO", "IVV", "VTI"],
        # Technology
        "Technology": ["QQQ", "XLK", "VGT", "IYW", "KWEB", "SCHK", "QQQM"],
        # Fixed Income / Bonds
        "Fixed Income": ["TLT", "BND", "AGG", "LQD", "HYG", "MBB", "SHV", "VGIT", "BLV"],
        # Natural Resources & Commodities
        "Commodities & Resources": ["GLD", "SLV", "USO", "DBC", "GSG", "DXJ", "GLD", "XLE", "XME"],
        # Financial Services
        "Financial Services": ["XLF", "VFV", "IYF", "KBWD", "KIE", "IYG"],
        # Utilities
        "Utilities": ["XLU", "VPU", "SPLG", "SCHP"],
        # Healthcare & Biotech
        "Healthcare & Biotech": ["XLV", "VHT", "IYH", "XBI", "IBB", "LABU", "XLV", "VITC"],
        # Real Estate
        "Real Estate": ["SCHH", "XLRE", "VNQ", "REM", "RES", "DBREAL"],
        # Emerging Markets
        "Emerging Markets": ["EEM", "VWO", "IEMG", "SCHE", "EUSA"],
        # International Developed
        "International": ["EFA", "IEFA", "VXUS", "SCHF"],
        # Consumer
        "Consumer": ["XLY", "XLP", "VCR", "VDC", "SPLG"],
        # Industrials
        "Industrials": ["XLI", "VIS", "IYJ"],
        # Crypto / Digital Assets
        "Cryptocurrency": ["GBTC", "IBIT", "FBTC", "ETHU", "ETHE"],
        # Dividend
        "Dividend": ["VYM", "SCHD", "DGRO", "SPYD", "RDIV"],
        # High Yield
        "High Yield": ["HYG", "ANGL", "JNK"],
        # Treasury
        "Treasury": ["SHY", "IEF", "TLT", "VGIT"],
        # Growth / Value
        "Growth": ["VUG", "SCHG", "VB", "VBK"],
        "Value": ["VTV", "SCHV", "VBR"],
        # Factor-Based
        "Momentum": ["MTUM", "IMTM"],
        "Quality": ["QUAL", "SCHQ"],
        # Bank ETFs
        "Banking": ["KRE", "IAT", "SCHB"],
        # Sector Specific
        "Energy": ["XLE", "VDE", "IYE"],
        "Materials": ["XLB", "VAW", "IYM"],
        "Communications": ["XLC", "VGT", "IYZ"],
        # Inverse / Leveraged
        "Inverse": ["SH", "PSQ", "RWM"],
        # VIX / Volatility
        "Volatility": ["VXX", "UVXY", "SVXY"],
    }


def scrape_etf_tickers_from_seeking_alpha() -> set:
    """
    Attempt to scrape popular ETF tickers from Seeking Alpha.
    Returns a set of tickers; empty set if scraping fails.
    """
    try:
        url = "https://seekingalpha.com/etfs/newest"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, timeout=10, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        
        tickers = set()
        # Look for ticker symbols (typically caps in links or table cells)
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            if len(text) <= 5 and text.isupper() and text.isalpha():
                tickers.add(text)
        
        return tickers
    except Exception as exc:
        print(f"Warning: Seeking Alpha scrape failed: {exc}")
        return set()


def scrape_etf_tickers_from_yahoo_finance() -> set:
    """
    Attempt to scrape popular ETF tickers from Yahoo Finance ETF page.
    Returns a set of tickers; empty set if scraping fails.
    """
    try:
        url = "https://finance.yahoo.com/etfs"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, timeout=10, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        
        tickers = set()
        # Look for ticker patterns in the page
        for link in soup.find_all("a"):
            href = link.get("href", "")
            if "/quote/" in href:
                parts = href.split("/")
                if len(parts) > 0:
                    potential_ticker = parts[-1].split("?")[0].upper()
                    if len(potential_ticker) <= 5 and potential_ticker.replace("-", "").isalnum():
                        tickers.add(potential_ticker)
        
        return tickers
    except Exception as exc:
        print(f"Warning: Yahoo Finance scrape failed: {exc}")
        return set()


def combine_etf_tickers() -> pd.DataFrame:
    """
    Combine tickers from:
    1. Existing ETF metadata CSV
    2. Popular ETF curated list
    3. Web scraping attempts (Seeking Alpha, Yahoo Finance)
    Remove duplicates and return as DataFrame with ticker column.
    """
    all_tickers = set()
    
    # Load existing tickers from CSV if it exists
    if OUTPUT_FILE.exists():
        try:
            existing_df = pd.read_csv(OUTPUT_FILE)
            if "ticker" in existing_df.columns:
                existing_tickers = set(existing_df["ticker"].dropna().astype(str).str.upper().str.strip())
                all_tickers.update(existing_tickers)
                print(f"Loaded {len(existing_tickers)} existing ETF tickers from {OUTPUT_FILE}")
        except Exception as exc:
            print(f"Warning: Could not load existing ETF tickers: {exc}")
    
    # Add curated popular ETFs
    curated = get_popular_etfs_by_category()
    for category, tickers in curated.items():
        all_tickers.update(t.upper().strip() for t in tickers if t)
    print(f"Added {sum(len(t) for t in curated.values())} curated ETF tickers across {len(curated)} categories")
    
    # Attempt web scraping (non-blocking failures)
    print("Attempting to scrape ETF tickers from Seeking Alpha...")
    sa_tickers = scrape_etf_tickers_from_seeking_alpha()
    all_tickers.update(sa_tickers)
    if sa_tickers:
        print(f"Scraped {len(sa_tickers)} tickers from Seeking Alpha")
    
    print("Attempting to scrape ETF tickers from Yahoo Finance...")
    yf_tickers = scrape_etf_tickers_from_yahoo_finance()
    all_tickers.update(yf_tickers)
    if yf_tickers:
        print(f"Scraped {len(yf_tickers)} tickers from Yahoo Finance")
    
    # Filter out obviously invalid tickers
    valid_tickers = {t for t in all_tickers if t and len(t) <= 5 and t.replace("-", "").isalnum()}
    
    result_df = pd.DataFrame({"ticker": sorted(valid_tickers)})
    print(f"Total unique ETF tickers: {len(result_df)}")
    
    return result_df


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
        return {
            "ticker": ticker,
            "sector_yahoo": None,
            "industry_yahoo": None,
            "quote_type_yahoo": None,
        }

    max_attempts = 4
    quote_type = None
    for attempt in range(max_attempts):
        try:
            ticker_obj = yf.Ticker(ticker)
            try:
                fast_info = ticker_obj.fast_info
                quote_type = getattr(fast_info, "quote_type", None)
                if quote_type is None and isinstance(fast_info, dict):
                    quote_type = fast_info.get("quoteType")
            except Exception:
                quote_type = None

            info = ticker_obj.get_info()
            if not isinstance(info, dict):
                info = {}
            if not quote_type:
                quote_type = info.get("quoteType")
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
        "quote_type_yahoo": quote_type,
    }


def _fetch_yahoo_quote_type(ticker: str) -> dict:
    """Fetch Yahoo quote type for ETF/equity classification."""
    if yf is None:
        return {"ticker": ticker, "quote_type_yahoo": None}

    max_attempts = 4
    quote_type = None
    for attempt in range(max_attempts):
        try:
            ticker_obj = yf.Ticker(ticker)
            fast_info = ticker_obj.fast_info
            quote_type = getattr(fast_info, "quote_type", None)
            if quote_type is None and isinstance(fast_info, dict):
                quote_type = fast_info.get("quoteType")
            if quote_type:
                break
            info = ticker_obj.get_info()
            if isinstance(info, dict):
                quote_type = info.get("quoteType")
            break
        except Exception as exc:
            if attempt < max_attempts - 1 and "rate" in str(exc).lower():
                time.sleep(2 ** attempt * 2)  # 2s, 4s, 8s
                continue
            break

    time.sleep(0.1)  # Polite delay between requests
    return {"ticker": ticker, "quote_type_yahoo": quote_type}


def _fetch_etf_details_from_yahoo(ticker: str) -> dict:
    """Fetch detailed ETF fields from Yahoo Finance."""
    if yf is None:
        return {
            "ticker": ticker,
            "etf_name": None,
            "category": None,
            "net_assets": None,
            "beta_5y": None,
            "sharpe_ratio": None,
            "treynor_ratio": None,
        }

    result = {
        "ticker": ticker,
        "etf_name": None,
        "category": None,
        "net_assets": None,
        "beta_5y": None,
        "sharpe_ratio": None,
        "treynor_ratio": None,
    }

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.get_info()
            if not isinstance(info, dict):
                info = {}

            result["etf_name"] = info.get("longName") or info.get("shortName")
            result["category"] = info.get("category")
            result["net_assets"] = info.get("totalAssets")
            result["beta_5y"] = info.get("beta")
            result["sharpe_ratio"] = info.get("sharpeRatio")
            result["treynor_ratio"] = info.get("treynoRatio")
            break
        except Exception as exc:
            if attempt < max_attempts - 1 and "rate" in str(exc).lower():
                time.sleep(2 ** attempt * 2)
                continue
            break

    time.sleep(0.1)
    return result


def _load_yahoo_cache() -> pd.DataFrame:
    """Load previously fetched Yahoo sector/industry results from local cache."""
    expected_cols = ["ticker", "sector_yahoo", "industry_yahoo", "quote_type_yahoo"]
    if YAHOO_CACHE_FILE.exists():
        cache_df = pd.read_parquet(YAHOO_CACHE_FILE)
        for col in expected_cols:
            if col not in cache_df.columns:
                cache_df[col] = pd.NA
        qt = cache_df["quote_type_yahoo"].astype("string").str.strip()
        none_like = qt.str.lower().isin(["", "none", "nan", "null", "na", "<na>"])
        cache_df.loc[none_like, "quote_type_yahoo"] = pd.NA
        return cache_df[expected_cols]
    return pd.DataFrame(columns=expected_cols)


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


def filter_to_etfs_using_yahoo_quote_type(
    df: pd.DataFrame,
    max_workers: int = 8,
    max_fetch_per_batch: int = 500,
    pause_seconds: float = 3.0,
    progress_every: int = 50,
) -> pd.DataFrame:
    """Filter rows to ETFs only based on Yahoo quote type cache/fetch."""
    if yf is None:
        raise RuntimeError(
            "yfinance is required to enforce ETF-only output. Install yfinance and rerun."
        )

    filtered = df.copy()
    tickers = sorted(set(filtered["ticker"].dropna().astype(str).str.upper().str.strip()))
    if not tickers:
        return filtered.iloc[0:0].copy()

    cache_df = _load_yahoo_cache()
    if not cache_df.empty:
        cache_df["ticker"] = cache_df["ticker"].astype(str).str.upper().str.strip()
        cache_df["quote_type_yahoo"] = cache_df["quote_type_yahoo"].astype("string").str.strip()
        none_like = cache_df["quote_type_yahoo"].str.lower().isin(
            ["", "none", "nan", "null", "na", "<na>"]
        )
        cache_df.loc[none_like, "quote_type_yahoo"] = pd.NA

    attempted_this_run = set()
    batch_num = 0
    while True:
        known_map = cache_df.drop_duplicates("ticker").set_index("ticker")["quote_type_yahoo"]
        # Fetch uncached tickers and tickers with unknown quote type once per run.
        to_fetch_all = [
            t
            for t in tickers
            if t not in attempted_this_run and (t not in known_map.index or pd.isna(known_map.get(t)))
        ]
        if not to_fetch_all:
            break

        batch_num += 1
        to_fetch = to_fetch_all[:max_fetch_per_batch]
        attempted_this_run.update(to_fetch)
        print(
            f"Quote-type batch {batch_num}: fetching {len(to_fetch)} tickers "
            f"({len(to_fetch_all)} remaining)"
        )

        newly_fetched = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_yahoo_quote_type, t): t for t in to_fetch}
            completed = 0
            for fut in as_completed(futures):
                newly_fetched.append(fut.result())
                completed += 1
                if completed % progress_every == 0 or completed == len(to_fetch):
                    print(f"  Quote-type progress: {completed}/{len(to_fetch)}")

        new_df = pd.DataFrame(newly_fetched)
        cache_df = cache_df.merge(new_df, on="ticker", how="outer", suffixes=("", "_new"))
        cache_df["quote_type_yahoo"] = cache_df["quote_type_yahoo"].combine_first(
            cache_df.get("quote_type_yahoo_new")
        )
        if "quote_type_yahoo_new" in cache_df.columns:
            cache_df = cache_df.drop(columns=["quote_type_yahoo_new"])

        _save_yahoo_cache(cache_df)

        if pause_seconds > 0:
            print(f"Pausing {pause_seconds:.1f}s before next quote-type batch...")
            time.sleep(pause_seconds)

    quote_df = cache_df[["ticker", "quote_type_yahoo"]].drop_duplicates("ticker")
    quote_df = quote_df.rename(columns={"quote_type_yahoo": "quote_type_yahoo_cache"})
    filtered = filtered.merge(quote_df, on="ticker", how="left")
    if "quote_type_yahoo" in filtered.columns:
        filtered["quote_type_yahoo"] = filtered["quote_type_yahoo"].combine_first(
            filtered["quote_type_yahoo_cache"]
        )
    else:
        filtered["quote_type_yahoo"] = filtered["quote_type_yahoo_cache"]
    filtered = filtered.drop(columns=["quote_type_yahoo_cache"])
    etf_mask = filtered["quote_type_yahoo"].astype("string").str.upper().eq("ETF")
    return filtered.loc[etf_mask].copy()


def enrich_etf_details_from_yahoo(
    df: pd.DataFrame,
    max_workers: int = 8,
    max_fetch_per_batch: int = 500,
    pause_seconds: float = 2.0,
    progress_every: int = 50,
) -> pd.DataFrame:
    """Fetch and merge detailed ETF fields from Yahoo for all tickers."""
    if yf is None:
        print("yfinance not available; skipping ETF details enrichment.")
        return df

    enriched = df.copy()
    tickers = sorted(set(enriched["ticker"].dropna().astype(str).str.upper().str.strip()))
    if not tickers:
        return enriched

    print(f"Fetching detailed ETF data from Yahoo for {len(tickers)} tickers...")

    batch_num = 0
    all_details = []
    while tickers:
        batch_num += 1
        batch = tickers[:max_fetch_per_batch]
        tickers = tickers[max_fetch_per_batch:]

        print(f"ETF details batch {batch_num}: fetching {len(batch)} tickers")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_etf_details_from_yahoo, t): t for t in batch}
            completed = 0
            for fut in as_completed(futures):
                all_details.append(fut.result())
                completed += 1
                if completed % progress_every == 0 or completed == len(batch):
                    print(f"  ETF details progress: {completed}/{len(batch)}")

        if pause_seconds > 0 and tickers:
            print(f"Pausing {pause_seconds:.1f}s before next ETF details batch...")
            time.sleep(pause_seconds)

    details_df = pd.DataFrame(all_details)
    enriched = enriched.merge(details_df, on="ticker", how="left")
    return enriched


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build etf_metadata.csv from liquidity + Tiingo + Yahoo fallback")
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


async def main(max_yahoo_batch: int, yahoo_workers: int, pause_seconds: float) -> None:
    print("=" * 70)
    print("Step 1: Collecting ETF tickers from all sources")
    print("=" * 70)
    
    # Collect all unique ETF tickers
    etf_tickers_df = combine_etf_tickers()
    
    print("\nStep 2: Fetching Tiingo metadata for collected tickers...")
    metadata_df = pd.DataFrame(columns=["ticker"])
    try:
        metadata_df = await fetch_tiingo_metadata()
    except TiingoQuotaError as exc:
        print(f"Tiingo quota warning: {exc}")
        print("Continuing without Tiingo metadata.")
    except Exception as exc:
        print(f"Tiingo metadata warning: {exc}")
        print("Continuing without Tiingo metadata.")

    # Merge with any available Tiingo metadata
    merged = etf_tickers_df.merge(metadata_df, on="ticker", how="left")
    
    # Enrich with Yahoo Finance sector/industry data
    print("\nStep 3: Enriching with Yahoo Finance metadata (sector, industry, etc.)...")
    merged = backfill_sector_industry_from_yahoo(
        merged,
        max_workers=yahoo_workers,
        max_fetch_per_batch=max_yahoo_batch,
        pause_seconds=pause_seconds,
    )
    
    # Enrich with additional ETF details from Yahoo
    print("Step 4: Enriching with additional ETF details...")
    merged = enrich_etf_details_from_yahoo(
        merged,
        max_workers=max(yahoo_workers, 4),
    )

    # Exclude mutual funds and non-ETF instruments using Yahoo quote type
    print("Step 5: Filtering out mutual funds and non-ETF instruments...")
    merged = filter_to_etfs_using_yahoo_quote_type(
        merged,
        max_workers=max(yahoo_workers, 4),
    )
    
    # Try to load liquidity data if available
    if INPUT_FILE.exists():
        try:
            print("Step 6: Adding liquidity data...")
            liquidity_df = load_liquidity()
            # Try different possible column names for volume
            volume_col = None
            for col in ["volume", "Volume", "adv", "avg_dollar_volume", "dollar_volume"]:
                if col in liquidity_df.columns:
                    volume_col = col
                    break
            if volume_col:
                merged = merged.merge(liquidity_df[["ticker", volume_col]], on="ticker", how="left")
                merged = merged.rename(columns={volume_col: "volume"})
        except Exception as exc:
            print(f"Info: Could not load liquidity data: {exc}")
    
    # Sort and deduplicate
    if "volume" in merged.columns:
        merged = merged.sort_values("volume", ascending=False, na_position="last")
    merged = merged.drop_duplicates(subset=["ticker"], keep="first").reset_index(drop=True)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Select columns to output (prioritize ticker and available columns)
    possible_cols = ["ticker", "volume", "etf_name", "category", "net_assets", "beta_5y", "sharpe_ratio", "treynor_ratio", "quote_type_yahoo", "sector", "industry", "classification_source"]
    available_cols = [c for c in possible_cols if c in merged.columns]
    output_df = merged[available_cols].copy()
    
    # Ensure ticker is always first
    if "ticker" not in output_df.columns:
        output_df.insert(0, "ticker", merged["ticker"])
    else:
        cols = output_df.columns.tolist()
        cols.remove("ticker")
        output_df = output_df[["ticker"] + cols]
    
    output_df = output_df.drop_duplicates(subset=["ticker"], keep="first").reset_index(drop=True)
    output_df.to_csv(OUTPUT_FILE, index=False)

    print(f"\nStep 7: Output written to {OUTPUT_FILE}")
    print(f"Final ETF tickers: {len(output_df)} unique tickers")
    print(f"Columns: {list(output_df.columns)}")
    for col in output_df.columns:
        if col != "ticker":
            filled = (1 - output_df[col].isna().sum() / len(output_df)) * 100
            print(f"  {col}: {filled:.1f}% filled")
    print("=" * 70)


if __name__ == "__main__":
    args = parse_arguments()
    asyncio.run(
        main(
            max_yahoo_batch=args.max_yahoo_batch,
            yahoo_workers=args.yahoo_workers,
            pause_seconds=args.pause_seconds,
        )
    )
