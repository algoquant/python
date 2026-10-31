import asyncio
import json
import threading
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from alpaca.data.enums import DataFeed

from MachineTrader.helpers.live_data import (
    collect_latest_proxy_bars,
    latest_alpaca_market_data_with_feed_fallback,
    stream_proxy_events,
)
from MachineTrader.helpers.file_handlers import clear_persisted_position_queues
from MachineTrader.helpers.liquidation_limit import (
    _fetch_alpaca_fallback_data,
    _wait_for_proxy_snapshot,
)
from MachineTrader.helpers.setup_strat import read_env_file_if_changed


class LiquidationDataFallbackTests(unittest.TestCase):
    def test_complete_proxy_coverage_does_not_initialize_alpaca_data_client(self):
        alpaca_sdk = Mock()

        result = _fetch_alpaca_fallback_data(
            [],
            env_file="/tmp/unused.env",
            alpaca_sdk=alpaca_sdk,
            data_client=None,
            print_fn=Mock(),
        )

        self.assertEqual((None, None, None, {}, {}), result)
        alpaca_sdk.create_data_client.assert_not_called()
        alpaca_sdk.get_data_client.assert_not_called()

    def test_partial_proxy_coverage_requests_only_missing_symbols(self):
        data_client = Mock()
        alpaca_sdk = Mock()
        fallback_result = (DataFeed.IEX, "bar-request", {"QCOM": object()}, {"QCOM": object()})

        with patch(
            "MachineTrader.helpers.liquidation_limit.latest_alpaca_market_data_with_feed_fallback",
            return_value=fallback_result,
        ) as fetch_fallback:
            result = _fetch_alpaca_fallback_data(
                ["QCOM"],
                env_file="/tmp/cross.env",
                alpaca_sdk=alpaca_sdk,
                data_client=data_client,
                print_fn=Mock(),
            )

        fetch_fallback.assert_called_once_with(
            data_client=data_client,
            symbols=["QCOM"],
            print_fn=fetch_fallback.call_args.kwargs["print_fn"],
        )
        self.assertIs(data_client, result[0])
        self.assertEqual(fallback_result, result[1:])
        alpaca_sdk.create_data_client.assert_not_called()

    def test_sip_quote_failure_uses_same_data_client_with_iex(self):
        data_client = Mock()
        data_client.get_stock_latest_bar.side_effect = [
            {"SPY": object()},
            {"SPY": object()},
        ]
        data_client.get_stock_latest_quote.side_effect = [
            RuntimeError("SIP unavailable"),
            {"SPY": object()},
        ]
        print_fn = Mock()

        feed, request, bars, quotes = latest_alpaca_market_data_with_feed_fallback(
            data_client=data_client,
            symbols=["SPY"],
            print_fn=print_fn,
        )

        self.assertEqual(DataFeed.IEX, feed)
        self.assertEqual(DataFeed.IEX, request.feed)
        self.assertIn("SPY", bars)
        self.assertIn("SPY", quotes)
        self.assertEqual(DataFeed.SIP, data_client.get_stock_latest_bar.call_args_list[0].args[0].feed)
        self.assertEqual(DataFeed.IEX, data_client.get_stock_latest_bar.call_args_list[1].args[0].feed)
        print_fn.assert_called_once()

    def test_sip_and_iex_failure_raises_fatal_error(self):
        failed_client = Mock()
        failed_client.get_stock_latest_bar.side_effect = [
            RuntimeError("SIP failed"),
            RuntimeError("IEX failed"),
        ]

        with self.assertRaisesRegex(RuntimeError, "SIP and IEX market data requests failed"):
            latest_alpaca_market_data_with_feed_fallback(
                data_client=failed_client,
                symbols=["SPY"],
                print_fn=Mock(),
            )

        self.assertEqual(2, failed_client.get_stock_latest_bar.call_count)

    def test_sip_success_is_used_without_iex(self):
        data_client = Mock()
        data_client.get_stock_latest_bar.return_value = {"SPY": object()}
        data_client.get_stock_latest_quote.return_value = {"SPY": object()}

        feed, request, bars, quotes = latest_alpaca_market_data_with_feed_fallback(
            data_client=data_client,
            symbols=["SPY"],
            print_fn=Mock(),
        )

        self.assertEqual(DataFeed.SIP, feed)
        self.assertEqual(DataFeed.SIP, request.feed)
        self.assertIn("SPY", bars)
        self.assertIn("SPY", quotes)
        self.assertEqual(1, data_client.get_stock_latest_bar.call_count)


class ProxySnapshotTests(unittest.TestCase):
    def test_initial_proxy_wait_finishes_when_all_symbols_arrive(self):
        snapshots = [
            {"AAPL": {"c": 200.0}},
            {"AAPL": {"c": 200.0}, "QCOM": {"c": 170.0}},
        ]

        with patch(
            "MachineTrader.helpers.liquidation_limit.time.monotonic",
            side_effect=[10.0, 10.1],
        ), patch("MachineTrader.helpers.liquidation_limit.time.sleep") as sleep:
            result = _wait_for_proxy_snapshot(
                ["AAPL", "QCOM"],
                lambda _symbols: snapshots.pop(0),
                timeout_seconds=65.0,
                poll_seconds=1.0,
            )

        self.assertEqual({"AAPL", "QCOM"}, set(result))
        sleep.assert_called_once()

    def test_collects_complete_proxy_bar_snapshot(self):
        payload = json.dumps(
            [
                {"T": "b", "S": "SPY", "c": 700.0, "t": "2026-09-21T14:00:00Z"},
                {"T": "b", "S": "QQQ", "c": 600.0, "t": "2026-09-21T14:00:00Z"},
            ]
        )

        class FakeConnection:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            async def recv(self):
                return payload

        with patch("MachineTrader.helpers.live_data.websockets.connect", return_value=FakeConnection()):
            bars = asyncio.run(
                collect_latest_proxy_bars(
                    ["SPY", "QQQ"],
                    data_proxy_url="ws://localhost:8765",
                    timeout_seconds=1.0,
                )
            )

        self.assertEqual({"QQQ", "SPY"}, set(bars))
        self.assertEqual(700.0, bars["SPY"]["c"])

    def test_shared_proxy_listener_streams_events_and_stops(self):
        stop_event = threading.Event()
        seen_events = []
        payload = json.dumps({"T": "b", "S": "QCOM", "c": 169.7})

        class FakeConnection:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            async def recv(self):
                return payload

        async def on_event(event):
            seen_events.append(event)
            stop_event.set()

        async def run_listener():
            await stream_proxy_events(
                "ws://localhost:8765",
                on_event,
                stop_event=stop_event,
            )

        with patch("MachineTrader.helpers.live_data.websockets.connect", return_value=FakeConnection()):
            asyncio.run(run_listener())

        self.assertEqual([{"T": "b", "S": "QCOM", "c": 169.7}], seen_events)


class EnvironmentReloadTests(unittest.TestCase):
    def test_reads_env_only_after_file_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / "liquidation.env"
            env_path.write_text("STRATEGY_LIMIT_SPREAD=0.10\n", encoding="utf-8")

            values, signature = read_env_file_if_changed(str(env_path))
            unchanged_values, unchanged_signature = read_env_file_if_changed(str(env_path), signature)
            env_path.write_text("STRATEGY_LIMIT_SPREAD=0.25\n", encoding="utf-8")
            changed_values, changed_signature = read_env_file_if_changed(str(env_path), unchanged_signature)

        self.assertEqual("0.10", values["STRATEGY_LIMIT_SPREAD"])
        self.assertIsNone(unchanged_values)
        self.assertEqual(signature, unchanged_signature)
        self.assertEqual("0.25", changed_values["STRATEGY_LIMIT_SPREAD"])
        self.assertNotEqual(unchanged_signature, changed_signature)


class PositionQueueResetTests(unittest.TestCase):
    def test_clears_all_positions_and_preserves_realized_pnl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            queue_path = Path(temp_dir) / "Momentum_Ratchet_positions.json"
            queue_path.write_text(
                json.dumps(
                    {
                        "symbols": ["SPY", "QQQ"],
                        "position_queue": {"SPY": [-100.0], "QQQ": [200.0]},
                        "local_realized_pnl_total": 12.5,
                        "local_realized_pnl_by_symbol": {"SPY": 10.0, "QQQ": 2.5},
                    }
                ),
                encoding="utf-8",
            )

            result_path = clear_persisted_position_queues(
                strategy_name="Momentum_Ratchet",
                log_dir_name=temp_dir,
            )
            payload = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual({"QQQ": [], "SPY": []}, payload["position_queue"])
        self.assertEqual(12.5, payload["local_realized_pnl_total"])

    def test_clears_only_selected_symbols(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            queue_path = Path(temp_dir) / "Momentum_Ratchet_positions.json"
            queue_path.write_text(
                json.dumps({"position_queue": {"SPY": [-100.0], "QQQ": [200.0]}}),
                encoding="utf-8",
            )

            result_path = clear_persisted_position_queues(
                strategy_name="Momentum_Ratchet",
                log_dir_name=temp_dir,
                symbols=["SPY"],
            )
            payload = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual({"QQQ": [200.0], "SPY": []}, payload["position_queue"])


if __name__ == "__main__":
    unittest.main()