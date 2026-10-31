from __future__ import annotations

"""Driver common helpers imported from shared helper modules."""

from pathlib import Path
from typing import Any
from MachineTrader.helpers.api_parsing import safe_float

try:
    from MachineTrader.helpers.timestamp_utils import NY_TZ, format_timestamp_ny
except ImportError:
    from MachineTrader.helpers.timestamp_utils import NY_TZ, format_timestamp_ny

from MachineTrader.helpers.parse_args import (
    hhmm_to_minutes,
    minutes_to_hhmm,
    parse_bool_env,
    parse_bool_with_default,
    parse_hhmm_or_default,
    resolve_close_minutes,
    resolve_symbol_quantity_map_from_env,
    resolve_symbols_from_env,
    split_tokens,
)
from MachineTrader.helpers.setup_strat import (
    StrategyContext,
    TradeInstruction,
    ZScoreTargetCalculation,
    calculate_zscore_target,
    cap_target_position,
    calculate_inventory_price_shift,
    calculate_inventory_price_buffer,
    default_noop_strategy,
    dollar_vol_floor,
    env_file_has_value,
    load_strategy_callable,
    make_strategy_logger,
    merge_strategy_params_with_env,
    merge_trade_plan,
    minute_session_status,
    normalize_strategy_output,
    read_env_file_if_changed,
    resolve_eod_flatten_timing,
    ratchet_target_position,
    strategy_dollar_vol_floor,
    strategy_quantity_by_symbol,
    strategy_param_bool,
    strategy_param_float,
    strategy_param_int,
    strategy_param_text,
    zscore_target_position,
)
from MachineTrader.helpers.live_data import (
    build_bar_timestamp_skew_warning,
    event_datetime_ny,
    event_minute_key,
    event_timing_ny,
    event_symbol,
    fill_missing_minute_bars,
    is_bar_event,
    make_na_bar,
    minute_to_str,
    normalize_symbol,
)
from MachineTrader.helpers.broker_orders import (
    compute_limit_price,
    is_terminal_order_status,
    normalize_order_status,
)
from MachineTrader.helpers.file_handlers import (
    build_client_order_id,
    fmt_optional_number,
    round_message_numbers,
    rounded_print,
    resolve_csv_path_with_strategy_params as _resolve_csv_path_with_strategy_params,
    sanitize_strategy_label,
    strategy_from_client_order_id,
    derive_strategy_report_name,
    build_position_queue_file_name,
)

def resolve_csv_path(raw_path: str, default_name: str, strategy_params: dict[str, Any]) -> Path:
    return _resolve_csv_path_with_strategy_params(raw_path, default_name, strategy_params)


__all__ = [
    "NY_TZ",
    "StrategyContext",
    "TradeInstruction",
    "ZScoreTargetCalculation",
    "build_client_order_id",
    "calculate_zscore_target",
    "cap_target_position",
    "calculate_inventory_price_shift",
    "calculate_inventory_price_buffer",
    "compute_limit_price",
    "default_noop_strategy",
    "dollar_vol_floor",
    "env_file_has_value",
    "build_bar_timestamp_skew_warning",
    "event_datetime_ny",
    "event_minute_key",
    "event_timing_ny",
    "event_symbol",
    "fill_missing_minute_bars",
    "hhmm_to_minutes",
    "is_bar_event",
    "make_na_bar",
    "load_strategy_callable",
    "make_strategy_logger",
    "merge_strategy_params_with_env",
    "minute_to_str",
    "minutes_to_hhmm",
    "normalize_order_status",
    "normalize_symbol",
    "parse_bool_env",
    "parse_bool_with_default",
    "parse_hhmm_or_default",
    "round_message_numbers",
    "rounded_print",
    "resolve_symbols_from_env",
    "resolve_symbol_quantity_map_from_env",
    "resolve_close_minutes",
    "strategy_param_bool",
    "strategy_param_float",
    "strategy_param_int",
    "strategy_param_text",
    "sanitize_strategy_label",
    "strategy_from_client_order_id",
    "safe_float",
    "derive_strategy_report_name",
    "resolve_csv_path",
    "fmt_optional_number",
    "minute_session_status",
    "resolve_eod_flatten_timing",
    "ratchet_target_position",
    "strategy_dollar_vol_floor",
    "strategy_quantity_by_symbol",
    "merge_trade_plan",
    "normalize_strategy_output",
    "read_env_file_if_changed",
    "zscore_target_position",
    "build_position_queue_file_name",
    "split_tokens",
    "format_timestamp_ny",
    "is_terminal_order_status",
]
