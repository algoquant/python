"""Shared Alpaca trade-confirmation stream owner.

This process owns the single Alpaca ``TradingStream`` connection used for order
updates and fans normalized broker confirmations out to master drivers over a
local websocket.

The local websocket address is configured with ``TRADE_PROXY_URL``. Resolution
order is:

1. ``--listen-url`` CLI override,
2. ``TRADE_PROXY_URL`` in ``--env-file``,
3. process environment ``TRADE_PROXY_URL``,
4. fallback ``ws://127.0.0.1:8766``.

Master drivers prefer to connect to an already running owner, but they can also
auto-start this process when the shared confirmation fanout is unavailable.

Example
-------
Use the env-file-defined confirmation fanout URL:

    python3 -m MachineTrader.confirm_stream_owner \
        --env-file /Users/jerzy/Develop/trading/config/.env_proxy

Override it explicitly on the command line:

    python3 -m MachineTrader.confirm_stream_owner \
        --env-file /Users/jerzy/Develop/trading/config/.env_proxy \
        --listen-url ws://127.0.0.1:8766
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from MachineTrader.helpers.confirmation_stream import (
    DEFAULT_CONFIRMATION_PROXY_URL,
    ConfirmationStreamOwner,
)

DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shared Alpaca trade-confirmation stream owner")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Environment file containing Alpaca trade credentials.")
    parser.add_argument(
        "--listen-url",
        default="",
        help="Local websocket url for driver fanout, for example ws://127.0.0.1:8766",
    )
    return parser.parse_args()


async def _main_async():
    args = _parse_args()
    owner = ConfirmationStreamOwner(env_file=args.env_file, listen_url=args.listen_url)
    try:
        await owner.run()
    finally:
        await owner.close()


def main():
    try:
        asyncio.run(_main_async())
    except KeyboardInterrupt:
        print("🛑 ", "Interrupted by user")


if __name__ == "__main__":
    main()