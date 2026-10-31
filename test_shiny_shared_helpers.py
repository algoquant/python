"""Tests for shared data helpers used by the Shiny dashboards."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from MachineTrader.helpers.file_handlers import discover_csv_files, discover_dated_csv_files, load_csv_frames
from MachineTrader.helpers.ohlc import build_date_slider_metadata, load_ohlc_csv


class SharedDashboardDataTests(unittest.TestCase):
    def test_dated_csv_discovery_deduplicates_and_sorts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Ladder_positions_20261015.csv").write_text("timestamp,SPY\n", encoding="utf-8")
            (root / "Ladder_positions_20261014.csv").write_text("timestamp,SPY\n", encoding="utf-8")

            results = discover_dated_csv_files(
                root,
                ("Ladder_positions_*.csv", "*_positions_*.csv"),
                date_pattern=r"_(\d{8})\.csv$",
            )

        self.assertEqual(["20261014", "20261015"], [day for day, _ in results])

    def test_csv_discovery_and_concat_parse_and_sort_timestamps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "state_20261015.csv").write_text(
                "Timestamp,SPY\n2026-10-15 09:32:00,2\n2026-10-15 09:31:00,1\n",
                encoding="utf-8",
            )
            paths = discover_csv_files(root, ("state_*.csv",))
            frame = load_csv_frames(
                paths,
                timestamp_column="timestamp",
                parse_timestamp=True,
                sort_timestamp=True,
            )

        self.assertEqual(["timestamp", "SPY"], frame.columns.tolist())
        self.assertEqual([1, 2], frame["SPY"].tolist())
        self.assertTrue(frame["timestamp"].is_monotonic_increasing)

    def test_ohlc_loader_and_slider_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "bars.csv"
            pd.DataFrame(
                {
                    "timestamp": ["2026-10-14T13:30:00Z", "2026-10-15T13:30:00Z"],
                    "open": [1, 2],
                    "high": [2, 3],
                    "low": [0.5, 1.5],
                    "close": [1.5, 2.5],
                    "volume": [100, 200],
                }
            ).to_csv(csv_path, index=False)
            frame = load_ohlc_csv(csv_path, {"timestamp", "open", "high", "low", "close", "volume"})
            metadata = build_date_slider_metadata(frame, months_back=1)

        self.assertEqual(2, len(frame))
        self.assertEqual("America/New_York", str(frame["timestamp"].dt.tz))
        self.assertEqual([0, 1], [metadata["default_start_idx"], metadata["default_end_idx"]])
        self.assertEqual(2, len(metadata["date_labels"]))


if __name__ == "__main__":
    unittest.main()