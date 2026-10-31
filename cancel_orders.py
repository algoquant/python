### Cancel the open trade orders for a symbol, using the Alpaca SDK.
# https://alpaca.markets/sdks/python/trading.html

# Examples:
# Cancel the open trade orders by running the script in the terminal:
#   python3 cancel_orders.py SPY
#   python3 cancel_orders.py SPY --env-file /path/to/.env
#   python3 cancel_orders.py NVDA
#   python3 cancel_orders.py AAPL --env-file /Users/jerzy/Develop/Python/sandbox/.env
#   python3 cancel_orders.py --env-file /Users/jerzy/Develop/trading/config/.env_ratchet_spy   # uses DATA_SYMBOLS or STRATEGY_SYMBOL


import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import dotenv_values
from MachineTrader.helpers.alpacasdk import AlpacAPI
from MachineTrader.helpers.parse_args import resolve_symbols_from_env


alpaca_sdk = AlpacAPI()


def parse_arguments():
    """Parse symbols and optional env-file arguments."""
    parser = argparse.ArgumentParser(description="Cancel open trade orders for a symbol.")
    parser.add_argument("symbols", nargs="*", help="Ticker symbols, e.g. SPY NVDA")
    parser.add_argument("--env-file", type=str, default=".env", help="Path to environment file (default: .env)")
    return parser.parse_args()


args = parse_arguments()
env_file = args.env_file
env_values = dotenv_values(env_file) if env_file and os.path.exists(env_file) else {}
alpaca_sdk.create_trade_clients(env_file=env_file)

# Resolve symbols: CLI first, then DATA_SYMBOLS from env file, then STRATEGY_SYMBOL fallback.
if args.symbols:
    symbols = [str(s).strip().upper() for s in args.symbols if str(s).strip()]
else:
    raw_data_symbols = str(env_values.get("DATA_SYMBOLS", "") or "").strip()
    if raw_data_symbols:
        symbols = [
            s.strip().upper()
            for s in raw_data_symbols.replace(",", " ").split()
            if s.strip()
        ]
    else:
        symbols = resolve_symbols_from_env(env_file)

if not symbols:
    symbols_input = input("Enter symbol(s), separated by spaces: ").strip()
    symbols = [s.strip().upper() for s in symbols_input.replace(",", " ").split() if s.strip()]

if not symbols:
    raise ValueError(
        "No symbols provided. Supply symbols as CLI arguments or set DATA_SYMBOLS/STRATEGY_SYMBOL in the env file."
    )


# Create file name with today's NY date
tzone = ZoneInfo("America/New_York")
log_dir_name = (
    str(env_values.get("LOG_DIR_NAME", "") or "").strip()
    or os.getenv("LOG_DIR_NAME")
    or str(env_values.get("DATA_DIR_NAME", "") or "").strip()
    or os.getenv("DATA_DIR_NAME")
    or "./"
)
log_dir_path = Path(str(log_dir_name)).expanduser()
log_dir_path.mkdir(parents=True, exist_ok=True)
date_short = datetime.now(tzone).strftime("%Y%m%d")
trade_blotter_file = str(log_dir_path / f"cancel_orders_blotter_{date_short}.csv")

# Disable other file outputs so cancel_orders writes only to trade blotter.
alpaca_sdk.state_file = None
alpaca_sdk.submits_file = None
alpaca_sdk.fills_file = None
alpaca_sdk.error_file = None
alpaca_sdk.canceled_file = trade_blotter_file

print(f"Trade blotter file: {trade_blotter_file}\n")


# Get all open orders for each symbol
for symbol in symbols:
    print(f"Canceling open orders for: {symbol}")
    alpaca_sdk.cancel_orders(symbol, canceled_file=trade_blotter_file)

