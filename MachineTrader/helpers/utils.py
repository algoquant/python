"""Minimal legacy utility helpers required by migrated strategy modules."""

from __future__ import annotations

import os
import signal
import warnings
from datetime import datetime
from zoneinfo import ZoneInfo

from .timestamp_utils import coerce_datetime_ny

NY_TZ = ZoneInfo("America/New_York")


def convert_to_nytzone(value):
    """Convert datetime-like values to America/New_York timezone when possible."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return coerce_datetime_ny(value, fallback_to_now=False)
    return value


def suppress_resource_tracker_warning() -> None:
    """Suppress the known non-fatal multiprocessing semaphore shutdown warning."""
    rule = "ignore:resource_tracker:UserWarning:multiprocessing.resource_tracker"
    existing = os.environ.get("PYTHONWARNINGS", "").strip()
    if rule not in existing.split(","):
        os.environ["PYTHONWARNINGS"] = f"{existing},{rule}" if existing else rule
    warnings.filterwarnings(
        "ignore",
        message=r"resource_tracker: There appear to be \d+ leaked semaphore objects to clean up at shutdown",
        category=UserWarning,
        module=r"multiprocessing\.resource_tracker",
    )


def install_graceful_sigint_handler(app_name: str = "Application") -> None:
    """Install a Ctrl-C handler that delegates to the previous handler cleanly."""
    log_ctrl_c = os.getenv("SHINY_CTRL_C_LOG", "1").strip().lower() not in {"0", "false", "no", "off"}
    suppress_resource_tracker_warning()
    previous_handler = signal.getsignal(signal.SIGINT)

    def handle_sigint(signum, frame):
        if log_ctrl_c:
            print(f"\n{app_name}: Ctrl-C received. Shutting down gracefully.")
        try:
            signal.signal(signal.SIGINT, previous_handler)
        except Exception:
            pass
        if callable(previous_handler):
            previous_handler(signum, frame)
        else:
            signal.default_int_handler(signum, frame)

    try:
        signal.signal(signal.SIGINT, handle_sigint)
    except Exception:
        pass
