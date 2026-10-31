"""Tests for extracting unique submitted orders from blotter CSV files."""

import csv
import math
import tempfile
import unittest
from pathlib import Path

from MachineTrader.helpers.blotter_orders import main
from MachineTrader.helpers.file_handlers import extract_signed_orders_from_blotters


class ExtractBlotterOrdersTests(unittest.TestCase):
    def test_deduplicates_orders_and_matches_market_fill_prices_by_order_id(self):
        fields = [
            "timestamp", "symbol", "price", "qty", "type", "order_type", "limit_price",
            "message", "broker_filled_qty", "order_id", "broker_event", "broker_execution_id",
            "broker_timestamp", "broker_event_price", "broker_event_qty",
        ]
        rows = [
            {
                "timestamp": "2026-10-16 09:30:00", "symbol": "ABC", "price": "10",
                "qty": "3", "type": "pending_new", "order_type": "ordertype.limit",
                "limit_price": "9.5", "order_id": "limit-buy", "broker_event": "pending_new",
            },
            {
                "timestamp": "2026-10-16 09:30:01", "symbol": "ABC", "price": "10",
                "qty": "3", "type": "new", "order_type": "limit", "limit_price": "9.5",
                "order_id": "limit-buy", "broker_event": "new",
            },
            {
                "timestamp": "2026-10-16 09:30:02", "symbol": "ABC", "price": "10",
                "qty": "-2", "type": "pending_new", "order_type": "limit", "limit_price": "",
                "order_id": "limit-sell-unpriced", "broker_event": "pending_new",
            },
            {
                "timestamp": "2026-10-16 09:31:00", "symbol": "XYZ", "price": "10", "limit_price": "11",
                "qty": "-4", "type": "pending_new", "order_type": "ordertype.market",
                "order_id": "market-sell", "broker_event": "pending_new",
            },
            {
                "timestamp": "2026-10-16 09:31:01", "symbol": "XYZ", "price": "10", "limit_price": "11",
                "qty": "-4", "type": "new", "order_type": "market",
                "order_id": "market-sell", "broker_event": "new",
            },
            {
                "timestamp": "2026-10-16 09:31:02", "symbol": "XYZ", "price": "10",
                "qty": "-4", "type": "partial fill", "order_type": "market",
                "message": "partially_filled qty=1 avg_price=10", "broker_filled_qty": "1",
                "order_id": "market-sell", "broker_event": "partial_fill",
                "broker_execution_id": "market-exec-1", "broker_timestamp": "2026-10-16 09:31:02",
                "broker_event_price": "10", "broker_event_qty": "1",
            },
            {
                "timestamp": "2026-10-16 09:31:03", "symbol": "XYZ", "price": "12",
                "qty": "-4", "type": "fill", "order_type": "market",
                "message": "filled qty=4 avg_price=11.5", "broker_filled_qty": "4",
                "order_id": "market-sell", "broker_event": "fill",
                "broker_execution_id": "market-exec-2", "broker_timestamp": "2026-10-16 09:31:03",
                "broker_event_price": "12", "broker_event_qty": "3",
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            blotter = Path(directory) / "Orders_blotter_20261016.csv"
            with blotter.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)

            orders = extract_signed_orders_from_blotters([blotter])

        self.assertEqual(
            ["timestamp", "symbol", "qty", "limit_price"],
            list(orders.columns),
        )
        extracted_rows = list(orders[["symbol", "qty", "limit_price"]].itertuples(index=False, name=None))
        self.assertEqual(("ABC", 3.0, -9.5), extracted_rows[0])
        self.assertEqual(("ABC", -2.0), extracted_rows[1][:2])
        self.assertTrue(math.isnan(extracted_rows[1][2]))
        self.assertEqual(("XYZ", -4.0, 11.0), extracted_rows[2])

    def test_cli_writes_strategy_orders_file_in_log_directory(self):
        fields = ["timestamp", "symbol", "qty", "type", "order_type", "limit_price", "order_id", "broker_event"]
        with tempfile.TemporaryDirectory() as directory:
            log_dir = Path(directory)
            blotter = log_dir / "Trend_blotter_20261016.csv"
            with blotter.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "timestamp": "2026-10-16 09:30:00",
                        "symbol": "ABC",
                        "qty": "2",
                        "type": "new",
                        "order_type": "limit",
                        "limit_price": "10",
                        "order_id": "order-1",
                        "broker_event": "new",
                    }
                )

            result = main(["Trend", "--log_dir", str(log_dir)])
            output = log_dir / "Trend_orders.csv"

            self.assertEqual(0, result)
            self.assertTrue(output.is_file())
            with output.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                self.assertEqual(
                    ["timestamp", "symbol", "qty", "limit_price"],
                    reader.fieldnames,
                )
                self.assertEqual("-10.0", next(reader)["limit_price"])


if __name__ == "__main__":
    unittest.main()