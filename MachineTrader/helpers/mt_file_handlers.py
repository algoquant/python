"""Shared file naming and file handling utilities for trading scripts and strategies."""

import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv


class FileMan:
    """Centralized file naming and CSV append helpers."""

    DEFAULT_TIMEZONE = "America/New_York"

    @staticmethod
    def _ensure_trailing_slash(dir_name: str) -> str:
        if dir_name.endswith(("/", "\\")):
            return dir_name
        return f"{dir_name}/"

    @classmethod
    def daily_path(cls, file_path, timezone=None):
        """Return the file path rewritten with today's YYYYMMDD suffix."""
        if not file_path:
            return file_path

        if timezone is None:
            timezone = ZoneInfo(cls.DEFAULT_TIMEZONE)

        directory, filename = os.path.split(file_path)
        stem, extension = os.path.splitext(filename)
        if "_" not in stem:
            return file_path

        prefix, _ = stem.rsplit("_", 1)
        date_short = datetime.now(timezone).strftime("%Y%m%d")
        return os.path.join(directory, f"{prefix}_{date_short}{extension}")

    @staticmethod
    def append_row_to_csv(file_path, row_data):
        """Append one record to a CSV, writing the header on first create."""
        if not file_path or row_data is None:
            return

        frame = pd.DataFrame([row_data])
        frame.to_csv(file_path, mode="a", header=not os.path.exists(file_path), index=False)

    @staticmethod
    def create_daily_file_names(strategy_name, dir_name, timezone):
        """Create daily CSV file names for a strategy."""
        dir_name = FileMan._ensure_trailing_slash(dir_name)
        date_short = datetime.now(timezone).strftime("%Y%m%d")

        return {
            "state_file": f"{dir_name}state_{strategy_name}_{date_short}.csv",
            "submits_file": f"{dir_name}submits_{strategy_name}_{date_short}.csv",
            "fills_file": f"{dir_name}fills_{strategy_name}_{date_short}.csv",
            "canceled_file": f"{dir_name}canceled_{strategy_name}_{date_short}.csv",
            "error_file": f"{dir_name}error_{strategy_name}_{date_short}.csv",
        }

    @classmethod
    def create_file_names(cls, strategy_name, timezone=None, dir_name=None, env_file=None, dir_env_var="DATA_DIR_NAME"):
        """Create standardized daily file names and return them in a dict.

        Relaunching a strategy on the same day resolves to the same file paths,
        and all CSV writes append to those files.
        """
        if timezone is None:
            timezone = ZoneInfo(cls.DEFAULT_TIMEZONE)

        if env_file is not None:
            load_dotenv(env_file)
            print(f"📄 Loading environment variables from: {env_file}")
        else:
            load_dotenv()
            print("📄 Loading environment variables from default .env file or system environment")

        if dir_name is None:
            dir_name = os.getenv(dir_env_var) or "./"
            if dir_name != "./":
                print(f"📁 Using directory from {dir_env_var}: {dir_name}")
            else:
                print("📁 Using default directory: ./")
        else:
            print(f"📁 Using specified directory: {dir_name}")

        dir_name = cls._ensure_trailing_slash(dir_name)
        file_names = cls.create_daily_file_names(
            strategy_name=strategy_name,
            dir_name=dir_name,
            timezone=timezone,
        )

        print(f"✅ Strategy files created successfully in directory: {dir_name}")
        print(
            f"📋 Files: {len(file_names)} daily files for strategy '{strategy_name}' "
            f"(relaunches append on same date)"
        )
        print("📁 Files set as instance variables: state_file, submits_file, fills_file, canceled_file, error_file")
        return file_names


def create_daily_file_names(strategy_name, dir_name, timezone):
    """Expose daily file name creation as a module-level helper."""
    return FileMan.create_daily_file_names(strategy_name, dir_name, timezone)


def to_float(value, default=None):
    """Convert value to float while handling empty/invalid/NaN values."""
    if value is None:
        return default
    try:
        number = float(value)
        if math.isnan(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def format_data(value, decimals=2):
    """Format numeric metric values for status and heartbeat output."""
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "n/a"