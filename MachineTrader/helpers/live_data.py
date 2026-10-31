from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import date, datetime, time as dtime, timedelta, timezone as dt_timezone
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

import websockets
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockLatestBarRequest, StockLatestQuoteRequest

from .markets import Markets
from .parse_args import parse_hhmm_or_default
from .setup_strat import get_env_text
from .timestamp_utils import coerce_market_datetime_ny

NY_TZ = ZoneInfo("America/New_York")


def resolve_proxy_schedule_from_env(env_values: dict[str, Any]) -> tuple[dtime, dtime]:
    """Return strategy start/end times, with legacy proxy setting fallbacks."""
    start_text = (
        get_env_text(env_values, "STRATEGY_START_TIME")
        or get_env_text(env_values, "PROXY_START_TIME")
        or "09:30"
    )
    end_text = (
        get_env_text(env_values, "STRATEGY_END_TIME")
        or get_env_text(env_values, "PROXY_END_TIME")
        or "16:00"
    )
    return (
        parse_hhmm_or_default(start_text, "00:00"),
        parse_hhmm_or_default(end_text, "23:59"),
    )


def minutes_since_midnight(value: dtime) -> int:
    return int(value.hour) * 60 + int(value.minute)


def is_within_time_window(now_time: dtime, start_time: dtime, end_time: dtime) -> bool:
    """Return True when now_time is inside [start_time, end_time), with overnight support."""
    start_minutes = minutes_since_midnight(start_time)
    end_minutes = minutes_since_midnight(end_time)
    now_minutes = minutes_since_midnight(now_time)

    # Equal times mean run continuously (no time-window suspension).
    if start_minutes == end_minutes:
        return True

    if start_minutes < end_minutes:
        return start_minutes <= now_minutes < end_minutes

    # Overnight window (for example start=20:00, end=04:00).
    return now_minutes >= start_minutes or now_minutes < end_minutes


def is_market_open_day(markets: Markets, day_value: date) -> bool:
    return bool(markets.is_trading_day(day_value))


def make_na_bar() -> dict[str, Any]:
    """Placeholder bar for a symbol with no current or prior price data."""
    return {"o": None, "h": None, "l": None, "c": None, "v": None, "t": None, "is_na_bar": True}


def fill_missing_minute_bars(
    bars_for_minute: dict[str, dict[str, Any]],
    required_symbols: set[str],
    last_known_bar_by_symbol: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Carry forward each symbol's last known bar when this minute's bar is missing; use an NA bar when none exists.

    ``last_known_bar_by_symbol`` is mutated in place so callers can keep a persistent cache across minutes.
    """
    completed: dict[str, dict[str, Any]] = {}
    for symbol in required_symbols:
        bar = bars_for_minute.get(symbol)
        if isinstance(bar, dict) and bar.get("c", bar.get("close")) is not None:
            completed[symbol] = bar
            last_known_bar_by_symbol[symbol] = bar
            continue
        previous_bar = last_known_bar_by_symbol.get(symbol)
        completed[symbol] = dict(previous_bar) if isinstance(previous_bar, dict) else make_na_bar()
    return completed


def proxy_schedule_status(now_ny: datetime, markets: Markets, start_time: dtime, end_time: dtime) -> tuple[bool, str]:
    """Return (should_run, reason) for proxy schedule + market day checks."""
    if not is_market_open_day(markets, now_ny.date()):
        return False, "market_closed_day"
    if not is_within_time_window(now_ny.time(), start_time, end_time):
        return False, "outside_proxy_window"
    return True, "active"


def proxy_idle_heartbeat_key(now_ny: datetime, reason: str, start_time: dtime, end_time: dtime) -> str:
    """Return stable key for deduplicating schedule-idle heartbeats."""
    day_text = now_ny.date().isoformat()
    reason_key = str(reason or "unknown").strip().lower()
    if reason_key == "market_closed_day":
        return f"market_closed_day:{day_text}"

    start_minutes = minutes_since_midnight(start_time)
    end_minutes = minutes_since_midnight(end_time)
    now_minutes = minutes_since_midnight(now_ny.time())

    # Non-overnight window: classify before-start and after-end once per day.
    if start_minutes < end_minutes:
        if now_minutes >= end_minutes:
            return f"outside_proxy_window:after_end:{day_text}"
        if now_minutes < start_minutes:
            return f"outside_proxy_window:before_start:{day_text}"

    # Overnight windows and uncommon boundary cases still dedupe once per day.
    return f"outside_proxy_window:{day_text}"


def format_proxy_idle_heartbeat_message(
    now_ny: datetime,
    reason: str,
    start_time: dtime,
    end_time: dtime,
    resume_at_ny: datetime,
) -> str:
    """Build a human-readable heartbeat for idle/suspended proxy periods."""
    now_text = now_ny.strftime("%Y-%m-%d %H:%M:%S %Z")
    resume_text = resume_at_ny.strftime("%Y-%m-%d %H:%M:%S %Z")
    window_text = f"{start_time.strftime('%H:%M')}->{end_time.strftime('%H:%M')}"
    reason_key = str(reason or "unknown").strip().lower()

    if reason_key == "market_closed_day":
        return (
            "[Alpaca Proxy] Heartbeat: proxy idle; market closed day "
            f"time={now_text} window={window_text} next_resume={resume_text}"
        )

    key = proxy_idle_heartbeat_key(now_ny, reason_key, start_time, end_time)
    if ":after_end:" in key:
        return (
            "[Alpaca Proxy] Heartbeat: proxy idle; after STRATEGY_END_TIME "
            f"time={now_text} window={window_text} next_resume={resume_text}"
        )
    if ":before_start:" in key:
        return (
            "[Alpaca Proxy] Heartbeat: proxy idle; before STRATEGY_START_TIME "
            f"time={now_text} window={window_text} next_resume={resume_text}"
        )

    return (
        "[Alpaca Proxy] Heartbeat: proxy idle; outside proxy window "
        f"time={now_text} window={window_text} next_resume={resume_text}"
    )


def next_proxy_start_datetime(
    now_ny: datetime,
    markets: Markets,
    start_time: dtime,
    end_time: dtime,
    *,
    timezone: ZoneInfo = NY_TZ,
    lookahead_days: int = 10,
) -> datetime:
    """Find next datetime when proxy should be active on a trading day."""
    candidate_day = now_ny.date()
    if not is_within_time_window(now_ny.time(), start_time, end_time):
        start_today = datetime.combine(candidate_day, start_time, tzinfo=timezone)
        if now_ny >= start_today:
            candidate_day = candidate_day + timedelta(days=1)

    for _ in range(max(1, int(lookahead_days))):
        if is_market_open_day(markets, candidate_day):
            return datetime.combine(candidate_day, start_time, tzinfo=timezone)
        candidate_day = candidate_day + timedelta(days=1)

    return datetime.combine(candidate_day, start_time, tzinfo=timezone)


def resolve_data_proxy_url(data_proxy_url: str | None = None) -> str:
    """Return effective proxy URL from explicit value or DATA_PROXY_URL env."""
    if str(data_proxy_url or "").strip():
        return str(data_proxy_url).strip()
    return str(os.getenv("DATA_PROXY_URL", "ws://localhost:8765") or "ws://localhost:8765").strip()


def is_bar_event(event: dict[str, Any]) -> bool:
    event_type = str(event.get("T", event.get("type", ""))).strip().lower()
    return event_type in {"b", "bar"}


def event_symbol(event: dict[str, Any]) -> str:
    return str(event.get("S", event.get("symbol", "")) or "").strip().upper()


def normalize_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if ":" in text:
        text = text.rsplit(":", 1)[-1]
    return text


def event_datetime_ny(
    event: dict[str, Any],
    *,
    wall_time_ny: datetime | None = None,
    timezone: ZoneInfo = NY_TZ,
) -> datetime:
    raw_ts = event.get("t", event.get("timestamp"))
    parsed = coerce_market_datetime_ny(raw_ts, fallback_to_now=False)
    if parsed is not None:
        return parsed.astimezone(timezone)

    if wall_time_ny is not None:
        return wall_time_ny.astimezone(timezone)
    return datetime.now(timezone)


def event_minute_key(
    event: dict[str, Any],
    *,
    wall_time_ny: datetime | None = None,
) -> tuple[int, int, int, int, int]:
    parsed = event_datetime_ny(event, wall_time_ny=wall_time_ny)
    return (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute)


def minute_to_str(minute_key: tuple[int, int, int, int, int]) -> str:
    y, m, d, hh, mm = minute_key
    return f"{y:04d}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}"


def minute_key_from_datetime(dt_value: datetime, timezone: ZoneInfo = NY_TZ) -> tuple[int, int, int, int, int]:
    dt_ny = dt_value.astimezone(timezone)
    return (dt_ny.year, dt_ny.month, dt_ny.day, dt_ny.hour, dt_ny.minute)


def minute_datetime_from_key(minute_key: tuple[int, int, int, int, int], timezone: ZoneInfo = NY_TZ) -> datetime:
    year, month, day, hour, minute = minute_key
    return datetime(year, month, day, hour, minute, tzinfo=timezone)


def numeric_bar_value(event: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = event.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return float(default)


def build_stale_bar(symbol: str, previous_bar: dict[str, Any], minute_time_ny: datetime) -> dict[str, Any] | None:
    close_value = numeric_bar_value(previous_bar, "c", "close", default=0.0)
    if close_value <= 0.0:
        return None

    minute_time = minute_time_ny.astimezone(NY_TZ)
    return {
        "T": "b",
        "S": str(symbol or "").strip().upper(),
        "o": close_value,
        "h": close_value,
        "l": close_value,
        "c": close_value,
        "v": 0.0,
        "n": 0,
        "vw": close_value,
        "t": minute_time.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_ny_time": minute_time,
        "_stale": True,
    }


def complete_symbol_bar_set(
    bars_by_symbol: dict[str, dict[str, Any]],
    latest_bars: dict[str, dict[str, Any]],
    symbols: list[str] | tuple[str, ...] | set[str],
    minute_key: tuple[int, int, int, int, int],
    timezone: ZoneInfo = NY_TZ,
) -> list[dict[str, Any]]:
    minute_time_ny = minute_datetime_from_key(minute_key, timezone=timezone)
    completed = {str(symbol or "").strip().upper(): dict(bar) for symbol, bar in (bars_by_symbol or {}).items()}
    ordered_symbols = [str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip()]

    for symbol in ordered_symbols:
        if symbol in completed:
            continue
        previous = latest_bars.get(symbol)
        if not isinstance(previous, dict):
            # Symbol hasn't traded yet this session; skip it rather than blocking every other symbol.
            continue
        stale_bar = build_stale_bar(symbol, previous, minute_time_ny)
        if stale_bar is None:
            continue
        completed[symbol] = stale_bar

    return [completed[symbol] for symbol in ordered_symbols if symbol in completed]


def bar_value(bar: dict[str, Any], short_key: str, long_key: str, default: float = 0.0) -> float:
    raw = bar.get(short_key)
    if raw is None:
        raw = bar.get(long_key, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def build_pair_bar(pair, bar1: dict[str, Any], bar2: dict[str, Any]) -> dict[str, Any]:
    q1 = float(getattr(pair, "quantity1", 1.0))
    q2 = float(getattr(pair, "quantity2", 1.0))

    open_px = q1 * bar_value(bar1, "o", "open") - q2 * bar_value(bar2, "o", "open")
    high_px = q1 * bar_value(bar1, "h", "high") - q2 * bar_value(bar2, "h", "high")
    low_px = q1 * bar_value(bar1, "l", "low") - q2 * bar_value(bar2, "l", "low")
    close_px = q1 * bar_value(bar1, "c", "close") - q2 * bar_value(bar2, "c", "close")
    vwap_px = q1 * bar_value(bar1, "vw", "vwap", default=close_px) - q2 * bar_value(bar2, "vw", "vwap", default=close_px)

    volume = bar_value(bar1, "v", "volume", default=0.0) + bar_value(bar2, "v", "volume", default=0.0)
    trade_count = bar_value(bar1, "n", "trade_count", default=0.0) + bar_value(bar2, "n", "trade_count", default=0.0)
    timestamp = bar1.get("t") or bar1.get("timestamp") or bar2.get("t") or bar2.get("timestamp")
    pair_symbol = str(getattr(pair, "pair_symbol", "PAIR")).strip()

    return {
        "T": "b",
        "S": pair_symbol,
        "symbol": pair_symbol,
        "t": timestamp,
        "timestamp": timestamp,
        "o": float(open_px),
        "h": float(high_px),
        "l": float(low_px),
        "c": float(close_px),
        "vw": float(vwap_px),
        "open": float(open_px),
        "high": float(high_px),
        "low": float(low_px),
        "close": float(close_px),
        "vwap": float(vwap_px),
        "v": float(volume),
        "n": int(round(float(trade_count))),
        "volume": float(volume),
        "trade_count": int(round(float(trade_count))),
    }


def pair_close_from_bars(pair, bar1: dict[str, Any], bar2: dict[str, Any]) -> float:
    pair_bar = build_pair_bar(pair, bar1, bar2)
    return bar_value(pair_bar, "c", "close", default=0.0)


def event_close(event: dict[str, Any]) -> float | None:
    close_value = event.get("c", event.get("close"))
    if close_value is None:
        return None
    try:
        return float(close_value)
    except (TypeError, ValueError):
        return None


def event_timestamp_text(event: dict[str, Any], timezone: ZoneInfo = NY_TZ) -> str:
    return event_datetime_ny(event, timezone=timezone).strftime("%Y-%m-%d %H:%M:%S")


def event_timing_ny(
    event: dict[str, Any],
    *,
    wall_time_ny: datetime | None = None,
    timezone: ZoneInfo = NY_TZ,
) -> tuple[datetime, tuple[int, int, int, int, int], float]:
    """Return NY bar datetime, minute key, and absolute skew vs wall time in seconds."""
    wall_time = wall_time_ny.astimezone(timezone) if wall_time_ny is not None else datetime.now(timezone)
    bar_time = event_datetime_ny(event, wall_time_ny=wall_time, timezone=timezone)
    minute_key = (bar_time.year, bar_time.month, bar_time.day, bar_time.hour, bar_time.minute)
    skew_seconds = abs((bar_time - wall_time).total_seconds())
    return bar_time, minute_key, skew_seconds


def build_bar_timestamp_skew_warning(
    symbol: str,
    *,
    bar_time_ny: datetime,
    wall_time_ny: datetime,
    skew_seconds: float,
    threshold_seconds: float = 10.0,
) -> str | None:
    # Minute bars are often stamped at minute start. During rollover, a healthy
    # stream can therefore appear ~60s behind wall clock. Treat one-bar lag as
    # expected and only warn on residual skew beyond that.
    raw_skew = abs(float(skew_seconds))
    one_bar_lag_skew = abs((bar_time_ny + timedelta(seconds=60) - wall_time_ny).total_seconds())
    effective_skew = min(raw_skew, one_bar_lag_skew)

    if effective_skew <= float(threshold_seconds):
        return None
    return (
        f"Bar timestamp skew detected: symbol={symbol} "
        f"bar_time={bar_time_ny.strftime('%Y-%m-%d %H:%M:%S')} "
        f"wall_time={wall_time_ny.strftime('%Y-%m-%d %H:%M:%S')} "
        f"skew_seconds={float(effective_skew):.2f}"
    )


async def stream_proxy_events(
    data_proxy_url: str,
    on_event: Callable[[dict[str, Any]], Awaitable[None]],
    *,
    reconnect_delay: float = 5.0,
    stop_event: threading.Event | None = None,
) -> None:
    """Read JSON events from proxy websocket and dispatch each event to callback."""
    while stop_event is None or not stop_event.is_set():
        try:
            async with websockets.connect(resolve_data_proxy_url(data_proxy_url)) as ws:
                while stop_event is None or not stop_event.is_set():
                    try:
                        if stop_event is None:
                            message = await ws.recv()
                        else:
                            message = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue
                    payload = json.loads(message)
                    events = payload if isinstance(payload, list) else [payload]
                    for event in events:
                        await on_event(event)
        except Exception:
            if stop_event is not None and stop_event.is_set():
                break
            await asyncio.sleep(max(0.0, float(reconnect_delay)))


async def collect_latest_proxy_bars(
    symbols: list[str] | set[str],
    *,
    data_proxy_url: str,
    timeout_seconds: float = 8.0,
) -> dict[str, dict[str, Any]]:
    """Collect the latest valid bar events for requested symbols from the proxy."""
    wanted = {str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}
    if not wanted:
        return {}

    latest: dict[str, dict[str, Any]] = {}
    deadline = asyncio.get_running_loop().time() + max(1.0, float(timeout_seconds))

    async with websockets.connect(resolve_data_proxy_url(data_proxy_url)) as ws:
        while asyncio.get_running_loop().time() < deadline:
            remaining = max(0.1, deadline - asyncio.get_running_loop().time())
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break

            payload = json.loads(message)
            events = payload if isinstance(payload, list) else [payload]
            for event in events:
                if not isinstance(event, dict) or not is_bar_event(event):
                    continue

                symbol = event_symbol(event)
                if symbol not in wanted:
                    continue
                close_value = event_close(event)
                if close_value is None or close_value <= 0.0:
                    continue
                latest[symbol] = dict(event)

            if set(latest.keys()) >= wanted:
                break

    return latest


async def collect_latest_proxy_prices(
    symbols: list[str] | set[str],
    *,
    data_proxy_url: str,
    convert_bar: Callable[[dict[str, Any]], Any] | None = None,
    timeout_seconds: float = 8.0,
) -> dict[str, float]:
    """Collect latest close prices for requested symbols from proxy stream."""
    latest_bars = await collect_latest_proxy_bars(
        symbols,
        data_proxy_url=data_proxy_url,
        timeout_seconds=timeout_seconds,
    )
    latest_prices: dict[str, float] = {}
    for symbol, event in latest_bars.items():
        close_value: float | None = None
        if callable(convert_bar):
            bar_obj = convert_bar(event)
            if bar_obj is not None:
                try:
                    close_value = float(getattr(bar_obj, "close", 0.0) or 0.0)
                except (TypeError, ValueError):
                    close_value = None
        if close_value is None:
            close_value = event_close(event)
        if close_value is not None and close_value > 0.0:
            latest_prices[symbol] = close_value
    return latest_prices


def latest_alpaca_market_data_with_feed_fallback(
    *,
    data_client,
    symbols: list[str],
    print_fn=print,
):
    """Fetch complete latest bars and quotes from SIP, then IEX."""
    errors: list[str] = []
    for feed in (DataFeed.SIP, DataFeed.IEX):
        bar_request = StockLatestBarRequest(symbol_or_symbols=symbols, feed=feed)
        quote_request = StockLatestQuoteRequest(symbol_or_symbols=symbols, feed=feed)
        try:
            latest_bars = data_client.get_stock_latest_bar(bar_request)
            latest_quotes = data_client.get_stock_latest_quote(quote_request)
            missing_bars = [symbol for symbol in symbols if latest_bars.get(symbol) is None]
            missing_quotes = [symbol for symbol in symbols if latest_quotes.get(symbol) is None]
            if missing_bars or missing_quotes:
                raise RuntimeError(f"missing bars={missing_bars} missing quotes={missing_quotes}")
            if feed == DataFeed.IEX:
                print_fn("⚠️ ", f"SIP market data failed; using IEX. SIP error: {errors[0]}")
            return feed, bar_request, latest_bars, latest_quotes
        except Exception as exc:
            errors.append(str(exc))

    raise RuntimeError(f"SIP and IEX market data requests failed. SIP error: {errors[0]}; IEX error: {errors[1]}")


__all__ = [
    "NY_TZ",
    "resolve_proxy_schedule_from_env",
    "minutes_since_midnight",
    "is_within_time_window",
    "is_market_open_day",
    "proxy_schedule_status",
    "proxy_idle_heartbeat_key",
    "format_proxy_idle_heartbeat_message",
    "next_proxy_start_datetime",
    "resolve_data_proxy_url",
    "is_bar_event",
    "normalize_symbol",
    "event_symbol",
    "event_datetime_ny",
    "event_minute_key",
    "minute_to_str",
    "minute_key_from_datetime",
    "minute_datetime_from_key",
    "numeric_bar_value",
    "build_stale_bar",
    "complete_symbol_bar_set",
    "event_close",
    "event_timestamp_text",
    "event_timing_ny",
    "build_bar_timestamp_skew_warning",
    "stream_proxy_events",
    "collect_latest_proxy_bars",
    "collect_latest_proxy_prices",
    "latest_alpaca_market_data_with_feed_fallback",
    "bar_value",
    "build_pair_bar",
    "pair_close_from_bars",
]
