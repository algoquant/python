"""
Lightweight argument parsing utilities for MachineTrader.

This module intentionally avoids importing trading runtime dependencies
(e.g., Alpaca SDK) so CLI argument parsing can run independently.
"""

import argparse
import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import dotenv_values


FALLBACK_CONFIRMATION_PROXY_URL = "ws://127.0.0.1:8766"


def resolve_confirmation_proxy_url(
    *,
    env_file: str | None = None,
    explicit_url: str | None = None,
    params: dict[str, Any] | None = None,
) -> str:
    direct_url = str(explicit_url or "").strip()
    if direct_url:
        return direct_url

    strategy_params = params if isinstance(params, dict) else {}
    param_url = str(strategy_params.get("trade_proxy_url", "") or "").strip()
    if param_url:
        return param_url

    env_path = str(env_file or "").strip()
    if env_path:
        try:
            values = dotenv_values(env_path)
        except Exception:
            values = {}
        env_file_url = str(values.get("TRADE_PROXY_URL", "") or "").strip()
        if env_file_url:
            return env_file_url

    process_env_url = str(os.getenv("TRADE_PROXY_URL", "") or "").strip()
    if process_env_url:
        return process_env_url

    return FALLBACK_CONFIRMATION_PROXY_URL


class GetArgs:
    """Class for handling command line argument parsing and user interaction."""

    def __init__(self):
        self.arguments = {}
        self.args = None

    def get_user_input(self, prompt, default_value, value_type=str, choices=None):
        """Get user input with validation and default values."""
        while True:
            if choices:
                prompt_text = f"{prompt} {choices} (default: {default_value}): "
            else:
                prompt_text = f"{prompt} (default: {default_value}): "

            user_input = input(prompt_text).strip()

            if not user_input:
                return default_value

            if choices and user_input not in choices:
                print(f"Invalid choice. Please select from {choices}")
                continue

            try:
                if value_type == float:
                    return float(user_input)
                if value_type == int:
                    return int(user_input)
                return user_input
            except ValueError:
                print(f"Invalid input. Please enter a valid {value_type.__name__}")
                continue

    def normalize_legacy_flags(self, argv, bare_flags=None):
        """Normalize bare flags like 'proxy' to '--proxy' for argparse parsing."""
        if bare_flags is None:
            bare_flags = set()

        normalized = []
        for arg in argv:
            token = (arg or "").strip()
            lower = token.lower()
            if lower in bare_flags and not lower.startswith("--"):
                normalized.append(f"--{lower}")
            else:
                normalized.append(token)
        return normalized

    def parse_custom(self, parser, argv=None):
        """Parse arguments with a caller-provided parser and keep results in GetArgs state."""
        self.args = parser.parse_args(argv)
        self.arguments = vars(self.args).copy()
        return self.args

    @staticmethod
    def parse_time_arg(value: str):
        """Parse HH:MM or HH:MM:SS into datetime.time."""
        text = value.strip()
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).time()
            except ValueError:
                continue
        raise argparse.ArgumentTypeError(f"Invalid time '{value}'. Use HH:MM or HH:MM:SS.")

    def parse_tanaka_intraday_arguments(self, data_proxy_url_default="ws://localhost:8765", argv=None):
        """Parse CLI args for the intraday Tanaka strategy."""
        raw_args = [arg.strip() for arg in (argv if argv is not None else __import__("sys").argv[1:])]

        normalized_reference_args = []
        for arg in raw_args:
            if arg.startswith("-"):
                key, sep, value = arg.partition("=")
                key_norm = "".join(ch for ch in key.lower() if ch.isalnum())
                if key_norm in {"ref", "referenceprice"}:
                    normalized_reference_args.append(
                        f"--reference-price{sep}{value}" if sep else "--reference-price"
                    )
                    continue
            normalized_reference_args.append(arg)

        normalized_args = self.normalize_legacy_flags(normalized_reference_args, {"proxy", "direct"})

        parser = argparse.ArgumentParser(
            description="Run intraday open-price reversion strategy from proxy bars.",
        )
        parser.add_argument("symbol", help="Trading symbol, e.g. SPY")
        parser.add_argument(
            "reference_price_pos",
            nargs="?",
            type=float,
            default=None,
            help="Optional positional fixed reference price.",
        )
        parser.add_argument(
            "--reference-price",
            type=float,
            default=None,
            help="Optional fixed reference price. If omitted, use first regular-session proxy price.",
        )
        parser.add_argument(
            "--start-time",
            type=self.parse_time_arg,
            default=None,
            help="Optional session start time in NY timezone (HH:MM or HH:MM:SS).",
        )
        parser.add_argument(
            "--end-time",
            type=self.parse_time_arg,
            default=None,
            help="Optional session end time in NY timezone (HH:MM or HH:MM:SS).",
        )
        parser.add_argument("--data-proxy-url", default=data_proxy_url_default, help="Local proxy websocket URL")

        args = self.parse_custom(parser, normalized_args)

        if args.reference_price is None and args.reference_price_pos is not None:
            args.reference_price = args.reference_price_pos

        if (args.start_time is None) != (args.end_time is None):
            parser.error("Provide both --start-time and --end-time, or provide neither.")
        if args.start_time is not None and args.end_time is not None and args.start_time >= args.end_time:
            parser.error("--start-time must be earlier than --end-time.")

        return args

    def parse_arguments(self):
        """Parse command line arguments and populate the arguments dictionary."""
        parser = argparse.ArgumentParser(
            description="Trading strategy using Alpaca API",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python3 parse_arguments.py trade_zscore SPY --shares_per_trade 1 --order_type limit --alpha 0.3
  python3 parse_arguments.py trade_zscore AAPL --shares_per_trade 10 --thresholdz 2.0 --delay 5.0
  python3 parse_arguments.py --interactive  # Force interactive mode
            """,
        )

        parser.add_argument(
            "--timezone",
            default=ZoneInfo("America/New_York"),
            help="Timezone for operations (default: America/New_York)",
        )

        parser.add_argument(
            "strategy_function",
            nargs="?",
            help="Name of the trading strategy function (default: trade_zscore)",
        )
        parser.add_argument(
            "symbol",
            nargs="?",
            help="Stock symbol to trade (e.g., SPY, AAPL)",
        )

        parser.add_argument(
            "--shares_per_trade",
            type=float,
            default=1.0,
            help="Number of shares per trade (default: 1)",
        )
        parser.add_argument(
            "--order_type",
            choices=["market", "limit"],
            default="market",
            help="Order type: market or limit (default: market)",
        )
        parser.add_argument(
            "--alpha",
            type=float,
            default=0.9,
            help="EMA decay factor 0 < alpha <= 1 (default: 0.9) - larger values produce smoother EMA",
        )
        parser.add_argument(
            "--vol_floor",
            type=float,
            default=0.1,
            help="Minimum volatility floor (default: 0.1)",
        )
        parser.add_argument(
            "--thresholdz",
            type=float,
            default=1.0,
            help="The Z-score threshold (default: 1.0) - trade if the Z-score exceeds the threshold",
        )
        parser.add_argument(
            "--take_profit",
            type=float,
            default=20.0,
            help="Take profit factor (default: 20.0) - Take profit if the unrealized PnL exceeds the factor times the volatility",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.0,
            help="Delay the trade order submission in seconds (default: 0.0) - to avoid different strategies from submitting at the same time",
        )
        parser.add_argument(
            "--indicator_name",
            default="calc_zscore_price",
            help="Name of the technical indicator to use (default: calc_zscore_price)",
        )
        parser.add_argument(
            "--strategy_name",
            default=None,
            help="Custom name for the trading strategy (default: auto-generated)",
        )
        parser.add_argument(
            "--env_file",
            default=None,
            help="Path to .env file for API keys (default: .env or system environment)",
        )
        parser.add_argument(
            "--interactive",
            action="store_true",
            help="Force interactive mode even if all arguments are provided",
        )

        self.args = parser.parse_args()

        self.arguments = {
            "timezone": self.args.timezone,
            "strategy_function": self.args.strategy_function,
            "symbol": self.args.symbol,
            "shares_per_trade": self.args.shares_per_trade,
            "order_type": self.args.order_type,
            "alpha": self.args.alpha,
            "vol_floor": self.args.vol_floor,
            "thresholdz": self.args.thresholdz,
            "take_profit": self.args.take_profit,
            "delay": self.args.delay,
            "indicator_name": self.args.indicator_name,
            "strategy_name": self.args.strategy_name,
            "env_file": self.args.env_file,
            "interactive": self.args.interactive,
        }

        return self.args

    def prompt_for_missing_args(self):
        """Prompt user for any missing arguments and update arguments dictionary."""
        print("\n=== Trading Strategy Configuration ===")
        print("Press Enter to use default values shown in parentheses\n")

        if str(self.args.timezone) == "America/New_York":
            new_timezone = self.get_user_input("Timezone", "America/New_York")
            if new_timezone != "America/New_York":
                try:
                    self.args.timezone = ZoneInfo(new_timezone)
                    self.arguments["timezone"] = self.args.timezone
                except Exception as e:
                    print(f"Invalid timezone '{new_timezone}': {e}")
                    print("Using default timezone: America/New_York")
                    self.args.timezone = ZoneInfo("America/New_York")
                    self.arguments["timezone"] = self.args.timezone

        if not self.args.strategy_function:
            self.args.strategy_function = self.get_user_input("Trading strategy function name", "trade_zscore")
            self.arguments["strategy_function"] = self.args.strategy_function

        if not self.args.symbol:
            self.args.symbol = self.get_user_input("Enter stock symbol", "SPY").upper()
            self.arguments["symbol"] = self.args.symbol

        if self.args.shares_per_trade is None:
            self.args.shares_per_trade = self.get_user_input("Number of shares per trade", 1.0, float)
            self.arguments["shares_per_trade"] = self.args.shares_per_trade

        if self.args.order_type is None:
            self.args.order_type = self.get_user_input("Order type", "market", str, ["market", "limit"])
            self.arguments["order_type"] = self.args.order_type

        if self.args.alpha is None:
            while True:
                self.args.alpha = self.get_user_input("EMA decay factor (0 < alpha <= 1)", 0.9, float)
                if 0 < self.args.alpha <= 1:
                    break
                print("Alpha must be between 0 and 1")
            self.arguments["alpha"] = self.args.alpha

        if self.args.vol_floor is None:
            while True:
                self.args.vol_floor = self.get_user_input("Minimum volatility floor", 0.1, float)
                if self.args.vol_floor >= 0:
                    break
                print("Volatility floor must be non-negative")
            self.arguments["vol_floor"] = self.args.vol_floor

        if self.args.thresholdz is None:
            while True:
                self.args.thresholdz = self.get_user_input("Z-score threshold for trading", 1.0, float)
                if self.args.thresholdz > 0:
                    break
                print("Risk premium must be positive")
            self.arguments["thresholdz"] = self.args.thresholdz

        if self.args.take_profit is None:
            while True:
                self.args.take_profit = self.get_user_input("Take profit factor", 20.0, float)
                if self.args.take_profit > 0:
                    break
                print("Take profit factor must be positive")
            self.arguments["take_profit"] = self.args.take_profit

        if self.args.delay is None:
            while True:
                self.args.delay = self.get_user_input("Order submission delay (seconds)", 0.0, float)
                if self.args.delay >= 0:
                    break
                print("Delay must be non-negative")
            self.arguments["delay"] = self.args.delay

        if not self.args.indicator_name:
            self.args.indicator_name = self.get_user_input("Technical indicator name", "calc_zscore_price")
            self.arguments["indicator_name"] = self.args.indicator_name

        if self.args.strategy_name is None:
            self.args.strategy_name = self.get_user_input("Custom strategy name (optional)", "", str)
            if not self.args.strategy_name:
                self.args.strategy_name = None
            self.arguments["strategy_name"] = self.args.strategy_name

        if self.args.env_file is None:
            self.args.env_file = self.get_user_input("Path to .env file (optional)", "", str)
            if not self.args.env_file:
                self.args.env_file = None
            self.arguments["env_file"] = self.args.env_file

        return self.args

    def confirm_parameters(self):
        """Show final parameters and ask for confirmation."""
        print("\n=== Final Trading Parameters ===")
        print(f"Timezone: {self.args.timezone}")
        print(f"Strategy function: {self.args.strategy_function}")
        print(f"Symbol: {self.args.symbol}")
        print(f"Shares per trade: {self.args.shares_per_trade}")
        print(f"Order type: {self.args.order_type}")
        print(f"EMA alpha: {self.args.alpha}")
        print(f"Volatility floor: {self.args.vol_floor}")
        print(f"Risk premium (Z-score threshold): {self.args.thresholdz}")
        print(f"Take profit factor: {self.args.take_profit}")
        print(f"Order delay: {self.args.delay} seconds")
        print(f"Strategy name: {self.args.strategy_name if self.args.strategy_name else 'Auto-generated'}")
        print(f"Environment file: {self.args.env_file if self.args.env_file else 'Default (.env or system)'}")

        while True:
            confirm = input("\nProceed with these parameters? (y/n): ").strip().lower()
            if confirm in ["y", "yes"]:
                return True
            if confirm in ["n", "no"]:
                return False
            print("Please enter 'y' or 'n'")


def parse_arguments():
    """Package-level parser function for convenient imports."""
    args_handler = GetArgs()
    return args_handler.parse_arguments()


def prompt_for_missing_args(args):
    """Package-level helper for interactive completion of missing args."""
    args_handler = GetArgs()
    args_handler.args = args
    args_handler.arguments = {
        "timezone": args.timezone,
        "strategy_function": args.strategy_function,
        "symbol": args.symbol,
        "shares_per_trade": args.shares_per_trade,
        "order_type": args.order_type,
        "alpha": args.alpha,
        "vol_floor": args.vol_floor,
        "thresholdz": args.thresholdz,
        "take_profit": args.take_profit,
        "delay": args.delay,
        "indicator_name": args.indicator_name,
        "strategy_name": args.strategy_name,
        "env_file": args.env_file,
        "interactive": args.interactive,
    }
    return args_handler.prompt_for_missing_args()


def confirm_parameters(args):
    """Package-level helper for parameter confirmation prompt."""
    args_handler = GetArgs()
    args_handler.args = args
    return args_handler.confirm_parameters()
