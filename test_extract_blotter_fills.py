"""Behavioral tests for extracting incremental fills from blotter CSVs.

The test writes a representative blotter into a temporary directory and
passes it directly to ``extract_signed_fills_from_blotters``. The fixture
covers explicit incremental quantities, quantities inferred from cumulative
filled totals, duplicate broker execution IDs, repeated cumulative fill
status, timestamp-near execution consolidation, and both sides of a trade.
The expected rows also document the output schema and signed-price convention:
buys have negative prices, sells positive prices, and share counts stay
positive.

Run this module from the repository root with::

    python -m unittest -v test_extract_blotter_fills
"""

import csv
import tempfile
import unittest
from pathlib import Path

from MachineTrader.helpers.file_handlers import extract_signed_fills_from_blotters


class ExtractBlotterFillsTests(unittest.TestCase):
    """Verify the public fill extractor against representative blotter data."""

    def test_extracts_incremental_fills_once_with_signed_prices(self):
        """Consolidate nearby unique executions and encode side by price sign.

        The second ``ABC`` event contributes only two new shares even though
        the order's cumulative filled quantity is six. Its execution is
        consolidated with the first, using a share-weighted price. A later
        status update adds no quantity, and repeated ``exec-1`` is deduplicated.
        The ``OLD`` rows omit event-level quantities, so their increments are
        recovered from cumulative quantities and consolidated as well. Buy
        prices remain negative; the ``XYZ`` sell price remains positive.
        """
        fieldnames = [
            "timestamp", "symbol", "price", "qty", "type", "message", "broker_filled_qty",
            "order_id", "broker_event", "broker_execution_id", "broker_timestamp",
            "broker_event_price", "broker_event_qty",
        ]
        rows = [
            {
                "timestamp": "2026-10-16 09:30:00", "symbol": "ABC", "price": "10",
                "qty": "4", "type": "partial fill", "message": "partially_filled qty=4 avg_price=10",
                "broker_filled_qty": "4", "order_id": "buy-1", "broker_event": "partial_fill",
                "broker_execution_id": "exec-1", "broker_timestamp": "2026-10-16 09:30:00",
                "broker_event_price": "10", "broker_event_qty": "4",
            },
            {
                "timestamp": "2026-10-16 09:30:01", "symbol": "ABC", "price": "11",
                "qty": "6", "type": "fill", "message": "filled qty=6 avg_price=10.33",
                "broker_filled_qty": "6", "order_id": "buy-1", "broker_event": "fill",
                "broker_execution_id": "exec-2", "broker_timestamp": "2026-10-16 09:30:01",
                "broker_event_price": "11", "broker_event_qty": "2",
            },
            {
                "timestamp": "2026-10-16 09:30:02", "symbol": "ABC", "price": "10.33",
                "qty": "6", "type": "fill", "message": "orderstatus.filled qty=6 avg_price=10.33",
                "broker_filled_qty": "6", "order_id": "buy-1", "broker_event": "",
                "broker_execution_id": "", "broker_timestamp": "2026-10-16 09:30:02",
                "broker_event_price": "", "broker_event_qty": "",
            },
            {
                "timestamp": "2026-10-16 09:30:03", "symbol": "ABC", "price": "10",
                "qty": "4", "type": "fill", "message": "filled qty=4 avg_price=10",
                "broker_filled_qty": "4", "order_id": "buy-1", "broker_event": "fill",
                "broker_execution_id": "exec-1", "broker_timestamp": "2026-10-16 09:30:03",
                "broker_event_price": "10", "broker_event_qty": "4",
            },
            {
                "timestamp": "2026-10-16 09:30:04", "symbol": "OLD", "price": "30",
                "qty": "3", "type": "partial fill", "message": "partially_filled qty=3 avg_price=30",
                "broker_filled_qty": "3", "order_id": "legacy-buy", "broker_event": "partial_fill",
                "broker_execution_id": "", "broker_timestamp": "2026-10-16 09:30:04",
                "broker_event_price": "", "broker_event_qty": "",
            },
            {
                "timestamp": "2026-10-16 09:30:05", "symbol": "OLD", "price": "30.4",
                "qty": "5", "type": "fill", "message": "filled qty=5 avg_price=30.4",
                "broker_filled_qty": "5", "order_id": "legacy-buy", "broker_event": "fill",
                "broker_execution_id": "", "broker_timestamp": "2026-10-16 09:30:05",
                "broker_event_price": "", "broker_event_qty": "",
            },
            {
                "timestamp": "2026-10-16 09:31:00", "symbol": "XYZ", "price": "20",
                "qty": "-3", "type": "fill", "message": "filled qty=3 avg_price=20",
                "broker_filled_qty": "3", "order_id": "sell-1", "broker_event": "fill",
                "broker_execution_id": "exec-3", "broker_timestamp": "2026-10-16 09:31:00",
                "broker_event_price": "20", "broker_event_qty": "3",
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            blotter = Path(directory) / "Ladder_blotter_20261016.csv"
            with blotter.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            fills = extract_signed_fills_from_blotters([blotter])

        self.assertEqual(["timestamp", "symbol", "num_shares", "fill_price"], list(fills.columns))
        self.assertEqual(
            [
                ("ABC", 6.0, -10.33333333),
                ("OLD", 5.0, -30.16),
                ("XYZ", 3.0, 20.0),
            ],
            list(fills[["symbol", "num_shares", "fill_price"]].itertuples(index=False, name=None)),
        )

    def test_merges_same_order_only_when_span_is_under_one_minute(self):
        """Keep different orders separate and split a group at 60 seconds."""
        fieldnames = [
            "timestamp", "symbol", "price", "qty", "type", "message", "broker_filled_qty",
            "order_id", "broker_event", "broker_execution_id", "broker_timestamp",
            "broker_event_price", "broker_event_qty",
        ]

        def fill_event(timestamp, order_id, execution_id, quantity, price):
            return {
                "timestamp": timestamp,
                "symbol": "ABC",
                "price": str(price),
                "qty": str(quantity),
                "type": "fill",
                "message": f"filled qty={quantity} avg_price={price}",
                "broker_filled_qty": str(quantity),
                "order_id": order_id,
                "broker_event": "fill",
                "broker_execution_id": execution_id,
                "broker_timestamp": timestamp,
                "broker_event_price": str(price),
                "broker_event_qty": str(quantity),
            }

        rows = [
            fill_event("2026-10-16 09:30:00", "order-a", "exec-a1", 2, 10),
            fill_event("2026-10-16 09:30:30", "order-b", "exec-b1", 4, 11),
            fill_event("2026-10-16 09:30:59", "order-a", "exec-a2", 1, 12),
            fill_event("2026-10-16 09:31:00", "order-a", "exec-a3", 3, 13),
        ]

        with tempfile.TemporaryDirectory() as directory:
            blotter = Path(directory) / "Ladder_blotter_20261016.csv"
            with blotter.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            fills = extract_signed_fills_from_blotters([blotter])

        self.assertEqual(
            [
                (3.0, -10.66666667),
                (4.0, -11.0),
                (3.0, -13.0),
            ],
            list(fills[["num_shares", "fill_price"]].itertuples(index=False, name=None)),
        )

    def test_does_not_merge_different_symbols_or_directions(self):
        """Nearby fills must match both symbol and buy/sell direction."""
        fieldnames = [
            "timestamp", "symbol", "price", "qty", "type", "message", "broker_filled_qty",
            "order_id", "broker_event", "broker_execution_id", "broker_timestamp",
            "broker_event_price", "broker_event_qty",
        ]
        rows = []
        for timestamp, symbol, quantity, execution_id in [
            ("2026-10-16 09:30:00", "ABC", 2, "exec-buy-1"),
            ("2026-10-16 09:30:10", "XYZ", 3, "exec-other-symbol"),
            ("2026-10-16 09:30:20", "ABC", -4, "exec-sell"),
            ("2026-10-16 09:30:30", "ABC", 1, "exec-buy-2"),
        ]:
            rows.append(
                {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "price": "10",
                    "qty": str(quantity),
                    "type": "fill",
                    "message": "filled",
                    "broker_filled_qty": str(abs(quantity)),
                    "order_id": "same-order-id",
                    "broker_event": "fill",
                    "broker_execution_id": execution_id,
                    "broker_timestamp": timestamp,
                    "broker_event_price": "10",
                    "broker_event_qty": str(abs(quantity)),
                }
            )

        with tempfile.TemporaryDirectory() as directory:
            blotter = Path(directory) / "Ladder_blotter_20261016.csv"
            with blotter.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            fills = extract_signed_fills_from_blotters([blotter])

        self.assertEqual(
            [
                ("ABC", 3.0, -10.0),
                ("XYZ", 3.0, -10.0),
                ("ABC", 4.0, 10.0),
            ],
            list(fills[["symbol", "num_shares", "fill_price"]].itertuples(index=False, name=None)),
        )


if __name__ == "__main__":
    unittest.main()
