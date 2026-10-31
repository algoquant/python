from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from MachineTrader.helpers.file_handlers import discover_dated_csv_files, load_csv_frames
from MachineTrader.helpers.timestamp_utils import coerce_datetime_ny


DEFAULT_PRICE_DIR = Path("/Users/jerzy/Develop/data/minutes/live")
DEFAULT_ORDER_DIR = Path("/Users/jerzy/Develop/trading/logs")


def discover_order_strategies(order_dir: str | Path) -> list[str]:
    """Find strategies with blotters on the latest dated blotter day.

    Undated ``*_orders.csv`` files are used only when no dated blotters exist.
    """
    root = Path(order_dir).expanduser()
    dated_blotters = discover_dated_csv_files(
        root,
        ["*_blotter_*.csv"],
        date_pattern=r"_(\d{8})\.[cC][sS][vV]$",
    )
    if dated_blotters:
        latest_day = dated_blotters[-1][0]
        names = {
        path.name.rsplit("_blotter_", 1)[0]
        for day, path in dated_blotters
        if day == latest_day
        if "_blotter_" in path.name
        }
    else:
        names = {
            path.name[: -len("_orders.csv")]
            for path in root.glob("*_orders.csv")
            if path.is_file()
        }
    return sorted((name for name in names if name), key=str.casefold)


def discover_price_symbols(price_dir: str | Path) -> list[str]:
    """Find symbols from dated per-symbol minute-bar CSV filenames."""
    root = Path(price_dir).expanduser()
    symbol_pattern = re.compile(r"^([A-Za-z][A-Za-z0-9.-]*)_(\d{8})\.csv$", re.IGNORECASE)
    symbols = {
        match.group(1).upper()
        for path in root.glob("*_????????.csv")
        if path.is_file()
        if (match := symbol_pattern.match(path.name))
    }
    return sorted(symbols)


def load_symbol_price_history(
    symbol: str,
    price_dir: str | Path,
    *,
    start_timestamp: object | None = None,
) -> tuple[pd.DataFrame, list[Path]]:
    """Load available minute prices from a timestamp through the latest dated file."""
    start = coerce_datetime_ny(start_timestamp, fallback_to_now=False) if start_timestamp is not None else None
    start_day = start.strftime("%Y%m%d") if start is not None else None
    today = pd.Timestamp.now(tz="America/New_York").strftime("%Y%m%d")
    dated_files = discover_dated_csv_files(
        price_dir,
        [f"{symbol}_*.csv"],
        date_pattern=r"_(\d{8})\.csv$",
    )
    selected_files = [
        (day, path)
        for day, path in dated_files
        if day <= today and (start_day is None or day >= start_day)
    ]
    if not selected_files:
        return pd.DataFrame(columns=["timestamp", "close"]), []

    prices = load_csv_frames([path for _, path in selected_files], timestamp_column="timestamp")
    if not {"timestamp", "close"}.issubset(prices.columns):
        return pd.DataFrame(columns=["timestamp", "close"]), [path for _, path in selected_files]

    prices["timestamp"] = prices["timestamp"].map(
        lambda value: coerce_datetime_ny(value, fallback_to_now=False)
    )
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    prices = prices.dropna(subset=["timestamp", "close"])
    if start is not None:
        prices = prices.loc[prices["timestamp"].map(lambda value: value.date() >= start.date())]
    prices = prices.sort_values("timestamp", kind="stable").drop_duplicates(
        subset="timestamp",
        keep="last",
    )
    return prices.reset_index(drop=True), [path for _, path in selected_files]


def ensure_strategy_orders_csv(
    strategy_name: str,
    order_dir: str | Path,
    *,
    extractor_script: str | Path | None = None,
) -> Path:
    """Return a strategy orders CSV, generating a missing one via the CLI."""
    root = Path(order_dir).expanduser()
    orders_path = root / f"{strategy_name}_orders.csv"
    if orders_path.is_file():
        return orders_path

    script_path = (
        Path(extractor_script).expanduser()
        if extractor_script is not None
        else Path(__file__).resolve().parents[2] / "extract_blotter_orders.py"
    )
    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--strategy",
            strategy_name,
            "--log_dir",
            str(root),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if not orders_path.is_file():
        raise FileNotFoundError(f"Order extractor did not create {orders_path}")
    return orders_path


def discover_strategy_order_symbols(
    strategy_name: str,
    order_dir: str | Path,
    *,
    extractor_script: str | Path | None = None,
) -> list[str]:
    """Get symbols ordered by most distinct submitted-order days first."""
    try:
        orders_path = ensure_strategy_orders_csv(
            strategy_name,
            order_dir,
            extractor_script=extractor_script,
        )
        orders = pd.read_csv(orders_path, usecols=["symbol", "timestamp"])
    except (OSError, ValueError, pd.errors.EmptyDataError, pd.errors.ParserError, subprocess.CalledProcessError):
        return []
    orders["symbol"] = orders["symbol"].fillna("").astype(str).str.strip().str.upper()
    timestamps = orders["timestamp"].map(lambda value: coerce_datetime_ny(value, fallback_to_now=False))
    orders["order_day"] = timestamps.map(lambda value: value.date() if value else None)
    day_counts = orders.loc[orders["symbol"].ne("")].groupby("symbol")["order_day"].nunique()
    return sorted(day_counts.index.tolist(), key=lambda symbol: (-day_counts[symbol], symbol.casefold()))


def load_order_price_chart_data(
    strategy_name: str,
    symbol: str,
    *,
    price_dir: str | Path = DEFAULT_PRICE_DIR,
    order_dir: str | Path = DEFAULT_ORDER_DIR,
    extractor_script: str | Path | None = None,
) -> dict[str, object]:
    """Load a symbol's close-price history and its submitted-order markers."""
    orders_path = Path(order_dir).expanduser() / f"{strategy_name}_orders.csv"
    generation_error = ""
    try:
        orders_path = ensure_strategy_orders_csv(
            strategy_name,
            order_dir,
            extractor_script=extractor_script,
        )
    except subprocess.CalledProcessError as error:
        generation_error = (error.stderr or error.stdout or str(error)).strip()

    try:
        orders = pd.read_csv(orders_path) if orders_path.is_file() else pd.DataFrame()
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
        orders = pd.DataFrame(columns=["timestamp", "symbol", "num_shares", "limit_price"])

    quantity_column = "num_shares" if "num_shares" in orders.columns else "qty"
    required_columns = {"timestamp", "symbol", quantity_column, "limit_price"}
    unpriced_order_count = 0
    order_days: set[object] = set()
    earliest_order_timestamp = None
    if required_columns.issubset(orders.columns):
        orders = orders.loc[orders["symbol"].astype(str).str.upper().eq(symbol.upper())].copy()
        orders["timestamp"] = orders["timestamp"].map(
            lambda value: coerce_datetime_ny(value, fallback_to_now=False)
        )
        orders["limit_price"] = pd.to_numeric(orders["limit_price"], errors="coerce")
        orders["num_shares"] = pd.to_numeric(orders[quantity_column], errors="coerce").abs()
        order_days = set(orders["timestamp"].dropna().map(lambda value: value.date()))
        if order_days:
            earliest_order_timestamp = min(orders["timestamp"].dropna())
        unpriced_order_count = int(orders["limit_price"].isna().sum())
        orders = orders.dropna(subset=["timestamp", "limit_price", "num_shares"])
        orders = orders.loc[orders["limit_price"].ne(0)].sort_values("timestamp", kind="stable")
    else:
        orders = pd.DataFrame(columns=["timestamp", "symbol", "num_shares", "limit_price"])

    if earliest_order_timestamp is not None:
        prices, price_paths = load_symbol_price_history(
            symbol,
            price_dir,
            start_timestamp=earliest_order_timestamp,
        )
    else:
        prices = pd.DataFrame(columns=["timestamp", "close"])
        price_paths = []

    if not order_days:
        prices = prices.iloc[0:0]
        price_paths = []

    return {
        "prices": prices.reset_index(drop=True),
        "orders": orders.reset_index(drop=True),
        "price_files": price_paths,
        "orders_path": orders_path,
        "unpriced_order_count": unpriced_order_count,
        "order_generation_error": generation_error,
        "has_symbol_orders": bool(order_days),
    }


def align_order_times_to_price_bars(prices: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    """Snap order timestamps to the nearest available bar within one minute.

    Minute-bar charts only have coordinates for bar timestamps. The original
    order timestamp is preserved in ``timestamp`` for tooltips, while
    ``chart_timestamp`` contains the nearest bar time used to position it.
    """
    aligned = orders.copy()
    if prices.empty or orders.empty or "timestamp" not in prices or "timestamp" not in orders:
        aligned["chart_timestamp"] = pd.NaT
        return aligned

    bar_times = pd.to_datetime(prices["timestamp"], errors="coerce").dropna().sort_values().reset_index(drop=True)
    if bar_times.empty:
        aligned["chart_timestamp"] = pd.NaT
        return aligned

    aligned["chart_timestamp"] = pd.Series(pd.NaT, index=aligned.index, dtype=bar_times.dtype)
    bar_ns = bar_times.astype("int64").to_numpy()
    order_times = pd.to_datetime(orders["timestamp"], errors="coerce")
    for index, order_time in order_times.items():
        if pd.isna(order_time):
            continue
        order_ns = order_time.value
        insertion = int(bar_ns.searchsorted(order_ns))
        candidates = [candidate for candidate in (insertion - 1, insertion) if 0 <= candidate < len(bar_ns)]
        nearest = min(candidates, key=lambda candidate: abs(int(bar_ns[candidate]) - order_ns))
        if abs(int(bar_ns[nearest]) - order_ns) <= 60_000_000_000:
            aligned.at[index, "chart_timestamp"] = bar_times.iloc[nearest]

    return aligned.dropna(subset=["chart_timestamp"]).reset_index(drop=True)


def build_combined_order_chart_data(prices: pd.DataFrame, orders: pd.DataFrame) -> dict[str, object]:
    """Build one continuous price series with order markers and day boundaries."""
    if prices.empty:
        return {"data": [], "orders": [], "sessions": []}

    aligned_orders = align_order_times_to_price_bars(prices, orders)
    price_points = [
        {"time": int(timestamp.timestamp()), "value": float(close)}
        for timestamp, close in zip(prices["timestamp"], prices["close"])
    ]
    order_points = [
        {
            "time": int(chart_timestamp.timestamp()),
            "price": abs(float(signed_price)),
            "side": "BUY" if signed_price < 0 else "SELL",
            "shares": float(shares),
            "orderTime": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for timestamp, chart_timestamp, signed_price, shares in zip(
            aligned_orders["timestamp"],
            aligned_orders["chart_timestamp"],
            aligned_orders["limit_price"],
            aligned_orders["num_shares"],
        )
    ]

    sessions = []
    grouped_prices = prices.groupby(prices["timestamp"].map(lambda value: value.date()), sort=True)
    for day, day_prices in grouped_prices:
        first_timestamp = day_prices["timestamp"].iloc[0]
        last_timestamp = day_prices["timestamp"].iloc[-1]
        sessions.append(
            {
                "time": int(first_timestamp.timestamp()),
                "label": day.strftime("%b %d, %Y"),
                "from": int(first_timestamp.timestamp()),
                "to": int(last_timestamp.timestamp()),
            }
        )

    return {
        "data": price_points,
        "orders": order_points,
        "sessions": sessions,
        "initialRange": {
            "from": sessions[-1]["from"],
            "to": sessions[-1]["to"],
        },
    }