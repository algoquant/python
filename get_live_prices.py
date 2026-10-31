"""
Get live stock prices using the Alpaca API.
https://alpaca.markets/sdks/python/api_reference/data/stock/requests.html
https://alpaca.markets/sdks/python/api_reference/data/stock.html
https://alpaca.markets/sdks/python/trading.html

Examples:
Use default env file (/Users/jerzy/Develop/trading/config/.env_proxy) and default symbols:
    python3 get_live_prices.py

Request specific symbols:
    python3 get_live_prices.py SPY NVDA

Use a specific env file:
    python3 get_live_prices.py --env-file /path/to/.env

Request latest trades from IEX:
    python3 get_live_prices.py SPY --type trade --feed iex
"""


import pandas as pd
from pathlib import Path
from dotenv import dotenv_values
from MachineTrader.helpers.alpacasdk import AlpacAPI
from MachineTrader.helpers.auth import AccountAuth
from MachineTrader.helpers.parse_args import resolve_symbols_from_env
from MachineTrader.helpers.parse_args import create_common_driver_arg_parser as _create_common_driver_arg_parser
from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest, StockLatestBarRequest
from alpaca.data.enums import DataFeed


# --------- Create the SDK clients --------

DEFAULT_ENV_FILE = Path("/Users/jerzy/Develop/trading/config/.env_proxy")


def _resolve_feed(feed_name: str) -> DataFeed:
    if str(feed_name).strip().lower() == "iex":
        return DataFeed.IEX
    return DataFeed.SIP


def _get_last_close_prices(data_client, symbols, data_feed: DataFeed):
    fallback_prices = {}
    try:
        bars_request = StockLatestBarRequest(symbol_or_symbols=symbols, feed=data_feed)
        latest_bars = data_client.get_stock_latest_bar(bars_request)
        for symbol in symbols:
            bar = latest_bars.get(symbol) if hasattr(latest_bars, "get") else None
            if bar and getattr(bar, "close", None) is not None:
                fallback_prices[symbol] = float(bar.close)
    except Exception as exc:
        print(f"Unable to load fallback last-close prices: {exc}")
    return fallback_prices


def _resolve_symbols(args_symbols, env_file_path: str):
    symbols = [s.strip().upper() for s in args_symbols if str(s or "").strip()]
    if symbols:
        return symbols

    env_values = dotenv_values(env_file_path) if env_file_path else {}
    raw_data_symbols = str(env_values.get("DATA_SYMBOLS", "") or "").strip()
    if raw_data_symbols:
        symbols = [
            s.strip().upper()
            for s in raw_data_symbols.replace(",", " ").split()
            if s.strip()
        ]

    if not symbols:
        symbols = resolve_symbols_from_env(env_file_path)

    return [s.strip().upper() for s in symbols if str(s or "").strip()]


def main():
    parser = _create_common_driver_arg_parser(
        description="Get latest stock prices from Alpaca",
        symbols_help="Symbols to request. If omitted, reads DATA_SYMBOLS from env file (falls back to STRATEGY_SYMBOL).",
        limit_spread_help="Unused in get_live_prices.py.",
        eod_flatten_help="Unused in get_live_prices.py.",
        message_file_help="Unused in get_live_prices.py.",
    )
    parser.set_defaults(env_file=str(DEFAULT_ENV_FILE))
    parser.add_argument(
        "--type",
        choices=["quote", "trade"],
        default="quote",
        help="Price type: latest quote or latest trade.",
    )
    parser.add_argument(
        "--feed",
        choices=["sip", "iex"],
        default="sip",
        help="Alpaca market data feed.",
    )
    args = parser.parse_args()
    env_file_path = str(args.env_file or "").strip() or str(DEFAULT_ENV_FILE)

    symbols = _resolve_symbols(args.symbols, env_file_path)
    if not symbols:
        raise ValueError(
            "No symbols provided. Supply symbols as CLI arguments or set DATA_SYMBOLS (or STRATEGY_SYMBOL) in the env file. "
            "Example: python3 get_live_prices.py SPY NVDA"
        )
    data_feed = _resolve_feed(args.feed)

    auth = AccountAuth(env_file=env_file_path)
    auth.resolve_data_credentials()

    alpaca_sdk = AlpacAPI()
    data_client = alpaca_sdk.create_data_client()

# For options:
# quotes_request = OptionLatestQuotesRequest(symbols=["AAPL240719C00150000"], feed=DataFeed.OPRA)  # Use OPRA for options
# latest_prices = client.get_latest_option_quotes(quotes_request)


    if args.type == "quote":
        print(f"Latest quote prices")
        request_params = StockLatestQuoteRequest(symbol_or_symbols=symbols, feed=data_feed)
        latest_prices = data_client.get_stock_latest_quote(request_params)
        fallback_prices = {}
        if len(latest_prices) > 0:
            for symbol in symbols:
                symbol_prices = latest_prices.get(symbol) if hasattr(latest_prices, "get") else None
                if symbol_prices and symbol_prices.ask_price is not None and symbol_prices.bid_price is not None:
                    symbol_prices = latest_prices[symbol]
                    ask_price = symbol_prices.ask_price
                    bid_price = symbol_prices.bid_price
                    print(f"{symbol}: Ask = {ask_price}, Bid = {bid_price}")
                else:
                    if not fallback_prices:
                        fallback_prices = _get_last_close_prices(data_client, symbols, data_feed)
                    fallback_close = fallback_prices.get(symbol)
                    if fallback_close is not None:
                        print(f"Live quote unavailable for {symbol}. Last valid close = {fallback_close}")
                    else:
                        print(f"No live or fallback prices were returned for {symbol}")
            print("Finished getting live prices")
        else:
            fallback_prices = _get_last_close_prices(data_client, symbols, data_feed)
            if fallback_prices:
                for symbol in symbols:
                    fallback_close = fallback_prices.get(symbol)
                    if fallback_close is not None:
                        print(f"Live quote unavailable for {symbol}. Last valid close = {fallback_close}")
                    else:
                        print(f"No live or fallback prices were returned for {symbol}")
                print("Finished getting live prices")
            else:
                print(f"No prices were returned")
    elif args.type == "trade":
        print(f"Latest trade prices")
        request_params = StockLatestTradeRequest(symbol_or_symbols=symbols, feed=data_feed)
        latest_prices = data_client.get_stock_latest_trade(request_params)
        fallback_prices = {}
        if len(latest_prices) > 0:
            for symbol in symbols:
                symbol_prices = latest_prices.get(symbol) if hasattr(latest_prices, "get") else None
                if symbol_prices and symbol_prices.price is not None:
                    trade_price = symbol_prices.price
                    trade_size = symbol_prices.size
                    print(f"Latest trade price for {symbol}: Price = {trade_price}, Size = {trade_size}")
                else:
                    if not fallback_prices:
                        fallback_prices = _get_last_close_prices(data_client, symbols, data_feed)
                    fallback_close = fallback_prices.get(symbol)
                    if fallback_close is not None:
                        print(f"Live trade unavailable for {symbol}. Last valid close = {fallback_close}")
                    else:
                        print(f"No live or fallback prices were returned for {symbol}")
            print("Finished getting live prices")
        else:
            fallback_prices = _get_last_close_prices(data_client, symbols, data_feed)
            if fallback_prices:
                for symbol in symbols:
                    fallback_close = fallback_prices.get(symbol)
                    if fallback_close is not None:
                        print(f"Live trade unavailable for {symbol}. Last valid close = {fallback_close}")
                    else:
                        print(f"No live or fallback prices were returned for {symbol}")
                print("Finished getting live prices")
            else:
                print(f"No prices were returned")


if __name__ == "__main__":
    main()


''' 

### Alternative method of downloading live prices using requests and the Alpaca endpoint.

import requests
# Define the request parameters for live stock prices
headers = {
    "APCA-API-KEY-ID": DATA_KEY,
    "APCA-API-SECRET-KEY": DATA_SECRET
}
params = {"symbols": symbol, "feed": "sip"}
# Submit the request to get the latest bid/ask prices
response = requests.get(
    "https://data.alpaca.markets/v2/stocks/quotes/latest", 
    headers = headers, 
    params = params)
json_data = response.json()
ask_price = json_data["quotes"][symbol]["ap"]
bid_price = json_data["quotes"][symbol]["bp"]
print(f"Endpoint latest quotes for {symbol}: Ask = {ask_price}, Bid = {bid_price}")


### Get the latest OHLCV bar of prices
response = requests.get(
    "https://data.alpaca.markets/v2/stocks/bars/latest",
    headers=headers,
    params=params
)
bar_data = response.json()
bar_data = bar_data["bars"][symbol]
print(f"Latest price bar for {symbol}: {bar_data}")
# Example: print open, high, low, close, volume
print(f"Open: {bar_data['o']}, High: {bar_data['h']}, Low: {bar_data['l']}, Close: {bar_data['c']}, Volume: {bar_data['v']}, VWAP: {bar_data['vw']}")

'''