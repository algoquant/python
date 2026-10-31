"""Download Tiingo OHLCV history using one environment-file argument.

Usage::

    python3 get_ohlc.py /Users/jerzy/Develop/trading/config/.env_tiingo

The environment file must define:

``DATA_KEY``
    Data account/public key. It is loaded and validated with the secret.
``DATA_SECRET``
    Tiingo API token used to authenticate historical price requests.
``SYMBOLS_FILE_NAME``
    CSV file containing symbols in its first column. The first row is treated
    as a header and ignored. Symbols are uppercased, trimmed, and deduplicated.
``DATA_DIR_NAME``
    Output directory for per-symbol Parquet files and run-level reports.

Optional request settings are ``BASE_URL``, ``HISTORY_START_DATE``,
``RESAMPLE_FREQ``, ``BATCH_SIZE``, ``FETCH_TIMEOUT_SECONDS``,
``FETCH_MAX_RETRIES``, and ``FETCH_BACKOFF``.

For a symbol such as ``SPY``, the command writes ``SPY.parquet`` under
``DATA_DIR_NAME`` with ``date``, prefixed adjusted OHLCV columns, and daily
dollar volume. It also writes:

``all_liquidity.parquet``
    Successful symbols ranked by mean daily dollar volume.
``ohlc_errors.csv``
    One row per failed symbol with ``ticker`` and ``error`` columns. The file
    is replaced on every run and contains its header even when no errors occur.

HTTP 429, HTTP 503, and request exceptions are retried by
:mod:`MachineTrader.helpers.ohlc`. A failed symbol does not stop other symbols.

Complete example
----------------
Create ``/tmp/ohlc-example/.env_history``::

    DATA_KEY=your_tiingo_api_key
    DATA_SECRET=your_data_secret
    SYMBOLS_FILE_NAME=symbols.csv
    DATA_DIR_NAME=output
    HISTORY_START_DATE=2020-01-01
    RESAMPLE_FREQ=daily
    BATCH_SIZE=8
    FETCH_TIMEOUT_SECONDS=60
    FETCH_MAX_RETRIES=5
    FETCH_BACKOFF=1.5

Create ``/tmp/ohlc-example/symbols.csv``::

    Symbol
    SPY
    QQQ
    AAPL
    SPY

Run the command from any directory::

    python3 get_ohlc.py /tmp/ohlc-example/.env_history

Because both configured paths are relative, they resolve from the directory
containing ``.env_history``. The duplicate ``SPY`` row is removed and these
files are produced::

    /tmp/ohlc-example/output/SPY.parquet
    /tmp/ohlc-example/output/QQQ.parquet
    /tmp/ohlc-example/output/AAPL.parquet
    /tmp/ohlc-example/output/all_liquidity.parquet
    /tmp/ohlc-example/output/ohlc_errors.csv

An example liquidity table is::

    ticker,volume
    AAPL,12500000000.0
    SPY,9800000000.0
    QQQ,6200000000.0

An error report for a symbol with no usable response is::

    ticker,error
    BAD,No complete OHLCV data returned

When all symbols succeed, ``ohlc_errors.csv`` contains only its header::

    ticker,error
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values

from MachineTrader.helpers.ohlc import (
    TiingoHistoryConfig,
    download_tiingo_history,
    load_symbols_file,
    write_ohlc_errors_csv,
)


LIQUIDITY_FILE_NAME = "all_liquidity.parquet"
ERROR_FILE_NAME = "ohlc_errors.csv"


def parse_arguments() -> argparse.Namespace:
    """Parse the single required environment-file argument."""
    parser = argparse.ArgumentParser(
                description="Download Tiingo OHLCV history for symbols configured in an env file.",
                formatter_class=argparse.RawDescriptionHelpFormatter,
                epilog="""examples:
    python3 get_ohlc.py /Users/jerzy/Develop/trading/config/.env_tiingo
    python3 get_ohlc.py ./config/.env_history
""",
    )
    parser.add_argument(
        "environment_file",
        type=Path,
        help="Path to the environment file containing data credentials and paths.",
    )
    return parser.parse_args()


def required_environment_value(values: Mapping[str, str | None], name: str) -> str:
    """Return a required nonblank value from the selected environment file."""
    value = str(values.get(name) or "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def integer_environment_value(
    values: Mapping[str, str | None],
    name: str,
    default: int,
) -> int:
    """Read an integer environment value with a descriptive validation error."""
    raw_value = values.get(name) or str(default)
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Environment variable {name} must be an integer, got {raw_value!r}"
        ) from exc


def float_environment_value(
    values: Mapping[str, str | None],
    name: str,
    default: float,
) -> float:
    """Read a floating-point environment value with validation."""
    raw_value = values.get(name) or str(default)
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Environment variable {name} must be a float, got {raw_value!r}"
        ) from exc


def resolve_configured_path(value: str, environment_file: Path) -> Path:
    """Resolve an absolute path or a path relative to the env file directory.

    Example:
        For ``environment_file=/tmp/job/.env`` and ``value=output``, the
        returned path is ``/tmp/job/output``.
    """
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return environment_file.parent / path


def load_history_config(
    environment_file: Path,
) -> tuple[TiingoHistoryConfig, Path, Path]:
    """Load credentials, symbols path, output path, and request settings.

    Values from the selected file override inherited process values. This
    ensures the explicit command-line configuration controls the run.

    Returns:
        ``(history_config, symbols_file, data_dir)``.

    Raises:
        FileNotFoundError: If the environment file does not exist.
        ValueError: If a required setting is missing or a numeric setting is
            invalid.
    """
    resolved_environment_file = environment_file.expanduser().resolve()
    if not resolved_environment_file.is_file():
        raise FileNotFoundError(f"Environment file not found: {resolved_environment_file}")

    values = dotenv_values(resolved_environment_file)
    data_key = required_environment_value(values, "DATA_KEY")
    data_secret = required_environment_value(values, "DATA_SECRET")
    symbols_file = resolve_configured_path(
        required_environment_value(values, "SYMBOLS_FILE_NAME"),
        resolved_environment_file,
    )
    data_dir = resolve_configured_path(
        required_environment_value(values, "DATA_DIR_NAME"),
        resolved_environment_file,
    )

    config = TiingoHistoryConfig(
        data_key=data_key,
        data_secret=data_secret,
        base_url=str(values.get("BASE_URL") or "https://api.tiingo.com").strip(),
        start_date=str(values.get("HISTORY_START_DATE") or "1900-01-01").strip(),
        resample_freq=str(values.get("RESAMPLE_FREQ") or "daily").strip(),
        timeout_seconds=integer_environment_value(
            values,
            "FETCH_TIMEOUT_SECONDS",
            60,
        ),
        max_retries=integer_environment_value(values, "FETCH_MAX_RETRIES", 5),
        backoff=float_environment_value(values, "FETCH_BACKOFF", 1.5),
        batch_size=integer_environment_value(values, "BATCH_SIZE", 64),
    )
    return config, symbols_file, data_dir


async def main(environment_file: Path) -> None:
    """Download all configured symbols and write Parquet and error outputs."""
    config, symbols_file, data_dir = load_history_config(environment_file)
    data_dir.mkdir(parents=True, exist_ok=True)
    error_file = data_dir / ERROR_FILE_NAME

    try:
        tickers = load_symbols_file(symbols_file)
    except Exception as exc:
        write_ohlc_errors_csv(
            [{"ticker": "", "error": f"{type(exc).__name__}: {exc}"}],
            error_file,
        )
        raise

    print(f"Environment file: {environment_file.expanduser().resolve()}")
    print(f"Symbols file: {symbols_file}")
    print(f"Found {len(tickers)} unique symbols")
    print(f"Writing output files to: {data_dir}")

    liquidity, errors = await download_tiingo_history(tickers, data_dir, config)
    liquidity = liquidity.sort_values("volume", ascending=False).reset_index(drop=True)
    liquidity_file = data_dir / LIQUIDITY_FILE_NAME
    liquidity.to_parquet(liquidity_file, index=False)
    write_ohlc_errors_csv(errors, error_file)

    print(f"Saved liquidity ranking: {liquidity_file}")
    print(f"Saved error report: {error_file} ({len(errors)} errors)")
    print("\nTop 20 most liquid symbols:")
    print(liquidity.head(20))


if __name__ == "__main__":
    arguments = parse_arguments()
    asyncio.run(main(arguments.environment_file))
