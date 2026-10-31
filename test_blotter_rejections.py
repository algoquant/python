import csv
import tempfile
import unittest
from types import SimpleNamespace

from MachineTrader.helpers.file_handlers import build_trade_blotter_owner, record_broker_order_update
from MachineTrader.helpers.master_driver_core import MasterDriver


class BlotterRejectionTests(unittest.TestCase):
    def test_submit_rejection_is_written_with_broker_reason_and_code(self):
        with tempfile.TemporaryDirectory() as log_dir:
            driver = object.__new__(MasterDriver)
            owner = build_trade_blotter_owner(strategy_name="test", log_dir_name=log_dir)
            driver.__dict__.update(owner.__dict__)
            driver.latest_symbol_prices = {"SPY": 99.5}
            driver.alpaca_api = SimpleNamespace(last_submit_attempt={
                "symbol": "SPY", "shares_available": 2.0, "reason": "submission failed",
            })
            driver._last_submit_rejection = {
                "symbol": "SPY", "message": "insufficient buying power", "code": 40310000,
            }
            driver._record_submit_failure("SPY", "sell", 3.0, "limit", 100.0)
            driver._last_submit_rejection = None
            driver.alpaca_api.last_submit_attempt["reason"] = "no shares available"
            driver._record_submit_failure("SPY", "buy", 3.0, "market", None)
            with driver._trade_blotter_path.open(newline="") as blotter:
                rows = list(csv.DictReader(blotter))
            self.assertEqual(2, len(rows))
            self.assertEqual("reject", rows[0]["type"])
            self.assertEqual(-3.0, float(rows[0]["qty"]))
            self.assertEqual(100.0, float(rows[0]["limit_price"]))
            self.assertIn("insufficient buying power", rows[0]["message"])
            self.assertIn("40310000", rows[0]["message"])
            self.assertEqual("submit_failed", rows[1]["type"])
            self.assertEqual(99.5, float(rows[1]["limit_price"]))

    def test_stream_rejection_is_written_once(self):
        with tempfile.TemporaryDirectory() as log_dir:
            owner = build_trade_blotter_owner(strategy_name="test", log_dir_name=log_dir)
            owner.latest_symbol_prices = {"SPY": 101.25}
            order = {
                "id": "rejected-order", "symbol": "SPY", "side": "buy", "qty": "2",
                "type": "market", "status": "rejected", "message": "short sale rejected",
                "updated_at": "2026-10-02T14:00:00Z",
            }
            record_broker_order_update(owner, order)
            record_broker_order_update(owner, order)
            with owner._trade_blotter_path.open(newline="") as blotter:
                rows = list(csv.DictReader(blotter))
            self.assertEqual(1, len(rows))
            self.assertEqual("reject", rows[0]["type"])
            self.assertEqual(101.25, float(rows[0]["limit_price"]))
            self.assertIn("short sale rejected", rows[0]["message"])