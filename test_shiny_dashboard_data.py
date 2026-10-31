"""Regression tests for strategy dashboard chart data preparation."""

import importlib.util
import csv
from pathlib import Path
import re
import tempfile
import unittest

import pandas as pd


APP_PATH = Path(__file__).parent / "Shiny" / "app_dashboard.py"
SPEC = importlib.util.spec_from_file_location("strategy_dashboard_under_test", APP_PATH)
DASHBOARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DASHBOARD)


class DashboardChartDataTests(unittest.TestCase):
    def test_duplicate_timestamps_are_reduced_to_unique_ordered_chart_times(self):
        duplicate_rows = pd.DataFrame(
            {
                "timestamp": ["2026-10-16 09:31:00", "2026-10-16 09:30:00", "2026-10-16 09:31:00"],
                "SPY": [101.0, 100.0, 102.0],
            }
        )
        data = {
            "frame": duplicate_rows,
            "data_type": "positions",
            "paths": [Path("test_positions_20261016.csv")],
            "strategy_name": "Test",
            "day_range": "20261016",
        }

        original_price_dir = DASHBOARD.PRICE_DIR
        with tempfile.TemporaryDirectory() as directory:
            DASHBOARD.PRICE_DIR = Path(directory)
            for day, price in (("20261015", 99.0), ("20261016", 100.0), ("20261017", 101.0)):
                price_path = DASHBOARD.PRICE_DIR / f"SPY_{day}.csv"
                with price_path.open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=["timestamp", "close"])
                    writer.writeheader()
                    writer.writerow(
                        {
                            "timestamp": f"{day[:4]}-{day[4:6]}-{day[6:]} 09:30:00",
                            "close": price,
                        }
                    )
            html_doc = DASHBOARD._build_data_chart_html(data, "SPY")
        payload_match = re.search(r"const payload = (\{.*?\});\n", html_doc)
        self.assertIsNotNone(payload_match)
        chart_payload = __import__("json").loads(payload_match.group(1))
        chart_data = chart_payload["data"]
        times = [point["time"] for point in chart_data]

        self.assertEqual(2, len(chart_data))
        self.assertEqual(sorted(set(times)), times)
        self.assertEqual([100.0, 102.0], [point["value"] for point in chart_data])
        self.assertEqual([100.0, 101.0], [point["value"] for point in chart_payload["priceData"]])
        self.assertEqual(chart_payload["sessions"][-1]["from"], chart_payload["initialRange"]["from"])
        self.assertEqual(2, len(chart_payload["sessions"]))
        self.assertIn("payload.sessions", html_doc)
        DASHBOARD.PRICE_DIR = original_price_dir

    def test_sharpema_positions_file_builds_unique_chart_times(self):
        sharpema_path = DASHBOARD.LOG_DIR / "SharpEMA_positions_20261016.csv"
        if not sharpema_path.exists():
            self.skipTest("SharpEMA positions sample is not present")

        data = DASHBOARD._load_all_data(DASHBOARD.LOG_DIR, "SharpEMA", "positions")
        html_doc = DASHBOARD._build_data_chart_html(data, "PLTR")
        payload_match = re.search(r"const payload = (\{.*?\});\n", html_doc)
        self.assertIsNotNone(payload_match)
        chart_data = __import__("json").loads(payload_match.group(1))["data"]
        times = [point["time"] for point in chart_data]

        self.assertEqual(sorted(set(times)), times)


if __name__ == "__main__":
    unittest.main()