from __future__ import annotations

import csv
import json
import math
import os
import re
import builtins as _builtins
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo
from MachineTrader.helpers.timestamp_utils import coerce_datetime_ny, coerce_market_datetime_ny, format_timestamp_ny
from MachineTrader.helpers.api_parsing import (
    normalize_order_status,
    order_to_broker_payload,
    safe_float,
    parse_broker_event_time,
)
from MachineTrader.helpers.api_responses import (
    blotter_event_type_from_status as _blotter_event_type_from_status,
    event_in_group,
    status_in_group,
)

NY_TZ = ZoneInfo("America/New_York")
FILL_MERGE_WINDOW = timedelta(minutes=1)


def discover_dated_csv_files(
    directory: str | Path,
    patterns: list[str] | tuple[str, ...],
    date_pattern: str = r"_(\d{8})\.[cC][sS][vV]$",
) -> list[tuple[str, Path]]:
    """Find matching CSV files and return them in date/name order."""
    root = Path(directory).expanduser()
    date_re = re.compile(date_pattern)
    candidates: dict[Path, str] = {}
    for path in discover_csv_files(root, patterns):
        match = date_re.search(path.name)
        if match:
            token = match.group(1) if match.lastindex else match.group(0)
            candidates[path] = token
    return sorted(((day, path) for path, day in candidates.items()), key=lambda item: (item[0], item[1].name))


def discover_csv_files(
    directory: str | Path,
    patterns: list[str] | tuple[str, ...],
) -> list[Path]:
    """Find unique files matching one or more directory glob patterns."""
    root = Path(directory).expanduser()
    return sorted(
        {
            path
            for pattern in patterns
            for path in root.glob(pattern)
            if path.is_file()
        },
        key=lambda path: path.name.casefold(),
    )


def load_csv_frames(
    paths: list[str | Path] | tuple[str | Path, ...],
    *,
    timestamp_column: str | None = None,
    parse_timestamp: bool = False,
    sort_timestamp: bool = False,
) -> pd.DataFrame:
    """Read and concatenate CSVs, optionally normalizing/sorting a timestamp column."""
    frames: list[pd.DataFrame] = []
    for item in paths:
        try:
            frame = pd.read_csv(item)
        except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
            continue
        frame.columns = [str(column).strip() for column in frame.columns]
        if timestamp_column:
            actual_name = next((column for column in frame.columns if column.casefold() == timestamp_column.casefold()), None)
            if actual_name and actual_name != timestamp_column:
                frame = frame.rename(columns={actual_name: timestamp_column})
        frames.append(frame)

    combined = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    if timestamp_column and timestamp_column in combined.columns and parse_timestamp:
        combined[timestamp_column] = pd.to_datetime(combined[timestamp_column], errors="coerce")
    if timestamp_column and timestamp_column in combined.columns and sort_timestamp:
        combined = combined.sort_values(timestamp_column, kind="stable", na_position="last")
    return combined.reset_index(drop=True)


def _consolidate_nearby_fills(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Combine nearby executions only when order, symbol, and direction match."""
    timed_rows = [
        (parse_broker_event_time(row["timestamp"], timezone=NY_TZ), index, row)
        for index, row in enumerate(rows)
    ]
    timed_rows.sort(
        key=lambda item: (
            item[2]["_order_id"],
            item[2]["symbol"],
            item[2]["fill_price"] > 0,
            item[0] or datetime.min.replace(tzinfo=NY_TZ),
            item[1],
        )
    )

    consolidated: list[dict[str, Any]] = []
    latest_group_by_order: dict[tuple[str, str, bool], dict[str, Any]] = {}
    for event_time, _, row in timed_rows:
        order_id = row["_order_id"]
        key = (order_id, row["symbol"], row["fill_price"] < 0)
        current_group = latest_group_by_order.get(key) if order_id and event_time else None
        if (
            current_group is not None
            and event_time - current_group["_start_time"] < FILL_MERGE_WINDOW
        ):
            current_group["num_shares"] += row["num_shares"]
            current_group["_notional"] += abs(row["fill_price"]) * row["num_shares"]
            sign = -1.0 if current_group["fill_price"] < 0 else 1.0
            current_group["fill_price"] = round(
                sign * current_group["_notional"] / current_group["num_shares"],
                8,
            )
            continue

        group = {
            "timestamp": row["timestamp"],
            "symbol": row["symbol"],
            "num_shares": row["num_shares"],
            "fill_price": row["fill_price"],
            "_start_time": event_time,
            "_notional": abs(row["fill_price"]) * row["num_shares"],
        }
        consolidated.append(group)
        if order_id and event_time:
            latest_group_by_order[key] = group

    consolidated.sort(
        key=lambda row: parse_broker_event_time(row["timestamp"], timezone=NY_TZ)
        or datetime.min.replace(tzinfo=NY_TZ)
    )
    return pd.DataFrame(
        [
            {key: row[key] for key in ("timestamp", "symbol", "num_shares", "fill_price")}
            for row in consolidated
        ],
        columns=["timestamp", "symbol", "num_shares", "fill_price"],
    )


def extract_signed_fills_from_blotters(paths: list[str | Path] | tuple[str | Path, ...]) -> pd.DataFrame:
    """Extract incremental fills and consolidate near-simultaneous executions.

    Executions are combined only when order, symbol, and side match and their
    timestamps span less than one minute. The combined price is share-weighted.
    ``num_shares`` remains positive, while ``fill_price`` is negative for buys
    and positive for sells, matching the signed-price position-queue convention.
    """
    rows: list[dict[str, Any]] = []
    seen_execution_ids: set[str] = set()
    accounted_cumulative_by_order: dict[str, float] = {}
    side_by_order: dict[str, str] = {}

    for path in paths:
        try:
            frame = pd.read_csv(path, dtype=str).fillna("")
        except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
            continue

        frame.columns = [str(column).strip() for column in frame.columns]
        records = frame.to_dict("records")
        records.sort(
            key=lambda row: (
                parse_broker_event_time(row.get("broker_timestamp") or row.get("timestamp"), timezone=NY_TZ)
                or datetime.min.replace(tzinfo=NY_TZ)
            )
        )

        for row in records:
            order_id = str(row.get("order_id", "") or "").strip()
            raw_qty = safe_float(row.get("qty"), 0.0)
            side = str(row.get("side", "") or "").strip().lower()
            if raw_qty > 0.0:
                side = "buy"
            elif raw_qty < 0.0:
                side = "sell"

            event_type = normalize_order_status(row.get("broker_event") or row.get("type") or "")
            if not event_in_group(event_type, "fill_progress"):
                message_status = normalize_order_status(row.get("message", "").split()[0] if row.get("message") else "")
                if not event_in_group(message_status, "fill_progress"):
                    if order_id and side in {"buy", "sell"} and row.get("type", "").strip().lower() == "submit":
                        side_by_order[order_id] = side
                    continue

            if side not in {"buy", "sell"}:
                side = side_by_order.get(order_id, "")
            if side not in {"buy", "sell"}:
                continue

            execution_id = str(row.get("broker_execution_id", "") or "").strip()
            if execution_id and execution_id in seen_execution_ids:
                continue

            cumulative_filled = abs(safe_float(row.get("broker_filled_qty"), 0.0))
            incremental_qty = abs(safe_float(row.get("broker_event_qty"), 0.0))
            if incremental_qty <= 0.0:
                previous_cumulative = accounted_cumulative_by_order.get(order_id, 0.0)
                incremental_qty = max(0.0, cumulative_filled - previous_cumulative)
            if incremental_qty <= 0.0:
                continue

            fill_price = safe_float(
                row.get("broker_event_price") or row.get("filled_avg_price") or row.get("price"),
                0.0,
            )
            if fill_price <= 0.0:
                message = str(row.get("message", ""))
                match = re.search(r"avg_price=([-+]?\d+(?:\.\d+)?)", message)
                fill_price = safe_float(match.group(1), 0.0) if match else 0.0
            if fill_price <= 0.0:
                continue

            raw_timestamp = row.get("broker_timestamp") or row.get("timestamp")
            timestamp = format_timestamp_ny(raw_timestamp, fallback_to_now=False)
            if not timestamp:
                continue

            rows.append(
                {
                    "timestamp": timestamp,
                    "symbol": str(row.get("symbol", "") or "").strip().upper(),
                    "num_shares": incremental_qty,
                    "fill_price": -fill_price if side == "buy" else fill_price,
                    "_order_id": order_id,
                }
            )
            if execution_id:
                seen_execution_ids.add(execution_id)
            if order_id:
                accounted_cumulative_by_order[order_id] = max(
                    accounted_cumulative_by_order.get(order_id, 0.0),
                    cumulative_filled,
                )

    return _consolidate_nearby_fills(rows)


def extract_signed_orders_from_blotters(paths: list[str | Path] | tuple[str | Path, ...]) -> pd.DataFrame:
    """Extract one row per submitted order, matching market fills by order ID.

    The output ``qty`` preserves the blotter sign. ``limit_price`` has the
    opposite sign: buys (positive qty) are negative, sells (negative qty) are
    positive. For both market and limit orders, the price comes from the
    blotter's ``limit_price`` field (or ``broker_limit_price`` alias).
    """
    records: list[tuple[datetime | None, int, dict[str, str]]] = []
    sequence = 0
    for path in paths:
        try:
            frame = pd.read_csv(path, dtype=str).fillna("")
        except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
            continue
        frame.columns = [str(column).strip() for column in frame.columns]
        for row in frame.to_dict("records"):
            raw_timestamp = row.get("broker_timestamp") or row.get("timestamp")
            event_time = parse_broker_event_time(raw_timestamp, timezone=NY_TZ)
            records.append((event_time, sequence, row))
            sequence += 1

    records.sort(key=lambda item: (item[0] or datetime.min.replace(tzinfo=NY_TZ), item[1]))

    submission_types = {"submit", "submitted", "pending_new", "new", "accepted"}
    submissions: dict[str, tuple[datetime | None, int, dict[str, str], str, str, float]] = {}
    execution_ids: set[str] = set()
    cumulative_filled: dict[str, float] = {}
    market_notional: dict[str, float] = {}
    market_fill_qty: dict[str, float] = {}
    market_final_avg_price: dict[str, float] = {}

    for event_time, row_index, row in records:
        order_id = str(row.get("order_id", "") or row.get("broker_client_order_id", "")).strip()
        if not order_id:
            continue

        raw_order_type = str(row.get("order_type") or row.get("broker_order_type") or "").strip().lower()
        order_type = "market" if "market" in raw_order_type else "limit" if "limit" in raw_order_type else ""
        row_status = normalize_order_status(row.get("type", ""))
        event_status = normalize_order_status(row.get("broker_event", ""))
        if order_type and (row_status in submission_types or event_status in submission_types):
            raw_qty = safe_float(row.get("qty") or row.get("broker_qty"), 0.0)
            if raw_qty:
                timestamp = format_timestamp_ny(
                    row.get("timestamp") or row.get("broker_timestamp"),
                    fallback_to_now=False,
                )
                previous = submissions.get(order_id)
                if previous is None:
                    submissions[order_id] = (event_time, row_index, row, order_type, timestamp or "", raw_qty)

        if not event_in_group(event_status or row_status, "fill_progress"):
            continue

        execution_id = str(row.get("broker_execution_id", "") or "").strip()
        if execution_id and execution_id in execution_ids:
            continue

        total_filled = abs(safe_float(row.get("broker_filled_qty"), 0.0))
        incremental_qty = abs(safe_float(row.get("broker_event_qty"), 0.0))
        if incremental_qty <= 0.0:
            incremental_qty = max(0.0, total_filled - cumulative_filled.get(order_id, 0.0))
        if incremental_qty <= 0.0:
            continue

        fill_price = safe_float(
            row.get("broker_event_price") or row.get("filled_avg_price") or row.get("price"),
            0.0,
        )
        message = str(row.get("message", ""))
        average_match = re.search(r"avg_price=([-+]?\d+(?:\.\d+)?)", message)
        if average_match and total_filled > 0.0:
            average_price = safe_float(average_match.group(1), 0.0)
            requested_qty = abs(submissions.get(order_id, (None, 0, {}, "", "", 0.0))[5])
            if average_price > 0.0 and requested_qty > 0.0 and total_filled >= requested_qty:
                market_final_avg_price[order_id] = average_price

        if fill_price <= 0.0 and average_match:
            fill_price = safe_float(average_match.group(1), 0.0)
        if fill_price > 0.0:
            market_notional[order_id] = market_notional.get(order_id, 0.0) + fill_price * incremental_qty
            market_fill_qty[order_id] = market_fill_qty.get(order_id, 0.0) + incremental_qty

        if execution_id:
            execution_ids.add(execution_id)
        cumulative_filled[order_id] = max(cumulative_filled.get(order_id, 0.0), total_filled)

    output_rows: list[dict[str, Any]] = []
    for order_id, (_, _, row, order_type, timestamp, signed_qty) in submissions.items():
        quantity = signed_qty
        price = safe_float(
            row.get("limit_price") or row.get("broker_limit_price"),
            0.0,
        )

        output_rows.append(
            {
                "timestamp": timestamp,
                "symbol": str(row.get("symbol", "") or "").strip().upper(),
                "qty": quantity,
                "limit_price": (-price if quantity > 0 else price) if price > 0.0 else float("nan"),
            }
        )

    output_rows.sort(key=lambda row: row["timestamp"])
    return pd.DataFrame(output_rows, columns=["timestamp", "symbol", "qty", "limit_price"])

# Backward-compat exports used by legacy AlpacaSDK modules.
try:
    from .mt_file_handlers import FileMan, create_daily_file_names, to_float, format_data
except Exception:
    FileMan = None

    def create_daily_file_names(*args, **kwargs):
        raise ImportError("mt_file_handlers.create_daily_file_names is unavailable")

    def to_float(value, default=None):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def format_data(value, decimals=2):
        try:
            return f"{float(value):.{int(decimals)}f}"
        except (TypeError, ValueError):
            return "n/a"

_MESSAGE_FLOAT_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?(?:\d+\.\d+|\d+\.|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z0-9_])")


def round_message_numbers(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        try:
            return f"{float(token):.2f}"
        except (TypeError, ValueError):
            return token
    return _MESSAGE_FLOAT_RE.sub(_replace, text)


def rounded_print(*args, **kwargs):
    rounded_args = [round_message_numbers(arg) if isinstance(arg, str) else arg for arg in args]
    _builtins.print(*rounded_args, **kwargs)


def sanitize_strategy_label(label: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(label or "strategy"))
    return safe[:24] if safe else "strategy"


def build_client_order_id(strategy_label: str, symbol: str) -> str:
    ts = datetime.now(NY_TZ).strftime("%H%M%S%f")
    strategy_key = sanitize_strategy_label(strategy_label)
    symbol_key = str(symbol or "UNK").upper()
    return f"md_{strategy_key}_{symbol_key}_{ts}"[:48]


def strategy_from_client_order_id(client_order_id: str) -> str:
    text = str(client_order_id or "")
    if not text.startswith("md_"):
        return "unattributed"
    payload = text[3:]
    parts = payload.rsplit("_", 2)
    if len(parts) != 3:
        return "unattributed"
    strategy_key, symbol_key, ts_key = parts
    if not strategy_key or not symbol_key or not ts_key:
        return "unattributed"
    return strategy_key

def fmt_optional_number(value: Any, precision: int = 6) -> str:
    try:
        return f"{float(value):.{precision}f}"
    except (TypeError, ValueError):
        return "n/a"


def _resolve_data_dir(dir_name: str | None) -> Path:
    resolved = Path(str(dir_name or "").strip() or ".").expanduser()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _sanitize_path_component(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return "strategy"
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    sanitized = sanitized.strip("._-")
    return sanitized or "strategy"


def _format_optional_number(value: Any, precision: int = 6) -> str:
    try:
        if value is None:
            return ""
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.{precision}f}"


def derive_strategy_report_name(strategy_name: str, suffix: str) -> str:
    strategy_component = _sanitize_path_component(strategy_name)
    suffix_text = str(suffix or "").strip()
    if not strategy_component:
        return suffix_text
    if suffix_text.startswith(strategy_component + "_"):
        return suffix_text
    return f"{strategy_component}_{suffix_text}" if suffix_text else strategy_component


def resolve_csv_path(raw_path: str, default_name: str) -> Path:
    resolved = str(raw_path or "").strip()
    if resolved:
        return Path(resolved).expanduser()
    return Path(str(default_name or "").strip() or "output.csv").expanduser()


def resolve_csv_path_with_strategy_params(raw_path: str, default_name: str, strategy_params: dict[str, Any] | None) -> Path:
    candidate = str(raw_path or "").strip()
    params = strategy_params or {}
    log_dir_name = str(
        params.get("log_dir_name")
        or params.get("LOG_DIR_NAME")
        or ""
    ).strip()
    if not log_dir_name:
        log_dir_name = str(
            params.get("data_dir_name")
            or params.get("DATA_DIR_NAME")
            or ""
        ).strip()
    output_dir = Path(log_dir_name) if log_dir_name else None

    if candidate:
        path = Path(candidate)
        if path.is_absolute() or output_dir is None:
            return path
        return output_dir / path

    if output_dir is not None:
        return output_dir / default_name
    return Path(default_name)


def _resolve_log_csv_path(default_name: str, owner: Any | None = None) -> Path:
    log_dir_name = ""
    if owner is not None:
        strategy_params = getattr(owner, "strategy_params", {})
        if isinstance(strategy_params, dict):
            log_dir_name = str(
                strategy_params.get("log_dir_name", "")
                or strategy_params.get("LOG_DIR_NAME", "")
                or ""
            ).strip()
        if not log_dir_name:
            trading_state = getattr(owner, "trading_state", None)
            log_dir_name = str(getattr(trading_state, "log_dir_name", "") or "").strip()

    if not log_dir_name:
        log_dir_name = str(os.getenv("LOG_DIR_NAME", "") or "").strip()
    if not log_dir_name:
        log_dir_name = "logs"
    return _resolve_data_dir(log_dir_name) / str(default_name or "output.csv").strip()


def _append_dict_rows(path: Path, fieldnames: list[str], rows: list[dict[str, Any]], *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with open(path, "a", newline="", encoding=encoding) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def _append_dict_row(path: Path, fieldnames: list[str], row: dict[str, Any], *, encoding: str = "utf-8") -> None:
    _append_dict_rows(path, fieldnames, [row], encoding=encoding)


def _strategy_name_from_owner(owner) -> str:
    strategy_params = getattr(owner, "strategy_params", {})
    if isinstance(strategy_params, dict):
        from_params = str(strategy_params.get("strategy_name", "") or "").strip()
        if from_params:
            return _sanitize_path_component(from_params)

    trading_state = getattr(owner, "trading_state", None)
    from_state = str(getattr(trading_state, "strategy_name", "") or "").strip()
    if from_state:
        return _sanitize_path_component(from_state)

    from_momentum = str(getattr(owner, "_momentum_strategy_name", "") or "").strip()
    if from_momentum:
        return _sanitize_path_component(from_momentum)

    return "master_driver"


def _strategy_daily_csv_name(owner, stem: str, timezone: ZoneInfo = NY_TZ) -> str:
    strategy_name = _strategy_name_from_owner(owner)
    date_suffix = datetime.now(timezone).strftime("%Y%m%d")
    return f"{strategy_name}_{stem}_{date_suffix}.csv"


def _strategy_eod_report_csv_name(owner) -> str:
    strategy_name = _strategy_name_from_owner(owner)
    return f"{strategy_name}_EODreports.csv"


def build_position_queue_file_name(strategy_name: str, prefix: str = "position") -> str:
    # Keep legacy signature for compatibility, but standardize naming to
    # STRATEGY_NAME_positions.json.
    del prefix
    strategy_component = _sanitize_path_component(strategy_name)
    return f"{strategy_component}_positions.json"


def build_position_queue_path(driver) -> Path:
    strategy_name = str(driver.trading_state.strategy_name or driver.strategy_params.get("strategy_name", "") or "")
    default_name = build_position_queue_file_name(strategy_name)
    return _resolve_log_csv_path(default_name, driver)


def build_legacy_position_queue_path(driver) -> Path:
    if hasattr(driver, "pair") and getattr(driver, "pair", None) is not None:
        symbol1 = str(getattr(driver.pair, "symbol1", "") or "").strip().upper()
        symbol2 = str(getattr(driver.pair, "symbol2", "") or "").strip().upper()
    else:
        symbol1 = str(driver.symbols[0]).strip().upper() if getattr(driver, "symbols", None) else "STOCK1"
        symbol2 = str(driver.symbols[1]).strip().upper() if getattr(driver, "symbols", None) and len(driver.symbols) > 1 else symbol1

    if not symbol1:
        symbol1 = "STOCK1"
    if not symbol2:
        symbol2 = "STOCK2"
    return resolve_csv_path("", f"position_{symbol1}{symbol2}.json")


def load_json_payload(path: Path) -> dict[str, Any] | None:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload if isinstance(payload, dict) else None


def save_json_payload(path: Path, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2, sort_keys=True)


def clear_persisted_position_queues(
    *,
    strategy_name: str,
    log_dir_name: str,
    symbols: list[str] | set[str] | None = None,
) -> Path:
    queue_path = _resolve_data_dir(log_dir_name) / build_position_queue_file_name(strategy_name)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    payload = load_json_payload(queue_path) if queue_path.exists() else {}
    payload = dict(payload or {})

    raw_queue = payload.get("position_queue")
    position_queue = dict(raw_queue) if isinstance(raw_queue, dict) else {}
    symbol_filter = {str(symbol).strip().upper() for symbol in (symbols or []) if str(symbol).strip()}
    if symbol_filter:
        for symbol_key in symbol_filter:
            position_queue[symbol_key] = []
    else:
        position_queue = {str(symbol_key).strip().upper(): [] for symbol_key in position_queue}

    payload["updated_at"] = datetime.now(NY_TZ).isoformat()
    payload["position_queue"] = position_queue
    if "symbols" not in payload:
        payload["symbols"] = sorted(symbol_filter or position_queue.keys())
    payload.setdefault("local_realized_pnl_total", 0.0)
    payload.setdefault("local_realized_pnl_by_symbol", {})
    save_json_payload(queue_path, payload)
    return queue_path


def create_daily_file_names(strategy_name: str, dir_name: str | None, timezone: ZoneInfo = NY_TZ) -> dict[str, str]:
    date_short = datetime.now(timezone).strftime("%Y%m%d")
    data_dir = _resolve_data_dir(dir_name)
    strategy_component = _sanitize_path_component(strategy_name)
    return {
        "state_file": str(data_dir / f"{strategy_component}_state_{date_short}.csv"),
        "submits_file": str(data_dir / f"{strategy_component}_submits_{date_short}.csv"),
        "fills_file": str(data_dir / f"{strategy_component}_fills_{date_short}.csv"),
        "canceled_file": str(data_dir / f"{strategy_component}_canceled_{date_short}.csv"),
        "error_file": str(data_dir / f"{strategy_component}_error_{date_short}.csv"),
    }


def current_price_bars_file_name(symbol: str, dir_name: str | None, timezone: ZoneInfo = NY_TZ) -> str:
    date_short = datetime.now(timezone).strftime("%Y%m%d")
    data_dir = _resolve_data_dir(dir_name)
    return str(data_dir / f"price_bars_{str(symbol).strip().upper()}_{date_short}.csv")


def refresh_order_daily_file_names(dir_name: str | None, timezone: ZoneInfo = NY_TZ) -> dict[str, str]:
    date_short = datetime.now(timezone).strftime("%Y%m%d")
    data_dir = _resolve_data_dir(dir_name)
    return {
        "submits_file": str(data_dir / f"submits_{date_short}.csv"),
        "fills_file": str(data_dir / f"fills_{date_short}.csv"),
        "error_file": str(data_dir / f"error_{date_short}.csv"),
    }


def build_proxy_error_csv_path(dir_name: str | None, timezone: ZoneInfo = NY_TZ) -> Path:
    date_short = datetime.now(timezone).strftime("%Y%m%d")
    data_dir = _resolve_data_dir(dir_name)
    return data_dir / f"proxy_errors_{date_short}.csv"


def append_proxy_error_csv(
    message: str,
    dir_name: str | None,
    *,
    timestamp: datetime | None = None,
    timezone: ZoneInfo = NY_TZ,
):
    path = build_proxy_error_csv_path(dir_name, timezone=timezone)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    stamp = timestamp or datetime.now(timezone)
    timestamp_text = stamp.strftime("%Y-%m-%d %H:%M:%S %Z")
    message_text = str(message or "").replace("\r\n", " ").replace("\n", " ").strip()

    with open(path, "a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        if not file_exists:
            writer.writerow(["line_type", "value"])
        writer.writerow(["timestamp", timestamp_text])
        writer.writerow(["message", message_text])
        writer.writerow([])

    return str(path)


def sync_strategy_daily_file_names(alpaca_sdk, strategy_name: str, dir_name: str | None, timezone: ZoneInfo = NY_TZ) -> dict[str, str]:
    resolved_dir_name = str(dir_name or "").strip() or "./"
    Path(resolved_dir_name).expanduser().mkdir(parents=True, exist_ok=True)
    file_names = create_daily_file_names(strategy_name, resolved_dir_name, timezone)
    alpaca_sdk.state_file = file_names["state_file"]
    alpaca_sdk.submits_file = None
    alpaca_sdk.fills_file = file_names["fills_file"]
    alpaca_sdk.canceled_file = file_names["canceled_file"]
    alpaca_sdk.error_file = file_names["error_file"]

    if not bool(getattr(alpaca_sdk, "_daily_file_paths_announced", False)):
        print(
            "📁 Strategy file paths:",
            f"state={file_names['state_file']}, submits=disabled, "
            f"fills={file_names['fills_file']}, canceled={file_names['canceled_file']}, "
            f"error={file_names['error_file']}",
        )
        setattr(alpaca_sdk, "_daily_file_paths_announced", True)

    return file_names


def bar_date_from_event(
    event: dict,
    fallback_tz: ZoneInfo = NY_TZ,
    date_format: str = "%Y-%m-%d",
) -> str:
    raw_timestamp = str(event.get("t", "") or "").strip()
    if raw_timestamp:
        parsed = coerce_market_datetime_ny(raw_timestamp, fallback_to_now=False)
        if parsed is not None:
            return parsed.astimezone(fallback_tz).strftime(date_format)
    return datetime.now(fallback_tz).strftime(date_format)


def bar_timestamp_from_event(
    event: dict,
    fallback_tz: ZoneInfo = NY_TZ,
    timestamp_format: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    raw_timestamp = str(event.get("t", "") or "").strip()
    if raw_timestamp:
        parsed = coerce_market_datetime_ny(raw_timestamp, fallback_to_now=False)
        if parsed is not None:
            return parsed.astimezone(fallback_tz).strftime(timestamp_format)
    return datetime.now(fallback_tz).strftime(timestamp_format)


def _latest_bar_timestamp_text(
    bars_for_minute: dict[str, dict[str, Any]] | None,
    *,
    timezone: ZoneInfo = NY_TZ,
    fallback_text: str = "",
    fallback_to_now: bool = True,
) -> str:
    bars = bars_for_minute if isinstance(bars_for_minute, dict) else {}
    parsed_candidates: list[datetime] = []
    for bar in bars.values():
        if not isinstance(bar, dict):
            continue
        raw_ts = bar.get("t", bar.get("timestamp"))
        if raw_ts is None:
            continue
        parsed_dt = coerce_market_datetime_ny(raw_ts, fallback_to_now=False)
        if parsed_dt is None:
            continue
        parsed_candidates.append(parsed_dt.astimezone(timezone))

    if parsed_candidates:
        return max(parsed_candidates).strftime("%Y-%m-%d %H:%M:%S")

    if fallback_text:
        return str(fallback_text)
    if fallback_to_now:
        return datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")
    return ""


def append_bar_to_symbol_date_csv(
    event: dict,
    data_dir_name: str | Path,
    fallback_tz: ZoneInfo = NY_TZ,
    date_format: str = "%Y-%m-%d",
    timestamp_format: str = "%Y-%m-%d %H:%M:%S",
) -> str | None:
    symbol = str(event.get("S", "") or "").strip().upper()
    if not symbol:
        return None

    data_dir_path = _resolve_data_dir(str(data_dir_name))
    target_date = bar_date_from_event(
        event,
        fallback_tz=fallback_tz,
        date_format=date_format,
    )
    file_path = data_dir_path / f"{symbol}_{target_date}.csv"
    row = {
        "symbol": symbol,
        "timestamp": bar_timestamp_from_event(
            event,
            fallback_tz=fallback_tz,
            timestamp_format=timestamp_format,
        ),
        "open": event.get("o"),
        "high": event.get("h"),
        "low": event.get("l"),
        "close": event.get("c"),
        "volume": event.get("v"),
        "trade_count": event.get("n"),
        "vwap": event.get("vw"),
    }

    _append_dict_row(file_path, list(row.keys()), row, encoding="utf-8")

    return str(file_path)


def compute_momentum_symbol_pnl_maps(
    driver,
    unrealized_by_symbol: dict[str, float] | None,
) -> tuple[dict[str, float], dict[str, float], dict[str, float], float, float]:
    return compute_symbol_pnl_maps(
        required_symbols=getattr(driver, "required_symbols", set()),
        unrealized_by_symbol=unrealized_by_symbol,
        realized_by_symbol=getattr(driver, "_local_realized_pnl_by_symbol", {}),
    )


def compute_symbol_pnl_maps(
    *,
    required_symbols: set[str] | list[str] | tuple[str, ...],
    unrealized_by_symbol: dict[str, float] | None,
    realized_by_symbol: dict[str, float] | None,
) -> tuple[dict[str, float], dict[str, float], dict[str, float], float, float]:
    symbol_unrealized: dict[str, float] = {}
    symbol_realized: dict[str, float] = {}
    symbol_total: dict[str, float] = {}

    raw_unrealized = unrealized_by_symbol if isinstance(unrealized_by_symbol, dict) else {}
    raw_realized = realized_by_symbol if isinstance(realized_by_symbol, dict) else {}
    if not isinstance(raw_realized, dict):
        raw_realized = {}

    normalized_required = {str(symbol).strip().upper() for symbol in (required_symbols or set()) if str(symbol).strip()}
    for symbol_key in sorted(normalized_required):
        unreal_value = float(raw_unrealized.get(symbol_key, 0.0) or 0.0)
        realized_value = float(raw_realized.get(symbol_key, 0.0) or 0.0)
        total_value = unreal_value + realized_value
        symbol_unrealized[symbol_key] = unreal_value
        symbol_realized[symbol_key] = realized_value
        symbol_total[symbol_key] = total_value

    strategy_unrealized = float(sum(symbol_unrealized.values()))
    strategy_realized = float(sum(symbol_realized.values()))
    return symbol_unrealized, symbol_realized, symbol_total, strategy_unrealized, strategy_realized


def ordered_symbol_columns(symbols: list[Any] | tuple[Any, ...] | set[Any] | None) -> list[str]:
    normalized = {str(symbol).strip().upper() for symbol in (symbols or []) if str(symbol).strip()}
    return sorted(normalized)


def _momentum_ordered_symbols(driver) -> list[str]:
    configured_symbols_raw = driver.strategy_params.get("strategy_symbols", []) if isinstance(driver.strategy_params, dict) else []
    configured_symbols = ordered_symbol_columns(configured_symbols_raw)
    if configured_symbols:
        return configured_symbols
    return ordered_symbol_columns(driver.required_symbols)


def build_momentum_symbol_snapshot_csv_path(driver, snapshot_kind: str) -> Path:
    if snapshot_kind in {"pnls", "total_pnl"}:
        suffix = _strategy_daily_csv_name(driver, "pnls")
    elif snapshot_kind == "positions":
        suffix = _strategy_daily_csv_name(driver, "positions")
    elif snapshot_kind == "posalpaca":
        suffix = _strategy_daily_csv_name(driver, "posalpaca")
    elif snapshot_kind == "targets":
        suffix = _strategy_daily_csv_name(driver, "targets")
    else:
        raise ValueError(f"Unsupported momentum snapshot kind: {snapshot_kind}")

    return _resolve_log_csv_path(suffix, driver)


def append_momentum_symbol_snapshot_csv(
    driver,
    *,
    snapshot_kind: str,
    timestamp_text: str,
    values_by_symbol: dict[str, float],
):
    path = build_momentum_symbol_snapshot_csv_path(driver, snapshot_kind)
    ordered_symbols = _momentum_ordered_symbols(driver)
    fieldnames = ["timestamp", *ordered_symbols]
    row: dict[str, str] = {
        "timestamp": str(timestamp_text),
    }
    for symbol_key in ordered_symbols:
        row[symbol_key] = driver._fmt_optional_number(values_by_symbol.get(symbol_key, 0.0), precision=6)

    _append_dict_row(path, fieldnames, row)


def append_momentum_total_pnl_and_positions_csv(
    driver,
    *,
    timestamp_text: str,
    merged_local_queue: dict[str, list[float]] | None,
    symbol_total_pnl_by_symbol: dict[str, float],
):
    queue_map = merged_local_queue if isinstance(merged_local_queue, dict) else {}
    positions_by_symbol: dict[str, float] = {}
    targets_by_symbol: dict[str, float] = {}
    for symbol_key in _momentum_ordered_symbols(driver):
        queue = queue_map.get(symbol_key, [])
        if not isinstance(queue, list):
            positions_by_symbol[symbol_key] = 0.0
        else:
            positions_by_symbol[symbol_key] = float(driver._signed_queue_to_qty(queue)) if queue else 0.0

        target_value = 0.0
        if hasattr(driver, "_extract_symbol_indicators"):
            indicators = driver._extract_symbol_indicators(symbol_key)
            if isinstance(indicators, dict):
                raw_target = indicators.get("target", indicators.get("entry_target", 0.0))
                try:
                    target_value = float(raw_target)
                except (TypeError, ValueError):
                    target_value = 0.0
        targets_by_symbol[symbol_key] = target_value

    append_momentum_symbol_snapshot_csv(
        driver,
        snapshot_kind="pnls",
        timestamp_text=timestamp_text,
        values_by_symbol=symbol_total_pnl_by_symbol,
    )
    append_momentum_symbol_snapshot_csv(
        driver,
        snapshot_kind="positions",
        timestamp_text=timestamp_text,
        values_by_symbol=positions_by_symbol,
    )
    append_momentum_symbol_snapshot_csv(
        driver,
        snapshot_kind="targets",
        timestamp_text=timestamp_text,
        values_by_symbol=targets_by_symbol,
    )

    # Persist broker-reported (Alpaca) signed share positions separately.
    alpaca_positions_by_symbol: dict[str, float] = {symbol_key: 0.0 for symbol_key in _momentum_ordered_symbols(driver)}
    trading_client = getattr(driver, "trading_client", None)
    if trading_client is not None:
        try:
            broker_positions_raw = trading_client.get_all_positions()
        except Exception:
            broker_positions_raw = []

        for pos in broker_positions_raw or []:
            symbol_key = str(getattr(pos, "symbol", "") or "").strip().upper()
            if not symbol_key or symbol_key not in alpaca_positions_by_symbol:
                continue

            try:
                qty_raw = float(getattr(pos, "qty", 0.0) or 0.0)
            except Exception:
                qty_raw = 0.0
            qty_abs = abs(qty_raw)
            side_text = str(getattr(pos, "side", "") or "").strip().lower()
            if side_text.endswith("short") or side_text == "sell":
                signed_qty = -qty_abs
            elif side_text.endswith("long") or side_text == "buy":
                signed_qty = qty_abs
            else:
                signed_qty = qty_raw

            alpaca_positions_by_symbol[symbol_key] = float(signed_qty)

    append_momentum_symbol_snapshot_csv(
        driver,
        snapshot_kind="posalpaca",
        timestamp_text=timestamp_text,
        values_by_symbol=alpaca_positions_by_symbol,
    )


def build_momentum_message_csv_path(driver, message_kind: str) -> Path:
    if message_kind != "heartbeat":
        return build_message_csv_path(driver, message_kind)

    default_name = _strategy_daily_csv_name(driver, "heartbeat")
    return _resolve_log_csv_path(default_name, driver)


def append_momentum_message_csv(driver, minute_text: str, message_text: str, message_kind: str):
    if message_kind != "heartbeat":
        return append_message_csv(driver, minute_text, message_text, message_kind)

    path = build_momentum_message_csv_path(driver, message_kind)
    fieldnames = [
        "timestamp",
        "symbol",
        "position",
        "pnlReal",
        "pnlUnreal",
        "limit_orders",
        "broker_message",
    ]

    row = {
        "timestamp": str(minute_text),
        "symbol": getattr(driver, "_momentum_strategy_name", "master_driver"),
        "position": "0",
        "pnlReal": "0",
        "pnlUnreal": "0",
        "limit_orders": "0",
        "broker_message": "none",
    }

    if isinstance(message_text, dict):
        row["timestamp"] = str(message_text.get("timestamp", row["timestamp"]) or row["timestamp"])
        row["symbol"] = str(message_text.get("symbol", row["symbol"]) or row["symbol"])
        row["position"] = str(message_text.get("position", "0") or "0")
        row["pnlReal"] = str(message_text.get("pnlReal", "0") or "0")
        row["pnlUnreal"] = str(message_text.get("pnlUnreal", "0") or "0")
        row["limit_orders"] = str(message_text.get("limit_orders", "0") or "0")
        row["broker_message"] = str(message_text.get("broker_message", "none") or "none")

    _append_dict_row(path, fieldnames, row)


def build_message_csv_path(driver, message_kind: str) -> Path:
    if message_kind == "bar":
        default_name = _strategy_daily_csv_name(driver, "bar_messages")
    elif message_kind == "heartbeat":
        default_name = _strategy_daily_csv_name(driver, "heartbeat")
    else:
        raise ValueError(f"Unsupported message kind for csv output: {message_kind}")

    return _resolve_log_csv_path(default_name, driver)


def print_heartbeat_csv_path(driver):
    try:
        path = build_message_csv_path(driver, "heartbeat")
    except Exception as exc:
        print("⚠️ ", f"Unable to resolve heartbeat csv path: {exc}")
        return
    print("📄 ", f"Heartbeat csv path: {path}")


def build_strategy_ema_csv_path(owner) -> Path:
    default_name = _strategy_daily_csv_name(owner, "ema")
    return _resolve_log_csv_path(default_name, owner)


def build_strategy_vol_csv_path(owner) -> Path:
    default_name = _strategy_daily_csv_name(owner, "vol")
    return _resolve_log_csv_path(default_name, owner)


def _timestamp_from_minute_bars(minute_bars: dict[str, dict[str, Any]] | None, timezone: ZoneInfo = NY_TZ) -> str:
    return _latest_bar_timestamp_text(minute_bars, timezone=timezone, fallback_to_now=False)


def symbols_with_new_price_bars(minute_bars: dict[str, dict[str, Any]] | None) -> set[str]:
    fresh_symbols: set[str] = set()
    for symbol, bar in (minute_bars or {}).items():
        if not isinstance(bar, dict):
            continue
        raw_timestamp = bar.get("t", bar.get("timestamp"))
        if coerce_market_datetime_ny(raw_timestamp, fallback_to_now=False) is None:
            continue
        raw_price = bar.get("c", bar.get("close"))
        try:
            float(raw_price)
        except (TypeError, ValueError):
            continue
        fresh_symbols.add(str(symbol).strip().upper())
    return fresh_symbols


def append_strategy_symbol_metric_csv(
    owner,
    *,
    minute_bars: dict[str, dict[str, Any]] | None,
    values_by_symbol: dict[str, float | None],
    symbol_order: list[str] | None = None,
    stem: str,
) -> str:
    ordered_symbols = ordered_symbol_columns(symbol_order)
    if not ordered_symbols:
        ordered_symbols = ordered_symbol_columns(list(values_by_symbol.keys()))

    timestamp_text = _timestamp_from_minute_bars(minute_bars, timezone=NY_TZ)
    if not timestamp_text:
        return ""
    date_suffix = timestamp_text[:10].replace("-", "")
    strategy_name = _strategy_name_from_owner(owner)
    default_name = f"{strategy_name}_{stem}_{date_suffix}.csv"
    path = _resolve_log_csv_path(default_name, owner)
    fieldnames = ["timestamp", *ordered_symbols]
    row: dict[str, str] = {
        "timestamp": str(timestamp_text),
    }
    for symbol_key in ordered_symbols:
        value = values_by_symbol.get(symbol_key)
        row[symbol_key] = "NA" if value is None else _format_optional_number(value, precision=6)

    if path.exists():
        with open(path, "r", newline="", encoding="utf-8") as existing_file:
            existing_header = next(csv.reader(existing_file), [])
        if existing_header != fieldnames:
            legacy_path = path.with_name(f"{path.stem}.legacy_long{path.suffix}")
            archive_index = 2
            while legacy_path.exists():
                legacy_path = path.with_name(f"{path.stem}.legacy_long_{archive_index}{path.suffix}")
                archive_index += 1
            path.replace(legacy_path)

    _append_dict_row(path, fieldnames, row)
    return str(path)


def append_strategy_symbol_indicator_csvs(
    owner,
    *,
    minute_bars: dict[str, dict[str, Any]] | None,
    zscores_by_symbol: dict[str, float | None],
    symbol_order: list[str] | None = None,
    ema_by_symbol: dict[str, float | None] | None = None,
    volatility_by_symbol: dict[str, float | None] | None = None,
) -> str:
    strategy_params = getattr(owner, "strategy_params", {})
    if isinstance(strategy_params, dict) and strategy_params.get("disable_live_reporting", False):
        return ""

    path = append_strategy_symbol_metric_csv(
        owner,
        minute_bars=minute_bars,
        values_by_symbol=zscores_by_symbol,
        symbol_order=symbol_order,
        stem="zscore",
    )
    if isinstance(ema_by_symbol, dict) and ema_by_symbol:
        append_strategy_symbol_metric_csv(
            owner,
            minute_bars=minute_bars,
            values_by_symbol=ema_by_symbol,
            symbol_order=symbol_order,
            stem="ema",
        )
    if isinstance(volatility_by_symbol, dict) and volatility_by_symbol:
        append_strategy_symbol_metric_csv(
            owner,
            minute_bars=minute_bars,
            values_by_symbol=volatility_by_symbol,
            symbol_order=symbol_order,
            stem="vol",
        )
    return str(path)


def append_strategy_symbol_zscores_state_csv(
    owner,
    *,
    minute_bars: dict[str, dict[str, Any]] | None,
    zscores_by_symbol: dict[str, float | None],
    symbol_order: list[str] | None = None,
    ema_by_symbol: dict[str, float | None] | None = None,
    volatility_by_symbol: dict[str, float | None] | None = None,
) -> str:
    return append_strategy_symbol_indicator_csvs(
        owner,
        minute_bars=minute_bars,
        zscores_by_symbol=zscores_by_symbol,
        symbol_order=symbol_order,
        ema_by_symbol=ema_by_symbol,
        volatility_by_symbol=volatility_by_symbol,
    )


def normalize_console_csv_message_fields(message_text: str) -> str:
    text = str(message_text or "")
    text = re.sub(r"\blocal_position_queue\b", "position_queue", text)
    text = re.sub(r"\bcurrent_price\b", "price", text)
    text = text.replace("pnl_unrealized_local=", "pnl_unrealized=")
    text = text.replace("pnl_realized_local=", "pnl_realized=")
    return text


def append_broker_response_message(
    owner,
    message_text: str,
    *,
    event_time: datetime | None = None,
    timezone: ZoneInfo = NY_TZ,
    keep_seconds: float = 300.0,
):
    text = str(message_text or "").strip()
    if not text:
        return

    now_dt = event_time if isinstance(event_time, datetime) else datetime.now(timezone)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone)
    else:
        now_dt = now_dt.astimezone(timezone)

    recent = getattr(owner, "_broker_response_messages_recent", None)
    if not isinstance(recent, list):
        recent = []
    recent.append((now_dt, text))

    cutoff = now_dt.timestamp() - max(1.0, float(keep_seconds))
    owner._broker_response_messages_recent = [
        (msg_dt, msg_text)
        for msg_dt, msg_text in recent
        if isinstance(msg_dt, datetime) and msg_dt.timestamp() >= cutoff
    ]


def is_insufficient_buying_power_message(message_text: str) -> bool:
    text = str(message_text or "").strip().lower()
    if not text:
        return False
    has_buying_power = "buying power" in text
    has_insufficient_marker = any(
        marker in text
        for marker in (
            "insufficient",
            "not enough",
            "too low",
            "exceeds",
            "insuff",
        )
    )
    return bool(has_buying_power and has_insufficient_marker)


def recent_broker_response_messages_text(
    owner,
    *,
    lookback_seconds: float = 60.0,
    timezone: ZoneInfo = NY_TZ,
    keep_seconds: float = 300.0,
    warning_only: bool = False,
) -> str:
    now_dt = datetime.now(timezone)
    lookback_cutoff = now_dt.timestamp() - max(1.0, float(lookback_seconds))

    recent = getattr(owner, "_broker_response_messages_recent", None)
    if not isinstance(recent, list):
        recent = []

    recent_rows: list[tuple[datetime, str]] = []
    for msg_dt, msg_text in recent:
        if not isinstance(msg_dt, datetime):
            continue
        if msg_dt.timestamp() >= lookback_cutoff:
            message_text = str(msg_text)
            if warning_only and not is_insufficient_buying_power_message(message_text):
                continue
            recent_rows.append((msg_dt, message_text))

    keep_cutoff = now_dt.timestamp() - max(1.0, float(keep_seconds))
    owner._broker_response_messages_recent = [
        (msg_dt, str(msg_text))
        for msg_dt, msg_text in recent
        if isinstance(msg_dt, datetime) and msg_dt.timestamp() >= keep_cutoff
    ]

    if not recent_rows:
        return "none"

    parts: list[str] = []
    for msg_dt, msg_text in recent_rows:
        parts.append(f"{msg_dt.strftime('%H:%M:%S')} {msg_text}")
    return " ; ".join(parts)


def sync_trade_blotter_broker_updates(driver: Any) -> None:
    collector = getattr(driver, "_collect_submitted_orders_by_id", None)
    if callable(collector):
        orders_by_id = collector()
    else:
        orders_by_id = {}
    for order in orders_by_id.values():
        # Keep blotter and local queue in sync from the same broker update feed.
        # Poll both OPEN and CLOSED submitted orders so a missed confirmation-stream
        # fill still reaches the single fill-accounting path.
        # Fill application is deduped by order_id + cumulative filled_qty in
        # apply_confirmed_fill_to_working_balance, so repeated polling snapshots
        # do not double-apply fills.
        driver._ingest_broker_order_update(order, apply_fill_updates=True)


def append_message_csv(driver, minute_text: str, message_text: str, message_kind: str):
    if message_kind != "heartbeat":
        # Persist only heartbeat rows via message CSV writer.
        return

    path = build_message_csv_path(driver, message_kind)
    file_exists = path.exists()
    fieldnames = [
        "timestamp",
        "symbol",
        "shares",
        "price",
        "pnlReal",
        "pnlUnreal",
        "limit_orders",
        "broker_message",
    ]

    schema_mismatch_detected = False
    if file_exists:
        try:
            with open(path, "r", encoding="utf-8") as f:
                first_line = str(f.readline() or "")
            first_line = first_line.lstrip("\ufeff").strip().lower()
            expected_header = ",".join(fieldnames).lower()
            schema_mismatch_detected = first_line != expected_header
        except Exception:
            schema_mismatch_detected = False

    if schema_mismatch_detected:
        file_exists = False

    row = {
        "timestamp": str(minute_text),
        "symbol": "",
        "shares": "0",
        "price": "None",
        "pnlReal": "0",
        "pnlUnreal": "0",
        "limit_orders": "0",
        "broker_message": "none",
    }

    if isinstance(message_text, dict):
        row["timestamp"] = str(message_text.get("timestamp", minute_text) or minute_text)
        row["symbol"] = str(message_text.get("symbol", "") or "")
        row["shares"] = str(message_text.get("shares", "0") or "0")
        row["price"] = str(message_text.get("price", "None") or "None")
        row["pnlReal"] = str(message_text.get("pnlReal", "0") or "0")
        row["pnlUnreal"] = str(message_text.get("pnlUnreal", "0") or "0")
        row["limit_orders"] = str(message_text.get("limit_orders", "0") or "0")
        row["broker_message"] = str(message_text.get("broker_message", "none") or "none")
    else:
        normalized_message_text = normalize_console_csv_message_fields(message_text)
        row["broker_message"] = str(normalized_message_text or "none")

    _append_dict_row(path, fieldnames, row)


def build_eod_report_path(driver) -> Path:
    explicit_report_file = str(driver.strategy_params.get("eod_report_file", "") or "").strip()
    if explicit_report_file:
        return resolve_csv_path(explicit_report_file, "EODreports.csv")

    default_name = _strategy_eod_report_csv_name(driver)
    return _resolve_log_csv_path(default_name or "EODreports.csv", driver)


def _write_momentum_eod_report_if_needed(
    driver,
    minute_key: tuple[int, int, int, int, int],
    account_snapshot: dict[str, Any],
    positions_snapshot: dict[str, dict[str, Any]],
):
    y, m, d, hh, mm = minute_key
    day_key = f"{y:04d}-{m:02d}-{d:02d}"
    if day_key in driver._eod_report_written_days:
        return

    report_path = build_eod_report_path(driver)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = report_path.exists()

    known_status_by_id = driver._collect_submitted_order_statuses_by_id()
    accepted_counts = driver._collect_accepted_order_counts_by_symbol(known_status_by_id)
    cancelled_counts = driver._collect_cancelled_order_counts_by_symbol(known_status_by_id)
    rejected_counts = driver._collect_rejected_order_counts_by_symbol(known_status_by_id)
    pnl_by_symbol = account_snapshot.get("unrealized_pnl_by_symbol", {}) if isinstance(account_snapshot, dict) else {}

    report_timestamp = driver._timestamp_from_bar_or_now()
    fieldnames = [
        "timestamp",
        "symbol",
        "total_pnl_close",
        "total_pnl_high",
        "total_pnl_low",
        "ending_shares",
        "num_submits",
        "num_accepted",
        "num_cancelled",
        "num_rejected",
    ]

    rows: list[dict[str, Any]] = []
    realized_local_total = driver._safe_float(account_snapshot.get("realized_pnl_local"), default=0.0)
    total_unrealized_local = driver._safe_float(
        account_snapshot.get("unrealized_pnl_total"),
        default=sum(driver._safe_float(value, default=0.0) for value in pnl_by_symbol.values()),
    )
    strategy_total_pnl_close = realized_local_total + total_unrealized_local
    strategy_total_pnl_high = driver._safe_float(driver._daily_total_pnl_high, default=strategy_total_pnl_close)
    strategy_total_pnl_low = driver._safe_float(driver._daily_total_pnl_low, default=strategy_total_pnl_close)

    for symbol_key in sorted(driver.required_symbols):
        ending_shares = driver._safe_float(positions_snapshot.get(symbol_key, {}).get("qty", 0.0), default=0.0)
        rows.append(
            {
                "timestamp": report_timestamp,
                "symbol": str(getattr(driver, "_momentum_strategy_name", "master_driver") or "master_driver"),
                "total_pnl_close": str(strategy_total_pnl_close),
                "total_pnl_high": str(strategy_total_pnl_high),
                "total_pnl_low": str(strategy_total_pnl_low),
                "ending_shares": str(ending_shares),
                "num_submits": int(driver._submitted_order_count_by_symbol.get(symbol_key, 0) or 0),
                "num_accepted": int(accepted_counts.get(symbol_key, 0) or 0),
                "num_cancelled": int(cancelled_counts.get(symbol_key, 0) or 0),
                "num_rejected": int(rejected_counts.get(symbol_key, 0) or 0),
            }
        )

    with open(report_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    driver._eod_report_written_days.add(day_key)
    print("🧾 ", f"Momentum EOD report saved: {report_path} rows={len(rows)}")


def write_eod_report_if_needed(
    driver,
    minute_key: tuple[int, int, int, int, int],
    account_snapshot: dict[str, Any],
    positions_snapshot: dict[str, dict[str, Any]],
):
    if hasattr(driver, "_momentum_strategy_name"):
        return _write_momentum_eod_report_if_needed(driver, minute_key, account_snapshot, positions_snapshot)

    y, m, d, hh, mm = minute_key
    day_key = f"{y:04d}-{m:02d}-{d:02d}"
    if day_key in driver._eod_report_written_days:
        return

    report_path = build_eod_report_path(driver)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = report_path.exists()

    known_status_by_id = driver._collect_submitted_order_statuses_by_id()
    accepted_counts = driver._collect_accepted_order_counts_by_symbol(known_status_by_id)
    cancelled_counts = driver._collect_cancelled_order_counts_by_symbol(known_status_by_id)
    rejected_counts = driver._collect_rejected_order_counts_by_symbol(known_status_by_id)
    pnl_by_symbol = account_snapshot.get("unrealized_pnl_by_symbol", {}) if isinstance(account_snapshot, dict) else {}

    report_timestamp = driver._timestamp_from_bar_or_now()
    fieldnames = [
        "timestamp",
        "symbol",
        "order_type",
        "stock_pnl",
        "open",
        "high",
        "low",
        "close",
        "total_pnl_close",
        "total_pnl_high",
        "total_pnl_low",
        "ending_shares",
        "num_submits",
        "num_accepted",
        "num_cancelled",
        "num_rejected",
    ]

    rows: list[dict[str, Any]] = []
    realized_local_total = driver._safe_float(account_snapshot.get("realized_pnl_local"), default=0.0)
    total_unrealized_local = driver._safe_float(
        account_snapshot.get("unrealized_pnl_total"),
        default=sum(driver._safe_float(value, default=0.0) for value in pnl_by_symbol.values()),
    )
    strategy_total_pnl_close = realized_local_total + total_unrealized_local
    strategy_total_pnl_high = driver._safe_float(driver._daily_total_pnl_high, default=strategy_total_pnl_close)
    strategy_total_pnl_low = driver._safe_float(driver._daily_total_pnl_low, default=strategy_total_pnl_close)

    for symbol_key in sorted(driver.required_symbols):
        stats = driver._daily_symbol_stats.get(symbol_key, {})

        day_open = driver._safe_float(stats.get("open"), default=0.0)
        day_high = driver._safe_float(stats.get("high"), default=0.0)
        day_low = driver._safe_float(stats.get("low"), default=0.0)
        day_close = driver._safe_float(stats.get("close"), default=0.0)

        session_open = driver._safe_float(stats.get("session_open"), default=0.0)
        session_close = driver._safe_float(stats.get("session_close"), default=0.0)
        stock_pnl = 0.0
        if session_open > 0.0 and session_close > 0.0:
            stock_pnl = session_close - session_open

        ending_shares = driver._safe_float(positions_snapshot.get(symbol_key, {}).get("qty", 0.0), default=0.0)
        order_types = {str(t).lower() for t in driver._submitted_order_types_by_symbol.get(symbol_key, set()) if str(t).strip()}
        if "market" in order_types:
            order_type_text = "market"
        elif "limit" in order_types:
            order_type_text = "limit"
        else:
            order_type_text = "none"

        rows.append(
            {
                "timestamp": report_timestamp,
                "symbol": symbol_key,
                "order_type": order_type_text,
                "stock_pnl": str(stock_pnl),
                "open": str(day_open),
                "high": str(day_high),
                "low": str(day_low),
                "close": str(day_close),
                "total_pnl_close": str(strategy_total_pnl_close),
                "total_pnl_high": str(strategy_total_pnl_high),
                "total_pnl_low": str(strategy_total_pnl_low),
                "ending_shares": str(ending_shares),
                "num_submits": int(driver._submitted_order_count_by_symbol.get(symbol_key, 0) or 0),
                "num_accepted": int(accepted_counts.get(symbol_key, 0) or 0),
                "num_cancelled": int(cancelled_counts.get(symbol_key, 0) or 0),
                "num_rejected": int(rejected_counts.get(symbol_key, 0) or 0),
            }
        )

    with open(report_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    driver._eod_report_written_days.add(day_key)
    print("🧾 ", f"EOD report saved: {report_path} rows={len(rows)}")


def write_pair_eod_report_if_needed(
    driver,
    minute_key: tuple[int, int, int, int, int],
    account_snapshot: dict[str, Any],
    positions_snapshot: dict[str, dict[str, Any]],
):
    y, m, d, hh, mm = minute_key
    day_key = f"{y:04d}-{m:02d}-{d:02d}"
    if day_key in driver._eod_report_written_days:
        return

    report_path = build_eod_report_path(driver)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = report_path.exists()

    known_status_by_id = driver._collect_submitted_order_statuses_by_id()
    accepted_counts = driver._collect_accepted_order_counts_by_symbol(known_status_by_id)
    cancelled_counts = driver._collect_cancelled_order_counts_by_symbol(known_status_by_id)
    rejected_counts = driver._collect_rejected_order_counts_by_symbol(known_status_by_id)

    q1 = float(driver.pair.quantity1)
    q2 = float(driver.pair.quantity2)
    s1 = driver.pair.symbol1
    s2 = driver.pair.symbol2

    stats1 = driver._daily_symbol_stats.get(s1, {})
    stats2 = driver._daily_symbol_stats.get(s2, {})

    open1 = driver._safe_float(stats1.get("open"), default=0.0)
    high1 = driver._safe_float(stats1.get("high"), default=0.0)
    low1 = driver._safe_float(stats1.get("low"), default=0.0)
    close1 = driver._safe_float(stats1.get("close"), default=0.0)

    open2 = driver._safe_float(stats2.get("open"), default=0.0)
    high2 = driver._safe_float(stats2.get("high"), default=0.0)
    low2 = driver._safe_float(stats2.get("low"), default=0.0)
    close2 = driver._safe_float(stats2.get("close"), default=0.0)

    pair_open = q1 * open1 - q2 * open2
    pair_high = q1 * high1 - q2 * high2
    pair_low = q1 * low1 - q2 * low2
    pair_close = q1 * close1 - q2 * close2

    session_open1 = driver._safe_float(stats1.get("session_open"), default=0.0)
    session_close1 = driver._safe_float(stats1.get("session_close"), default=0.0)
    session_open2 = driver._safe_float(stats2.get("session_open"), default=0.0)
    session_close2 = driver._safe_float(stats2.get("session_close"), default=0.0)
    pnl1 = (session_close1 - session_open1) if (session_open1 > 0.0 and session_close1 > 0.0) else 0.0
    pnl2 = (session_close2 - session_open2) if (session_open2 > 0.0 and session_close2 > 0.0) else 0.0
    pair_stock_pnl = q1 * pnl1 - q2 * pnl2

    realized_local_total = driver._safe_float(account_snapshot.get("realized_pnl_local"), default=0.0)
    total_unrealized_local = driver._safe_float(
        account_snapshot.get("unrealized_pnl_total"),
        default=0.0,
    )
    pair_total_pnl_close = realized_local_total + total_unrealized_local
    pair_total_pnl_high = driver._safe_float(driver._daily_total_pnl_high, default=pair_total_pnl_close)
    pair_total_pnl_low = driver._safe_float(driver._daily_total_pnl_low, default=pair_total_pnl_close)

    ending_shares = (
        driver._safe_float(positions_snapshot.get(s1, {}).get("qty", 0.0), default=0.0)
        + driver._safe_float(positions_snapshot.get(s2, {}).get("qty", 0.0), default=0.0)
    )

    num_submits = int(driver._submitted_order_count_by_symbol.get(s1, 0) or 0) + int(
        driver._submitted_order_count_by_symbol.get(s2, 0) or 0
    )
    num_accepted = int(accepted_counts.get(s1, 0) or 0) + int(accepted_counts.get(s2, 0) or 0)
    num_cancelled = int(cancelled_counts.get(s1, 0) or 0) + int(cancelled_counts.get(s2, 0) or 0)
    num_rejected = int(rejected_counts.get(s1, 0) or 0) + int(rejected_counts.get(s2, 0) or 0)

    all_order_types = {
        str(order_type).lower()
        for symbol_key in (s1, s2)
        for order_type in driver._submitted_order_types_by_symbol.get(symbol_key, set())
        if str(order_type).strip()
    }
    if "market" in all_order_types:
        order_type_text = "market"
    elif "limit" in all_order_types:
        order_type_text = "limit"
    else:
        order_type_text = "none"

    row = {
        "timestamp": driver._timestamp_from_bar_or_now(),
        "symbol": f"{s1}_{s2}",
        "order_type": order_type_text,
        "stock_pnl": str(pair_stock_pnl),
        "open": str(pair_open),
        "high": str(pair_high),
        "low": str(pair_low),
        "close": str(pair_close),
        "total_pnl_close": str(pair_total_pnl_close),
        "total_pnl_high": str(pair_total_pnl_high),
        "total_pnl_low": str(pair_total_pnl_low),
        "ending_shares": str(ending_shares),
        "num_submits": num_submits,
        "num_accepted": num_accepted,
        "num_cancelled": num_cancelled,
        "num_rejected": num_rejected,
    }

    fieldnames = [
        "timestamp",
        "symbol",
        "order_type",
        "stock_pnl",
        "open",
        "high",
        "low",
        "close",
        "total_pnl_close",
        "total_pnl_high",
        "total_pnl_low",
        "ending_shares",
        "num_submits",
        "num_accepted",
        "num_cancelled",
        "num_rejected",
    ]

    with open(report_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    driver._eod_report_written_days.add(day_key)
    print("🧾 ", f"Pair EOD report saved: {report_path} row_symbol={row['symbol']}")


def build_ratchet_strategy_state_csv_path(context) -> Path:
    strategy_name = str(
        getattr(context.trading_state, "strategy_name", "")
        or context.strategy_params.get("strategy_name", "")
        or "master_driver"
    ).strip()
    date_suffix = datetime.now(NY_TZ).strftime("%Y%m%d")
    default_name = derive_strategy_report_name(strategy_name, f"zscore_{date_suffix}.csv")
    return _resolve_log_csv_path(default_name, context)


def append_ratchet_strategy_state_csv(context, symbol_key: str, indicators: dict[str, Any], delta: float):
    path = build_ratchet_strategy_state_csv_path(context)
    fieldnames = ["date_time", "symbol", "price", "EMA price", "volatility", "z-score", "order", "rationale"]

    order_text = "none"
    if float(delta) > 0.0:
        order_text = "buy"
    elif float(delta) < 0.0:
        order_text = "sell"

    bar = context.minute_bars.get(symbol_key, {}) if isinstance(context.minute_bars, dict) else {}
    raw_ts = bar.get("t", bar.get("timestamp")) if isinstance(bar, dict) else None
    date_time = datetime.now(NY_TZ).strftime("%Y-%m-%d %H:%M:%S")
    if raw_ts is not None:
        parsed_dt = coerce_market_datetime_ny(raw_ts, fallback_to_now=False)
        if parsed_dt is not None:
            date_time = parsed_dt.astimezone(NY_TZ).strftime("%Y-%m-%d %H:%M:%S")

    explicit_rationale = str(indicators.get("last_rationale", "") or "").strip()
    if explicit_rationale:
        rationale = explicit_rationale
    elif float(delta) > 0.0:
        rationale = "signal buy"
    elif float(delta) < 0.0:
        rationale = "signal sell"
    elif bool(indicators.get("pullback_waiting", False)):
        rationale = "waiting for pullback"
    elif bool(indicators.get("pending_order_waiting", False)):
        rationale = "waiting for pending fill"
    else:
        rationale = "no trade"

    row = {
        "date_time": date_time,
        "symbol": symbol_key,
        "price": _format_optional_number(indicators.get("price"), precision=6),
        "EMA price": _format_optional_number(indicators.get("ema"), precision=6),
        "volatility": _format_optional_number(indicators.get("volatility"), precision=6),
        "z-score": _format_optional_number(indicators.get("zscore"), precision=6),
        "order": order_text,
        "rationale": rationale,
    }

    print(
        "📊 ",
        f"date_time={row['date_time']} | symbol={row['symbol']} | price={row['price']} | "
        f"EMA={row['EMA price']} | volatility={row['volatility']} | z-score={row['z-score']} | "
        f"order={row['order']} | rationale={row['rationale']}",
    )

    _append_dict_row(path, fieldnames, row)


def default_trade_blotter_config() -> dict[str, Any]:
    return {
        "fieldnames": [
            "timestamp",
            "symbol",
            "price",
            "qty",
            "type",
            "order_type",
            "limit_price",
            "message",
        ],
        "excluded_fields": {
            "misc",
            "broker_asset_class",
            "broker_asset_id",
            "broker_id",
            "broker_extended_hours",
            "broker_order_class",
            "broker_status",
            "broker_submitted_at",
            "broker_symbol",
            "broker_side",
            "broker_time_in_force",
            "broker_type",
            "broker_expires_at",
            "broker_created_at",
            "broker_order_type",
            "broker_position_intent",
            "broker_qty",
            "broker_updated_at",
            "broker_filled_at",
            "broker_filled_avg_price",
        },
        "field_renames": {
            "timestamp_ny": "timestamp",
            "broker_client_order_id": "order_id",
            "broker_limit_price": "limit_price",
        },
    }


def initialize_trade_blotter_tracking(owner: Any, *, keep_path: bool = False) -> None:
    config = default_trade_blotter_config()
    owner._trade_blotter_fieldnames = list(config["fieldnames"])
    owner._trade_blotter_excluded_fields = set(config["excluded_fields"])
    owner._trade_blotter_field_renames = dict(config["field_renames"])
    owner._trade_blotter_logged_status_by_order_id = {}
    owner._trade_blotter_logged_submission_keys = set()
    owner._trade_blotter_logged_cancel_keys = set()
    if not keep_path:
        owner._trade_blotter_path = None
        owner._trade_blotter_day_key = None


def build_trade_blotter_owner(
    *,
    strategy_name: str,
    log_dir_name: str,
    blotter_suffix: str = "blotter",
    fieldnames: list[str] | None = None,
    excluded_fields: set[str] | None = None,
    field_renames: dict[str, str] | None = None,
):
    date_suffix = datetime.now(NY_TZ).strftime("%Y%m%d")
    suffix = str(blotter_suffix or "blotter").strip()
    blotter_path = Path(log_dir_name).expanduser() / f"{strategy_name}_{suffix}_{date_suffix}.csv"
    blotter_path.parent.mkdir(parents=True, exist_ok=True)

    defaults = default_trade_blotter_config()

    return SimpleNamespace(
        strategy_params={"strategy_name": strategy_name, "log_dir_name": str(log_dir_name)},
        trading_state=SimpleNamespace(strategy_name=strategy_name, log_dir_name=str(log_dir_name)),
        latest_execution_hints={},
        _safe_float=lambda value, default=0.0: float(value) if value not in (None, "") else float(default),
        _trade_blotter_path=blotter_path,
        _trade_blotter_day_key=date_suffix,
        _trade_blotter_fieldnames=list(fieldnames or defaults["fieldnames"]),
        _trade_blotter_excluded_fields=set(excluded_fields or defaults["excluded_fields"]),
        _trade_blotter_field_renames=dict(field_renames or defaults["field_renames"]),
        _trade_blotter_logged_status_by_order_id={},
        _trade_blotter_logged_submission_keys=set(),
        _trade_blotter_logged_cancel_keys=set(),
    )


def build_trade_blotter_path(driver) -> Path:
    date_suffix = datetime.now(NY_TZ).strftime("%Y%m%d")
    current_day_key = str(date_suffix)
    cached_day_key = str(getattr(driver, "_trade_blotter_day_key", "") or "")

    if driver._trade_blotter_path is not None and cached_day_key == current_day_key:
        return driver._trade_blotter_path

    default_name = _strategy_daily_csv_name(driver, "blotter")
    driver._trade_blotter_path = _resolve_log_csv_path(default_name, driver)
    driver._trade_blotter_day_key = current_day_key
    prune_trade_blotter_file_columns(driver, driver._trade_blotter_path)
    return driver._trade_blotter_path


def blotter_field_allowed(driver, field: str) -> bool:
    return bool(str(field or "").strip()) and field not in driver._trade_blotter_excluded_fields


def blotter_output_field_name(driver, field: str) -> str:
    return driver._trade_blotter_field_renames.get(field, field)


def simplify_client_order_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("md_") and "_" in text:
        candidate = text.rsplit("_", 1)[-1]
        if candidate.isdigit():
            return candidate
    return text


def normalize_blotter_field_value(field: str, value: Any) -> Any:
    timestamp_fields = {
        "timestamp",
        "timestamp_ny",
        "broker_timestamp",
        "submitted_at",
        "updated_at",
        "filled_at",
        "created_at",
        "broker_submitted_at",
        "broker_updated_at",
        "broker_filled_at",
        "broker_created_at",
    }
    if field in timestamp_fields:
        normalized = format_timestamp_ny(value, fallback_to_now=False)
        return normalized if normalized else value
    if field == "order_id":
        return simplify_client_order_id(value)
    return value


def _signed_qty_for_side(qty: Any, side_text: Any) -> float:
    try:
        qty_value = abs(float(qty or 0.0))
    except (TypeError, ValueError):
        return 0.0

    side = str(side_text or "").strip().lower()
    side_token = side.replace("-", "_").replace(" ", "_")
    if side_token in {"sell", "short", "sell_short", "sell_to_open", "sto", "s"} or "sell" in side_token:
        return -qty_value
    if side_token in {"buy", "long", "buy_to_open", "buy_to_cover", "btc", "b"} or "buy" in side_token:
        return qty_value
    return qty_value


def normalize_blotter_payload_fields(driver, payload_fields: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in payload_fields.items():
        if not blotter_field_allowed(driver, key):
            continue
        output_key = blotter_output_field_name(driver, key)
        if not blotter_field_allowed(driver, output_key):
            continue
        normalized_value = normalize_blotter_field_value(output_key, value)
        normalized[output_key] = normalized_value
    return normalized


def ordered_trade_blotter_fields(fieldnames: list[str]) -> list[str]:
    ordered = [field for field in fieldnames if str(field or "").strip()]
    if "limit_price" not in ordered:
        return ordered

    ordered = [field for field in ordered if field != "limit_price"]
    if "order_type" in ordered:
        insert_at = ordered.index("order_type") + 1
        ordered.insert(insert_at, "limit_price")
    else:
        ordered.append("limit_price")
    return ordered


def prune_trade_blotter_file_columns(driver, path: Path):
    if not path.exists():
        return

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        existing_fields = list(reader.fieldnames or [])
        if not existing_fields:
            return
        existing_rows = list(reader)

    field_name_changed = any(blotter_output_field_name(driver, field) != field for field in existing_fields)
    filtered_fields: list[str] = []
    for field in existing_fields:
        if not blotter_field_allowed(driver, field):
            continue
        output_field = blotter_output_field_name(driver, field)
        if output_field not in filtered_fields:
            filtered_fields.append(output_field)
    filtered_fields = ordered_trade_blotter_fields(filtered_fields)

    if filtered_fields == existing_fields and not field_name_changed:
        return

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=filtered_fields)
        writer.writeheader()
        for row in existing_rows:
            normalized_row = {field: "" for field in filtered_fields}
            for field in existing_fields:
                if not blotter_field_allowed(driver, field):
                    continue
                output_field = blotter_output_field_name(driver, field)
                normalized_row[output_field] = normalize_blotter_field_value(output_field, row.get(field, ""))
            writer.writerow(normalized_row)


def blotter_cell_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.astimezone(NY_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    if isinstance(value, (str, int, float, bool)):
        return value
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (str, int, float, bool)):
        return enum_value
    return json.dumps(value, default=str, ensure_ascii=True)


def flatten_broker_payload(prefix: str, value: Any, out: dict[str, Any]):
    if value is None:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}_{key}" if prefix else str(key)
            flatten_broker_payload(child_prefix, child, out)
        return
    if isinstance(value, (list, tuple, set)):
        out[prefix] = json.dumps(list(value), default=str, ensure_ascii=True)
        return
    out[prefix] = blotter_cell_value(value)

def ensure_trade_blotter_fieldnames(driver, additional_fields: list[str]):
    new_fields = [
        blotter_output_field_name(driver, field)
        for field in additional_fields
        if blotter_field_allowed(driver, field)
        and blotter_field_allowed(driver, blotter_output_field_name(driver, field))
        and blotter_output_field_name(driver, field) not in driver._trade_blotter_fieldnames
    ]
    if not new_fields:
        return

    driver._trade_blotter_fieldnames.extend(sorted(new_fields))
    driver._trade_blotter_fieldnames = ordered_trade_blotter_fields(driver._trade_blotter_fieldnames)
    path = build_trade_blotter_path(driver)
    if not path.exists():
        return

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        existing_rows = list(reader)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=driver._trade_blotter_fieldnames)
        writer.writeheader()
        for row in existing_rows:
            normalized_row = {field: row.get(field, "") for field in driver._trade_blotter_fieldnames}
            writer.writerow(normalized_row)


def append_trade_blotter_row(driver, row: dict[str, Any], broker_payload: dict[str, Any] | None = None):
    payload_fields: dict[str, Any] = {}
    if isinstance(broker_payload, dict):
        flatten_broker_payload("broker", broker_payload, payload_fields)
    payload_fields = normalize_blotter_payload_fields(driver, payload_fields)

    ensure_trade_blotter_fieldnames(driver, list(payload_fields.keys()))

    path = build_trade_blotter_path(driver)

    normalized_row = {field: "" for field in driver._trade_blotter_fieldnames}
    for key, value in row.items():
        output_key = blotter_output_field_name(driver, key)
        if blotter_field_allowed(driver, output_key) and output_key in normalized_row:
            normalized_value = normalize_blotter_field_value(output_key, value)
            normalized_row[output_key] = blotter_cell_value(normalized_value)
    for key, value in payload_fields.items():
        if key in normalized_row:
            normalized_row[key] = blotter_cell_value(value)

    order_type = str(normalized_row.get("order_type", "") or "").strip().lower()
    if order_type in {"market", "mkt"}:
        try:
            limit_price = float(normalized_row.get("limit_price", ""))
        except (TypeError, ValueError):
            limit_price = 0.0
        if not math.isfinite(limit_price) or limit_price <= 0.0:
            symbol = str(normalized_row.get("symbol", "") or "").strip().upper()
            latest_prices = getattr(driver, "latest_symbol_prices", {})
            close_price = None
            if isinstance(latest_prices, dict):
                raw_close = latest_prices.get(symbol)
                if raw_close is None:
                    raw_close = next(
                        (value for key, value in latest_prices.items() if str(key).strip().upper() == symbol),
                        None,
                    )
                try:
                    candidate = float(raw_close)
                    if math.isfinite(candidate) and candidate > 0.0:
                        close_price = candidate
                except (TypeError, ValueError):
                    pass

            if close_price is None:
                minute_bars = getattr(driver, "current_minute_bars", {})
                if isinstance(minute_bars, dict):
                    bar = next(
                        (value for key, value in minute_bars.items() if str(key).strip().upper() == symbol),
                        {},
                    )
                    if isinstance(bar, dict):
                        try:
                            candidate = float(bar.get("c", bar.get("close")))
                            if math.isfinite(candidate) and candidate > 0.0:
                                close_price = candidate
                        except (TypeError, ValueError):
                            pass

            if close_price is None:
                raise ValueError(
                    f"Cannot write market-order blotter row for {symbol}: no valid latest close price is available"
                )
            normalized_row["limit_price"] = close_price
            row["limit_price"] = close_price

    _append_dict_row(path, driver._trade_blotter_fieldnames, normalized_row)


def record_trade_submission(
    driver,
    *,
    symbol: str,
    side_text: str,
    qty: float,
    order_type: str,
    price: float | None,
    strategy_label: str,
    broker_order: Any = None,
    misc: str = "",
):
    broker_payload = order_to_broker_payload(broker_order)
    if not isinstance(broker_payload, dict):
        broker_payload = {}

    symbol_text = str(symbol or broker_payload.get("symbol", "") or broker_payload.get("broker_symbol", "") or "").strip().upper()
    side_text = str(side_text or broker_payload.get("side", "") or broker_payload.get("broker_side", "") or "").strip().lower()
    order_type_text = str(order_type or broker_payload.get("order_type", "") or broker_payload.get("type", "") or "market").strip().lower()
    limit_price = broker_payload.get("limit_price", broker_payload.get("broker_limit_price", price if order_type_text == "limit" else ""))
    submitted_at = format_timestamp_ny(None)
    rationale = submission_rationale_message(driver, symbol_text, side_text)
    broker_message = broker_message_from_payload(broker_payload)
    submission_key = str(
        broker_payload.get("client_order_id", "")
        or broker_payload.get("id", "")
        or f"{symbol_text}|{side_text}|{qty}|{order_type_text}|{price}"
    ).strip()
    if not hasattr(driver, "_trade_blotter_logged_submission_keys"):
        driver._trade_blotter_logged_submission_keys = set()
    if submission_key and submission_key in driver._trade_blotter_logged_submission_keys:
        return None

    row = {
        "timestamp_ny": submitted_at,
        "symbol": symbol_text,
        "price": price if price is not None else limit_price,
        "qty": _signed_qty_for_side(qty, side_text),
        "type": "submit",
        "order_type": order_type_text or "market",
        "limit_price": limit_price,
        "message": broker_message or rationale,
        "side": side_text,
        "status": "submitted",
        "misc": misc or broker_payload.get("misc", ""),
        "strategy_label": strategy_label,
    }

    append_trade_blotter_row(driver, row, broker_payload=broker_payload)
    if submission_key:
        driver._trade_blotter_logged_submission_keys.add(submission_key)
    return row


def record_trade_submit_failure(
    driver,
    *,
    symbol: str,
    side_text: str,
    requested_qty: float,
    order_type: str,
    limit_price: float | None = None,
    shares_available: float | None = None,
    reason: str = "",
    rejection: dict[str, Any] | None = None,
):
    """Blotter a rejected or locally dropped submission without an order ID."""
    symbol_text = str(symbol or "").strip().upper()
    side_text = str(side_text or "").strip().lower()
    order_type_text = str(order_type or "market").strip().lower()
    requested_value = abs(float(requested_qty or 0.0))
    available_text = "unknown" if shares_available is None else f"{float(shares_available):.4f}"

    rejected = isinstance(rejection, dict) and bool(rejection)
    rejection_reason = str(rejection.get("message", "") or "").strip() if rejected else ""
    rejection_code = rejection.get("code") if rejected else None
    code_text = f"; broker_code={rejection_code}" if rejection_code not in (None, "") else ""
    message = (
        f"{'broker rejected' if rejected else 'submit dropped'}: "
        f"{rejection_reason or reason or 'no order id returned'}{code_text}; "
        f"requested_qty={requested_value:.4f} shares_available={available_text}"
    )

    row = {
        "timestamp_ny": format_timestamp_ny(None),
        "symbol": symbol_text,
        "price": limit_price if order_type_text == "limit" else "",
        "qty": _signed_qty_for_side(requested_value, side_text),
        "type": "reject" if rejected else "submit_failed",
        "order_type": order_type_text,
        "limit_price": limit_price if order_type_text == "limit" else "",
        "message": message,
    }

    append_trade_blotter_row(driver, row)
    rounded_print("🚫 ", f"Order gate: {symbol_text} side={side_text} {message}")
    return row


def record_trade_cancel_request(
    driver,
    *,
    symbol: str,
    qty: float,
    order_type: str,
    price: float | None,
    message: str,
    order: Any = None,
    misc: str = "",
):
    broker_payload = order_to_broker_payload(order)
    if not isinstance(broker_payload, dict):
        broker_payload = {}

    symbol_text = str(symbol or broker_payload.get("symbol", "") or broker_payload.get("broker_symbol", "") or "").strip().upper()
    side_text = str(broker_payload.get("side", "") or broker_payload.get("broker_side", "") or "").strip().lower()
    order_type_text = str(order_type or broker_payload.get("order_type", "") or broker_payload.get("type", "") or "market").strip().lower()
    limit_price = broker_payload.get("limit_price", broker_payload.get("broker_limit_price", price if order_type_text == "limit" else ""))
    cancel_at = broker_payload.get("submitted_at", broker_payload.get("updated_at", datetime.now(NY_TZ)))
    cancel_at_text = format_timestamp_ny(cancel_at)
    cancel_key = str(
        broker_payload.get("client_order_id", "")
        or broker_payload.get("id", "")
        or f"{symbol_text}|cancel|{qty}|{order_type_text}|{price}|{message}"
    ).strip()
    if not hasattr(driver, "_trade_blotter_logged_cancel_keys"):
        driver._trade_blotter_logged_cancel_keys = set()
    if cancel_key and cancel_key in driver._trade_blotter_logged_cancel_keys:
        return None

    row = {
        "timestamp_ny": cancel_at_text,
        "symbol": symbol_text,
        "price": price if price is not None else limit_price,
        "qty": _signed_qty_for_side(qty, side_text),
        "type": "cancel",
        "order_type": order_type_text or "market",
        "limit_price": limit_price,
        "message": str(message or broker_message_from_payload(broker_payload) or "cancel request").strip(),
        "misc": misc or broker_payload.get("misc", ""),
        "status": "cancel_requested",
    }

    append_trade_blotter_row(driver, row, broker_payload=broker_payload)
    if cancel_key:
        driver._trade_blotter_logged_cancel_keys.add(cancel_key)
    return row


def record_broker_order_update(driver, order: Any):
    broker_payload = order_to_broker_payload(order)
    if not isinstance(broker_payload, dict):
        broker_payload = {}

    status = str(broker_payload.get("status", "") or broker_payload.get("order_status", "") or "").strip()
    event_type = blotter_event_type_from_status(status)
    symbol = str(broker_payload.get("symbol", "") or broker_payload.get("broker_symbol", "") or "").strip().upper()
    side = str(broker_payload.get("side", "") or broker_payload.get("broker_side", "") or "").strip().lower()
    qty = broker_payload.get("qty", broker_payload.get("broker_qty", ""))
    order_type = str(broker_payload.get("type", "") or broker_payload.get("order_type", "") or broker_payload.get("broker_order_type", "NA") or "NA").strip().lower()
    limit_price = broker_payload.get("limit_price", broker_payload.get("broker_limit_price", ""))
    filled_qty = broker_payload.get("filled_qty", broker_payload.get("broker_filled_qty", ""))
    if filled_qty in (None, ""):
        filled_qty = broker_payload.get("filled_quantity", "")
    if filled_qty in (None, ""):
        filled_qty = broker_payload.get("qty_filled", "")
    if filled_qty in (None, ""):
        filled_qty = broker_payload.get("last_fill_qty", "")
    if filled_qty in (None, ""):
        filled_qty = broker_payload.get("last_filled_qty", "")
    if filled_qty in (None, ""):
        filled_qty = broker_payload.get("cum_qty", "")
    if filled_qty in (None, ""):
        filled_qty = broker_payload.get("event_qty", "")
    filled_avg_price = broker_payload.get("filled_avg_price", broker_payload.get("broker_filled_avg_price", ""))
    order_id = broker_payload.get("client_order_id", broker_payload.get("broker_client_order_id", broker_payload.get("id", "")))
    broker_timestamp = broker_payload.get(
        "updated_at",
        broker_payload.get("filled_at", broker_payload.get("submitted_at", broker_payload.get("created_at", datetime.now(NY_TZ)))),
    )
    broker_timestamp_text = format_timestamp_ny(broker_timestamp)
    response_key = "|".join(
        [
            str(order_id or "").strip(),
            str(status or "").strip().lower(),
            str(filled_qty or "").strip(),
            str(filled_avg_price or "").strip(),
            str(broker_timestamp or "").strip(),
        ]
    )
    if not hasattr(driver, "_trade_blotter_logged_status_by_order_id"):
        driver._trade_blotter_logged_status_by_order_id = {}
    existing_key = str(driver._trade_blotter_logged_status_by_order_id.get(str(order_id), "") or "")
    if order_id and response_key and response_key == existing_key:
        return None

    row = {
        "timestamp_ny": broker_timestamp_text,
        "symbol": symbol,
        "price": filled_avg_price if event_type in {"fill", "partial fill"} else limit_price,
        "qty": _signed_qty_for_side(filled_qty, side) if event_type in {"fill", "partial fill"} else _signed_qty_for_side(qty, side),
        "type": event_type,
        "order_type": order_type or "NA",
        "message": broker_message_from_payload(broker_payload) or status or event_type,
        "misc": broker_payload.get("misc", ""),
        "order_id": order_id,
        "side": side,
        "status": status,
        "limit_price": limit_price,
        "filled_qty": filled_qty,
        "filled_avg_price": filled_avg_price,
    }

    append_trade_blotter_row(driver, row, broker_payload=broker_payload)
    if order_id and response_key:
        driver._trade_blotter_logged_status_by_order_id[str(order_id)] = response_key
    return row


def submission_rationale_message(driver, symbol: str, side_text: str) -> str:
    hint = driver.latest_execution_hints.get(symbol, {}) if isinstance(driver.latest_execution_hints, dict) else {}
    hint = hint if isinstance(hint, dict) else {}

    explicit_reason = str(hint.get("reason", "") or "").strip()
    if explicit_reason:
        return explicit_reason

    if bool(hint.get("take_profit_triggered", False)):
        reason = str(hint.get("take_profit_reason", "") or "").strip()
        return f"take-profit:{reason}" if reason else "take-profit"
    if bool(hint.get("stop_loss_triggered", False)):
        return "stop-loss"
    if bool(hint.get("eod_flatten", False)):
        return "eod-flatten"

    zscore = driver._safe_float(hint.get("zscore"), default=0.0)
    if side_text == "buy" and zscore < 0.0:
        return "cheap"
    if side_text == "sell" and zscore > 0.0:
        return "rich"
    return str(hint.get("strategy", "") or "strategy signal").strip()


def broker_message_from_payload(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    status = str(payload.get("status", "") or "").strip().lower()
    reject_reason = str(
        payload.get("reject_reason", "")
        or payload.get("rejected_reason", "")
        or payload.get("status_message", "")
        or payload.get("message", "")
        or ""
    ).strip()
    filled_qty = payload.get("filled_qty")
    filled_avg_price = payload.get("filled_avg_price")
    if reject_reason:
        return f"{status or 'broker'}: {reject_reason}" if status else reject_reason
    if status_in_group(status, "fill_progress"):
        qty_text = "" if filled_qty in (None, "") else f" qty={filled_qty}"
        px_text = "" if filled_avg_price in (None, "") else f" avg_price={filled_avg_price}"
        return f"{status}{qty_text}{px_text}".strip()
    return status


def blotter_event_type_from_status(status: str) -> str:
    return _blotter_event_type_from_status(status)


