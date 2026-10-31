"""Tests for repairing blank blotter prices from nearest minute closes."""

import csv
import tempfile
import unittest
from pathlib import Path

from repair_blotter_limit_prices import repair_blotters


class BlotterLimitPriceRepairTests(unittest.TestCase):
    def test_dry_run_and_apply_fill_nearest_close_and_add_missing_column(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            logs = root / "logs"
            prices = root / "prices"
            logs.mkdir()
            prices.mkdir()
            blotter = logs / "Demo_blotter_20261022.csv"
            with blotter.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["timestamp_ny", "symbol", "qty", "type", "order_type", "status"])
                writer.writerow(["2026-10-22 09:30:40", "SPY", 2, "submit", "market", "accepted"])
            with (prices / "SPY_20261022.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["symbol", "timestamp", "close"])
                writer.writeheader()
                writer.writerow({"symbol": "SPY", "timestamp": "2026-10-22 09:30:00", "close": "100.00"})
                writer.writerow({"symbol": "SPY", "timestamp": "2026-10-22 09:31:00", "close": "101.00"})

            before = blotter.read_bytes()
            self.assertEqual((1, 0, 0), repair_blotters(logs, prices))
            self.assertEqual(before, blotter.read_bytes())
            self.assertEqual((1, 0, 0), repair_blotters(logs, prices, apply=True, backup_dir=root / "backup"))
            with blotter.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual("101", rows[0]["limit_price"])
            self.assertEqual("accepted", rows[0]["status"])
            self.assertTrue((root / "backup" / blotter.name).is_file())

    def test_unresolved_row_prevents_any_apply(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            logs = root / "logs"
            prices = root / "prices"
            logs.mkdir()
            prices.mkdir()
            blotter = logs / "Demo_blotter_20261022.csv"
            blotter.write_text(
                "timestamp,symbol,limit_price\n2026-10-22 09:30:00,SPY,\n",
                encoding="utf-8",
            )
            before = blotter.read_bytes()
            self.assertEqual((0, 1, 0), repair_blotters(logs, prices, apply=True))
            self.assertEqual(before, blotter.read_bytes())


if __name__ == "__main__":
    unittest.main()