"""Backtest entrypoint: replays minute bars through the momentum driver.

Runs the real MasterMomentumDriver logic (strategy callbacks, gating, target
maths, execution deltas, position queue, blotter) against a simulated broker and
a clock driven by bar timestamps instead of wall time.

    python3 -m MachineTrader.master_backtest \
        --strategy MachineTrader.strat_trend:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum_trend \
        --date 2026-09-04

Run the ladder strategy against chained parquet bars:

    python3 -m MachineTrader.master_backtest \
        --strategy MachineTrader.strat_ladder:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_ladder \
        --date 2026-09-23 \
        --bars-dir /Users/jerzy/Develop/data/minutes/chained \
        --bar-start-time 08:50

Bars are read from --bars-dir (default /Users/jerzy/Develop/data/minutes/live)
as <SYMBOL>_<YYYYMMDD>.csv. All output is written under --out-dir, which
defaults to <LOG_DIR_NAME>/backtest/<date>/ so live logs and the live position
queue are never touched.

Market hours come from the bar timestamp, so orders are market during RTH and
limit outside it.

Per bar, existing orders are tested against the new high/low/close, fills are
applied to the position queues, then the strategy sees the updated positions.
The shared momentum order manager keeps a pending order across bars while its
symbol's signed strategy delta is unchanged, and cancels/replaces it when that
delta changes. End-of-day liquidation still cancels remaining simulated orders.
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
DEFAULT_BARS_DIR = "/Users/jerzy/Develop/data/minutes/live"

from MachineTrader.helpers.driver_entrypoint_helpers import (
    build_strategy_functions as _build_shared_strategy_functions,
    build_strategy_params as _build_shared_strategy_params,
    create_common_driver_arg_parser as _create_common_driver_arg_parser,
    run_async_entrypoint as _run_async_entrypoint,
)
from MachineTrader.helpers.parse_args import (
    resolve_symbols_and_quantity_map_from_args as _resolve_symbols_and_quantity_map_from_args,
)
from MachineTrader.helpers.driver_common import (
    NY_TZ,
    default_noop_strategy as _default_noop_strategy,
    env_file_has_value as _env_file_has_value,
    load_strategy_callable as _load_strategy_callable,
    merge_strategy_params_with_env as _merge_strategy_params_with_env,
    rounded_print as _rounded_print,
)
from MachineTrader.helpers.backtest_sim import (
    SimAlpacaAPI,
    SimBroker,
    SimClock,
    available_bar_date_bounds,
    load_minute_bars_range,
    minute_bar_time_bounds,
)
from MachineTrader.helpers.live_data import minute_key_from_datetime
import MachineTrader.helpers.file_handlers as _reporting_helpers
from MachineTrader.master_momentum import MasterMomentumDriver

__all__ = ["MasterMomentumBacktestDriver", "main"]


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


class _NullWriter:
    def write(self, value):
        return len(value)

    def flush(self):
        pass


class MasterMomentumBacktestDriver(MasterMomentumDriver):
    def __init__(self, *args, bars_by_minute=None, sim_broker=None, sim_clock=None, **kwargs):
        self._sim_broker = sim_broker
        self._sim_clock = sim_clock
        super().__init__(*args, **kwargs)
        self._bars_by_minute = bars_by_minute or []
        self._last_prices: dict[str, float] = {}
        self._backtest_progress_file_initialized = False

    def _create_alpaca_api(self):
        return SimAlpacaAPI(self._sim_broker)

    def initialize_clients(self):
        self.trading_client = self._sim_broker

    def _is_market_open_now(self) -> bool:
        return self._sim_clock.is_open

    def _sync_market_clock_cache(self):
        # resolve_order_preference() calls the shared helper, whose 60s cache is
        # keyed off real time and would freeze on the first simulated answer.
        self._market_clock_cached_is_open = self._sim_clock.is_open
        self._market_clock_cached_at = datetime.now(NY_TZ)

    def _load_or_create_position_queue_file(self):
        print("📥 ", "Backtest starts flat: skipping position queue file load.")

    def _refresh_broker_state(self) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        positions = {
            symbol: {
                "qty": qty,
                "avg_entry_price": self._sim_broker.cost_basis.get(symbol, 0.0),
                "side": "long" if qty >= 0 else "short",
            }
            for symbol, qty in self._sim_broker.positions.items()
            if qty
        }
        equity = 100000.0 + self._sim_broker.realized_pnl
        account = {"equity": equity, "cash": equity, "buying_power": equity * 4.0}
        return account, positions

    async def _heartbeat_loop(self, interval_seconds: float = 60.0):
        return None

    def _emit_heartbeat(
        self,
        *,
        minute_text: str,
        merged_local_queue: dict[str, list[float]],
        unrealized_by_symbol: dict[str, float],
        realized_local_num: float,
        emit_none_price: bool,
    ):
        if self.strategy_params.get("disable_live_reporting", False):
            return
        return super()._emit_heartbeat(
            minute_text=minute_text,
            merged_local_queue=merged_local_queue,
            unrealized_by_symbol=unrealized_by_symbol,
            realized_local_num=realized_local_num,
            emit_none_price=emit_none_price,
        )

    async def _submit_eod_liquidation_before_strategy(
        self,
        minute_key,
        end_text,
        positions_snapshot,
        *,
        market_is_open_now,
    ) -> bool:
        """Flatten simulated positions immediately at the current bar close."""
        if not self._eod_flatten_enabled():
            return False

        for order in self._sim_broker.cancel_unfilled(self._sim_clock.now_ny):
            await self._handle_confirmation_fanout_payload(order.payload("canceled"))

        flattened = False
        for symbol, quantity in list(self._sim_broker.positions.items()):
            if abs(float(quantity)) <= 1e-9:
                continue
            price = self._last_prices.get(symbol)
            if price is None:
                continue
            side = "sell" if quantity > 0.0 else "buy"
            order = self._sim_broker.submit(
                symbol,
                abs(float(quantity)),
                side,
                "market",
                None,
            )
            self._sim_broker._apply_fill(order, float(price), self._sim_clock.now_ny)
            await self._handle_confirmation_fanout_payload(order.payload("fill"))
            flattened = True
        return flattened

    async def run(self):
        with contextlib.redirect_stdout(_NullWriter()):
            self.initialize_clients()
            self._load_or_create_position_queue_file()
            self._print_startup_configuration()

            for index, (minute_time, bars) in enumerate(self._bars_by_minute):
                date_text = minute_time.strftime("%Y-%m-%d")
                self._sim_clock.advance_to(minute_time)
                self._sync_market_clock_cache()

                for bar in bars:
                    for order in self._sim_broker.resolve_against_bar(bar):
                        await self._handle_confirmation_fanout_payload(order.payload("fill"))

                for bar in bars:
                    self._last_prices[bar["S"]] = float(bar["c"])
                    await self.handle_bar_event(bar)

                self._flush_pending_minute(minute_time)
                await self._drain_minute_chain()

                next_date = None
                if index + 1 < len(self._bars_by_minute):
                    next_date = self._bars_by_minute[index + 1][0].date()
                if next_date != minute_time.date():
                    progress_message = f"Backtest progress: {date_text}"
                    self._write_daily_progress_report(minute_time.date(), progress_message)
                    self._print_backtest_progress(progress_message)

            await self._drain_minute_chain()
        self._print_backtest_summary()

    @staticmethod
    def _print_backtest_progress(message: str) -> None:
        _rounded_print("📅 ", message, file=sys.__stdout__, flush=True)

    def _flush_pending_minute(self, minute_time: datetime):
        """Process this minute now even if some symbols never reported a bar.

        Live waits for the next minute's first bar to detect rollover; a replay knows the
        minute is complete, so the strategy sees each bar in its own minute.
        """
        if self.current_minute_processed or self.current_minute_key is None:
            return
        minute_key = minute_key_from_datetime(minute_time, timezone=NY_TZ)
        if self.current_minute_key != minute_key:
            return
        self._enqueue_minute_processing(self.current_minute_key, dict(self.current_minute_bars))
        self.current_minute_processed = True

    async def _drain_minute_chain(self):
        task = self._minute_process_chain_task
        if task is not None:
            try:
                await task
            except Exception as exc:
                print("⚠️ ", f"Minute processing raised: {exc}")

    def _print_backtest_summary(self):
        broker = self._sim_broker
        unrealized = broker.mark_to_market(self._last_prices)
        open_positions = {s: q for s, q in broker.positions.items() if q}

        fills_path = Path(self.strategy_params["log_dir_name"]) / "backtest_fills.csv"
        fills_path.parent.mkdir(parents=True, exist_ok=True)
        if broker.fills:
            with fills_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(broker.fills[0].keys()))
                writer.writeheader()
                writer.writerows(broker.fills)

        by_symbol: dict[str, int] = {}
        for fill in broker.fills:
            by_symbol[fill["symbol"]] = by_symbol.get(fill["symbol"], 0) + 1

        print("📊 ", "===== Backtest summary =====")
        print("📊 ", f"Fills: {len(broker.fills)} across {len(by_symbol)} symbols")
        print("📊 ", f"Realized PnL: {broker.realized_pnl:.2f}")
        print("📊 ", f"Unrealized PnL: {unrealized:.2f}")
        print("📊 ", f"Total PnL: {broker.realized_pnl + unrealized:.2f}")
        print("📊 ", f"Open positions at end: {open_positions or 'flat'}")
        print("📊 ", f"Unfilled open orders: {len(broker.open_order_ids)}")
        if by_symbol:
            ranked = ", ".join(f"{s}={n}" for s, n in sorted(by_symbol.items(), key=lambda kv: -kv[1]))
            print("📊 ", f"Fills per symbol: {ranked}")
        if broker.fills:
            print("📊 ", f"Fill blotter: {fills_path}")

    def _write_daily_progress_report(self, report_date, progress_message: str):
        path = Path(self.strategy_params["log_dir_name"]) / "backtest_daily_progress.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        position_value = sum(
            float(quantity) * float(self._last_prices.get(symbol, 0.0) or 0.0)
            for symbol, quantity in self._sim_broker.positions.items()
        )
        merged_local_queue = self._merge_position_queue()
        unrealized_by_symbol, _ = self._compute_unrealized_pnl_from_local_signed_queue(merged_local_queue)
        _, _, symbol_total_pnl_by_symbol, strategy_unrealized, strategy_realized = _reporting_helpers.compute_momentum_symbol_pnl_maps(
            self,
            unrealized_by_symbol,
        )
        strategy_total_pnl = strategy_realized + strategy_unrealized
        row = {
            "date": report_date.isoformat(),
            "progress_message": str(progress_message),
            "fills_total": len(self._sim_broker.fills),
            "realized_pnl": round(strategy_realized, 6),
            "unrealized_pnl": round(strategy_unrealized, 6),
            "total_pnl": round(strategy_total_pnl, 6),
            "position_value": round(position_value, 6),
            "open_symbols": sum(1 for quantity in self._sim_broker.positions.values() if abs(float(quantity)) > 1e-9),
            "flat": not any(abs(float(quantity)) > 1e-9 for quantity in self._sim_broker.positions.values()),
        }
        for symbol in sorted(symbol_total_pnl_by_symbol):
            row[f"{symbol}_pnl"] = round(float(symbol_total_pnl_by_symbol[symbol]), 6)
        fieldnames = list(row)
        write_header = not self._backtest_progress_file_initialized
        file_mode = "w" if write_header else "a"
        with path.open(file_mode, newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        self._backtest_progress_file_initialized = True


async def _main_async():
    parser = _create_common_driver_arg_parser(
        description="Backtest the momentum master driver against stored minute bars",
        symbols_help="Symbols to replay. If not provided, reads STRATEGY_SYMBOLS from env file.",
        limit_spread_help="Volatility multiplier for limit pricing.",
        eod_flatten_help="Liquidate all positions before the end of the trading window.",
        message_file_help="Optional csv file path where strategy log messages are appended.",
    )
    parser.set_defaults(env_file=str(DEFAULT_ENV_FILE))
    parser.add_argument("--date", default="", help="Replay one date as YYYY-MM-DD. Without dates, replays the full available bar-data range.")
    parser.add_argument("--start-date", default="", help="Inclusive first replay date as YYYY-MM-DD.")
    parser.add_argument("--end-date", default="", help="Inclusive last replay date as YYYY-MM-DD. Without dates, defaults to the latest bar-data date.")
    parser.add_argument("--bars-dir", default=DEFAULT_BARS_DIR, help=f"Folder holding CSV or chained parquet minute bars (default: {DEFAULT_BARS_DIR}).")
    parser.add_argument("--bar-start-time", default="", help="Daily input-bar start time as HH:MM[:SS], including for chained parquet input.")
    parser.add_argument("--disable-live-reporting", action="store_true", help="Skip per-minute live-style heartbeat, indicator, PnL, position, target, and queue persistence during profiling.")
    parser.add_argument("--out-dir", default="", help="Output folder for backtest logs. Default: <LOG_DIR_NAME>/backtest/<date>/")
    parser.add_argument("--append-logs", action="store_true", help="Append to existing logs in --out-dir instead of clearing them first.")
    args = parser.parse_args()

    symbols, quantity_by_symbol = _resolve_symbols_and_quantity_map_from_args(
        args,
        symbols_key="STRATEGY_SYMBOLS",
        quantities_key="STRATEGY_QUANTITY",
        default_quantity=1.0,
    )
    if not symbols:
        raise ValueError(
            "No symbols provided. Supply symbols as CLI arguments or set STRATEGY_SYMBOLS in the env file."
        )

    date_text = str(args.date or "").strip()
    requested_start = str(args.start_date or "").strip()
    requested_end = str(args.end_date or "").strip()
    if date_text:
        start_date_text = end_date_text = date_text
    elif not requested_start and not requested_end:
        start_date_text, end_date_text = available_bar_date_bounds(args.bars_dir)
    else:
        start_date_text = requested_start or requested_end
        end_date_text = requested_end or requested_start
    strategy_params = _build_shared_strategy_params(args, _merge_strategy_params_with_env)
    strategy_params["disable_live_reporting"] = bool(args.disable_live_reporting)
    strategy_params["quantity_by_symbol"] = dict(quantity_by_symbol)
    strategy_params["strategy_symbols"] = list(symbols)

    live_log_dir = str(strategy_params.get("log_dir_name") or os.getenv("LOG_DIR_NAME") or "logs").strip()
    out_dir = str(args.out_dir or "").strip()
    if not out_dir:
        output_label = start_date_text if start_date_text == end_date_text else f"{start_date_text}_to_{end_date_text}"
        out_dir = str(Path(live_log_dir).expanduser() / "backtest" / output_label)
    if Path(out_dir).expanduser().resolve() == Path(live_log_dir).expanduser().resolve():
        raise ValueError(
            f"--out-dir must not be the live log directory ({live_log_dir}). "
            "Backtest writers share live file names and would overwrite or append to live logs."
        )
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    # Isolate every downstream artifact (position queue, blotter, reports) from live state.
    strategy_params["log_dir_name"] = out_dir
    strategy_params["data_dir_name"] = out_dir
    os.environ["LOG_DIR_NAME"] = out_dir
    os.environ["DATA_DIR_NAME"] = out_dir

    bars_by_minute = load_minute_bars_range(
        args.bars_dir,
        start_date_text,
        end_date_text,
        symbols,
        start_time_text=args.bar_start_time,
    )
    if not bars_by_minute:
        raise ValueError(f"No bars found for {start_date_text} through {end_date_text} in {args.bars_dir}")

    first_bar_time, last_bar_time = minute_bar_time_bounds(bars_by_minute)
    if args.start_time is None and not _env_file_has_value(args.env_file, "START_TIME", "STRATEGY_START_TIME"):
        strategy_params["start_time"] = first_bar_time.strftime("%H:%M:%S")
    if args.end_time is None and not _env_file_has_value(args.env_file, "END_TIME", "STRATEGY_END_TIME"):
        strategy_params["end_time"] = last_bar_time.strftime("%H:%M:%S")

    stale_bars = sum(1 for _, bars in bars_by_minute for bar in bars if bar.get("_stale"))
    complete = sum(1 for _, bars in bars_by_minute if len(bars) == len(symbols))

    if not args.append_logs:
        removed = _clear_previous_logs(out_dir, str(strategy_params.get("strategy_name", "") or ""))
        del removed

    strategy_functions, strategy_labels = _build_shared_strategy_functions(
        args,
        load_strategy_callable=_load_strategy_callable,
        default_noop_strategy=_default_noop_strategy,
        print_fn=print,
        no_strategy_prefix="ℹ️ ",
    )

    clock = SimClock(bars_by_minute[0][0])
    broker = SimBroker(clock)

    del complete, stale_bars

    driver = MasterMomentumBacktestDriver(
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
        bars_by_minute=bars_by_minute,
        sim_broker=broker,
        sim_clock=clock,
    )

    await driver.run()


def _clear_previous_logs(out_dir: str, strategy_name: str) -> int:
    """Remove this backtest's own artifacts so writers do not append to a prior run."""
    directory = Path(out_dir).expanduser()
    patterns = ["backtest_fills.csv"]
    name = strategy_name.strip()
    if name:
        patterns += [f"{name}_*.csv", f"{name}_*.json"]

    removed = 0
    for pattern in patterns:
        for path in sorted(directory.glob(pattern)):
            if path.is_file():
                path.unlink()
                removed += 1
    return removed


def _latest_date_in(bars_dir: str) -> str:
    suffixes = sorted(
        {
            path.stem.rsplit("_", 1)[-1]
            for path in Path(bars_dir).expanduser().glob("*_*.csv")
            if path.stem.rsplit("_", 1)[-1].isdigit()
        }
    )
    if suffixes:
        return datetime.strptime(suffixes[-1], "%Y%m%d").strftime("%Y-%m-%d")

    parquet_paths = sorted(Path(bars_dir).expanduser().glob("*.parquet"))
    if parquet_paths:
        try:
            import pandas as pd

            latest_timestamp = None
            for parquet_path in parquet_paths:
                frame = pd.read_parquet(parquet_path, columns=["timestamp"])
                if frame.empty:
                    continue
                candidate = pd.to_datetime(frame["timestamp"], errors="coerce").max()
                if pd.notna(candidate) and (latest_timestamp is None or candidate > latest_timestamp):
                    latest_timestamp = candidate
            if latest_timestamp is not None:
                return latest_timestamp.strftime("%Y-%m-%d")
        except ImportError as exc:
            raise RuntimeError("Inferring a date from chained parquet bars requires pandas and a parquet engine.") from exc

    raise ValueError(f"No dated CSV or timestamped parquet bars found in {bars_dir}")


def _date_range(start_date_text: str, end_date_text: str) -> list[str]:
    start_date = datetime.strptime(start_date_text, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_text, "%Y-%m-%d").date()
    if end_date < start_date:
        raise ValueError(f"End date {end_date_text} is before start date {start_date_text}")
    dates: list[str] = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.isoformat())
        current_date += timedelta(days=1)
    return dates


def main():
    _run_async_entrypoint(
        _main_async,
        print_fn=print,
        interrupted_message="Interrupted by user",
        runtime_error_help="Momentum backtest driver exited.",
    )


if __name__ == "__main__":
    main()
