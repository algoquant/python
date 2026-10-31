from __future__ import annotations

import argparse
import importlib
import math
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from dotenv import dotenv_values

from .parse_args import (
    hhmm_to_minutes,
    minutes_to_hhmm,
    parse_bool_env,
    parse_bool_with_default,
    parse_hhmm_or_default,
    resolve_close_minutes,
)


@dataclass
class TradeInstruction:
    symbol: str
    qty: float


@dataclass
class StrategyContext:
    minute_key: tuple[int, int, int, int, int]
    minute_bars: dict[str, dict]
    account: dict[str, Any]
    positions: dict[str, dict[str, Any]]
    alpaca_api: Any
    trading_state: Any
    strategy_params: dict[str, float]
    last_fill_prices: dict[str, float | None] = field(default_factory=dict)


@dataclass(frozen=True)
class ZScoreTargetCalculation:
    current_position: int
    notional_position: int
    target_position: int
    delta: int
    strategy_sign: int
    scaled_signal: float


def read_env_file_if_changed(
    env_file: str | None,
    previous_signature: tuple[int, int] | None = None,
) -> tuple[dict[str, Any] | None, tuple[int, int]]:
    """Read an env file only when its modification time or size changes."""
    env_path = Path(str(env_file or "").strip())
    try:
        if not str(env_file or "").strip() or not env_path.is_file():
            raise FileNotFoundError
        stat_result = env_path.stat()
        signature = (int(stat_result.st_mtime_ns), int(stat_result.st_size))
    except (OSError, ValueError):
        signature = (-1, -1)

    if previous_signature == signature:
        return None, signature
    if signature == (-1, -1):
        return {}, signature
    return dict(dotenv_values(env_path)), signature


def load_strategy_callable(spec: str) -> Callable[[StrategyContext], Any]:
    if ":" not in spec:
        raise ValueError(f"Invalid strategy spec '{spec}'. Expected format module:function")
    module_name, fn_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    fn = getattr(module, fn_name, None)
    if fn is None or not callable(fn):
        raise ValueError(f"Strategy '{spec}' is not a callable")
    return fn


def merge_strategy_params_with_env(cli_params: dict[str, Any], env_file: str | None) -> dict[str, Any]:
    merged = dict(cli_params or {})
    env_path = str(env_file or "").strip()
    if not env_path or not os.path.exists(env_path):
        return merged

    values = dotenv_values(env_path)

    def _pick(*keys: str) -> Any:
        for key in keys:
            if key in values and values[key] not in {None, ""}:
                return values[key]
        return None

    float_fields = {
        "alpha": ("ALPHA", "STRATEGY_ALPHA"),
        "vol_floor": ("VOL_FLOOR", "STRATEGY_VOL_FLOOR"),
        "limit_spread": ("LIMIT_SPREAD", "STRATEGY_LIMIT_SPREAD"),
        "risk_premium": ("RISK_PREMIUM", "STRATEGY_RISK_PREMIUM"),
        "take_profit_threshold": ("TAKE_PROFIT_THRESHOLD", "STRATEGY_TAKE_PROFIT_THRESHOLD"),
        "take_profit_factor": ("TAKE_PROFIT_FACTOR", "STRATEGY_TAKE_PROFIT_FACTOR"),
        "pos_cap": ("POS_CAP", "STRATEGY_POS_CAP"),
        "price_premium": ("PRICE_PREMIUM", "STRATEGY_PRICE_PREMIUM"),
        "vol_premium": ("VOL_PREMIUM", "STRATEGY_VOL_PREMIUM"),
    }
    for field, keys in float_fields.items():
        raw = _pick(*keys)
        if raw is None:
            continue
        try:
            if merged.get(field) in (None, ""):
                merged[field] = float(raw)
        except (TypeError, ValueError):
            pass

    for field, keys in {
        "start_time": ("START_TIME", "STRATEGY_START_TIME"),
        "end_time": ("END_TIME", "STRATEGY_END_TIME"),
        "heartbeat_interval": ("HEARTBEAT_INTERVAL", "STRATEGY_HEARTBEAT_INTERVAL"),
        "message_file": ("MESSAGE_FILE", "STRATEGY_MESSAGE_FILE"),
        "eod_report_file": ("EOD_REPORT_FILE", "STRATEGY_EOD_REPORT_FILE"),
        "data_dir_name": ("DATA_DIR_NAME", "STRATEGY_DATA_DIR_NAME"),
        "log_dir_name": ("LOG_DIR_NAME", "STRATEGY_LOG_DIR_NAME"),
    }.items():
        raw = _pick(*keys)
        if raw is not None:
            if merged.get(field) in (None, ""):
                merged[field] = str(raw).strip()

    strategy_name_raw = _pick("STRATEGY_NAME")
    if strategy_name_raw is not None and str(strategy_name_raw).strip():
        if merged.get("strategy_name") in (None, ""):
            merged["strategy_name"] = str(strategy_name_raw).strip()

    merged["message_file"] = ""

    eod_flatten = parse_bool_env(_pick("EOD_FLATTEN", "STRATEGY_EOD_FLATTEN"))
    if eod_flatten is not None:
        if merged.get("eod_flatten") is None:
            merged["eod_flatten"] = eod_flatten
    suppress_console = parse_bool_env(_pick("SUPPRESS_CONSOLE_MESSAGES", "STRATEGY_SUPPRESS_CONSOLE_MESSAGES"))
    if suppress_console is not None:
        if merged.get("suppress_console_messages") is None:
            merged["suppress_console_messages"] = suppress_console
    strategy_reverse = parse_bool_env(_pick("STRATEGY_REVERSE"))
    if strategy_reverse is not None:
        if merged.get("strategy_reverse") is None:
            merged["strategy_reverse"] = strategy_reverse
    use_limit = parse_bool_env(_pick("USE_LIMIT", "STRATEGY_USE_LIMIT"))
    if use_limit is not None and merged.get("use_limit") is None:
        merged["use_limit"] = use_limit
    save_eod = parse_bool_env(_pick("SAVE_EOD", "STRATEGY_SAVE_EOD"))
    if save_eod is not None:
        if merged.get("save_eod") is None:
            merged["save_eod"] = save_eod
    return merged


def env_file_has_value(env_file: str | None, *keys: str) -> bool:
    """Return whether an env file defines a non-empty value for any key."""
    env_path = str(env_file or "").strip()
    if not env_path or not os.path.exists(env_path):
        return False
    values = dotenv_values(env_path)
    return any(key in values and values[key] not in (None, "") for key in keys)


def default_noop_strategy(_: StrategyContext):
    return {}


def merge_trade_plan(aggregate: dict[str, float], incoming: dict[str, float], required_symbols: set[str]):
    for symbol, qty in incoming.items():
        symbol_key = str(symbol or "").upper()
        if symbol_key not in required_symbols:
            continue
        aggregate[symbol_key] = aggregate.get(symbol_key, 0.0) + float(qty)


def normalize_strategy_output(output: Any) -> list[TradeInstruction]:
    instructions: list[TradeInstruction] = []
    if output is None:
        return instructions
    if isinstance(output, dict):
        for symbol, qty in output.items():
            instructions.append(TradeInstruction(symbol=str(symbol).upper(), qty=float(qty)))
        return instructions
    if isinstance(output, list):
        for item in output:
            if isinstance(item, TradeInstruction):
                instructions.append(TradeInstruction(symbol=item.symbol.upper(), qty=float(item.qty)))
            elif isinstance(item, dict):
                symbol = str(item.get("symbol", "")).upper()
                qty = item.get("qty", item.get("amount", 0))
                if symbol:
                    instructions.append(TradeInstruction(symbol=symbol, qty=float(qty)))
        return instructions
    raise TypeError("Unsupported strategy output. Return dict, list, or None.")


def strategy_param_text(strategy_params: dict[str, Any], key: str, default: Any = "", *, env_key: str | None = None) -> str:
    raw = strategy_params.get(key, default)
    if raw in (None, ""):
        raw = os.getenv(env_key, default) if env_key else default
    return str(raw or "").strip()


def strategy_param_int(strategy_params: dict[str, Any], key: str, default: Any, *, env_key: str | None = None) -> int:
    raw = strategy_params.get(key, default)
    if raw in (None, ""):
        raw = os.getenv(env_key, default) if env_key else default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def strategy_param_float(strategy_params: dict[str, Any], key: str, default: Any, *, env_key: str | None = None) -> float:
    raw = strategy_params.get(key, default)
    if raw in (None, ""):
        raw = os.getenv(env_key, default) if env_key else default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def dollar_vol_floor(stock_price: float, floor_percent: float) -> float:
    """Convert percentage points to a dollar volatility floor."""
    return abs(float(stock_price)) * max(0.0, float(floor_percent)) / 100.0


def strategy_dollar_vol_floor(
    strategy_params: dict[str, Any],
    stock_price: float,
    default_percent: float,
) -> float:
    """Convert STRATEGY_VOL_FLOOR percentage points to a dollar price floor."""
    floor_percent = strategy_param_float(
        strategy_params,
        "vol_floor",
        default_percent,
        env_key="STRATEGY_VOL_FLOOR",
    )
    return dollar_vol_floor(stock_price, floor_percent)


def strategy_param_bool(strategy_params: dict[str, Any], key: str, default: bool = False, *, env_key: str | None = None) -> bool:
    raw = strategy_params.get(key, default)
    if raw in (None, ""):
        raw = os.getenv(env_key, default) if env_key else default
    return parse_bool_with_default(raw, default=default)


def strategy_quantity_by_symbol(strategy_params: dict[str, Any]) -> dict[str, float]:
    raw_map = strategy_params.get("quantity_by_symbol", {})
    if not isinstance(raw_map, dict):
        return {}

    quantities: dict[str, float] = {}
    for symbol, quantity in raw_map.items():
        symbol_key = str(symbol or "").strip().upper()
        if not symbol_key:
            continue
        try:
            quantities[symbol_key] = float(quantity)
        except (TypeError, ValueError):
            continue
    return quantities


def calculate_inventory_price_shift(
    position: float,
    stock_price: float,
    quantity: float,
    price_premium: float,
) -> float:
    """Calculate the signed price shift for inventory-aware strategy bands."""
    price_inventory = float(position) * float(stock_price)
    price_quantity = float(quantity) * float(stock_price)
    if abs(price_quantity) <= 1e-12:
        return 0.0
    return float(price_premium) * price_inventory / price_quantity


def calculate_inventory_price_buffer(
    volatility: float,
    risk_premium: float,
    inventory_price: float,
    price_quantity: float,
    vol_premium: float,
) -> float:
    """Calculate a volatility buffer with an inventory-size penalty."""
    inventory_ratio = (
        abs(float(inventory_price)) / abs(float(price_quantity))
        if abs(float(price_quantity)) > 1e-12
        else 0.0
    )
    return float(risk_premium) * (float(volatility) + float(vol_premium) * inventory_ratio)


def zscore_target_position(zscore: float, quantity: float, risk_premium: float, *, reverse: bool = False) -> int:
    premium = float(risk_premium)
    if premium <= 0.0:
        raise ValueError("STRATEGY_RISK_PREMIUM must be greater than zero")
    direction = -1.0 if reverse else 1.0
    return int(math.trunc((direction * float(zscore) * float(quantity)) / premium))


def ratchet_target_position(
    zscore: float,
    quantity: float,
    risk_premium: float,
    current_position: float,
    *,
    reverse: bool = False,
) -> tuple[int, float]:
    notional_position = zscore_target_position(zscore, quantity, risk_premium, reverse=reverse)
    if notional_position > 0:
        target_position = max(float(current_position), float(notional_position))
    elif notional_position < 0:
        target_position = min(float(current_position), float(notional_position))
    else:
        target_position = float(current_position)
    return notional_position, target_position


def calculate_zscore_target(
    zscore: float,
    quantity: float,
    risk_premium: float,
    current_position: float,
    *,
    reverse: bool = False,
    ratchet: bool = False,
) -> ZScoreTargetCalculation:
    current_shares = int(round(float(current_position)))
    notional_position = zscore_target_position(
        zscore,
        quantity,
        risk_premium,
        reverse=reverse,
    )
    if ratchet:
        _, target_position_raw = ratchet_target_position(
            zscore,
            quantity,
            risk_premium,
            current_shares,
            reverse=reverse,
        )
        target_position = int(round(target_position_raw))
    else:
        target_position = int(notional_position)
    strategy_sign = -1 if reverse else 1
    scaled_signal = (
        float(strategy_sign) * float(zscore) * float(quantity)
    ) / float(risk_premium)
    return ZScoreTargetCalculation(
        current_position=current_shares,
        notional_position=int(notional_position),
        target_position=target_position,
        delta=int(target_position - current_shares),
        strategy_sign=strategy_sign,
        scaled_signal=float(scaled_signal),
    )


def cap_target_position(target_position: float, pos_cap: float) -> float:
    """Clamp target_position to [-pos_cap, pos_cap]; pos_cap <= 0 disables the cap."""
    cap = float(pos_cap)
    if cap <= 0.0:
        return float(target_position)
    return max(-cap, min(cap, float(target_position)))


def resolve_eod_flatten_timing(
    minute_key: tuple[int, int, int, int, int] | None,
    strategy_params: dict[str, Any],
    *,
    default_end_time: str | None = None,
    default_eod_flatten: bool = True,
) -> dict[str, Any]:
    if not isinstance(minute_key, tuple) or len(minute_key) != 5:
        return {"should_flatten": False, "eod_flatten": bool(default_eod_flatten), "end_time": str(default_end_time or ""), "liquidation_time": "", "close_minutes": None, "bar_minutes": None}
    _, _, _, bar_hour, bar_minute = minute_key
    bar_minutes = int(bar_hour) * 60 + int(bar_minute)
    end_time_str = strategy_param_text(strategy_params, "end_time", default_end_time, env_key="STRATEGY_END_TIME")
    market_close_time_str = strategy_param_text(strategy_params, "market_close_time", "", env_key="STRATEGY_MARKET_CLOSE_TIME")
    end_minutes = hhmm_to_minutes(end_time_str) if end_time_str else None
    market_close_minutes = hhmm_to_minutes(market_close_time_str) if market_close_time_str else None
    close_minutes = resolve_close_minutes(end_minutes, market_close_minutes)
    liquidation_time = minutes_to_hhmm(close_minutes)
    eod_flatten = strategy_param_bool(strategy_params, "eod_flatten", default_eod_flatten, env_key="STRATEGY_EOD_FLATTEN")
    should_flatten = bool(eod_flatten) and bar_minutes == close_minutes
    return {
        "should_flatten": bool(should_flatten),
        "eod_flatten": bool(eod_flatten),
        "end_time": str(end_time_str or liquidation_time),
        "liquidation_time": str(liquidation_time),
        "close_minutes": int(close_minutes),
        "bar_minutes": int(bar_minutes),
    }


def make_strategy_logger(strategy_params: dict[str, Any], minute_key: tuple[int, int, int, int, int], *, timestamp_field: str, use_log_dir_name: bool = False):
    del minute_key, timestamp_field, use_log_dir_name
    suppress_console_messages = bool(strategy_params.get("suppress_console_messages", False) or False)
    try:
        from .file_handlers import rounded_print
    except ImportError:
        from .file_handlers import rounded_print

    def strategy_log(*args, **kwargs):
        text = str(kwargs.get("sep", " ")).join(str(arg) for arg in args)
        if not suppress_console_messages:
            rounded_print(text, flush=kwargs.get("flush", False))

    return strategy_log


def minute_session_status(minute_key: tuple[int, int, int, int, int], strategy_params: dict[str, Any]) -> tuple[str, str, str]:
    _, _, _, hh, mm = minute_key
    minute_time = datetime.strptime(f"{hh:02d}:{mm:02d}", "%H:%M").time()
    start_text = str((strategy_params or {}).get("start_time", "09:30") or "09:30")
    end_text = str((strategy_params or {}).get("end_time", "16:00") or "16:00")
    start_time = parse_hhmm_or_default(start_text, "09:30")
    end_time = parse_hhmm_or_default(end_text, "16:00")
    if minute_time < start_time:
        return "before_start", start_text, end_text
    if minute_time >= end_time:
        return "after_end", start_text, end_text
    return "in_session", start_text, end_text


@dataclass(frozen=True)
class PairConfig:
    symbol1: str
    quantity1: float
    symbol2: str
    quantity2: float

    @property
    def pair_symbol(self) -> str:
        return f"PAIR_{self.symbol1}_{self.symbol2}"

    @property
    def display_symbol(self) -> str:
        return f"{self.symbol1}_{self.symbol2}"


def _normalize_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    if ":" in text:
        text = text.rsplit(":", 1)[-1]
    return text


def get_env_text(values: dict[str, Any], key: str) -> str:
    raw = values.get(key)
    return str(raw or "").strip()


def get_env_float(values: dict[str, Any], key: str) -> float:
    text = get_env_text(values, key)
    if not text:
        raise ValueError(f"Missing required env value: {key}")
    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric env value for {key}: {text!r}") from exc
    if value <= 0.0:
        raise ValueError(f"{key} must be > 0. Received {value}")
    return value


def resolve_pair_config(env_file: str) -> PairConfig:
    env_values = dotenv_values(env_file) if env_file else {}
    symbol1 = _normalize_symbol(get_env_text(env_values, "STRATEGY_SYMBOL1"))
    symbol2 = _normalize_symbol(get_env_text(env_values, "STRATEGY_SYMBOL2"))
    if not symbol1 or not symbol2:
        raise ValueError("Missing STRATEGY_SYMBOL1/STRATEGY_SYMBOL2. Set them in --env-file.")
    if symbol1 == symbol2:
        raise ValueError("STRATEGY_SYMBOL1 and STRATEGY_SYMBOL2 must be different symbols.")
    quantity1 = get_env_float(env_values, "STRATEGY_QUANTITY1")
    quantity2 = get_env_float(env_values, "STRATEGY_QUANTITY2")
    return PairConfig(symbol1=symbol1, quantity1=quantity1, symbol2=symbol2, quantity2=quantity2)


def build_strategy_params(
    args: argparse.Namespace,
    merge_strategy_params_with_env: Callable[[dict[str, Any], str | None], dict[str, Any]],
) -> dict[str, Any]:
    """Build strategy params from CLI and merge with env-backed overrides."""
    strategy_params = {
        "alpha": args.alpha,
        "vol_floor": args.vol_floor,
        "limit_spread": args.limit_spread,
        "risk_premium": args.risk_premium,
        "price_premium": args.price_premium,
        "vol_premium": args.vol_premium,
        "pos_cap": args.pos_cap,
        "take_profit_threshold": args.take_profit_threshold,
        "take_profit_factor": args.take_profit_factor,
        "start_time": args.start_time,
        "end_time": args.end_time,
        "eod_flatten": args.eod_flatten,
        "use_limit": args.use_limit,
        "hold_overnight": args.hold_overnight,
        "suppress_console_messages": args.suppress_console_messages,
        "message_file": args.message_file,
        "eod_report_file": args.eod_report_file,
        "strategy_reverse": bool(args.strategy_reverse) if args.strategy_reverse is not None else None,
        "heartbeat_interval": args.heartbeat_interval,
    }
    merged = merge_strategy_params_with_env(strategy_params, args.env_file)
    defaults = {
        "alpha": 0.9,
        "vol_floor": 0.5,
        "risk_premium": 1.0,
        "limit_spread": 0.01,
        "take_profit_threshold": 150.0,
        "take_profit_factor": 400.0,
        "pos_cap": 0.0,
        "price_premium": 0.0,
        "vol_premium": 0.0,
        "heartbeat_interval": 60.0,
        "start_time": "07:00:00",
        "end_time": "16:59:00",
        "eod_flatten": False,
        "hold_overnight": False,
        "suppress_console_messages": False,
        "use_limit": False,
    }
    for field, default in defaults.items():
        if merged.get(field) in (None, ""):
            merged[field] = default
    if args.strategy_reverse is not None:
        merged["strategy_reverse"] = bool(args.strategy_reverse)
    else:
        if merged.get("strategy_reverse") is None:
            merged["strategy_reverse"] = True
    return merged


def build_strategy_functions(
    args: argparse.Namespace,
    *,
    load_strategy_callable: Callable[[str], Callable[..., Any]],
    default_noop_strategy: Callable[..., Any],
    print_fn: Callable[..., None] | None = None,
    no_strategy_prefix: str | None = None,
    no_strategy_message: str = "No strategy configured. Running with no-op strategy.",
) -> tuple[list[Callable[..., Any]], list[str]]:
    """Resolve strategy specs from bundles/flags into callables and labels."""
    strategy_functions: list[Callable[..., Any]] = []
    strategy_specs: list[str] = []

    if args.strategy_bundle:
        registry = importlib.import_module("strategy_registry")
        bundle_specs = registry.get_bundle_specs(args.strategy_bundle)
        strategy_specs.extend(bundle_specs)

    if args.strategy:
        strategy_specs.extend(args.strategy)

    deduped_specs: list[str] = []
    for spec in strategy_specs:
        if spec not in deduped_specs:
            deduped_specs.append(spec)

    if deduped_specs:
        for spec in deduped_specs:
            strategy_functions.append(load_strategy_callable(spec))
    else:
        strategy_functions = [default_noop_strategy]
        if callable(print_fn):
            if no_strategy_prefix is None:
                print_fn(no_strategy_message)
            else:
                print_fn(no_strategy_prefix, no_strategy_message)

    labels = deduped_specs if deduped_specs else ["noop"]
    return strategy_functions, labels


__all__ = [
    "build_strategy_functions",
    "build_strategy_params",
    "StrategyContext",
    "TradeInstruction",
    "default_noop_strategy",
    "dollar_vol_floor",
    "load_strategy_callable",
    "make_strategy_logger",
    "merge_strategy_params_with_env",
    "env_file_has_value",
    "merge_trade_plan",
    "minute_session_status",
    "normalize_strategy_output",
    "resolve_eod_flatten_timing",
    "strategy_dollar_vol_floor",
    "calculate_inventory_price_shift",
    "calculate_inventory_price_buffer",
    "strategy_param_bool",
    "strategy_param_float",
    "strategy_param_int",
    "strategy_param_text",
    "PairConfig",
    "get_env_float",
    "get_env_text",
    "resolve_pair_config",
]
