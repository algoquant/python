"""Reusable helpers for downloading and storing historical Tiingo OHLCV data."""

from __future__ import annotations

import asyncio
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import aiohttp
import pandas as pd
from tqdm.asyncio import tqdm_asyncio

from .metadata import fetch_tiingo_json, normalize_ticker_column
from .timestamp_utils import coerce_market_datetime_ny


def load_ohlc_csv(
    csv_path: str | Path,
    required_columns: set[str],
    timestamp_col: str = "timestamp",
    timezone: str = "America/New_York",
) -> pd.DataFrame:
    """Load, validate, parse, and sort an OHLCV CSV for charting or analysis."""
    path = Path(csv_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    frame = pd.read_csv(path)
    missing = required_columns.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if timezone == "America/New_York":
        parsed = frame[timestamp_col].map(
            lambda value: coerce_market_datetime_ny(value, fallback_to_now=False)
        )
        frame[timestamp_col] = pd.to_datetime(parsed, utc=True, errors="coerce").dt.tz_convert(timezone)
    else:
        frame[timestamp_col] = pd.to_datetime(frame[timestamp_col], utc=True, errors="coerce").dt.tz_convert(timezone)

    for column in ("open", "high", "low", "close", "volume"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    numeric_columns = [column for column in ("open", "high", "low", "close", "volume") if column in required_columns]
    frame = frame.dropna(subset=[timestamp_col, *numeric_columns]).sort_values(timestamp_col).reset_index(drop=True)
    return frame


def build_date_slider_metadata(
    frame: pd.DataFrame,
    timestamp_col: str = "timestamp",
    months_back: int = 1,
    label_format: str = "%m-%d-%y",
) -> dict[str, Any]:
    """Build unique date labels and default index bounds for a range slider."""
    dates = pd.Index(sorted(frame[timestamp_col].dt.date.dropna().unique()))
    labels = [day.strftime(label_format) for day in dates]
    if len(dates) == 0:
        return {
            "date_options": dates,
            "date_labels": labels,
            "default_start_idx": 0,
            "default_end_idx": 0,
        }

    newest = dates[-1]
    earliest = dates[0]
    minimum = max(earliest, (pd.Timestamp(newest) - pd.DateOffset(months=months_back)).date())
    return {
        "date_options": dates,
        "date_labels": labels,
        "default_start_idx": int(dates.searchsorted(minimum, side="left")),
        "default_end_idx": len(dates) - 1,
    }


@dataclass(frozen=True)
class TiingoHistoryConfig:
    """Settings shared by all requests in one historical download run."""

    data_key: str
    data_secret: str
    base_url: str = "https://api.tiingo.com"
    start_date: str = "1900-01-01"
    resample_freq: str = "daily"
    timeout_seconds: int = 60
    max_retries: int = 5
    backoff: float = 1.5
    batch_size: int = 64

    def __post_init__(self) -> None:
        """Reject settings that would make request processing invalid."""
        if not self.data_key.strip():
            raise ValueError("DATA_KEY is required")
        if not self.data_secret.strip():
            raise ValueError("DATA_SECRET is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_retries <= 0:
            raise ValueError("max_retries must be positive")
        if self.backoff <= 0:
            raise ValueError("backoff must be positive")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")


def load_tickers_csv(metadata_file: str | Path) -> list[str]:
    """Load normalized unique tickers from a CSV in first-occurrence order."""
    path = Path(metadata_file)
    if not path.exists():
        raise FileNotFoundError(f"Metadata file not found: {path}")

    try:
        metadata = pd.read_csv(path)
        if "ticker" in metadata.columns:
            metadata = metadata.loc[metadata["ticker"].notna()].copy()
        metadata = normalize_ticker_column(metadata)
    except ValueError as exc:
        raise ValueError(f"Expected 'ticker' column in {path}") from exc

    tickers = metadata.loc[metadata["ticker"].ne(""), "ticker"]
    return list(dict.fromkeys(tickers.tolist()))


def load_symbols_file(symbols_file: str | Path) -> list[str]:
    """Load symbols from the first column of a header-based CSV file.

    ``pandas.read_csv`` consumes the first row as column names, so the header
    is not returned as a symbol. Blank values are dropped and symbols are
    normalized to uppercase and deduplicated in first-occurrence order.
    """
    path = Path(symbols_file).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Symbols file not found: {path}")

    symbols_frame = pd.read_csv(path, dtype=str)
    if len(symbols_frame.columns) == 0:
        raise ValueError(f"Symbols file has no columns: {path}")

    first_column = symbols_frame.iloc[:, 0].dropna().astype(str).str.upper().str.strip()
    symbols = first_column[first_column.ne("")].tolist()
    return list(dict.fromkeys(symbols))


def normalize_tiingo_bars(
    data: Any,
    ticker: str,
    before_date: date | None = None,
) -> pd.DataFrame | None:
    """Normalize a Tiingo price payload into complete adjusted OHLCV rows."""
    bars = pd.DataFrame(data)
    required_columns = {"date", "open", "high", "low", "close", "volume"}
    if bars.empty or not required_columns.issubset(bars.columns):
        return None

    bars["date"] = pd.to_datetime(bars["date"], errors="coerce")
    adjusted_columns = {
        "open": "adjOpen",
        "high": "adjHigh",
        "low": "adjLow",
        "close": "adjClose",
        "volume": "adjVolume",
    }
    for base_column, adjusted_column in adjusted_columns.items():
        if adjusted_column in bars.columns:
            bars[base_column] = bars[adjusted_column]

    cutoff = before_date or date.today()
    valid_dates = bars["date"].notna() & (bars["date"].dt.date < cutoff)
    bars = bars.loc[valid_dates].dropna(subset=list(required_columns))
    if bars.empty:
        return None

    bars["dollar_volume"] = bars["close"] * bars["volume"]
    bars["ticker"] = str(ticker).upper().strip()
    return bars[
        ["date", "open", "high", "low", "close", "volume", "dollar_volume", "ticker"]
    ]


async def fetch_tiingo_bars(
    session: aiohttp.ClientSession,
    ticker: str,
    config: TiingoHistoryConfig,
) -> pd.DataFrame | None:
    """Download and normalize all configured Tiingo history for one ticker."""
    data = await fetch_tiingo_json(
        session,
        f"{config.base_url}/tiingo/daily/{ticker}/prices",
        config.data_secret,
        params={
            "startDate": config.start_date,
            "resampleFreq": config.resample_freq,
        },
        max_retries=config.max_retries,
        backoff=config.backoff,
        timeout_seconds=config.timeout_seconds,
        raise_on_failure=True,
    )
    if not data:
        return None
    return normalize_tiingo_bars(data, ticker)


def prefix_ticker_columns(bars: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Format normalized bars for a collision-free per-ticker Parquet file."""
    symbol = str(ticker).upper().strip()
    return bars[["date", "open", "high", "low", "close", "volume", "dollar_volume"]].rename(
        columns={
            "open": f"{symbol}.Open",
            "high": f"{symbol}.High",
            "low": f"{symbol}.Low",
            "close": f"{symbol}.Close",
            "volume": f"{symbol}.Volume",
            "dollar_volume": f"{symbol}.VolumeD",
        }
    )


async def process_tiingo_ticker(
    session: aiohttp.ClientSession,
    ticker: str,
    output_dir: str | Path,
    config: TiingoHistoryConfig,
) -> tuple[str, float] | None:
    """Download one ticker, replace its Parquet file, and return its liquidity."""
    bars = await fetch_tiingo_bars(session, ticker, config)
    if bars is None or bars.empty:
        return None

    symbol = str(ticker).upper().strip()
    output_path = Path(output_dir) / f"{symbol}.parquet"
    prefix_ticker_columns(bars, symbol).to_parquet(output_path, index=False)
    return symbol, float(bars["dollar_volume"].mean())


async def compute_tiingo_liquidity(
    tickers: Iterable[str],
    output_dir: str | Path,
    config: TiingoHistoryConfig,
) -> pd.DataFrame:
    """Process a ticker universe in batches and return successful liquidity rows."""
    ticker_list = list(tickers)
    liquidity: list[tuple[str, float]] = []
    connector = aiohttp.TCPConnector(limit=config.batch_size)

    async with aiohttp.ClientSession(connector=connector) as session:
        batch_starts = range(0, len(ticker_list), config.batch_size)
        for start in tqdm_asyncio(batch_starts, desc="Batches"):
            batch = ticker_list[start : start + config.batch_size]
            results = await asyncio.gather(
                *(
                    process_tiingo_ticker(session, ticker, output_dir, config)
                    for ticker in batch
                ),
                return_exceptions=True,
            )
            liquidity.extend(
                result
                for result in results
                if result is not None and not isinstance(result, BaseException)
            )

    return pd.DataFrame(liquidity, columns=["ticker", "volume"])


async def download_tiingo_history(
    tickers: Iterable[str],
    output_dir: str | Path,
    config: TiingoHistoryConfig,
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    """Download a universe and return liquidity plus one record per failure.

    A request that returns no complete historical rows is reported as
    ``No complete OHLCV data returned``. Unexpected task exceptions include
    their exception type and message. Failures do not interrupt other symbols.
    """
    ticker_list = list(tickers)
    liquidity: list[tuple[str, float]] = []
    errors: list[dict[str, str]] = []
    connector = aiohttp.TCPConnector(limit=config.batch_size)

    async with aiohttp.ClientSession(connector=connector) as session:
        batch_starts = range(0, len(ticker_list), config.batch_size)
        for start in tqdm_asyncio(batch_starts, desc="Batches"):
            batch = ticker_list[start : start + config.batch_size]
            results = await asyncio.gather(
                *(
                    process_tiingo_ticker(session, ticker, output_dir, config)
                    for ticker in batch
                ),
                return_exceptions=True,
            )
            for ticker, result in zip(batch, results):
                if isinstance(result, BaseException):
                    errors.append(
                        {
                            "ticker": ticker,
                            "error": f"{type(result).__name__}: {result}",
                        }
                    )
                elif result is None:
                    errors.append(
                        {
                            "ticker": ticker,
                            "error": "No complete OHLCV data returned",
                        }
                    )
                else:
                    liquidity.append(result)

    return pd.DataFrame(liquidity, columns=["ticker", "volume"]), errors


def write_ohlc_errors_csv(
    errors: Iterable[dict[str, str]],
    error_file: str | Path,
) -> Path:
    """Replace an OHLC error CSV, writing its header even when no errors occur."""
    path = Path(error_file).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["ticker", "error"])
        writer.writeheader()
        writer.writerows(errors)
    return path


__all__ = [
    "TiingoHistoryConfig",
    "compute_tiingo_liquidity",
    "download_tiingo_history",
    "fetch_tiingo_bars",
    "load_symbols_file",
    "load_tickers_csv",
    "normalize_tiingo_bars",
    "prefix_ticker_columns",
    "process_tiingo_ticker",
    "write_ohlc_errors_csv",
]