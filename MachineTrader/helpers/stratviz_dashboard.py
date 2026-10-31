from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from MachineTrader.helpers.file_handlers import discover_dated_csv_files, load_csv_frames
from MachineTrader.helpers.orders_dashboard import (
    DEFAULT_ORDER_DIR,
    DEFAULT_PRICE_DIR,
    load_order_price_chart_data,
    load_symbol_price_history,
)
from MachineTrader.helpers.timestamp_utils import coerce_datetime_ny

FEATURE_TYPES = ("positions", "pnls", "zscore", "ema", "vol")


def discover_metric_strategies(log_dir: str | Path) -> list[str]:
    """Discover strategies from position files on their most recent date."""
    files = discover_dated_csv_files(
        log_dir,
        ["*_positions_*.csv"],
        date_pattern=r"_(\d{8})\.csv$",
    )
    if not files:
        return []
    latest_day = files[-1][0]
    return sorted(
        {
            path.name.rsplit("_positions_", 1)[0]
            for day, path in files
            if day == latest_day and "_positions_" in path.name
        },
        key=str.casefold,
    )


def load_order_feature_chart_data(
    strategy_name: str,
    symbol: str,
    feature: str,
    *,
    log_dir: str | Path = DEFAULT_ORDER_DIR,
    price_dir: str | Path = DEFAULT_PRICE_DIR,
) -> dict[str, Any]:
    """Load price, order, and feature history starting at the earliest relevant date."""
    if feature not in FEATURE_TYPES:
        raise ValueError(f"Unsupported feature {feature!r}; choose from {FEATURE_TYPES}")

    order_data = load_order_price_chart_data(
        strategy_name,
        symbol,
        price_dir=price_dir,
        order_dir=log_dir,
    )
    prices = order_data["prices"]
    orders = order_data["orders"]
    feature_files = discover_dated_csv_files(
        log_dir,
        [f"{strategy_name}_{feature}_*.csv"],
        date_pattern=r"_(\d{8})\.csv$",
    )
    today = pd.Timestamp.now(tz="America/New_York").strftime("%Y%m%d")
    candidate_paths = [path for day, path in feature_files if day <= today]

    if candidate_paths:
        feature_frame = load_csv_frames(candidate_paths, timestamp_column="timestamp")
    else:
        feature_frame = pd.DataFrame(columns=["timestamp", symbol])

    if "timestamp" in feature_frame.columns:
        feature_frame["timestamp"] = feature_frame["timestamp"].map(
            lambda value: coerce_datetime_ny(value, fallback_to_now=False)
        )
        feature_frame = feature_frame.dropna(subset=["timestamp"])
        feature_frame = feature_frame.sort_values("timestamp", kind="stable").drop_duplicates(
            subset="timestamp",
            keep="last",
        )
    if symbol in feature_frame.columns:
        feature_frame[feature] = pd.to_numeric(feature_frame[symbol], errors="coerce")
        feature_frame = feature_frame.dropna(subset=[feature])
    else:
        feature_frame[feature] = pd.Series(dtype=float)
        feature_frame = feature_frame.iloc[0:0]

    earliest_timestamps = []
    if not orders.empty:
        earliest_timestamps.append(orders["timestamp"].min())
    if not feature_frame.empty:
        earliest_timestamps.append(feature_frame["timestamp"].min())
    if earliest_timestamps:
        prices, price_files = load_symbol_price_history(
            symbol,
            price_dir,
            start_timestamp=min(earliest_timestamps),
        )
        order_data["prices"] = prices
        order_data["price_files"] = price_files

    feature_points = [
        {"time": int(timestamp.timestamp()), "value": float(value)}
        for timestamp, value in zip(feature_frame["timestamp"], feature_frame[feature])
    ]
    return {
        **order_data,
        "feature": feature,
        "feature_data": feature_points,
        "feature_files": candidate_paths,
        "feature_available": bool(feature_points),
        "feature_strategies": discover_metric_strategies(log_dir),
    }
