"""Network-free tests for MachineTrader historical OHLCV helpers."""

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

import pandas as pd

from MachineTrader.helpers import ohlc


class OhlcHelperTests(unittest.TestCase):
    def test_load_tickers_csv_normalizes_deduplicates_and_drops_missing(self):
        with TemporaryDirectory() as temp_dir:
            metadata_file = Path(temp_dir) / "metadata.csv"
            pd.DataFrame({"ticker": [" spy ", "QQQ", "SPY", None]}).to_csv(
                metadata_file,
                index=False,
            )

            tickers = ohlc.load_tickers_csv(metadata_file)

        self.assertEqual(tickers, ["SPY", "QQQ"])

    def test_load_symbols_file_skips_header_and_uses_first_column(self):
        with TemporaryDirectory() as temp_dir:
            symbols_file = Path(temp_dir) / "symbols.csv"
            symbols_file.write_text(
                "Symbol,Weight\n spy ,1\nQQQ,2\nSPY,3\n,4\n",
                encoding="utf-8",
            )

            symbols = ohlc.load_symbols_file(symbols_file)

        self.assertEqual(symbols, ["SPY", "QQQ"])

    def test_write_errors_csv_writes_header_and_rows(self):
        with TemporaryDirectory() as temp_dir:
            error_file = Path(temp_dir) / "ohlc_errors.csv"

            result = ohlc.write_ohlc_errors_csv(
                [{"ticker": "BAD", "error": "No data"}],
                error_file,
            )

            written = pd.read_csv(error_file)

        self.assertEqual(result, error_file)
        self.assertEqual(written.to_dict("records"), [{"ticker": "BAD", "error": "No data"}])

    def test_normalize_tiingo_bars_prefers_adjusted_values_and_excludes_cutoff(self):
        payload = [
            {
                "date": "2024-01-02T00:00:00Z",
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "volume": 100,
                "adjOpen": 5,
                "adjHigh": 6,
                "adjLow": 4.5,
                "adjClose": 5.5,
                "adjVolume": 200,
            },
            {
                "date": "2024-01-03T00:00:00Z",
                "open": 20,
                "high": 22,
                "low": 19,
                "close": 21,
                "volume": 300,
            },
        ]

        bars = ohlc.normalize_tiingo_bars(
            payload,
            "spy",
            before_date=date(2024, 1, 3),
        )

        self.assertIsNotNone(bars)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars.iloc[0]["ticker"], "SPY")
        self.assertEqual(bars.iloc[0]["close"], 5.5)
        self.assertEqual(bars.iloc[0]["volume"], 200)
        self.assertEqual(bars.iloc[0]["dollar_volume"], 1100)

    def test_prefix_ticker_columns_produces_expected_schema(self):
        bars = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-02"]),
                "open": [1],
                "high": [2],
                "low": [0.5],
                "close": [1.5],
                "volume": [100],
                "dollar_volume": [150],
                "ticker": ["SPY"],
            }
        )

        prefixed = ohlc.prefix_ticker_columns(bars, "spy")

        self.assertEqual(
            prefixed.columns.tolist(),
            [
                "date",
                "SPY.Open",
                "SPY.High",
                "SPY.Low",
                "SPY.Close",
                "SPY.Volume",
                "SPY.VolumeD",
            ],
        )

    def test_history_config_rejects_invalid_batch_size(self):
        with self.assertRaisesRegex(ValueError, "batch_size must be positive"):
            ohlc.TiingoHistoryConfig(
                data_key="key",
                data_secret="token",
                batch_size=0,
            )


class OhlcAsyncHelperTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_tiingo_bars_authenticates_with_data_secret(self):
        config = ohlc.TiingoHistoryConfig(
            data_key="public-key",
            data_secret="tiingo-token",
        )
        payload = [
            {
                "date": "2024-01-02T00:00:00Z",
                "open": 1,
                "high": 2,
                "low": 0.5,
                "close": 1.5,
                "volume": 100,
            }
        ]

        with patch.object(
            ohlc,
            "fetch_tiingo_json",
            new=AsyncMock(return_value=payload),
        ) as fetch:
            await ohlc.fetch_tiingo_bars(object(), "SPY", config)

        self.assertEqual(fetch.await_args.args[2], "tiingo-token")

    async def test_compute_liquidity_keeps_successful_tickers(self):
        config = ohlc.TiingoHistoryConfig(
            data_key="key",
            data_secret="token",
            batch_size=2,
        )
        process_result = AsyncMock(side_effect=[("SPY", 100.0), None, ("IWM", 50.0)])

        with patch.object(ohlc, "process_tiingo_ticker", new=process_result):
            liquidity = await ohlc.compute_tiingo_liquidity(
                ["SPY", "BAD", "IWM"],
                "/tmp/unused",
                config,
            )

        self.assertEqual(liquidity["ticker"].tolist(), ["SPY", "IWM"])
        self.assertEqual(liquidity["volume"].tolist(), [100.0, 50.0])

    async def test_download_history_reports_empty_and_exception_results(self):
        config = ohlc.TiingoHistoryConfig(
            data_key="key",
            data_secret="token",
            batch_size=3,
        )
        process_result = AsyncMock(
            side_effect=[("SPY", 100.0), None, RuntimeError("request failed")]
        )

        with patch.object(ohlc, "process_tiingo_ticker", new=process_result):
            liquidity, errors = await ohlc.download_tiingo_history(
                ["SPY", "EMPTY", "BROKEN"],
                "/tmp/unused",
                config,
            )

        self.assertEqual(liquidity.to_dict("records"), [{"ticker": "SPY", "volume": 100.0}])
        self.assertEqual(
            errors,
            [
                {"ticker": "EMPTY", "error": "No complete OHLCV data returned"},
                {"ticker": "BROKEN", "error": "RuntimeError: request failed"},
            ],
        )


if __name__ == "__main__":
    unittest.main()