"""Build a deduplicated ETF metadata CSV from multiple data sources.

The script combines an existing ETF metadata file, a curated ticker catalog,
and best-effort web discovery. Shared :mod:`MachineTrader.helpers.metadata`
functions then download Tiingo fundamentals, fill missing classifications from
Yahoo Finance, enforce Yahoo's ``ETF`` quote type, enrich ETF-specific fields,
and normalize optional liquidity data.

Data flow
---------
1. Read tickers from the existing output CSV when it exists.
2. Add curated tickers covering broad-market, sector, factor, fixed-income,
   commodity, international, inverse, leveraged, and volatility products.
3. Scrape candidate tickers from Seeking Alpha and Yahoo Finance. Scraping
   failures are warnings and do not stop the pipeline.
4. Left-join Tiingo fundamentals metadata. Tiingo quota or request failures
   are tolerated so Yahoo enrichment can continue.
5. Backfill missing sector and industry values using the persistent Yahoo
   cache, then add descriptive and risk fields.
6. Remove mutual funds, equities, and unknown instruments by retaining only
   rows whose Yahoo quote type is ``ETF``.
7. Optionally merge the best available liquidity column and write the final
   CSV sorted by descending volume.

Environment
-----------
``API_KEY``
    Required Tiingo API token.
``ETF_METADATA_INPUT_FILE``
    Optional liquidity Parquet file. Defaults to
    ``/Users/jerzy/Develop/data/all_liquidity_etf.parquet``.
``ETF_METADATA_OUTPUT_FILE``
    Existing ticker source and final CSV destination. Defaults to
    ``/Users/jerzy/Develop/data/etf_metadata.csv``.
``YAHOO_CACHE_FILE``
    Shared Yahoo sector, industry, and quote-type Parquet cache. Defaults to
    ``/Users/jerzy/Develop/data/yahoo_sector_cache.parquet``.
``TIINGO_BASE_URL``
    Optional Tiingo API origin override. Defaults to
    ``https://api.tiingo.com``.

Example::

    API_KEY=... python get_metadata_etf.py \
        --max-yahoo-batch 300 \
        --yahoo-workers 4 \
        --pause-seconds 5

The script requires ``yfinance`` for ETF-only filtering. ``requests`` and
``beautifulsoup4`` are used only for optional ticker discovery.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from MachineTrader.helpers.metadata import (
    TiingoQuotaError,
    backfill_sector_industry_from_yahoo,
    enrich_etf_details_from_yahoo,
    fetch_tiingo_metadata,
    filter_to_etfs_using_yahoo_quote_type,
    load_normalized_parquet,
    pick_liquidity_sort_column,
)


load_dotenv()

API_KEY = os.getenv("API_KEY", "")
if not API_KEY:
    raise ValueError("Missing API_KEY in environment")

INPUT_FILE = Path(
    os.getenv(
        "ETF_METADATA_INPUT_FILE",
        "/Users/jerzy/Develop/data/all_liquidity_etf.parquet",
    )
)
OUTPUT_FILE = Path(
    os.getenv(
        "ETF_METADATA_OUTPUT_FILE",
        "/Users/jerzy/Develop/data/etf_metadata.csv",
    )
)
YAHOO_CACHE_FILE = Path(
    os.getenv(
        "YAHOO_CACHE_FILE",
        "/Users/jerzy/Develop/data/yahoo_sector_cache.parquet",
    )
)
BASE_URL = os.getenv("TIINGO_BASE_URL", "https://api.tiingo.com")

OUTPUT_COLUMNS = (
    "ticker",
    "volume",
    "etf_name",
    "category",
    "net_assets",
    "beta_5y",
    "sharpe_ratio",
    "treynor_ratio",
    "quote_type_yahoo",
    "sector",
    "industry",
    "classification_source",
)


def get_popular_etfs_by_category() -> dict[str, tuple[str, ...]]:
    """Return the curated ETF universe grouped by investment category.

    Category membership is used only to organize maintenance of the ticker
    catalog. Duplicate tickers across categories are removed later, and these
    category labels do not populate the output's Yahoo ``category`` field.
    """
    return {
        "Large Cap": ("SPY", "VOO", "IVV", "VTI"),
        "Technology": ("QQQ", "XLK", "VGT", "IYW", "KWEB", "SCHK", "QQQM"),
        "Fixed Income": ("TLT", "BND", "AGG", "LQD", "HYG", "MBB", "SHV", "VGIT", "BLV"),
        "Commodities & Resources": ("GLD", "SLV", "USO", "DBC", "GSG", "DXJ", "XLE", "XME"),
        "Financial Services": ("XLF", "VFV", "IYF", "KBWD", "KIE", "IYG"),
        "Utilities": ("XLU", "VPU", "SPLG", "SCHP"),
        "Healthcare & Biotech": ("XLV", "VHT", "IYH", "XBI", "IBB", "LABU", "VITC"),
        "Real Estate": ("SCHH", "XLRE", "VNQ", "REM", "RES", "DBREAL"),
        "Emerging Markets": ("EEM", "VWO", "IEMG", "SCHE", "EUSA"),
        "International": ("EFA", "IEFA", "VXUS", "SCHF"),
        "Consumer": ("XLY", "XLP", "VCR", "VDC", "SPLG"),
        "Industrials": ("XLI", "VIS", "IYJ"),
        "Cryptocurrency": ("GBTC", "IBIT", "FBTC", "ETHU", "ETHE"),
        "Dividend": ("VYM", "SCHD", "DGRO", "SPYD", "RDIV"),
        "High Yield": ("HYG", "ANGL", "JNK"),
        "Treasury": ("SHY", "IEF", "TLT", "VGIT"),
        "Growth": ("VUG", "SCHG", "VB", "VBK"),
        "Value": ("VTV", "SCHV", "VBR"),
        "Momentum": ("MTUM", "IMTM"),
        "Quality": ("QUAL", "SCHQ"),
        "Banking": ("KRE", "IAT", "SCHB"),
        "Energy": ("XLE", "VDE", "IYE"),
        "Materials": ("XLB", "VAW", "IYM"),
        "Communications": ("XLC", "VGT", "IYZ"),
        "Inverse": ("SH", "PSQ", "RWM"),
        "Volatility": ("VXX", "UVXY", "SVXY"),
    }


def scrape_etf_tickers_from_seeking_alpha() -> set[str]:
    """Return plausible uppercase tickers found on Seeking Alpha's ETF page.

    A candidate must be alphabetic, uppercase, and no longer than five
    characters. Network, HTTP, and parsing failures are reported as warnings
    and produce an empty set so curated and existing tickers remain usable.
    """
    try:
        response = requests.get(
            "https://seekingalpha.com/etfs/newest",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        return {
            text
            for link in soup.find_all("a")
            if (text := link.get_text(strip=True))
            and len(text) <= 5
            and text.isupper()
            and text.isalpha()
        }
    except Exception as exc:
        print(f"Warning: Seeking Alpha scrape failed: {exc}")
        return set()


def scrape_etf_tickers_from_yahoo_finance() -> set[str]:
    """Return plausible quote symbols linked from Yahoo Finance's ETF page.

    Symbols are extracted from ``/quote/<symbol>`` links and may contain a
    hyphen. Failures are non-fatal and return an empty set.
    """
    try:
        response = requests.get(
            "https://finance.yahoo.com/etfs",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        tickers = set()
        for link in soup.find_all("a"):
            href = str(link.get("href", ""))
            if "/quote/" not in href:
                continue
            ticker = href.split("/quote/", 1)[1].split("/", 1)[0].split("?", 1)[0]
            ticker = ticker.upper().strip()
            if ticker and len(ticker) <= 5 and ticker.replace("-", "").isalnum():
                tickers.add(ticker)
        return tickers
    except Exception as exc:
        print(f"Warning: Yahoo Finance scrape failed: {exc}")
        return set()


def combine_etf_tickers(output_file: Path = OUTPUT_FILE) -> pd.DataFrame:
    """Combine existing, curated, and scraped ETF ticker candidates.

    Args:
        output_file: Existing metadata CSV to use as an additional ticker
            source. A missing file is expected; read or schema failures are
            warnings and do not stop discovery.

    Returns:
        A one-column DataFrame named ``ticker`` containing sorted, normalized,
        unique candidates no longer than five characters.
    """
    all_tickers: set[str] = set()
    if output_file.exists():
        try:
            existing = pd.read_csv(output_file)
            if "ticker" in existing.columns:
                existing_tickers = set(
                    existing["ticker"].dropna().astype(str).str.upper().str.strip()
                )
                all_tickers.update(existing_tickers)
                print(f"Loaded {len(existing_tickers)} existing ETF tickers from {output_file}")
            else:
                print(f"Warning: Existing ETF metadata has no 'ticker' column: {output_file}")
        except Exception as exc:
            print(f"Warning: Could not load existing ETF tickers: {exc}")

    curated = get_popular_etfs_by_category()
    for tickers in curated.values():
        all_tickers.update(ticker.upper().strip() for ticker in tickers if ticker)
    print(
        f"Added {sum(len(tickers) for tickers in curated.values())} curated ETF tickers "
        f"across {len(curated)} categories"
    )

    print("Attempting to scrape ETF tickers from Seeking Alpha...")
    seeking_alpha_tickers = scrape_etf_tickers_from_seeking_alpha()
    all_tickers.update(seeking_alpha_tickers)
    if seeking_alpha_tickers:
        print(f"Scraped {len(seeking_alpha_tickers)} tickers from Seeking Alpha")

    print("Attempting to scrape ETF tickers from Yahoo Finance...")
    yahoo_tickers = scrape_etf_tickers_from_yahoo_finance()
    all_tickers.update(yahoo_tickers)
    if yahoo_tickers:
        print(f"Scraped {len(yahoo_tickers)} tickers from Yahoo Finance")

    valid_tickers = {
        ticker
        for ticker in all_tickers
        if ticker and len(ticker) <= 5 and ticker.replace("-", "").isalnum()
    }
    print(f"Total unique ETF ticker candidates: {len(valid_tickers)}")
    return pd.DataFrame({"ticker": sorted(valid_tickers)})


def parse_arguments() -> argparse.Namespace:
    """Parse Yahoo concurrency, batch-size, and pacing controls."""
    parser = argparse.ArgumentParser(
        description="Build etf_metadata.csv from existing, Tiingo, and Yahoo data"
    )
    parser.add_argument(
        "--max-yahoo-batch",
        type=int,
        default=300,
        help="Maximum number of Yahoo tickers fetched per batch.",
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


def add_optional_liquidity(df: pd.DataFrame, input_file: Path = INPUT_FILE) -> pd.DataFrame:
    """Merge the preferred available liquidity measure as ``volume``.

    Missing liquidity input is silently accepted because ticker discovery does
    not depend on it. Read and schema failures are reported and leave the input
    DataFrame unchanged.
    """
    if not input_file.exists():
        return df

    try:
        liquidity = load_normalized_parquet(input_file)
        volume_column = pick_liquidity_sort_column(liquidity)
        if volume_column is None and "Volume" in liquidity.columns:
            volume_column = "Volume"
        if volume_column is None:
            print(f"Info: No supported liquidity column found in {input_file}")
            return df

        liquidity = liquidity[["ticker", volume_column]].drop_duplicates("ticker")
        liquidity = liquidity.rename(columns={volume_column: "volume"})
        return df.merge(liquidity, on="ticker", how="left")
    except Exception as exc:
        print(f"Info: Could not load liquidity data: {exc}")
        return df


async def main(max_yahoo_batch: int, yahoo_workers: int, pause_seconds: float) -> None:
    """Run ETF discovery, enrichment, validation, and CSV export.

    Tiingo errors are warnings. Yahoo quote-type validation is mandatory and
    raises when yfinance is unavailable, preventing non-ETF candidates from
    entering the final file.
    """
    print("=" * 70)
    print("Step 1: Collecting ETF tickers from all sources")
    print("=" * 70)
    etf_tickers = combine_etf_tickers()

    print("\nStep 2: Fetching Tiingo metadata for collected tickers...")
    tiingo_metadata = pd.DataFrame(columns=["ticker"])
    try:
        tiingo_metadata = await fetch_tiingo_metadata(API_KEY, BASE_URL)
    except TiingoQuotaError as exc:
        print(f"Tiingo quota warning: {exc}")
        print("Continuing without Tiingo metadata.")
    except Exception as exc:
        print(f"Tiingo metadata warning: {exc}")
        print("Continuing without Tiingo metadata.")

    metadata_subset = tiingo_metadata[
        tiingo_metadata["ticker"].isin(etf_tickers["ticker"])
    ].copy()
    merged = etf_tickers.merge(metadata_subset, on="ticker", how="left")

    print("\nStep 3: Backfilling Yahoo sector and industry metadata...")
    merged = backfill_sector_industry_from_yahoo(
        merged,
        cache_file=YAHOO_CACHE_FILE,
        max_workers=yahoo_workers,
        max_fetch_per_batch=max_yahoo_batch,
        pause_seconds=pause_seconds,
    )

    print("Step 4: Filtering out mutual funds and non-ETF instruments...")
    merged = filter_to_etfs_using_yahoo_quote_type(
        merged,
        cache_file=YAHOO_CACHE_FILE,
        max_workers=max(yahoo_workers, 4),
        max_fetch_per_batch=max_yahoo_batch,
        pause_seconds=pause_seconds,
    )

    print("Step 5: Enriching ETF-specific Yahoo fields...")
    merged = enrich_etf_details_from_yahoo(
        merged,
        max_workers=max(yahoo_workers, 4),
        max_fetch_per_batch=max_yahoo_batch,
        pause_seconds=pause_seconds,
    )

    print("Step 6: Adding optional liquidity data...")
    merged = add_optional_liquidity(merged)
    if "volume" in merged.columns:
        merged = merged.sort_values("volume", ascending=False, na_position="last")
    merged = merged.drop_duplicates("ticker", keep="first").reset_index(drop=True)

    available_columns = [column for column in OUTPUT_COLUMNS if column in merged.columns]
    output_df = merged[available_columns].copy()
    if "ticker" not in output_df.columns:
        output_df.insert(0, "ticker", merged["ticker"])

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nStep 7: Output written to {OUTPUT_FILE}")
    print(f"Final ETF tickers: {len(output_df)} unique tickers")
    print(f"Columns: {list(output_df.columns)}")


if __name__ == "__main__":
    arguments = parse_arguments()
    asyncio.run(
        main(
            max_yahoo_batch=arguments.max_yahoo_batch,
            yahoo_workers=arguments.yahoo_workers,
            pause_seconds=arguments.pause_seconds,
        )
    )