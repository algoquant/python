"""Build a stock metadata CSV with shared MachineTrader helpers.

The pipeline loads a liquidity Parquet table, removes Tiingo-identified OTC
securities, joins Tiingo fundamentals metadata, backfills missing sector and
industry values from Yahoo Finance, and exports the result as CSV.

Configuration is loaded from ``.env`` and the process environment:

``API_KEY``
    Required Tiingo API token.
``STOCK_METADATA_INPUT_FILE``
    Liquidity Parquet source. It must contain a ``ticker`` column.
``STOCK_METADATA_OUTPUT_FILE``
    Destination CSV path.
``YAHOO_CACHE_FILE``
    Persistent Parquet cache for Yahoo classification lookups.
``TIINGO_BASE_URL``
    Optional Tiingo API origin override.

Example::

    API_KEY=... python get_metadata_stock.py \
        --max-yahoo-batch 300 \
        --yahoo-workers 4 \
        --pause-seconds 5
"""

import argparse
import asyncio
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from MachineTrader.helpers.metadata import (
    TiingoQuotaError,
    backfill_sector_industry_from_yahoo,
    exclude_otc_stocks,
    fetch_tiingo_metadata,
    load_normalized_parquet,
    pick_liquidity_sort_column,
)


load_dotenv()

API_KEY = os.getenv("API_KEY", "")
if not API_KEY:
    raise ValueError("Missing API_KEY in environment")

INPUT_FILE = Path(
    os.getenv(
        "STOCK_METADATA_INPUT_FILE",
        "/Users/jerzy/Develop/data/all_liquidity.parquet",
    )
)
OUTPUT_FILE = Path(
    os.getenv(
        "STOCK_METADATA_OUTPUT_FILE",
        "/Users/jerzy/Develop/data/stock_metadata.csv",
    )
)
YAHOO_CACHE_FILE = Path(
    os.getenv(
        "YAHOO_CACHE_FILE",
        "/Users/jerzy/Develop/data/yahoo_sector_cache.parquet",
    )
)
BASE_URL = os.getenv("TIINGO_BASE_URL", "https://api.tiingo.com")


def parse_arguments() -> argparse.Namespace:
    """Parse Yahoo request batching and pacing controls."""
    parser = argparse.ArgumentParser(
        description="Build stock_metadata.csv from liquidity, Tiingo, and Yahoo data"
    )
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
    """Run the metadata enrichment pipeline and write the configured CSV."""
    print(f"Loading liquidity data: {INPUT_FILE}")
    liquidity_df = load_normalized_parquet(INPUT_FILE)
    liquidity_df = await exclude_otc_stocks(
        liquidity_df,
        api_key=API_KEY,
        base_url=BASE_URL,
    )

    print("Downloading Tiingo classification metadata...")
    metadata_df = pd.DataFrame(columns=["ticker"])
    try:
        metadata_df = await fetch_tiingo_metadata(API_KEY, BASE_URL)
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
        cache_file=YAHOO_CACHE_FILE,
        max_workers=yahoo_workers,
        max_fetch_per_batch=max_yahoo_batch,
        pause_seconds=pause_seconds,
    )

    sort_column = pick_liquidity_sort_column(merged)
    if sort_column is not None:
        merged = merged.sort_values(sort_column, ascending=False)
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
    arguments = parse_arguments()
    asyncio.run(
        main(
            max_yahoo_batch=arguments.max_yahoo_batch,
            yahoo_workers=arguments.yahoo_workers,
            pause_seconds=arguments.pause_seconds,
        )
    )