"""Liquidate open positions using limit orders.

If symbols are provided, only those symbols are liquidated.
If symbols are omitted, all open positions are considered.
After Alpaca confirms that the selected positions are gone, the corresponding
queues in ``LOG_DIR_NAME/STRATEGY_NAME_positions.json`` are set to empty lists.
Interrupted, failed, or incomplete liquidation leaves the JSON file unchanged.
The script uses AlpacaSDK helpers and loads trade credentials from an
environment file. It listens to the existing DATA_PROXY_URL WebSocket and uses
its latest bars first. On startup it waits up to 65 seconds for the first
completed proxy bar batch; Alpaca market-data credentials are used only for
symbols still missing from the proxy cache. When fallback is needed, requests
are limited to those missing symbols.

Liquidation limit orders are canceled and repriced on the next available bar;
the DAY expiration is the broker order's session lifetime, not the interval
that each individual limit order remains working. A minute-bar trade price
does not guarantee a fill: the corresponding executable bid or ask must reach
the limit while the order is active.

Examples
--------
Liquidate all open positions using STRATEGY_LIMIT_SPREAD from env:

    python3 liquidate_positions_limit.py \
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum

Override limit spread from CLI:

    python3 liquidate_positions_limit.py \
        --limit-spread 0.5 \
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum
"""

from __future__ import annotations

from pathlib import Path
from MachineTrader.helpers.driver_common import rounded_print as _rounded_print
from MachineTrader.helpers.liquidation_limit import liquidate_positions_with_limit_loop
from MachineTrader.helpers.parse_args import (
    create_liquidate_positions_limit_arg_parser,
    parse_liquidate_positions_limit_runtime,
)

DEFAULT_ENV_FILE = Path(__file__).resolve().parent / ".env"


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


def main():
    parser = create_liquidate_positions_limit_arg_parser(default_env_file=DEFAULT_ENV_FILE)
    args = parser.parse_args()
    env_file, symbols, limit_spread, bar_poll_seconds, data_proxy_url = parse_liquidate_positions_limit_runtime(args)

    result = liquidate_positions_with_limit_loop(
        env_file=env_file,
        limit_spread=limit_spread,
        bar_poll_seconds=bar_poll_seconds,
        data_proxy_url=data_proxy_url,
        symbols=symbols,
        print_fn=print,
    )
    if result.get("error"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
