"""Tests for the environment-file interface of get_ohlc.py."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import get_ohlc


class GetOhlcConfigTests(unittest.TestCase):
    def test_load_history_config_reads_required_values_and_relative_paths(self):
        with TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            env_file = directory / ".env_test"
            env_file.write_text(
                "DATA_KEY=test-key\n"
                "DATA_SECRET=test-secret\n"
                "SYMBOLS_FILE_NAME=symbols.csv\n"
                "DATA_DIR_NAME=output\n"
                "BATCH_SIZE=7\n",
                encoding="utf-8",
            )

            config, symbols_file, data_dir = get_ohlc.load_history_config(env_file)

        self.assertEqual(config.data_key, "test-key")
        self.assertEqual(config.data_secret, "test-secret")
        self.assertEqual(config.batch_size, 7)
        self.assertEqual(symbols_file, directory.resolve() / "symbols.csv")
        self.assertEqual(data_dir, directory.resolve() / "output")

    def test_load_history_config_requires_data_secret_in_selected_file(self):
        with TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env_test"
            env_file.write_text(
                "DATA_KEY=test-key\n"
                "SYMBOLS_FILE_NAME=symbols.csv\n"
                "DATA_DIR_NAME=output\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "DATA_SECRET"):
                get_ohlc.load_history_config(env_file)


if __name__ == "__main__":
    unittest.main()