"""Tests for reusable MachineTrader security metadata helpers."""

import unittest
from unittest.mock import AsyncMock, patch
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from MachineTrader.helpers import metadata


class MetadataHelperTests(unittest.TestCase):
    def test_normalize_ticker_column_returns_copy(self):
        source = pd.DataFrame({"ticker": [" aapl ", "MsFt"], "volume": [2, 1]})

        normalized = metadata.normalize_ticker_column(source)

        self.assertEqual(normalized["ticker"].tolist(), ["AAPL", "MSFT"])
        self.assertEqual(source["ticker"].tolist(), [" aapl ", "MsFt"])

    def test_clean_classification_fields_adds_and_normalizes_columns(self):
        source = pd.DataFrame(
            {
                "ticker": ["AAPL", "MSFT"],
                "sector": ["Technology", " "],
                "industry": [metadata.UNAVAILABLE_FREE_TEXT, "Software"],
            }
        )

        cleaned = metadata.clean_classification_fields(source)

        self.assertEqual(cleaned.loc[0, "sector"], "Technology")
        self.assertTrue(pd.isna(cleaned.loc[1, "sector"]))
        self.assertTrue(pd.isna(cleaned.loc[0, "industry"]))
        self.assertTrue(pd.isna(cleaned.loc[0, "sicCode"]))

    def test_yahoo_backfill_preserves_tiingo_values(self):
        source = pd.DataFrame(
            {
                "ticker": ["AAPL", "MSFT"],
                "sector": ["Technology", pd.NA],
                "industry": [pd.NA, "Software"],
            }
        )

        def fake_fetch(ticker):
            return {
                "ticker": ticker,
                "sector_yahoo": "Yahoo sector",
                "industry_yahoo": "Yahoo industry",
            }

        with (
            patch.object(metadata, "yf", object()),
            patch.object(metadata, "load_yahoo_cache", return_value=pd.DataFrame(
                columns=["ticker", "sector_yahoo", "industry_yahoo"]
            )),
            patch.object(metadata, "save_yahoo_cache"),
            patch.object(metadata, "fetch_yahoo_sector_industry", side_effect=fake_fetch),
        ):
            enriched = metadata.backfill_sector_industry_from_yahoo(
                source,
                cache_file=metadata.Path("unused.parquet"),
                max_workers=1,
                pause_seconds=0,
            )

        self.assertEqual(enriched.loc[0, "sector"], "Technology")
        self.assertEqual(enriched.loc[0, "industry"], "Yahoo industry")
        self.assertEqual(enriched.loc[1, "sector"], "Yahoo sector")
        self.assertEqual(enriched.loc[1, "industry"], "Software")
        self.assertEqual(enriched["classification_source"].tolist(), ["yahoo", "yahoo"])

    def test_pick_liquidity_sort_column_uses_priority_order(self):
        frame = pd.DataFrame(columns=["dollar_volume", "adv", "volume"])

        self.assertEqual(metadata.pick_liquidity_sort_column(frame), "volume")
        self.assertIsNone(metadata.pick_liquidity_sort_column(pd.DataFrame(columns=["ticker"])))

    def test_load_yahoo_cache_upgrades_legacy_schema(self):
        legacy = pd.DataFrame(
            {"ticker": [" spy "], "sector_yahoo": ["Financial Services"]}
        )

        with TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "cache.parquet"
            legacy.to_parquet(cache_file, index=False)
            loaded = metadata.load_yahoo_cache(cache_file)

        self.assertEqual(loaded.columns.tolist(), list(metadata.YAHOO_CACHE_COLUMNS))
        self.assertEqual(loaded.loc[0, "ticker"], "SPY")
        self.assertTrue(pd.isna(loaded.loc[0, "quote_type_yahoo"]))

    def test_quote_type_filter_retains_only_etfs(self):
        source = pd.DataFrame({"ticker": ["SPY", "AAPL", "VFINX"]})
        cache = pd.DataFrame(
            {
                "ticker": ["SPY", "AAPL", "VFINX"],
                "sector_yahoo": [pd.NA] * 3,
                "industry_yahoo": [pd.NA] * 3,
                "quote_type_yahoo": ["ETF", "EQUITY", "MUTUALFUND"],
            }
        )

        with (
            patch.object(metadata, "yf", object()),
            patch.object(metadata, "load_yahoo_cache", return_value=cache),
        ):
            filtered = metadata.filter_to_etfs_using_yahoo_quote_type(
                source,
                cache_file=Path("unused.parquet"),
                pause_seconds=0,
            )

        self.assertEqual(filtered["ticker"].tolist(), ["SPY"])
        self.assertEqual(filtered.loc[filtered.index[0], "quote_type_yahoo"], "ETF")

    def test_etf_detail_enrichment_merges_each_ticker(self):
        source = pd.DataFrame({"ticker": ["SPY", "QQQ"]})

        def fake_details(ticker):
            return {
                "ticker": ticker,
                "etf_name": f"{ticker} Fund",
                "category": "Test",
                "net_assets": 100,
                "beta_5y": 1.0,
                "sharpe_ratio": 2.0,
                "treynor_ratio": 3.0,
            }

        with (
            patch.object(metadata, "yf", object()),
            patch.object(metadata, "fetch_yahoo_etf_details", side_effect=fake_details),
        ):
            enriched = metadata.enrich_etf_details_from_yahoo(
                source,
                max_workers=1,
                pause_seconds=0,
            )

        self.assertEqual(enriched["etf_name"].tolist(), ["SPY Fund", "QQQ Fund"])
        self.assertEqual(enriched["treynor_ratio"].tolist(), [3.0, 3.0])


class OtcFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_exclude_otc_stocks_removes_otc_ticker(self):
        source = pd.DataFrame({"ticker": ["AAPL", "OTCM"], "volume": [2, 1]})

        async def fake_profile(session, ticker, api_key, base_url):
            del session, api_key, base_url
            return {"is_otc": ticker == "OTCM"}

        with patch.object(
            metadata,
            "get_tiingo_ticker_profile",
            new=AsyncMock(side_effect=fake_profile),
        ):
            filtered = await metadata.exclude_otc_stocks(
                source,
                api_key="test-token",
                base_url="https://example.invalid",
                concurrency=2,
            )

        self.assertEqual(filtered["ticker"].tolist(), ["AAPL"])


if __name__ == "__main__":
    unittest.main()