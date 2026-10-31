"""Thin entrypoint for live bar ingestion and execution orchestration.

MasterDriver implementation is defined in master_driver_core.py.
This module parses runtime inputs, loads strategies, and delegates execution.

Confirmation Flow
-----------------
All master drivers now require a shared trade-confirmation owner process.
The owner maintains the single Alpaca ``TradingStream`` connection and fans out
order updates to drivers over a local websocket.

If the owner is not already running, the driver attempts to start it safely in
the background and then waits for the confirmation websocket handshake.
Concurrent driver startups converge on a single owner by retrying the shared
fanout port instead of requiring each process to own its own stream.

You can still launch the owner manually from the repo root:

    python3 -m MachineTrader.confirm_stream_owner \
        --env-file /Users/jerzy/Develop/trading/config/.env_proxy

If the owner cannot be reached and auto-start does not succeed, the driver
fails fast at startup.
The local fanout address is configured with ``TRADE_PROXY_URL``. Resolution
order is:

1. ``trade_proxy_url`` in merged strategy parameters,
2. ``TRADE_PROXY_URL`` in the selected ``--env-file``,
3. process environment ``TRADE_PROXY_URL``,
4. fallback ``ws://127.0.0.1:8766``.

Order Lifecycle
---------------
The master driver is the sole owner of live order submission and management.
All master variants use the shared order-management helpers. Submitted order
IDs and signed deltas (buy positive, sell negative) are tracked per symbol.
Pending orders remain open across bars while the strategy delta is unchanged;
when it changes, the driver cancels that symbol's stale tracked order(s) before
submitting the new delta. A zero delta leaves pending orders untouched; a
different nonzero delta requests cancellation before replacement. Broker
confirmations are processed asynchronously from the shared
stream: terminal orders are removed from tracking, and confirmed fills update
the local position queue. Existing strategy-owned open orders are reconciled
once at startup and are not blanket-canceled on each bar.

Examples
--------
Run a single strategy using ``TRADE_PROXY_URL`` from the env file:

    python3 -m MachineTrader.master_driver SPY \
        --strategy MachineTrader.strat_ratchet_single:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_proxy

Run multiple symbols with the same env-driven confirmation fanout:

    python3 -m MachineTrader.master_driver SPY NVDA AAPL \
        --strategy MachineTrader.strat_bollinger_limit:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_proxy

Override the confirmation fanout URL explicitly via environment:

    TRADE_PROXY_URL=ws://127.0.0.1:9001 \
    python3 -m MachineTrader.master_driver SPY \
        --strategy MachineTrader.strat_ratchet_single:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_proxy

Note: ``--strategy`` module paths must be package-qualified (e.g.
``MachineTrader.strat_ratchet_single:call_back``); a bare module name like
``strat_ratchet_single`` is not importable when running via
``python3 -m MachineTrader.master_driver``.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

from MachineTrader.helpers.driver_entrypoint_helpers import (
    build_strategy_functions as _build_shared_strategy_functions,
    build_strategy_params as _build_shared_strategy_params,
    create_common_driver_arg_parser as _create_common_driver_arg_parser,
    run_async_entrypoint as _run_async_entrypoint,
)
from MachineTrader.helpers.parse_args import (
    resolve_symbols_from_args as _resolve_symbols_from_args,
)
from MachineTrader.helpers.driver_common import (
    default_noop_strategy as _default_noop_strategy,
    load_strategy_callable as _load_strategy_callable,
    merge_strategy_params_with_env as _merge_strategy_params_with_env,
    rounded_print as _rounded_print,
)
from MachineTrader.helpers.master_driver_core import MasterDriver

__all__ = ["MasterDriver", "main"]


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


async def _main_async():
    parser = _create_common_driver_arg_parser(
        description="Master driver for strategy orchestration",
        symbols_help="Symbols expected from proxy stream. If not provided, reads STRATEGY_SYMBOL from env file.",
        limit_spread_help="Volatility multiplier for limit pricing: buy = current price - limit_spread * volatility, sell = current price + limit_spread * volatility (default: 0.01).",
        eod_flatten_help="Liquidate all positions before the end of the trading window. Default: enabled. Use --no-eod-flatten to disable.",
        message_file_help="Optional csv file path where strategy log messages are appended (columns: minute,message).",
    )
    parser.set_defaults(env_file=str(DEFAULT_ENV_FILE))
    args = parser.parse_args()

    symbols = _resolve_symbols_from_args(args)
    if not symbols:
        raise ValueError(
            "No symbols provided. Supply symbols as CLI arguments or set STRATEGY_SYMBOL in the env file. "
            "Example: python3 -m MachineTrader.master_driver SPY NVDA"
        )

    strategy_params = _build_shared_strategy_params(args, _merge_strategy_params_with_env)
    strategy_functions, strategy_labels = _build_shared_strategy_functions(
        args,
        load_strategy_callable=_load_strategy_callable,
        default_noop_strategy=_default_noop_strategy,
        print_fn=print,
        no_strategy_prefix="ℹ️ ",
    )

    driver = MasterDriver(
        symbols=symbols,
        strategy_functions=strategy_functions,
        strategy_labels=strategy_labels,
        strategy_params=strategy_params,
        data_proxy_url=args.data_proxy_url,
        env_file=args.env_file,
        preflight_timeout=args.preflight_timeout,
        preflight_wait_for_bars=args.preflight_bars_timeout,
        preflight_connect_only=args.preflight_connect_only,
        cancel_stale_order_seconds=args.cancel_stale_order_seconds,
        order_fill_timeout=args.order_fill_timeout,
        order_fill_poll_seconds=args.order_fill_poll,
    )

    await driver.run()


def main():
    _run_async_entrypoint(
        _main_async,
        print_fn=print,
        interrupted_message="Interrupted by user",
        runtime_error_help="Master driver exited. Start the proxy server and retry.",
    )


if __name__ == "__main__":
    main()
