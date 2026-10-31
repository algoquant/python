from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")


def lightweight_charts_ny_time_formatters_js() -> str:
        """Return shared Lightweight Charts formatters for New York timestamps."""
        return """const formatNyChartTime = (time) => {
    const epoch = typeof time === 'number'
        ? time
        : Date.UTC(time.year, time.month - 1, time.day) / 1000;
    return new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/New_York',
        month: '2-digit',
        day: '2-digit',
        year: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
    }).format(new Date(epoch * 1000));
};"""


def _parse_epoch_to_tz(text: str, *, timezone: ZoneInfo) -> datetime | None:
    """Parse numeric epoch text (seconds/ms/us/ns) into requested timezone."""
    try:
        raw = float(text)
    except Exception:
        return None

    abs_raw = abs(raw)
    scale = 1.0
    # Heuristic by magnitude:
    # seconds: ~1e9, milliseconds: ~1e12, microseconds: ~1e15, nanoseconds: ~1e18
    if abs_raw >= 1e17:
        scale = 1e9
    elif abs_raw >= 1e14:
        scale = 1e6
    elif abs_raw >= 1e11:
        scale = 1e3

    try:
        return datetime.fromtimestamp(raw / scale, tz=timezone)
    except Exception:
        return None


def coerce_datetime(
    raw_timestamp: Any,
    *,
    target_tz: ZoneInfo,
    naive_tz: ZoneInfo,
    fallback_to_now: bool = True,
) -> datetime | None:
    """Coerce timestamp text/epoch/datetime into target_tz with explicit naive timezone."""
    dt: datetime | None

    if isinstance(raw_timestamp, datetime):
        dt = raw_timestamp
    elif raw_timestamp is None:
        dt = None
    else:
        text = str(raw_timestamp).strip()
        if not text:
            dt = None
        else:
            dt = None
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except Exception:
                pass

            if dt is None:
                dt = _parse_epoch_to_tz(text, timezone=target_tz)

    if dt is None:
        if fallback_to_now:
            return datetime.now(target_tz)
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=naive_tz)
    return dt.astimezone(target_tz)


def coerce_datetime_ny(raw_timestamp: Any, *, fallback_to_now: bool = True) -> datetime | None:
    return coerce_datetime(
        raw_timestamp,
        target_tz=NY_TZ,
        naive_tz=NY_TZ,
        fallback_to_now=fallback_to_now,
    )


def coerce_market_datetime_ny(raw_timestamp: Any, *, fallback_to_now: bool = True) -> datetime | None:
    """Coerce market-bar timestamps into NY datetime.

    Rules:
    - timezone-aware inputs are converted to NY,
    - naive ISO strings/datetimes are treated as UTC market timestamps,
    - numeric epochs support seconds/ms/us/ns via magnitude detection.
    """
    return coerce_datetime(
        raw_timestamp,
        target_tz=NY_TZ,
        naive_tz=UTC_TZ,
        fallback_to_now=fallback_to_now,
    )


def format_timestamp_ny(raw_timestamp: Any, *, fallback_to_now: bool = True) -> str:
    dt = coerce_datetime_ny(raw_timestamp, fallback_to_now=fallback_to_now)
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def bar_second_from_payload(bar: dict[str, Any]) -> int | None:
    raw_ts = bar.get("t", bar.get("timestamp"))
    if raw_ts in (None, ""):
        return None
    dt = coerce_market_datetime_ny(raw_ts, fallback_to_now=False)
    if dt is None:
        return None
    return int(dt.second)
