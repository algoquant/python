"""Tests for shared inputs used by the combined price/feature dashboard."""

import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from MachineTrader.helpers.stratviz_dashboard import load_order_feature_chart_data
from MachineTrader.helpers.timestamp_utils import (
    NY_TZ,
    coerce_datetime_ny,
    lightweight_charts_ny_time_formatters_js,
)


class StratVizDashboardTests(unittest.TestCase):
    def test_csv_wall_time_keeps_new_york_time_on_chart_axis(self):
        csv_timestamp = "2026-10-16 16:00:00"
        parsed = coerce_datetime_ny(csv_timestamp, fallback_to_now=False)
        chart_epoch = int(parsed.timestamp())

        self.assertEqual("16:00", datetime.fromtimestamp(chart_epoch, NY_TZ).strftime("%H:%M"))
        self.assertIn("timeZone: 'America/New_York'", lightweight_charts_ny_time_formatters_js())

    def test_loads_feature_history_and_prices_through_latest_available_day(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prices_dir = root / "prices"
            logs_dir = root / "logs"
            prices_dir.mkdir()
            logs_dir.mkdir()

            for date, price in (
                ("20261013", 99.0),
                ("20261014", 100.0),
                ("20261015", 102.0),
                ("20261016", 105.0),
                ("20261017", 108.0),
            ):
                with (prices_dir / f"ABC_{date}.csv").open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=["symbol", "timestamp", "open", "high", "low", "close"])
                    writer.writeheader()
                    day = f"{date[:4]}-{date[4:6]}-{date[6:]}"
                    writer.writerow({"symbol": "ABC", "timestamp": f"{day} 09:30:00", "open": price, "high": price + 1, "low": price - 1, "close": price})

            with (logs_dir / "Demo_orders.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["timestamp", "symbol", "num_shares", "limit_price"])
                writer.writeheader()
                writer.writerow({"timestamp": "2026-10-15 09:30:00", "symbol": "ABC", "num_shares": 1, "limit_price": -100})
                writer.writerow({"timestamp": "2026-10-16 09:30:00", "symbol": "ABC", "num_shares": 1, "limit_price": 102})

            for date, feature_value in (
                ("20261014", 1.0),
                ("20261015", 1.5),
                ("20261016", 2.5),
                ("20261017", 3.5),
            ):
                with (logs_dir / f"Demo_zscore_{date}.csv").open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=["timestamp", "ABC"])
                    writer.writeheader()
                    day = f"{date[:4]}-{date[4:6]}-{date[6:]}"
                    writer.writerow({"timestamp": f"{day} 09:30:00", "ABC": feature_value})

            result = load_order_feature_chart_data(
                "Demo",
                "ABC",
                "zscore",
                log_dir=logs_dir,
                price_dir=prices_dir,
            )

            self.assertEqual([100.0, 102.0, 105.0, 108.0], result["prices"]["close"].tolist())
            self.assertEqual([1.0, 1.5, 2.5, 3.5], [point["value"] for point in result["feature_data"]])
            self.assertTrue(result["feature_available"])
            self.assertEqual(2, len(result["orders"]))


if __name__ == "__main__":
    unittest.main()
