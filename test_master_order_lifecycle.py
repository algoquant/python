import os
import csv
import asyncio
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from MachineTrader.helpers.common_driver import CommonDriver
from MachineTrader.helpers.driver_common import NY_TZ
from MachineTrader.helpers.backtest_sim import SimBroker, SimClock
from MachineTrader.helpers.master_driver_core import MasterDriver
from MachineTrader.helpers.master_driver_orders import cancel_strategy_limit_orders_after_market_open, cancel_tracked_order
from MachineTrader.master_backtest import MasterMomentumBacktestDriver
from MachineTrader.master_momentum import MasterMomentumDriver
from MachineTrader.helpers.master_driver_execution import (
    execute_bar_deltas,
    execute_per_share_take_profit_loop,
    execute_symbol_delta,
)


class _OrderGateDriver(CommonDriver):
    def __init__(self):
        self._tracked_open_order_ids = {}
        self.submit_order = Mock()

    @staticmethod
    def _normalize_symbol(symbol):
        return str(symbol or "").strip().upper()


class _TradingClient:
    def __init__(self, open_orders=None):
        self.canceled_order_ids = []
        self.open_orders = list(open_orders or [])
        self.get_orders_calls = 0
        self.clock = SimpleNamespace(is_open=True)

    def get_orders(self, *, filter):
        self.get_orders_calls += 1
        return list(self.open_orders)

    def get_clock(self):
        return self.clock

    def cancel_order_by_id(self, *, order_id):
        self.canceled_order_ids.append(order_id)


class MasterOrderLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_bar_deltas_summarizes_gated_symbols_once(self):
        driver = SimpleNamespace(
            required_symbols={"SPY", "QQQ"},
            _execute_symbol_delta=AsyncMock(return_value="tracked_order_pending"),
        )
        with patch("builtins.print") as mocked_print:
            await execute_bar_deltas(
                driver,
                {"SPY": 1.0, "QQQ": -1.0},
                {"SPY": {"qty": 0.0}, "QQQ": {"qty": 0.0}},
            )

        summaries = [
            call for call in mocked_print.call_args_list
            if "Trade deltas gated type=tracked_order_pending" in str(call)
        ]
        self.assertEqual(1, len(summaries))
        self.assertIn("['QQQ', 'SPY']", str(summaries[0]))

    async def test_last_fill_prices_seed_once_then_follow_confirmed_fills(self):
        driver = object.__new__(MasterMomentumDriver)
        driver.required_symbols = {"SPY", "QQQ"}
        driver.last_fill_prices = {"SPY": None, "QQQ": None}
        driver.latest_execution_hints = {}
        driver._calculate_volatility_gap = Mock(return_value=0.0)
        driver._compute_take_profit_delta = Mock(return_value=(0.0, {}))
        driver._apply_volatility_spacing_gate = Mock()
        context = SimpleNamespace(
            minute_bars={"SPY": {"c": 100.0}, "QQQ": {"close": None}},
            positions={}, account={},
        )
        with patch.object(MasterDriver, "_run_strategies", new_callable=AsyncMock, return_value={}):
            await driver._run_strategies(context)
            self.assertEqual({"SPY": 100.0, "QQQ": None}, driver.last_fill_prices)
            self.assertEqual(driver.last_fill_prices, context.last_fill_prices)
            for invalid_price in (float("nan"), float("inf"), 0.0, -1.0):
                context.minute_bars = {"SPY": {"c": 110.0}, "QQQ": {"c": invalid_price}}
                await driver._run_strategies(context)
                self.assertEqual({"SPY": 100.0, "QQQ": None}, driver.last_fill_prices)
            context.minute_bars["QQQ"] = {"close": 200.0}
            await driver._run_strategies(context)
            self.assertEqual(200.0, driver.last_fill_prices["QQQ"])
            driver._record_confirmed_fill_price("SPY", "buy", 105.0, 1.0, {})
            driver._record_confirmed_fill_price("QQQ", "sell", 202.0, 1.0, {})
            await driver._run_strategies(context)
            self.assertEqual({"SPY": -105.0, "QQQ": 202.0}, driver.last_fill_prices)
            self.assertEqual(driver.last_fill_prices, context.last_fill_prices)

    def test_use_limit_preserves_orders_during_automatic_market_open_cleanup(self):
        driver = self._build_master_driver()
        driver.strategy_params = {"use_limit": True}
        driver._post_open_limit_cleanup_day = None
        driver._cancel_all_limit_orders = Mock(return_value=1)

        canceled_count = cancel_strategy_limit_orders_after_market_open(driver)

        self.assertEqual(0, canceled_count)
        driver._cancel_all_limit_orders.assert_not_called()
        self.assertEqual([], driver.trading_client.canceled_order_ids)

    def test_default_market_open_cleanup_still_cancels_limits(self):
        driver = self._build_master_driver()
        driver.strategy_params = {"use_limit": False}
        driver._post_open_limit_cleanup_day = None
        driver._cancel_all_limit_orders = Mock(return_value=1)

        with patch("MachineTrader.helpers.master_driver_orders.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = datetime(2026, 9, 28, 10, 0, tzinfo=NY_TZ)
            cancel_strategy_limit_orders_after_market_open(driver)

        self.assertEqual("2026-09-28", driver._post_open_limit_cleanup_day)
        driver._cancel_all_limit_orders.assert_called_once_with(
            "SPY",
            strategy_label="strat_cross",
            reason="post_open_cleanup",
        )

    def test_backtest_limit_order_persists_until_later_bar_can_fill_it(self):
        first_bar_time = datetime(2026, 9, 25, 9, 30, tzinfo=NY_TZ)
        clock = SimClock(first_bar_time)
        broker = SimBroker(clock)
        order = broker.submit("SPY", 1, "buy", "limit", 100.0)

        untouched_bar = {
            "S": "SPY",
            "_ny_time": first_bar_time.replace(minute=31),
            "h": 103.0,
            "l": 101.0,
            "c": 102.0,
        }
        self.assertEqual([], broker.resolve_against_bar(untouched_bar))
        self.assertEqual([order.id], broker.open_order_ids)

        later_touch_bar = {
            "S": "SPY",
            "_ny_time": first_bar_time.replace(minute=32),
            "h": 101.0,
            "l": 99.0,
            "c": 100.5,
        }
        filled = broker.resolve_against_bar(later_touch_bar)

        self.assertEqual([order], filled)
        self.assertEqual([], broker.open_order_ids)
        self.assertEqual(1.0, broker.positions["SPY"])
        self.assertEqual(100.0, broker.fills[0]["price"])

    def test_backtest_daily_progress_overwrites_on_first_write_per_run(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            progress_path = Path(tmp_dir) / "backtest_daily_progress.csv"
            progress_path.write_text("old,row\n")
            driver = object.__new__(MasterMomentumBacktestDriver)
            driver.strategy_params = {"log_dir_name": tmp_dir}
            driver._backtest_progress_file_initialized = False
            driver.required_symbols = {"SPY", "QQQ"}
            driver._local_realized_pnl_by_symbol = {"SPY": 3.0, "QQQ": -1.0}
            driver._merge_position_queue = Mock(return_value={"SPY": [-100.0], "QQQ": []})
            driver._compute_unrealized_pnl_from_local_signed_queue = Mock(
                return_value=({"SPY": 5.0, "QQQ": 0.0}, 5.0)
            )
            driver._sim_broker = SimpleNamespace(
                mark_to_market=lambda prices: 0.0,
                realized_pnl=0.0,
                positions={},
                fills=[],
            )
            driver._last_prices = {}

            driver._write_daily_progress_report(
                datetime(2026, 9, 25, tzinfo=NY_TZ).date(),
                "Backtest progress: 2026-09-25",
            )
            driver._write_daily_progress_report(
                datetime(2026, 9, 26, tzinfo=NY_TZ).date(),
                "Backtest progress: 2026-09-26",
            )

            with progress_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(["2026-09-25", "2026-09-26"], [row["date"] for row in rows])

    def test_backtest_daily_progress_writes_symbol_total_pnl_columns(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            progress_path = Path(tmp_dir) / "backtest_daily_progress.csv"
            driver = object.__new__(MasterMomentumBacktestDriver)
            driver.strategy_params = {"log_dir_name": tmp_dir}
            driver._backtest_progress_file_initialized = False
            driver.required_symbols = {"SPY", "QQQ"}
            driver._local_realized_pnl_by_symbol = {"SPY": 3.0, "QQQ": -1.0}
            driver._merge_position_queue = Mock(return_value={"SPY": [-100.0], "QQQ": []})
            driver._compute_unrealized_pnl_from_local_signed_queue = Mock(
                return_value=({"SPY": 5.0, "QQQ": 0.0}, 5.0)
            )
            driver._sim_broker = SimpleNamespace(
                mark_to_market=lambda prices: 5.0,
                realized_pnl=2.0,
                positions={"SPY": 1.0},
                fills=[],
            )
            driver._last_prices = {"SPY": 105.0}

            driver._write_daily_progress_report(
                datetime(2026, 9, 25, tzinfo=NY_TZ).date(),
                "Backtest progress: 2026-09-25",
            )

            with progress_path.open(newline="") as handle:
                row = next(csv.DictReader(handle))

        self.assertEqual("8.0", row["SPY_pnl"])
        self.assertEqual("-1.0", row["QQQ_pnl"])

    def test_eod_local_position_snapshot_uses_signed_queue(self):
        driver = self._build_master_driver()
        driver.required_symbols = {"SPY", "QQQ"}
        driver._position_queue = {"SPY": [-100.0, -101.0], "QQQ": [200.0]}

        self.assertEqual({"QQQ": -1.0, "SPY": 2.0}, driver._local_position_qty_snapshot())

    def test_shared_liquidation_order_is_tracked_for_streamed_fills(self):
        driver = self._build_master_driver()
        order = SimpleNamespace(id="eod-1", symbol="SPY", side="sell", type="limit", qty="2")

        driver._track_shared_liquidation_order(order)

        self.assertIn("eod-1", driver._tracked_open_order_ids)
        self.assertIn("eod-1", driver._session_submitted_order_ids)

    async def test_eod_flatten_disabled_does_not_submit(self):
        driver = self._build_master_driver()
        driver.strategy_params = {"eod_flatten": False}

        submitted = await driver._submit_eod_liquidation_before_strategy(
            (2026, 9, 22, 15, 55),
            "15:55:00",
            {"SPY": {"qty": 2.0}},
            market_is_open_now=True,
        )

        self.assertFalse(submitted)

    async def test_closed_market_eod_uses_shared_loop_with_local_provider(self):
        driver = self._build_master_driver()
        driver.strategy_params = {"eod_flatten": True, "limit_spread": 0.5}
        driver.env_file = "/tmp/strategy.env"
        driver.data_proxy_url = "ws://127.0.0.1:8765"
        driver.alpaca_api = SimpleNamespace(data_client=None)
        to_thread = AsyncMock(return_value={})

        with patch("MachineTrader.helpers.master_driver_core.asyncio.to_thread", to_thread):
            submitted = await driver._submit_eod_liquidation_before_strategy(
                (2026, 9, 22, 16, 0),
                "15:55:00",
                {"SPY": {"qty": 2.0}},
                market_is_open_now=False,
            )

        self.assertTrue(submitted)
        call_kwargs = to_thread.call_args.kwargs
        self.assertIs(call_kwargs["position_qty_provider"].__self__, driver)
        self.assertIs(call_kwargs["on_order_submitted"].__self__, driver)

    def test_eod_trigger_is_claimed_only_once_per_day(self):
        driver = MasterDriver.__new__(MasterDriver)
        driver._eod_trigger_day = None
        minute_key = (2026, 9, 22, 15, 55)

        self.assertTrue(driver._claim_eod_trigger(minute_key))
        self.assertFalse(driver._claim_eod_trigger((2026, 9, 22, 16, 0)))

    def test_eod_trigger_can_be_claimed_on_next_day(self):
        driver = MasterDriver.__new__(MasterDriver)
        driver._eod_trigger_day = "2026-09-22"

        self.assertTrue(driver._claim_eod_trigger((2026, 9, 23, 15, 55)))

    def test_eod_flatten_does_not_restore_prior_day_queue(self):
        driver = MasterDriver.__new__(MasterDriver)
        driver.strategy_params = {"eod_flatten": True, "end_time": "15:55:00"}
        now_ny = datetime.now(NY_TZ).replace(hour=12, minute=0, second=0, microsecond=0)
        yesterday = now_ny - timedelta(days=1)

        self.assertFalse(driver._should_restore_queue_payload({"updated_at": yesterday.isoformat()}, now_ny=now_ny))

    def test_eod_flatten_restores_same_day_queue_for_restart(self):
        driver = MasterDriver.__new__(MasterDriver)
        driver.strategy_params = {"eod_flatten": True, "end_time": "15:55:00"}
        now_ny = datetime.now(NY_TZ).replace(hour=12, minute=0, second=0, microsecond=0)

        self.assertTrue(driver._should_restore_queue_payload({"updated_at": now_ny.isoformat()}, now_ny=now_ny))

    def test_eod_flatten_does_not_restore_same_day_queue_after_end(self):
        driver = MasterDriver.__new__(MasterDriver)
        driver.strategy_params = {"eod_flatten": True, "end_time": "15:55:00"}
        updated_at = datetime.now(NY_TZ).replace(hour=15, minute=44, second=0, microsecond=0)
        now_ny = updated_at.replace(hour=16)

        self.assertFalse(driver._should_restore_queue_payload({"updated_at": updated_at.isoformat()}, now_ny=now_ny))

    def test_hold_overnight_restores_prior_day_queue(self):
        driver = MasterDriver.__new__(MasterDriver)
        driver.strategy_params = {"eod_flatten": False}
        now_ny = datetime.now(NY_TZ)
        yesterday = now_ny - timedelta(days=1)

        self.assertTrue(driver._should_restore_queue_payload({"updated_at": yesterday.isoformat()}, now_ny=now_ny))

    def test_env_reload_updates_params_without_reloading_position_queue(self):
        driver = _OrderGateDriver()
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / "strategy.env"
            env_path.write_text("STRATEGY_EOD_FLATTEN=true\n")
            driver.env_file = str(env_path)
            driver.strategy_params = {"eod_flatten": False}
            driver.base_strategy_params = {"eod_flatten": False}
            driver._load_or_create_position_queue_file = Mock()

            with patch(
                "MachineTrader.helpers.common_driver.merge_strategy_params_with_env",
                return_value={"eod_flatten": True},
            ), patch("builtins.print"):
                driver._reload_strategy_params_from_env()

        self.assertTrue(driver.strategy_params["eod_flatten"])
        driver._load_or_create_position_queue_file.assert_not_called()

    def test_env_reload_skips_reparse_while_env_file_is_unchanged(self):
        driver = _OrderGateDriver()
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / "strategy.env"
            env_path.write_text("STRATEGY_RISK_PREMIUM=1.0\n")
            driver.env_file = str(env_path)
            driver.strategy_params = {"risk_premium": 1.0}
            driver.base_strategy_params = {"risk_premium": 1.0}

            merge = Mock(return_value={"risk_premium": 1.0})
            with patch(
                "MachineTrader.helpers.common_driver.merge_strategy_params_with_env", merge
            ), patch("builtins.print"):
                driver._reload_strategy_params_from_env()
                driver._reload_strategy_params_from_env()
                driver._reload_strategy_params_from_env()

        self.assertEqual(2, merge.call_count)

    def test_env_reload_applies_new_values_after_env_file_changes(self):
        driver = _OrderGateDriver()
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / "strategy.env"
            env_path.write_text("STRATEGY_RISK_PREMIUM=1.0\n")
            driver.env_file = str(env_path)
            driver.strategy_params = {"risk_premium": 1.0}
            driver.base_strategy_params = {"risk_premium": 1.0}

            with patch(
                "MachineTrader.helpers.common_driver.merge_strategy_params_with_env",
                return_value={"risk_premium": 1.0},
            ), patch("builtins.print"):
                driver._reload_strategy_params_from_env()

            env_path.write_text("STRATEGY_RISK_PREMIUM=4.0\n")
            os.utime(env_path, (time.time() + 5, time.time() + 5))

            with patch(
                "MachineTrader.helpers.common_driver.merge_strategy_params_with_env",
                return_value={"risk_premium": 4.0},
            ), patch("builtins.print") as mocked_print:
                driver._reload_strategy_params_from_env()

        self.assertEqual(4.0, driver.strategy_params["risk_premium"])
        self.assertTrue(
            any("Updated parameters: {'risk_premium': 4.0}" in str(call) for call in mocked_print.call_args_list)
        )

    def test_env_reload_overrides_cli_value_after_env_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / "strategy.env"
            env_path.write_text("STRATEGY_RISK_PREMIUM=1.0\n")

            env_driver = _OrderGateDriver()
            env_driver.env_file = str(env_path)
            env_driver.strategy_params = {"risk_premium": 1.0}
            with patch("builtins.print"):
                env_driver._reload_strategy_params_from_env()
                env_path.write_text("STRATEGY_RISK_PREMIUM=4.0\n")
                os.utime(env_path, (time.time() + 5, time.time() + 5))
                env_driver._reload_strategy_params_from_env()
            self.assertEqual(4.0, env_driver.strategy_params["risk_premium"])

            env_path.write_text("STRATEGY_RISK_PREMIUM=1.0\n")
            os.utime(env_path, (time.time() + 10, time.time() + 10))
            cli_driver = _OrderGateDriver()
            cli_driver.env_file = str(env_path)
            cli_driver.strategy_params = {"risk_premium": 2.0}
            env_path.write_text("STRATEGY_RISK_PREMIUM=4.0\n")
            os.utime(env_path, (time.time() + 15, time.time() + 15))
            with patch("builtins.print"):
                cli_driver._reload_strategy_params_from_env()
            self.assertEqual(4.0, cli_driver.strategy_params["risk_premium"])

    def test_env_reload_updates_quantities_for_active_symbols(self):
        driver = _OrderGateDriver()
        driver.required_symbols = {"SPY", "QQQ"}
        driver.symbols = ["SPY", "QQQ"]
        driver.strategy_params = {"quantity_by_symbol": {"SPY": 1.0, "QQQ": 2.0}}
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / "strategy.env"
            env_path.write_text("STRATEGY_SYMBOLS=SPY QQQ\nSTRATEGY_QUANTITY=1 2\n")
            driver.env_file = str(env_path)
            with patch("builtins.print"):
                driver._reload_strategy_params_from_env()
                env_path.write_text("STRATEGY_SYMBOLS=SPY QQQ\nSTRATEGY_QUANTITY=4 5\n")
                os.utime(env_path, (time.time() + 5, time.time() + 5))
                driver._reload_strategy_params_from_env()

        self.assertEqual({"SPY": 4.0, "QQQ": 5.0}, driver.strategy_params["quantity_by_symbol"])

    async def test_watchdog_does_not_reload_env_every_second(self):
        driver = MasterDriver.__new__(MasterDriver)
        driver._reload_strategy_params_from_env = Mock()
        driver._trigger_wall_clock_eod_if_needed = AsyncMock()
        driver._warn_if_no_proxy_bar_timeout_once = Mock(return_value=True)
        driver._cancel_strategy_limit_orders_after_market_open = Mock()

        with patch(
            "MachineTrader.helpers.master_driver_core.asyncio.sleep",
            side_effect=asyncio.CancelledError,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await driver._heartbeat_loop()

        driver._reload_strategy_params_from_env.assert_not_called()

    def test_env_reload_keeps_params_when_env_file_is_missing(self):
        driver = _OrderGateDriver()
        driver.env_file = "/nonexistent/strategy.env"
        driver.strategy_params = {"risk_premium": 3.0}
        driver.base_strategy_params = {"risk_premium": 1.0}

        merge = Mock(return_value={"risk_premium": 1.0})
        with patch(
            "MachineTrader.helpers.common_driver.merge_strategy_params_with_env", merge
        ), patch("builtins.print"):
            driver._reload_strategy_params_from_env()

        merge.assert_not_called()
        self.assertEqual(3.0, driver.strategy_params["risk_premium"])

    async def test_unchanged_delta_keeps_existing_open_order(self):
        driver = _OrderGateDriver()
        driver._track_submitted_order_id(
            order_id="order-1",
            symbol="SPY",
            side="buy",
            order_type="market",
            qty=2,
        )
        driver._tracked_open_order_ids["order-1"]["delta"] = 2.0
        driver._cancel_tracked_order = Mock(return_value=True)

        await execute_symbol_delta(driver, "SPY", 2, 0)

        driver.submit_order.assert_not_called()
        driver._cancel_tracked_order.assert_not_called()
        self.assertEqual({"order-1"}, set(driver._tracked_open_order_ids))

    async def test_changed_delta_waits_for_stream_before_replacing_symbol_order(self):
        driver = self._build_master_driver()
        driver._track_submitted_order_id(
            order_id="order-1",
            symbol="SPY",
            side="buy",
            order_type="limit",
            qty=2,
        )
        driver._track_submitted_order_id(
            order_id="order-stale-2",
            symbol="SPY",
            side="sell",
            order_type="market",
            qty=1,
        )
        driver._session_submitted_order_ids.update({"order-1", "order-stale-2"})
        driver._is_market_open_now = Mock(return_value=True)
        driver._resolve_order_preference = Mock(return_value=("market", None))

        def submit_replacement(symbol, side, qty, order_type, limit_price):
            driver._track_submitted_order_id(
                order_id="order-2",
                symbol=symbol,
                side=driver._normalize_order_status(side),
                order_type=order_type,
                qty=qty,
            )
            return "order-2"

        driver._submit_order = Mock(side_effect=submit_replacement)

        await execute_symbol_delta(driver, "SPY", -3, 0)

        self.assertEqual(["order-1", "order-stale-2"], driver.trading_client.canceled_order_ids)
        self.assertIn("order-1", driver._tracked_open_order_ids)
        self.assertIn("order-stale-2", driver._tracked_open_order_ids)
        driver._submit_order.assert_not_called()

        await execute_symbol_delta(driver, "SPY", -3, 0)
        self.assertEqual(["order-1", "order-stale-2"], driver.trading_client.canceled_order_ids)
        with self._patched_reporting():
            for order_id in ("order-1", "order-stale-2"):
                driver._ingest_broker_order_update(
                    {"id": order_id, "symbol": "SPY", "status": "canceled", "event": "canceled"},
                    apply_fill_updates=True,
                )

        await execute_symbol_delta(driver, "SPY", -3, 0)
        self.assertNotIn("order-1", driver._tracked_open_order_ids)
        self.assertNotIn("order-stale-2", driver._tracked_open_order_ids)
        self.assertEqual(-3.0, driver._last_delta_by_symbol["SPY"])
        self.assertIn("order-2", driver._tracked_open_order_ids)
        driver._submit_order.assert_called_once()

    async def test_zero_delta_keeps_pending_order_until_different_nonzero_delta(self):
        driver = self._build_master_driver()
        driver._track_submitted_order_id(
            order_id="order-1",
            symbol="SPY",
            side="buy",
            order_type="market",
            qty=2,
        )
        driver._session_submitted_order_ids.add("order-1")

        await execute_symbol_delta(driver, "SPY", 0, 0)

        self.assertEqual([], driver.trading_client.canceled_order_ids)
        self.assertIn("order-1", driver._tracked_open_order_ids)
        self.assertFalse(driver._tracked_open_order_ids["order-1"].get("cancel_requested", False))

        result = await execute_symbol_delta(driver, "SPY", -1, 0)

        self.assertEqual("tracked_order_pending", result)
        self.assertEqual(["order-1"], driver.trading_client.canceled_order_ids)
        self.assertIn("order-1", driver._tracked_open_order_ids)
        self.assertTrue(driver._tracked_open_order_ids["order-1"]["cancel_requested"])

    def test_pending_cancel_reply_retains_id_without_error_or_duplicate_cancel(self):
        driver = self._build_master_driver()
        driver._track_submitted_order_id(
            order_id="order-1", symbol="SPY", side="buy", order_type="limit", qty=2,
        )
        driver.trading_client.cancel_order_by_id = Mock(
            side_effect=RuntimeError('{"code":42210000,"message":"order pending cancel"}')
        )
        driver._print_error_with_stale_proxy_throttle = Mock()

        self.assertFalse(cancel_tracked_order(driver, "order-1"))
        self.assertFalse(cancel_tracked_order(driver, "order-1"))
        self.assertIn("order-1", driver._tracked_open_order_ids)
        driver.trading_client.cancel_order_by_id.assert_called_once()
        driver._print_error_with_stale_proxy_throttle.assert_not_called()

    async def test_already_expired_cancel_releases_symbol_for_replacement(self):
        for error_message in (
            'order is already in "expired" state',
            r'{"code":42210000,"message":"order is already in \"expired\" state"}',
        ):
            with self.subTest(error_message=error_message):
                driver = self._build_master_driver()
                driver._track_submitted_order_id(
                    order_id="order-1", symbol="SPY", side="buy", order_type="limit", qty=2,
                )
                driver.trading_client.cancel_order_by_id = Mock(
                    side_effect=RuntimeError(error_message)
                )
                driver._print_error_with_stale_proxy_throttle = Mock()
                driver._is_market_open_now = Mock(return_value=True)
                driver._resolve_order_preference = Mock(return_value=("market", None))
                driver._submit_order = Mock(return_value="replacement-order")

                result = await execute_symbol_delta(driver, "SPY", -3, 0)

                self.assertNotEqual("tracked_order_pending", result)
                self.assertNotIn("order-1", driver._tracked_open_order_ids)
                driver._submit_order.assert_called_once()
                self.assertEqual("SPY", driver._submit_order.call_args.args[0])
                self.assertEqual(3.0, driver._submit_order.call_args.args[2])
                driver._print_error_with_stale_proxy_throttle.assert_not_called()

    def test_cancel_failure_mentioning_expired_without_terminal_state_keeps_tracking(self):
        driver = self._build_master_driver()
        driver._track_submitted_order_id(
            order_id="order-1", symbol="SPY", side="buy", order_type="limit", qty=2,
        )
        driver.trading_client.cancel_order_by_id = Mock(
            side_effect=RuntimeError("request expired before cancellation could be confirmed")
        )
        driver._print_error_with_stale_proxy_throttle = Mock()

        self.assertFalse(cancel_tracked_order(driver, "order-1"))
        self.assertIn("order-1", driver._tracked_open_order_ids)
        driver._print_error_with_stale_proxy_throttle.assert_called_once()

    def test_stale_cleanup_keeps_partial_fill_tracked_until_terminal_stream_event(self):
        driver = self._build_master_driver()
        driver._track_submitted_order_id(
            order_id="order-1", symbol="SPY", side="buy", order_type="limit", qty=2,
        )
        driver._tracked_open_order_ids["order-1"]["submitted_at"] = datetime.now(NY_TZ) - timedelta(seconds=120)
        driver._broker_order_updates_by_id["order-1"] = {
            "status": "partially_filled", "event": "partial_fill",
        }

        self.assertEqual(1, driver._cancel_stale_tracked_open_orders_between_bars())
        self.assertIn("order-1", driver._tracked_open_order_ids)
        self.assertEqual(0, driver._cancel_stale_tracked_open_orders_between_bars())
        self.assertEqual(["order-1"], driver.trading_client.canceled_order_ids)

    def test_already_filled_cancel_waits_for_stream_without_polling(self):
        driver = self._build_master_driver()
        driver._track_submitted_order_id(
            order_id="order-1", symbol="SPY", side="buy", order_type="market", qty=2,
        )
        driver.trading_client.cancel_order_by_id = Mock(
            side_effect=RuntimeError('order is already in "filled" state')
        )
        driver._recover_filled_order_by_id = Mock()

        self.assertFalse(cancel_tracked_order(driver, "order-1"))
        self.assertIn("order-1", driver._tracked_open_order_ids)
        driver._recover_filled_order_by_id.assert_not_called()

    def test_terminal_stream_status_releases_pending_cancellation(self):
        for status in ("canceled", "rejected", "expired"):
            with self.subTest(status=status):
                driver = self._build_master_driver()
                driver._track_submitted_order_id(
                    order_id="order-1", symbol="SPY", side="buy", order_type="limit", qty=2,
                )
                driver._session_submitted_order_ids.add("order-1")
                cancel_tracked_order(driver, "order-1")
                with self._patched_reporting():
                    driver._ingest_broker_order_update(
                        {"id": "order-1", "symbol": "SPY", "status": status, "event": status},
                        apply_fill_updates=True,
                    )
                self.assertNotIn("order-1", driver._tracked_open_order_ids)

    async def test_cancel_pending_symbol_does_not_block_other_symbols(self):
        driver = self._build_master_driver()
        driver._track_submitted_order_id(
            order_id="order-1", symbol="SPY", side="buy", order_type="limit", qty=2,
        )
        driver._is_market_open_now = Mock(return_value=True)
        driver._resolve_order_preference = Mock(return_value=("market", None))
        driver._submit_order = Mock(return_value="other-order")

        await execute_symbol_delta(driver, "SPY", -3, 0)
        await execute_symbol_delta(driver, "QQQ", 1, 0)

        self.assertIn("order-1", driver._tracked_open_order_ids)
        driver._submit_order.assert_called_once()
        self.assertEqual("QQQ", driver._submit_order.call_args.args[0])

    async def test_per_share_take_profit_does_not_wait_for_fill_resolution(self):
        driver = self._build_master_driver()
        driver._submit_order = Mock(return_value="take-profit-1")

        with patch(
            "MachineTrader.helpers.master_driver_execution.wait_for_market_order_resolution",
            new_callable=AsyncMock,
        ) as wait_for_resolution:
            await execute_per_share_take_profit_loop(
                driver,
                "SPY",
                -2,
                {"per_share_take_profit_level": 0.25},
            )

        driver._submit_order.assert_called_once()
        wait_for_resolution.assert_not_awaited()

    def test_streamed_fill_updates_queue_and_removes_open_order_id(self):
        driver = self._build_master_driver()
        driver._track_submitted_order_id(
            order_id="order-1",
            symbol="SPY",
            side="buy",
            order_type="market",
            qty=2,
        )
        driver._session_submitted_order_ids.add("order-1")
        driver._working_balance_by_symbol["SPY"] = 2.0
        cancel_tracked_order(driver, "order-1")
        self.assertIn("order-1", driver._tracked_open_order_ids)

        payload = {
            "id": "order-1",
            "symbol": "SPY",
            "side": "buy",
            "status": "filled",
            "event": "fill",
            "filled_qty": "2",
            "filled_avg_price": "100.25",
        }
        with self._patched_reporting():
            driver._ingest_broker_order_update(payload, apply_fill_updates=True)

        self.assertNotIn("order-1", driver._tracked_open_order_ids)
        self.assertEqual([-100.25, -100.25], driver._position_queue["SPY"])
        self.assertEqual(0.0, driver._working_balance_by_symbol["SPY"])

    def test_open_order_reconciliation_tracks_without_canceling_and_runs_once(self):
        driver = self._build_master_driver()
        driver.strategy_functions = [lambda context: None]
        driver.strategy_functions[0].__module__ = "MachineTrader.strat_cross"
        driver.strategy_params = {}
        driver.trading_state = SimpleNamespace(strategy_name="strat_cross")
        driver.trading_client.open_orders = [
            SimpleNamespace(
                id="existing-1",
                symbol="SPY",
                side="buy",
                type="limit",
                qty="1",
                status="new",
                client_order_id="md_strat_cross_SPY_123456",
            )
        ]

        first_tracked_count = driver._reconcile_open_orders_once()
        second_tracked_count = driver._reconcile_open_orders_once()

        self.assertEqual(1, first_tracked_count)
        self.assertEqual(0, second_tracked_count)
        self.assertEqual(1, driver.trading_client.get_orders_calls)
        self.assertEqual([], driver.trading_client.canceled_order_ids)
        self.assertIn("existing-1", driver._tracked_open_order_ids)

    @staticmethod
    def _build_master_driver():
        driver = object.__new__(MasterDriver)
        strategy_function = lambda context: None
        strategy_function.__module__ = "MachineTrader.strat_cross"
        driver.symbols = ["SPY"]
        driver.required_symbols = {"SPY"}
        driver.strategy_functions = [strategy_function]
        driver.strategy_params = {}
        driver.trading_state = SimpleNamespace(strategy_name="strat_cross")
        driver.trading_client = _TradingClient()
        driver._tracked_open_order_ids = {}
        driver._open_orders_reconciled = False
        driver._last_delta_by_symbol = {"SPY": 0.0}
        driver._session_submitted_order_ids = set()
        driver._submitted_order_ids_by_symbol = {}
        driver._submitted_order_types_by_symbol = {}
        driver._submitted_order_count_by_symbol = {}
        driver._broker_order_updates_by_id = {}
        driver._broker_order_update_events_by_id = {}
        driver._processed_session_fill_confirmations = set()
        driver._filled_qty_accounted_by_order_id = {}
        driver._selected_unwind_queue_prices_by_order_id = {}
        driver._position_queue = {"SPY": []}
        driver._working_balance_by_symbol = {"SPY": 0.0}
        driver._local_realized_pnl_by_symbol = {"SPY": 0.0}
        driver._local_realized_pnl_total = 0.0
        driver.latest_symbol_prices = {"SPY": 100.25}
        driver._broker_response_messages_recent = []
        driver._stale_proxy_error_log_minute_by_key = {}
        return driver

    @staticmethod
    def _patched_reporting():
        record_patch = patch(
            "MachineTrader.helpers.master_driver_core._reporting_helpers.record_broker_order_update"
        )
        message_patch = patch(
            "MachineTrader.helpers.master_driver_core._reporting_helpers.broker_message_from_payload",
            return_value="",
        )

        class _ReportingPatches:
            def __enter__(self):
                record_patch.start()
                message_patch.start()

            def __exit__(self, exc_type, exc_value, traceback):
                message_patch.stop()
                record_patch.stop()

        return _ReportingPatches()


if __name__ == "__main__":
    unittest.main()