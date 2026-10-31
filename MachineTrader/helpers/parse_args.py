from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values


def hhmm_to_minutes(hhmm: str) -> int:
    text = str(hhmm or "").strip()
    parts = text.split(":")
    if len(parts) < 2:
        raise ValueError(f"Invalid time value '{hhmm}'. Expected HH:MM or HH:MM:SS")
    return int(parts[0]) * 60 + int(parts[1])


def hhmm_to_minutes_or_default(raw_time: str, default_minutes: int) -> int:
    text = str(raw_time or "").strip()
    if not text:
        return int(default_minutes)
    try:
        return int(hhmm_to_minutes(text))
    except (TypeError, ValueError):
        return int(default_minutes)


def minutes_to_hhmm(total_minutes: int) -> str:
    minutes = int(total_minutes)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def resolve_close_minutes(
    end_minutes: int | None,
    market_close_minutes: int | None,
    *,
    default_close_minutes: int = 16 * 60,
) -> int:
    candidates: list[int] = []
    if end_minutes is not None:
        candidates.append(int(end_minutes))
    if market_close_minutes is not None:
        candidates.append(int(market_close_minutes))
    if not candidates:
        return int(default_close_minutes)
    return min(candidates)


def parse_bool_env(value) -> bool | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    return None


def parse_bool_with_default(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    parsed = parse_bool_env(value)
    if parsed is None:
        return bool(default)
    return parsed


def parse_hhmm_or_default(raw_value, default_hhmm: str):
    value = raw_value if raw_value is not None else default_hhmm
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return value

    text = str(value).strip() or default_hhmm
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue

    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(str(default_hhmm).strip(), fmt).time()
        except ValueError:
            continue

    return datetime.strptime("09:30", "%H:%M").time()


def resolve_symbols_from_env(env_file: str | None) -> list[str]:
    env_path = str(env_file or "").strip()
    if not env_path or not os.path.exists(env_path):
        return []

    values = dotenv_values(env_path)
    # Canonical source is STRATEGY_SYMBOLS; keep STRATEGY_SYMBOL as backward-compatible fallback.
    strategy_symbols_raw = values.get("STRATEGY_SYMBOLS", "") or values.get("STRATEGY_SYMBOL", "") or ""
    strategy_symbols_text = str(strategy_symbols_raw).strip()
    if not strategy_symbols_text:
        return []

    return [s.strip().upper() for s in strategy_symbols_text.replace(",", " ").split() if s.strip()]


def resolve_symbols_from_args(args: argparse.Namespace, *, env_file: str | None = None) -> list[str]:
    cli_symbols = [str(symbol).strip().upper() for symbol in (getattr(args, "symbols", []) or []) if str(symbol).strip()]
    if cli_symbols:
        return cli_symbols
    source_env_file = env_file if env_file is not None else getattr(args, "env_file", None)
    return resolve_symbols_from_env(source_env_file)


def split_tokens(raw) -> list[str]:
    text = str(raw or "").replace(",", " ")
    return [token.strip() for token in text.split() if token.strip()]


def resolve_symbol_quantity_map_from_env(
    env_file: str | None,
    *,
    symbols_key: str = "STRATEGY_SYMBOLS",
    quantities_key: str = "STRATEGY_QUANTITY",
) -> tuple[list[str], dict[str, float]]:
    env_path = str(env_file or "").strip()
    if not env_path or not os.path.exists(env_path):
        return [], {}

    values = dotenv_values(env_path)
    symbol_tokens = [token.upper() for token in split_tokens(values.get(symbols_key, ""))]
    quantity_tokens = split_tokens(values.get(quantities_key, ""))
    if not symbol_tokens:
        return [], {}

    if len(quantity_tokens) != len(symbol_tokens):
        raise ValueError(
            f"{quantities_key} must contain one quantity per {symbols_key} entry. "
            f"symbols={len(symbol_tokens)} quantities={len(quantity_tokens)}"
        )

    quantity_by_symbol: dict[str, float] = {}
    for idx, symbol in enumerate(symbol_tokens):
        raw_qty = quantity_tokens[idx]
        try:
            qty = float(raw_qty)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid quantity '{raw_qty}' for symbol '{symbol}'") from exc
        quantity_by_symbol[symbol] = qty

    return symbol_tokens, quantity_by_symbol


def resolve_symbols_and_quantity_map_from_args(
    args: argparse.Namespace,
    *,
    symbols_key: str = "STRATEGY_SYMBOLS",
    quantities_key: str = "STRATEGY_QUANTITY",
    default_quantity: float = 1.0,
) -> tuple[list[str], dict[str, float]]:
    env_symbols, env_quantity_by_symbol = resolve_symbol_quantity_map_from_env(
        getattr(args, "env_file", None),
        symbols_key=symbols_key,
        quantities_key=quantities_key,
    )

    cli_symbols = list(getattr(args, "symbols", []) or [])
    source_symbols = cli_symbols if cli_symbols else env_symbols
    symbols = [str(symbol).strip().upper() for symbol in source_symbols if str(symbol).strip()]

    quantity_by_symbol: dict[str, float] = {}
    for symbol in symbols:
        quantity_by_symbol[symbol] = float(env_quantity_by_symbol.get(symbol, default_quantity) or default_quantity)

    return symbols, quantity_by_symbol


def warn_ignored_pair_cli_symbols(
    args: argparse.Namespace,
    *,
    pair_symbol1: str,
    pair_symbol2: str,
    normalize_symbol,
    print_fn,
    prefix: str = "INFO",
) -> None:
    cli_symbols = {
        normalize_symbol(symbol)
        for symbol in (getattr(args, "symbols", []) or [])
        if normalize_symbol(symbol)
    }
    pair_symbols = {str(pair_symbol1).strip().upper(), str(pair_symbol2).strip().upper()}
    if cli_symbols and cli_symbols != pair_symbols:
        print_fn(
            prefix,
            "Ignoring CLI symbol list for master_pairs. "
            f"Using STRATEGY_SYMBOL1/2 from env file: {pair_symbol1}, {pair_symbol2}",
        )


def create_common_driver_arg_parser(
    *,
    description: str,
    symbols_help: str,
    limit_spread_help: str,
    eod_flatten_help: str,
    message_file_help: str,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("symbols", nargs="*", help=symbols_help)
    parser.add_argument("--strategy", action="append", default=[], help="Strategy function spec in module:function format. Repeat flag for multiple strategies.")
    parser.add_argument("--strategy-bundle", action="append", default=[], help="Named strategy bundle from strategy_registry.py (for example: core, bollinger, tanaka).")
    parser.add_argument("--data-proxy-url", default=os.getenv("DATA_PROXY_URL", "ws://localhost:8765"))
    parser.add_argument("--env-file", default="")
    parser.add_argument("--preflight-timeout", type=float, default=10.0)
    parser.add_argument("--preflight-bars-timeout", type=float, default=60.0)
    parser.add_argument("--preflight-connect-only", action="store_true", help="Only verify websocket connectivity during preflight; do not require immediate bar events.")
    parser.add_argument("--order-fill-timeout", type=float, default=30.0)
    parser.add_argument("--order-fill-poll", type=float, default=0.5)
    parser.add_argument("--alpha", type=float, default=None, help="EMA decay parameter (0 < alpha <= 1).")
    parser.add_argument(
        "--vol-floor",
        type=float,
        default=None,
        help="Minimum volatility floor as a percentage of each stock price (0.5 means 0.5%%).",
    )
    parser.add_argument("--risk-premium", type=float, default=None, help="Risk premium used for Z-score calculations.")
    parser.add_argument("--price-premium", type=float, default=None, help="Inventory price-band shift premium.")
    parser.add_argument("--vol-premium", type=float, default=None, help="Inventory volatility-buffer premium.")
    parser.add_argument("--pos-cap", type=float, default=None, help="Maximum absolute target position; zero disables the cap.")
    parser.add_argument("--limit-spread", type=float, default=None, help=limit_spread_help)
    parser.add_argument("--take-profit-threshold", type=float, default=None, help="Take-profit multiplier for EMA Bollinger strategy.")
    parser.add_argument("--take-profit-factor", type=float, default=None, help="Per-share take-profit multiplier for EMA Bollinger strategy.")
    parser.add_argument("--start-time", type=str, default=None, help="Strategy trading-window start time in HH:MM (America/New_York). Default: 09:30.")
    parser.add_argument("--end-time", type=str, default=None, help="Strategy trading-window end time in HH:MM (America/New_York). Default: 16:00.")
    parser.add_argument("--heartbeat-interval", type=float, default=None, help="Heartbeat interval in seconds.")
    parser.add_argument("--cancel-stale-order-seconds", type=float, default=10.0, help="Auto-cancel active pending market order after this many seconds (0 disables).")
    parser.add_argument("--eod-flatten", action=argparse.BooleanOptionalAction, default=None, help=eod_flatten_help)
    parser.add_argument("--use-limit", action=argparse.BooleanOptionalAction, default=None, help="Use limit orders during market hours. Default: disabled.")
    parser.add_argument("--hold-overnight", action=argparse.BooleanOptionalAction, default=None, help="Retain positions overnight without end-of-day liquidation. Default: disabled.")
    parser.add_argument("--suppress-console-messages", action=argparse.BooleanOptionalAction, default=None, help="Suppress strategy console print messages. Default: disabled.")
    parser.add_argument("--message-file", type=str, default="", help=message_file_help)
    parser.add_argument("--eod-report-file", type=str, default="", help="Optional csv file path for end-of-day summary rows.")
    parser.add_argument("--strategy-reverse", action=argparse.BooleanOptionalAction, default=None, help="Reverse all trade signals from strategy: buy becomes sell and vice versa. Can also be set via STRATEGY_REVERSE in the env file.")
    return parser


def create_data_proxy_arg_parser(
    *,
    default_env_file: str | Path,
    description: str = "Alpaca WebSocket proxy for bar relaying",
) -> argparse.ArgumentParser:
    parser = create_common_driver_arg_parser(
        description=description,
        symbols_help="Symbols expected from proxy stream. If not provided, reads DATA_SYMBOLS from env file (falls back to STRATEGY_SYMBOL).",
        limit_spread_help="Unused in live_data_proxy.py.",
        eod_flatten_help="Unused in live_data_proxy.py.",
        message_file_help="Unused in live_data_proxy.py.",
    )
    parser.set_defaults(env_file=str(default_env_file))
    parser.add_argument("--force", action="store_true", help="Break stale lock file if PID is no longer running.")
    return parser


def parse_stream_bars_single_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream bars from local websocket proxy.")
    parser.add_argument("symbol", nargs="?", help="Ticker symbol, e.g. SPY")
    parser.add_argument("--nofile", action="store_true", help="Print bars only, do not write CSV")
    parser.add_argument("--env-file", type=str, default=".env", help="Path to environment file (default: .env)")
    return parser.parse_args(argv)


def create_liquidate_positions_limit_arg_parser(*, default_env_file: str | Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Liquidate open positions using limit orders.")
    parser.add_argument(
        "symbols",
        nargs="*",
        help="Optional symbols to liquidate. If omitted, liquidates all open positions.",
    )
    parser.add_argument(
        "--limit-spread",
        type=float,
        default=None,
        help="Limit spread override. If omitted, reads STRATEGY_LIMIT_SPREAD/LIMIT_SPREAD from env file.",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=str(default_env_file),
        help="Path to env file containing ALPACA_TRADE_KEY/SECRET and ALPACA_DATA_KEY/SECRET.",
    )
    parser.add_argument(
        "--bar-poll-seconds",
        type=float,
        default=1.0,
        help="Polling interval while waiting for the next bar.",
    )
    parser.add_argument(
        "--data-proxy-url",
        type=str,
        default=None,
        help="Proxy URL override. If omitted, reads DATA_PROXY_URL from the env file.",
    )
    return parser


def parse_liquidate_positions_limit_runtime(
    args: argparse.Namespace,
) -> tuple[str, list[str], float | None, float, str | None]:
    env_file = str(getattr(args, "env_file", "") or "").strip()
    env_values = dotenv_values(env_file) if env_file and Path(env_file).exists() else {}

    symbols = [str(symbol).strip().upper() for symbol in (getattr(args, "symbols", []) or []) if str(symbol).strip()]

    limit_spread_cli = getattr(args, "limit_spread", None)
    if limit_spread_cli is not None:
        limit_spread = float(limit_spread_cli)
    else:
        raw = env_values.get(
            "STRATEGY_LIMIT_SPREAD",
            env_values.get("LIMIT_SPREAD", os.getenv("STRATEGY_LIMIT_SPREAD", "")),
        )
        limit_spread = None
        if str(raw or "").strip():
            try:
                limit_spread = float(raw)
            except (TypeError, ValueError):
                limit_spread = None

    bar_poll_seconds = max(0.2, float(getattr(args, "bar_poll_seconds", 1.0)))
    data_proxy_url = str(getattr(args, "data_proxy_url", "") or "").strip() or None

    return env_file, symbols, limit_spread, bar_poll_seconds, data_proxy_url


__all__ = [
    "create_common_driver_arg_parser",
    "create_data_proxy_arg_parser",
    "create_liquidate_positions_limit_arg_parser",
    "parse_liquidate_positions_limit_runtime",
    "parse_stream_bars_single_args",
    "hhmm_to_minutes",
    "hhmm_to_minutes_or_default",
    "minutes_to_hhmm",
    "parse_bool_env",
    "parse_bool_with_default",
    "parse_hhmm_or_default",
    "resolve_close_minutes",
    "resolve_symbols_from_args",
    "warn_ignored_pair_cli_symbols",
    "resolve_symbol_quantity_map_from_env",
    "resolve_symbols_and_quantity_map_from_args",
    "resolve_symbols_from_env",
    "split_tokens",
]
