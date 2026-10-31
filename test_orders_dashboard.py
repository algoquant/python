"""Tests for shared price/order loading used by the orders dashboard."""

import csv
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from MachineTrader.helpers.orders_dashboard import (
    align_order_times_to_price_bars,
    build_combined_order_chart_data,
    discover_order_strategies,
    discover_strategy_order_symbols,
    load_order_price_chart_data,
)


class OrdersDashboardTests(unittest.TestCase):
    def test_strategy_choices_use_only_latest_dated_blotters(self):
        with tempfile.TemporaryDirectory() as directory:
            order_dir = Path(directory)
            for name in (
                "Old_blotter_20261015.csv",
                "CurrentA_blotter_20261016.csv",
                "CurrentB_blotter_20261016.csv",
            ):
                (order_dir / name).touch()
            (order_dir / "Undated_orders.csv").touch()

            self.assertEqual(
                ["CurrentA", "CurrentB"],
                discover_order_strategies(order_dir),
            )

    def test_symbol_choices_use_order_day_coverage_and_only_selected_strategy_orders(self):
        with tempfile.TemporaryDirectory() as directory:
            order_dir = Path(directory)
            with (order_dir / "Wider_orders.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["symbol", "timestamp"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"symbol": "AAPL", "timestamp": "2026-10-16 09:30:00"},
                        {"symbol": "XLK", "timestamp": "2026-10-15 09:30:00"},
                        {"symbol": "XLK", "timestamp": "2026-10-16 09:30:00"},
                        {"symbol": "AAPL", "timestamp": "2026-10-16 09:31:00"},
                    ]
                )

            self.assertEqual(
                ["XLK", "AAPL"],
                discover_strategy_order_symbols("Wider", order_dir),
            )

    def test_loads_prices_and_generates_missing_orders_csv_via_extractor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            price_dir = root / "prices"
            order_dir = root / "orders"
            price_dir.mkdir()
            order_dir.mkdir()

            with (price_dir / "ABC_20261016.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["symbol", "timestamp", "open", "high", "low", "close"])
                writer.writeheader()
                writer.writerow({"symbol": "ABC", "timestamp": "2026-10-16 09:30:00", "open": 10, "high": 11, "low": 9, "close": 10.5})
                writer.writerow({"symbol": "ABC", "timestamp": "2026-10-16 09:31:00", "open": 10.5, "high": 12, "low": 10, "close": 11.5})
            with (price_dir / "ABC_20261015.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["symbol", "timestamp", "open", "high", "low", "close"])
                writer.writeheader()
                writer.writerow({"symbol": "ABC", "timestamp": "2026-10-15 09:30:00", "open": 9, "high": 10, "low": 8, "close": 9.5})

            with (order_dir / "Demo_blotter_20261016.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=["timestamp", "symbol", "price", "qty", "type", "order_type", "limit_price", "order_id", "broker_event"],
                )
                writer.writeheader()
                writer.writerow({"timestamp": "2026-10-16 09:30:10", "symbol": "ABC", "price": 10, "qty": 2, "type": "new", "order_type": "limit", "limit_price": 10, "order_id": "order-1", "broker_event": "new"})

            data = load_order_price_chart_data("Demo", "ABC", price_dir=price_dir, order_dir=order_dir)

            self.assertEqual(2, len(data["prices"]))
            self.assertEqual(
                {pd.Timestamp("2026-10-16").date()},
                set(data["prices"]["timestamp"].map(lambda value: value.date())),
            )
            self.assertEqual(1, len(data["orders"]))
            self.assertEqual(-10, data["orders"].iloc[0]["limit_price"])
            self.assertTrue((order_dir / "Demo_orders.csv").is_file())

    def test_aligns_intraminute_order_to_nearest_bar(self):
        prices = pd.DataFrame(
            {"timestamp": pd.to_datetime(["2026-10-16 09:30:00", "2026-10-16 09:31:00"])}
        )
        orders = pd.DataFrame(
            {"timestamp": pd.to_datetime(["2026-10-16 09:30:43"]), "limit_price": [-10.0]}
        )

        aligned = align_order_times_to_price_bars(prices, orders)

        self.assertEqual(pd.Timestamp("2026-10-16 09:31:00"), aligned.iloc[0]["chart_timestamp"])
        self.assertEqual(pd.Timestamp("2026-10-16 09:30:43"), aligned.iloc[0]["timestamp"])

    def test_combines_full_price_history_and_orders_from_multiple_days(self):
        prices = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    [
                        "2026-10-15 09:30:00",
                        "2026-10-15 09:31:00",
                        "2026-10-16 09:30:00",
                        "2026-10-16 09:31:00",
                    ]
                ),
                "close": [100.0, 101.0, 95.0, 96.0],
            }
        )
        orders = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-10-15 09:30:10", "2026-10-16 09:31:10"]),
                "symbol": ["ABC", "ABC"],
                "num_shares": [2.0, 3.0],
                "limit_price": [-100.0, 96.0],
            }
        )

        combined = build_combined_order_chart_data(prices, orders)

        self.assertEqual(["Oct 15, 2026", "Oct 16, 2026"], [session["label"] for session in combined["sessions"]])
        self.assertEqual([100.0, 101.0, 95.0, 96.0], [point["value"] for point in combined["data"]])
        self.assertEqual(["BUY", "SELL"], [order["side"] for order in combined["orders"]])
        self.assertEqual(combined["sessions"][-1]["from"], combined["initialRange"]["from"])
        self.assertEqual(combined["sessions"][-1]["to"], combined["initialRange"]["to"])
        self.assertLess(combined["sessions"][0]["from"], combined["sessions"][1]["from"])


if __name__ == "__main__":
    unittest.main()