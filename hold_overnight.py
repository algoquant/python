#!/usr/bin/env python3
"""
hold_overnight.py
=================

Hold-Overnight stock strategy.
    Keep overnight stock positions for the tickers.  Buy 1 minute before the market close and exit 1 minute after the market open the next day.

Examples:
    python3 hold_overnight.py --test-mode SPY 1 QQQ 1 AAPL 3
    python3 hold_overnight.py SPY 1 QQQ 1 AAPL 3
    python3 hold_overnight.py args.csv

Lifecycle (ET):
    1) Startup diagnostics validate auth, data availability, and CSV logging.
    2) Scheduler loop runs continuously and triggers once-daily actions.
    3) SELL trigger runs at 09:31, then BUY trigger runs at 15:59.
    4) Heartbeat logs status every 5 minutes for observability.
    5) SIGINT/SIGTERM stop the loop gracefully.

Schedule:
  BUY  — Mon–Fri at 15:59 ET
  SELL — Mon–Fri at 09:31 ET

CSV log columns:
  timestamp, action, ticker, qty, order_id, order_status,
  fill_price, cost_basis, pnl, pnl_pct, note

Keys from .env:
    SUPABASE_URL / SUPABASE_KEY       → credential source

Supabase account source:
    Account label Aiv010 resolves to:
        acctname = Aiv010
        slot     = P2  -> apikeyp2 / apisecretp2

Design notes:
    - All network calls are centralized in HTTP helpers for consistent timeout,
        error handling, and payload parsing.
    - Daily buy/sell flags prevent duplicate submissions if the scheduler loop
        iterates multiple times around trigger boundaries.
    - A persistent inventory ledger tracks shares owned by this strategy only,
        so sell logic is scoped to strategy inventory instead of account totals.
    - CSV rows are append-only to preserve an audit trail of every action.
"""

import os
import sys
import argparse
import csv
import json
import time
import threading
import signal
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import re

import requests
from MachineTrader.helpers.alpacasdk import AlpacAPI
from MachineTrader import GetArgs

# ── Timezone sanity check ─────────────────────────────────────────────────────
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    _ET_CHECK = ZoneInfo("America/New_York")
    # Use a fixed winter date: New York should never resolve to UTC offset 0 then.
    # This catches missing/broken tzdata early before schedule-based trading starts.
    _utc_offset = _ET_CHECK.utcoffset(__import__("datetime").datetime(2026, 1, 1))
    if _utc_offset is not None and _utc_offset.total_seconds() == 0:
        raise RuntimeError(
            "ZoneInfo('America/New_York') resolved to UTC offset 0 — "
            "tzdata package is missing.  Install it:  pip install tzdata"
        )
except ZoneInfoNotFoundError:
    raise RuntimeError(
        "ZoneInfo('America/New_York') not found — "
        "tzdata package is missing.  Install it:  pip install tzdata"
    )

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("hold_overnight")

# ── Config ────────────────────────────────────────────────────────────────────
# Load runtime configuration from .env in the current working directory.
_ENV_FILE = os.path.join(os.getcwd(), ".env")
auth = AlpacAPI()

_TRADE_HEADERS: dict[str, str] = {
    "accept": "application/json",
    "content-type": "application/json",
    "apca-api-key-id": "",
    "apca-api-secret-key": "",
}
_DATA_HEADERS: dict[str, str] = {
    "accept": "application/json",
    "apca-api-key-id": "",
    "apca-api-secret-key": "",
}

PAPER_BASE = "https://paper-api.alpaca.markets"
DATA_BASE  = "https://data.alpaca.markets"

ET = ZoneInfo("America/New_York")

# ── NYSE calendar cache ───────────────────────────────────────────────────────
# Cached open-market dates from Alpaca calendar endpoint.
_market_open_days: set[date] = set()
_calendar_loaded_until: date | None = None
_market_close_mins: dict[date, int] = {}

# Strategy parameters
TICKERS = ["VTI", "QQQ", "MU", "MGM"]
QTY     = 1.0   # shares per ticker (fractional supported)
QTY_BY_TICKER: dict[str, float] = {t: QTY for t in TICKERS}

# Schedule (ET)
BUY_HOUR,  BUY_MIN  = 15, 59   # 15:59 — 1 min before market close
SELL_HOUR, SELL_MIN =  9, 31   # 09:31 — 1 min after market open

# Fill-poll settings
POLL_INITIAL_WAIT = 3
POLL_RETRY_WAIT   = 5
POLL_MAX_RETRIES  = 8

# Monitor interval (seconds)
MONITOR_INTERVAL = 120   # 2 min


def _parse_csv_file(filepath: str) -> list[tuple[str, float]]:
    """
    Parse CSV file with two columns: symbol and shares.
    Supports headers or headerless format.
    Returns list of (symbol, qty) tuples.
    """
    ticker_qty_pairs: list[tuple[str, float]] = []
    seen: set[str] = set()

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    with open(filepath, "r") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise ValueError(f"CSV file is empty: {filepath}")

    # Detect and skip header row if present (common patterns: "symbol", "ticker", "Symbol", "Ticker", etc.)
    start_idx = 0
    first_row = rows[0]
    if (
        len(first_row) >= 2
        and first_row[0].lower() in ("symbol", "ticker", "sym", "stock")
        and first_row[1].lower() in ("shares", "qty", "quantity", "amount")
    ):
        start_idx = 1

    for idx, row in enumerate(rows[start_idx:], start=start_idx + 1):
        row = [col.strip() for col in row if col.strip()]

        if len(row) < 2:
            raise ValueError(
                f"CSV row {idx} has fewer than 2 columns: {row}. "
                "Expected: symbol, shares"
            )

        symbol = row[0].strip().upper()
        qty_raw = row[1].strip()

        if not symbol or not re.fullmatch(r"[A-Z][A-Z0-9.\-]*", symbol):
            raise ValueError(f"Invalid symbol in CSV row {idx}: {row[0]}")

        if symbol in seen:
            raise ValueError(f"Duplicate symbol in CSV file: {symbol}")
        seen.add(symbol)

        try:
            qty = float(qty_raw)
        except ValueError:
            raise ValueError(
                f"Invalid share quantity in CSV row {idx} for {symbol}: {qty_raw}"
            )

        if qty == 0:
            raise ValueError(
                f"Share quantity must be non-zero in CSV row {idx} for {symbol}: {qty_raw}"
            )

        ticker_qty_pairs.append((symbol, qty))

    if not ticker_qty_pairs:
        raise ValueError(f"No valid symbol/qty pairs found in CSV file: {filepath}")

    return ticker_qty_pairs
# End of CSV parsing function


def parse_arguments():
    """
    Parse CLI arguments in two modes:
      1. CSV file: python3 hold_overnight.py trading_config.csv
         CSV format: two columns (symbol, shares), header optional
      2. SYMBOL QTY pairs: python3 hold_overnight.py SPY 1 QQQ 1 AAPL 3
    """
    parser = argparse.ArgumentParser(
        description="Hold-Overnight stock strategy",
        epilog="Examples:\n"
               "  python3 hold_overnight.py SPY 1 QQQ 1 AAPL 3\n"
               "  python3 hold_overnight.py trading_config.csv\n"
               "  python3 hold_overnight.py --test-mode SPY 1 QQQ 1",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run immediate test mode: buy now, then sell 1 minute later.",
    )
    parser.add_argument(
        "pairs",
        nargs="+",
        help="Either CSV filename or alternating SYMBOL QTY values",
    )

    args_handler = GetArgs()
    args = args_handler.parse_custom(parser)
    values = args.pairs

    # Detect input mode: CSV file vs. CLI pairs
    ticker_qty_pairs: list[tuple[str, float]] = []

    # Check if first argument is a CSV file
    if len(values) == 1 and values[0].endswith(".csv"):
        try:
            ticker_qty_pairs = _parse_csv_file(values[0])
            print(f"Loaded {len(ticker_qty_pairs)} symbols from CSV: {values[0]}")
        except (FileNotFoundError, ValueError) as e:
            parser.error(f"CSV parsing error: {e}")
    else:
        # Parse as CLI SYMBOL QTY pairs
        if len(values) % 2 != 0:
            parser.error(
                "Arguments must be SYMBOL QTY pairs. Example: python3 hold_overnight.py SPY 1 QQQ 1 AAPL 3"
            )

        seen: set[str] = set()

        for i in range(0, len(values), 2):
            symbol = values[i].strip().upper()
            qty_raw = values[i + 1].strip()

            if not symbol or not re.fullmatch(r"[A-Z][A-Z0-9.\-]*", symbol):
                parser.error(f"Invalid symbol: {values[i]}")

            if symbol in seen:
                parser.error(f"Duplicate symbol provided: {symbol}")
            seen.add(symbol)

            try:
                qty = float(qty_raw)
            except ValueError:
                parser.error(f"Invalid share quantity for {symbol}: {qty_raw}")

            if qty == 0:
                parser.error(f"Share quantity must be non-zero for {symbol}: {qty_raw}")

            ticker_qty_pairs.append((symbol, qty))

    args.ticker_qty_pairs = ticker_qty_pairs
    return args
# End of argument parsing function


def _configure_strategy_from_args(mt_args) -> None:
    """Set runtime strategy tickers and quantity from parsed CLI arguments."""
    global TICKERS, QTY, QTY_BY_TICKER, _inventory

    pairs = getattr(mt_args, "ticker_qty_pairs", None)
    if not pairs:
        raise ValueError(
            "No symbols provided. Example: python3 hold_overnight.py SPY 1 QQQ 1 AAPL 3"
        )

    TICKERS = [symbol for symbol, _ in pairs]
    QTY_BY_TICKER = {symbol: qty for symbol, qty in pairs}
    QTY = max(abs(v) for v in QTY_BY_TICKER.values())

    # Re-shape in-memory inventory to the configured ticker universe.
    with _state_lock:
        _inventory = _ledger_default()
# End of strategy configuration function


def _parse_hhmm_to_minutes(hhmm: str | None) -> int | None:
    """Parse HH:MM or HH:MM:SS strings into minutes since midnight."""
    if not hhmm or not isinstance(hhmm, str):
        return None
    try:
        parts = hhmm.split(":")
        if len(parts) < 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour * 60 + minute
        return None
    except Exception:
        return None
# End of HH:MM parsing function


def _load_market_calendar(lookahead_days: int = 120) -> None:
    """Load/refresh NYSE open days from Alpaca calendar into local cache."""
    global _market_open_days, _calendar_loaded_until, _market_close_mins

    today = datetime.now(ET).date()
    end = today + timedelta(days=lookahead_days)

    # Reuse cache when it still comfortably covers upcoming days.
    if _calendar_loaded_until is not None and _calendar_loaded_until >= end:
        return

    try:
        r = requests.get(
            f"{PAPER_BASE}/v2/calendar",
            headers=_trade_headers(),
            params={"start": today.isoformat(), "end": end.isoformat()},
            timeout=15,
        )
        if not r.ok:
            log.warning(
                "Market calendar fetch failed (HTTP %d). Falling back to weekday-only schedule.",
                r.status_code,
            )
            return

        payload = r.json()
        if not isinstance(payload, list):
            log.warning("Market calendar payload not list. Falling back to weekday-only schedule.")
            return

        open_days: set[date] = set()
        close_mins: dict[date, int] = {}
        for item in payload:
            if not isinstance(item, dict) or "date" not in item:
                continue
            d = date.fromisoformat(item["date"])
            open_days.add(d)
            cm = _parse_hhmm_to_minutes(item.get("close"))
            if cm is not None:
                close_mins[d] = cm

        _market_open_days = open_days
        _market_close_mins = close_mins
        _calendar_loaded_until = end
        log.info(
            "Market calendar loaded: %d open day(s) through %s",
            len(_market_open_days),
            _calendar_loaded_until,
        )
    except Exception as exc:
        log.warning("Market calendar fetch exception (%s). Falling back to weekday-only schedule.", exc)
# End of market calendar loading function


def _is_nyse_trading_day(d: date) -> bool:
    """Return True when the provided ET date is an NYSE trading day."""
    # Never trade on weekends regardless of calendar API availability.
    if d.weekday() > 4:
        return False

    _load_market_calendar()
    if not _market_open_days:
        # Safe fallback if calendar is unavailable: weekday-only behavior.
        return True
    return d in _market_open_days
# End of trading day check function


def _buy_trigger_mins_for_day(d: date) -> int:
    """
    Return BUY trigger minute for date d.

    On regular sessions, this is 15:59.
    On early-close sessions, this is exactly one minute before that session close.
    """
    _load_market_calendar()

    # Fallback behavior when calendar data is unavailable.
    default_buy = BUY_HOUR * 60 + BUY_MIN
    if not _market_close_mins:
        return default_buy

    close_mins = _market_close_mins.get(d)
    if close_mins is None:
        return default_buy

    # One minute before market close.
    return max(0, close_mins - 1)
# End of BUY trigger minute function


# ── CSV trade log ─────────────────────────────────────────────────────────────
# Append-only trade journal used for post-trade analysis and reconciliation.
CSV_LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hold_overnight_log.csv"
)

# Persistent per-strategy inventory ledger.
# This file tracks shares attributed to this strategy only.
LEDGER_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hold_overnight_ledger.json"
)

_CSV_COLUMNS = [
    "timestamp", "action", "ticker", "qty",
    "order_id", "order_status", "fill_price", "trade_value",
    "cost_basis", "pnl", "pnl_pct", "strategy_inventory", "note",
]

def _csv_ensure_header() -> None:
    """Create the CSV file with a header row if it does not exist yet."""
    try:
        write_header = not os.path.exists(CSV_LOG_PATH) or os.path.getsize(CSV_LOG_PATH) == 0
        if write_header:
            with open(CSV_LOG_PATH, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=_CSV_COLUMNS).writeheader()
            log.info("CSV log created: %s", CSV_LOG_PATH)
    except Exception as exc:
        log.error("CSV header write failed: %s", exc)

def _csv_log_row(
    action: str,
    ticker: str,
    qty: float,
    order_id: str,
    order_status: str,
    fill_price: float | None = None,
    trade_value: float | None = None,
    cost_basis: float | None = None,
    pnl: float | None = None,
    pnl_pct: float | None = None,
    strategy_inventory: float | None = None,
    note: str = "",
) -> None:
    """Append one normalized log row to the strategy CSV output."""
    _csv_ensure_header()
    row = {
        "timestamp":    datetime.now(ET).isoformat(),
        "action":       action,
        "ticker":       ticker,
        "qty":          round(qty, 6),
        "order_id":     order_id,
        "order_status": order_status,
        "fill_price":   round(fill_price, 4) if fill_price is not None else "",
        "trade_value":  round(trade_value, 2) if trade_value is not None else "",
        "cost_basis":   round(cost_basis, 4) if cost_basis is not None else "",
        "pnl":          round(pnl,        2) if pnl        is not None else "",
        "pnl_pct":      round(pnl_pct,    4) if pnl_pct    is not None else "",
        "strategy_inventory": round(strategy_inventory, 6) if strategy_inventory is not None else "",
        "note":         note,
    }
    try:
        with open(CSV_LOG_PATH, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=_CSV_COLUMNS).writerow(row)
        log.info("CSV row written — action=%s  ticker=%s  status=%s",
                 action, ticker, order_status)
    except Exception as exc:
        log.error("CSV row write failed: %s", exc)

# ── Graceful shutdown ─────────────────────────────────────────────────────────
_shutdown = threading.Event()

def _sighandler(sig, frame):
    """Signal handler that requests a clean shutdown of the scheduler loop."""
    log.info("Shutdown signal received — exiting cleanly.")
    _shutdown.set()

signal.signal(signal.SIGINT,  _sighandler)
signal.signal(signal.SIGTERM, _sighandler)

# ── HTTP helpers ──────────────────────────────────────────────────────────────
# Centralized request helpers keep auth, timeout, and error handling consistent.
def _trade_headers() -> dict:
    """Return authenticated headers for Alpaca trading endpoints."""
    return dict(_TRADE_HEADERS)

def _data_headers() -> dict:
    """Return authenticated headers for Alpaca market-data endpoints."""
    return dict(_DATA_HEADERS)

def _get(url: str, headers: dict, params: dict | None = None) -> dict | list | None:
    """HTTP GET wrapper with timeout and uniform JSON/error handling."""
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.error("GET %s failed: %s", url, exc)
        return None

def _post(url: str, headers: dict, body: dict) -> tuple[dict | None, int]:
    """HTTP POST wrapper returning (json_payload_or_none, status_code)."""
    try:
        r = requests.post(url, headers=headers, data=json.dumps(body), timeout=15)
        try:
            payload = r.json()
        except Exception:
            # Keep raw response text when the server reply is not valid JSON.
            payload = {"raw": r.text}
        if not r.ok:
            log.error("POST %s HTTP %s: %s", url, r.status_code, r.text[:400])
            return None, r.status_code
        return payload, r.status_code
    except Exception as exc:
        log.error("POST %s failed: %s", url, exc)
        return None, 0

# ── Fill poll ─────────────────────────────────────────────────────────────────
def poll_fill(order_id: str, label: str,
              max_retries: int = POLL_MAX_RETRIES) -> dict | None:
    """Poll an order until it is filled or reaches a terminal non-filled state."""
    time.sleep(POLL_INITIAL_WAIT)
    url = f"{PAPER_BASE}/v2/orders/{order_id}"
    order = None
    for attempt in range(max_retries + 1):
        order = _get(url, _trade_headers())
        if order:
            status = order.get("status", "")
            if status == "filled":
                filled_avg = float(order.get("filled_avg_price") or 0)
                log.info("%s: filled ✓  avg_price=$%.4f", label, filled_avg)
                return order
            if status in ("rejected", "canceled", "expired"):
                log.warning("%s: terminal status=%s", label, status)
                return order
            log.info("%s: status=%s, attempt %d/%d", label, status, attempt, max_retries)
        else:
            log.warning("%s: GET order failed (attempt %d)", label, attempt)
        if attempt < max_retries:
            time.sleep(POLL_RETRY_WAIT)
    return order

def _poll_fills_parallel(submitted: list[dict], side_label: str) -> dict[str, dict | None]:
    """
    Poll fills for a batch of submitted orders concurrently.

    Returns a mapping: order_id -> final order payload (or None on poll failure).
    """
    if not submitted:
        return {}

    max_workers = max(1, min(8, len(submitted)))
    results: dict[str, dict | None] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_meta = {
            pool.submit(poll_fill, str(meta["order_id"]), f"{side_label}-{meta['ticker']}"): meta
            for meta in submitted
        }
        for future in as_completed(future_to_meta):
            meta = future_to_meta[future]
            order_id = str(meta["order_id"])
            ticker = str(meta["ticker"])
            try:
                results[order_id] = future.result()
            except Exception as exc:
                log.error("Fill polling crashed for %s (%s): %s", ticker, order_id, exc)
                results[order_id] = None

    return results

# ── Price fetch ───────────────────────────────────────────────────────────────
def get_stock_price(ticker: str) -> float | None:
    """Fetch latest stock price from snapshot, preferring trade then quote mid."""
    url  = f"{DATA_BASE}/v2/stocks/{ticker}/snapshot"
    data = _get(url, _data_headers())
    if not data:
        log.error("Snapshot for %s returned None", ticker)
        return None
    trade = data.get("latestTrade") or data.get("latest_trade")
    if trade:
        price = trade.get("p") or trade.get("price")
        if price:
            return float(price)
    quote = data.get("latestQuote") or data.get("latest_quote")
    if quote:
        ap = float(quote.get("ap") or quote.get("ask_price") or 0)
        bp = float(quote.get("bp") or quote.get("bid_price") or 0)
        if ap > 0 and bp > 0:
            return (ap + bp) / 2
    log.error("Could not parse snapshot for %s: %s", ticker, str(data)[:200])
    return None

# ── Positions ─────────────────────────────────────────────────────────────────
def get_all_positions() -> list[dict]:
    """Return open positions filtered down to strategy tickers only."""
    positions = _get(f"{PAPER_BASE}/v2/positions", _trade_headers())
    if not isinstance(positions, list):
        return []
    return [
        p for p in positions
        if isinstance(p, dict)
        and str(p.get("symbol", "")) in TICKERS
    ]

def get_position(ticker: str) -> dict | None:
    """Return open position for one ticker, or None when flat/not found."""
    data = _get(f"{PAPER_BASE}/v2/positions/{ticker}", _trade_headers())
    if not data or "code" in data:
        return None
    return data

# ── Shared state ──────────────────────────────────────────────────────────────
_state_lock     = threading.Lock()
_bought_today   = False   # True once BUY leg has fired today
_sold_today     = False   # True once SELL leg has fired today
_trade_history: list[dict] = []
_inventory: dict[str, float] = {t: 0.0 for t in TICKERS}

def _ledger_default() -> dict[str, float]:
    """Return a zeroed inventory ledger shape for all configured tickers."""
    return {t: 0.0 for t in TICKERS}


def _format_qty_for_order(qty: float) -> str:
    """Format fractional share qty for Alpaca API without scientific notation."""
    return f"{qty:.6f}".rstrip("0").rstrip(".")

def _ledger_load() -> None:
    """Load strategy inventory ledger from disk, creating it when absent."""
    global _inventory
    with _state_lock:
        if not os.path.exists(LEDGER_PATH):
            _inventory = _ledger_default()
            with open(LEDGER_PATH, "w", encoding="utf-8") as f:
                json.dump(_inventory, f, indent=2, sort_keys=True)
            log.info("Ledger created: %s", LEDGER_PATH)
            return
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            base = _ledger_default()
            if isinstance(raw, dict):
                for t in TICKERS:
                    base[t] = float(raw.get(t, 0) or 0)
            _inventory = base
            log.info("Ledger loaded: %s  %s", LEDGER_PATH, _inventory)
        except Exception as exc:
            log.error("Ledger load failed (%s) — resetting to zeros", exc)
            _inventory = _ledger_default()

def _ledger_save() -> None:
    """Persist current strategy inventory ledger to disk."""
    with _state_lock:
        snap = {t: round(float(_inventory.get(t, 0) or 0), 6) for t in TICKERS}
    try:
        with open(LEDGER_PATH, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2, sort_keys=True)
    except Exception as exc:
        log.error("Ledger save failed: %s", exc)

def _ledger_get(ticker: str) -> float:
    """Read strategy-owned quantity for one ticker from in-memory ledger."""
    with _state_lock:
        return float(_inventory.get(ticker, 0) or 0)

def _ledger_add(ticker: str, qty: float) -> None:
    """Adjust strategy inventory upward (or downward if qty is negative)."""
    if qty == 0:
        return
    with _state_lock:
        _inventory[ticker] = float(_inventory.get(ticker, 0) or 0) + float(qty)
    _ledger_save()

def _ledger_sub(ticker: str, qty: float) -> None:
    """Adjust strategy inventory downward (or upward if qty is negative)."""
    if qty == 0:
        return
    with _state_lock:
        cur = float(_inventory.get(ticker, 0) or 0)
        _inventory[ticker] = cur - float(qty)
    _ledger_save()

# ── BUY — enter positions at 15:59 ───────────────────────────────────────────
def buy_positions():
    """
    Submit one market buy order per configured ticker.

    Side effects:
      - Sets daily buy flag.
      - Appends in-memory trade records.
      - Writes CSV rows for each order attempt.
    """
    global _bought_today
    with _state_lock:
        if _bought_today:
            log.info("Already bought today — skipping BUY.")
            return
        # Mark as done before network I/O to avoid duplicate trigger races.
        _bought_today = True

    log.info("═══ Hold-Overnight: ENTRY (%s tickers × up to %.6g share) ═══",
             len(TICKERS), QTY)

    submitted_orders: list[dict] = []

    for ticker in TICKERS:
        if _shutdown.is_set():
            return

        configured_qty = float(QTY_BY_TICKER.get(ticker, QTY))
        if configured_qty == 0:
            continue
        qty_to_enter = abs(configured_qty)
        entry_side = "buy" if configured_qty > 0 else "sell"
        entry_action = "BUY" if entry_side == "buy" else "SHORT"

        price = get_stock_price(ticker)
        price_str = f"${price:.2f}" if price is not None else "unknown"
        if entry_side == "buy":
            log.info("Buying %.6g share(s) of %s at market (~%s) …", qty_to_enter, ticker, price_str)
        else:
            log.info("Shorting %.6g share(s) of %s at market (~%s) …", qty_to_enter, ticker, price_str)

        body = {
            "symbol":        ticker,
            "qty":           _format_qty_for_order(qty_to_enter),
            "side":          entry_side,
            "type":          "market",
            "time_in_force": "day",
        }
        order, status_code = _post(f"{PAPER_BASE}/v2/orders", _trade_headers(), body)

        if order is None:
            log.error("BUY order for %s failed (HTTP %d)", ticker, status_code)
            _csv_log_row(
                action=entry_action, ticker=ticker, qty=configured_qty,
                order_id="", order_status="FAILED",
                strategy_inventory=_ledger_get(ticker),
                note=f"POST failed HTTP {status_code}",
            )
            continue

        order_id     = order.get("id", "")
        order_status = order.get("status", "unknown")
        log.info("BUY %s order submitted: id=%s  status=%s", ticker, order_id, order_status)

        if not order_id:
            log.error("BUY order for %s returned no order id", ticker)
            _csv_log_row(
                action=entry_action, ticker=ticker, qty=configured_qty,
                order_id="", order_status="FAILED",
                strategy_inventory=_ledger_get(ticker),
                note="Order submitted but missing order id",
            )
            continue

        submitted_orders.append({
            "ticker": ticker,
            "qty": qty_to_enter,
            "configured_qty": configured_qty,
            "entry_side": entry_side,
            "entry_action": entry_action,
            "order": order,
            "order_id": order_id,
            "order_status": order_status,
        })

    if not submitted_orders:
        log.info("BUY leg complete: no orders submitted.")
        return

    log.info("BUY fast-pass submit complete: %d order(s) queued for fill polling.", len(submitted_orders))
    fill_by_id = _poll_fills_parallel(submitted_orders, "entry")

    for meta in submitted_orders:
        if _shutdown.is_set():
            return

        ticker = str(meta["ticker"])
        qty = float(meta["qty"])
        configured_qty = float(meta["configured_qty"])
        entry_side = str(meta["entry_side"])
        entry_action = str(meta["entry_action"])
        order = meta["order"]
        order_id = str(meta["order_id"])
        order_status = str(meta["order_status"])

        # Fallback to initial order payload when polling fails/returns None.
        filled_order = fill_by_id.get(order_id) or order
        final_status = filled_order.get("status", order_status)
        filled_qty_raw = filled_order.get("filled_qty")
        filled_qty = float(filled_qty_raw or 0) if filled_qty_raw is not None else 0.0
        if filled_qty <= 0 and final_status == "filled":
            filled_qty = qty
        fill_price   = float(filled_order.get("filled_avg_price") or 0) or None
        trade_value  = None
        if fill_price is not None and filled_qty > 0:
            trade_value = (fill_price * filled_qty) if entry_side == "sell" else -(fill_price * filled_qty)

        if filled_qty > 0:
            ledger_delta = filled_qty if entry_side == "buy" else -filled_qty
            _ledger_add(ticker, ledger_delta)
            log.info("Ledger %+.6g %s => %.6g", ledger_delta, ticker, _ledger_get(ticker))

        record = {
            "timestamp":  datetime.now(ET).isoformat(),
            "action":     entry_action,
            "ticker":     ticker,
            "qty":        configured_qty,
            "order_id":   order_id,
            "status":     final_status,
            "fill_price": fill_price,
        }
        with _state_lock:
            _trade_history.append(record)

        _csv_log_row(
            action=entry_action, ticker=ticker, qty=configured_qty,
            order_id=order_id, order_status=final_status,
            fill_price=fill_price,
            trade_value=trade_value,
            strategy_inventory=_ledger_get(ticker),
        )

    log.info("BUY leg complete for all tickers.")

# ── SELL — exit positions at 09:31 ───────────────────────────────────────────
def sell_positions():
    """
    Liquidate all strategy ticker positions using market sells.

    Side effects:
      - Sets daily sell flag.
      - Appends in-memory trade records.
      - Writes CSV rows including realized snapshot PnL metrics.
    """
    global _sold_today
    with _state_lock:
        if _sold_today:
            log.info("Already sold today — skipping SELL.")
            return
        # Mark as done before network I/O to avoid duplicate trigger races.
        _sold_today = True

    log.info("═══ Hold-Overnight: EXIT (closing overnight positions) ═══")

    positions = get_all_positions()
    acct_qty_by_ticker: dict[str, float] = {}
    for pos in positions:
        ticker = str(pos.get("symbol", ""))
        acct_qty_by_ticker[ticker] = float(pos.get("qty") or 0)

    if not positions:
        log.info("No open account positions found for strategy tickers.")

    submitted_orders: list[dict] = []

    for ticker in TICKERS:
        if _shutdown.is_set():
            return

        strategy_qty = _ledger_get(ticker)
        account_qty  = float(acct_qty_by_ticker.get(ticker, 0))

        if strategy_qty == 0:
            continue

        close_side = "sell" if strategy_qty > 0 else "buy"
        close_action = "SELL" if close_side == "sell" else "COVER"
        strategy_abs_qty = abs(strategy_qty)
        account_abs_matching_side = max(0, account_qty) if strategy_qty > 0 else max(0, -account_qty)
        qty_to_close = min(strategy_abs_qty, account_abs_matching_side)

        if qty_to_close <= 0:
            log.warning(
                "Ledger says %s=%.6g, but account has %.6g on matching side — cannot close now; keeping ledger qty.",
                ticker, strategy_qty, account_qty,
            )
            continue

        pos = next((p for p in positions if str(p.get("symbol", "")) == ticker), {})
        cost = float(pos.get("avg_entry_price") or pos.get("cost_basis") or 0)
        unrealised = float(pos.get("unrealized_pl") or 0)
        pnl_for_qty = (unrealised * (qty_to_close / abs(account_qty))) if account_qty != 0 else 0.0

        if close_side == "sell":
            log.info("Selling %.6g share(s) of %s (cost_basis=%.4f  pnl_unreal=$%.2f) …",
                     qty_to_close, ticker, cost, pnl_for_qty)
        else:
            log.info("Covering %.6g share(s) of %s (cost_basis=%.4f  pnl_unreal=$%.2f) …",
                     qty_to_close, ticker, cost, pnl_for_qty)

        body = {
            "symbol":        ticker,
            "qty":           _format_qty_for_order(qty_to_close),
            "side":          close_side,
            "type":          "market",
            "time_in_force": "day",
        }
        order, status_code = _post(f"{PAPER_BASE}/v2/orders", _trade_headers(), body)

        if order is None:
            log.error("%s order for %s failed (HTTP %d)", close_action, ticker, status_code)
            _csv_log_row(
                action=close_action, ticker=ticker, qty=qty_to_close,
                order_id="", order_status="FAILED",
                cost_basis=cost,
                strategy_inventory=_ledger_get(ticker),
                note=f"POST failed HTTP {status_code}",
            )
            continue

        order_id     = order.get("id", "")
        order_status = order.get("status", "unknown")
        log.info("%s %s order submitted: id=%s  status=%s", close_action, ticker, order_id, order_status)

        if not order_id:
            log.error("%s order for %s returned no order id", close_action, ticker)
            _csv_log_row(
                action=close_action, ticker=ticker, qty=qty_to_close,
                order_id="", order_status="FAILED",
                cost_basis=cost,
                strategy_inventory=_ledger_get(ticker),
                note="Order submitted but missing order id",
            )
            continue

        submitted_orders.append({
            "ticker": ticker,
            "qty_to_close": float(qty_to_close),
            "close_side": close_side,
            "close_action": close_action,
            "cost": cost,
            "pnl_for_qty": pnl_for_qty,
            "order": order,
            "order_id": order_id,
            "order_status": order_status,
        })

    if not submitted_orders:
        _print_cumulative()
        log.info("SELL leg complete (no submitted orders).")
        return

    log.info("SELL fast-pass submit complete: %d order(s) queued for fill polling.", len(submitted_orders))
    fill_by_id = _poll_fills_parallel(submitted_orders, "exit")

    for meta in submitted_orders:
        if _shutdown.is_set():
            return

        ticker = str(meta["ticker"])
        qty_to_close = float(meta["qty_to_close"])
        close_side = str(meta["close_side"])
        close_action = str(meta["close_action"])
        cost = float(meta["cost"])
        pnl_for_qty = float(meta["pnl_for_qty"])
        order = meta["order"]
        order_id = str(meta["order_id"])
        order_status = str(meta["order_status"])

        # Fallback to initial order payload when polling fails/returns None.
        filled_order = fill_by_id.get(order_id) or order
        final_status = filled_order.get("status", order_status)
        filled_qty_raw = filled_order.get("filled_qty")
        filled_qty = float(filled_qty_raw or 0) if filled_qty_raw is not None else 0.0
        if filled_qty <= 0 and final_status == "filled":
            filled_qty = qty_to_close
        fill_price   = float(filled_order.get("filled_avg_price") or 0) or None
        trade_value  = None
        if fill_price is not None and filled_qty > 0:
            trade_value = (fill_price * filled_qty) if close_side == "sell" else -(fill_price * filled_qty)
        pnl          = pnl_for_qty
        pnl_pct      = (pnl / (cost * qty_to_close)) if cost and qty_to_close else None

        if filled_qty > 0:
            ledger_delta = -filled_qty if close_side == "sell" else filled_qty
            _ledger_add(ticker, ledger_delta)
            log.info("Ledger %+.6g %s => %.6g", ledger_delta, ticker, _ledger_get(ticker))

        record = {
            "timestamp":  datetime.now(ET).isoformat(),
            "action":     close_action,
            "ticker":     ticker,
            "qty":        int(qty_to_close),
            "order_id":   order_id,
            "status":     final_status,
            "fill_price": fill_price,
            "pnl":        pnl,
        }
        with _state_lock:
            _trade_history.append(record)

        _csv_log_row(
            action=close_action, ticker=ticker, qty=qty_to_close,
            order_id=order_id, order_status=final_status,
            fill_price=fill_price,
            trade_value=trade_value,
            cost_basis=cost,
            pnl=pnl,
            pnl_pct=pnl_pct,
            strategy_inventory=_ledger_get(ticker),
        )

    _print_cumulative()
    log.info("SELL leg complete.")

# ── Position monitor ──────────────────────────────────────────────────────────
def monitor_positions():
    """Log a lightweight snapshot of open strategy positions and unrealized PnL."""
    positions = get_all_positions()
    if not positions:
        return
    total_pnl = sum(float(p.get("unrealized_pl") or 0) for p in positions)
    log.info(
        "Position monitor: %d position(s)  total_unrealized_pnl=$%.2f",
        len(positions), total_pnl,
    )
    for pos in positions:
        ticker     = pos.get("symbol", "?")
        qty        = pos.get("qty", "?")
        pnl        = float(pos.get("unrealized_pl") or 0)
        entry      = float(pos.get("avg_entry_price") or 0)
        market_val = float(pos.get("market_value") or 0)
        log.info(
            "  %-6s  qty=%-4s  entry=$%.2f  mkt_val=$%.2f  pnl=$%.2f",
            ticker, qty, entry, market_val, pnl,
        )

# ── Cumulative summary ────────────────────────────────────────────────────────
def _print_cumulative():
    """Print aggregated sell-side PnL and win-rate from in-memory history."""
    with _state_lock:
        history = list(_trade_history)
    sells = [
        r
        for r in history
        if r.get("action") in ("SELL", "COVER") and r.get("pnl") is not None
    ]
    if not sells:
        return
    total_pnl = sum(r.get("pnl", 0) for r in sells)
    wins      = sum(1 for r in sells if r.get("pnl", 0) > 0)
    n         = len(sells)
    win_pct   = wins / n * 100 if n else 0
    log.info(
        "Cumulative SELL summary: %d trade(s)  total_pnl=$%.2f  win_rate=%.1f%%",
        n, total_pnl, win_pct,
    )

# ── Daily state reset ─────────────────────────────────────────────────────────
def _reset_daily():
    """Reset one-day execution flags so next session can trigger buy/sell again."""
    global _bought_today, _sold_today
    with _state_lock:
        _bought_today = False
        _sold_today   = False
    log.info("Daily state reset (bought_today=False  sold_today=False)")

# ── Startup diagnostics ───────────────────────────────────────────────────────
def startup_diagnostics():
    """
    Run preflight checks for data, trading auth, and CSV write path.

    This function is informational: it logs failures but does not raise.
    """
    # Preflight checks are run before scheduler start to surface config/API issues early.
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("STARTUP DIAGNOSTICS — Hold-Overnight")
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    failures: list[str] = []

    # ── 1. Stock prices ───────────────────────────────────────────────────────
    log.info("[1/4] Fetching latest prices for all tickers …")
    for ticker in TICKERS:
        price = get_stock_price(ticker)
        if price is None:
            log.error("  ✗ FAIL — could not fetch price for %s", ticker)
            failures.append(f"{ticker} price fetch")
        else:
            log.info("  ✓ %s = $%.2f", ticker, price)

    # ── 2. Trade API auth ──────────────────────────────────────────────────────
    log.info("[2/4] Checking trade API auth + open positions …")
    try:
        r = requests.get(
            f"{PAPER_BASE}/v2/positions",
            headers=_trade_headers(),
            timeout=15,
        )
        if r.status_code == 401:
            log.error(
                "  ✗ FAIL — 401 Unauthorized.  "
                "Trading credentials are wrong or missing."
            )
            failures.append("trade API 401 Unauthorized — check credential source")
        elif not r.ok:
            log.error("  ✗ FAIL — trade API returned HTTP %d: %s",
                      r.status_code, r.text[:200])
            failures.append(f"trade API HTTP {r.status_code}")
        else:
            positions = [
                p for p in r.json()
                if isinstance(p, dict) and str(p.get("symbol", "")) in TICKERS
            ] if isinstance(r.json(), list) else []
            log.info("  ✓ PASS — trade API auth OK")
            if not positions:
                log.info("  (no open positions for strategy tickers)")
            else:
                log.info("  Found %d existing position(s):", len(positions))
                for pos in positions:
                    sym   = pos.get("symbol", "?")
                    qty   = pos.get("qty", "?")
                    entry = float(pos.get("avg_entry_price") or 0)
                    pnl   = float(pos.get("unrealized_pl") or 0)
                    log.info("    %-6s  qty=%-4s  entry=$%.2f  pnl_unreal=$%.2f",
                             sym, qty, entry, pnl)
    except Exception as exc:
        log.error("  ✗ FAIL — trade API request failed: %s", exc)
        failures.append(f"trade API exception: {exc}")

    # ── 3. CSV log ─────────────────────────────────────────────────────────────
    log.info("[3/4] Verifying CSV log path …")
    _csv_ensure_header()
    if os.path.exists(CSV_LOG_PATH):
        log.info("  ✓ CSV log ready: %s", CSV_LOG_PATH)
    else:
        log.warning("  ✗ WARN — CSV log file could not be created at: %s", CSV_LOG_PATH)

    # ── 4. Inventory ledger ───────────────────────────────────────────────────
    log.info("[4/4] Verifying inventory ledger …")
    _ledger_load()
    if os.path.exists(LEDGER_PATH):
        log.info("  ✓ Ledger ready: %s  state=%s", LEDGER_PATH, {t: _ledger_get(t) for t in TICKERS})
    else:
        log.warning("  ✗ WARN — ledger file could not be created at: %s", LEDGER_PATH)

    _load_market_calendar()
    today = datetime.now(ET).date()
    log.info(
        "  Calendar status: today=%s trading_day=%s",
        today,
        _is_nyse_trading_day(today),
    )

    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if failures:
        log.error("DIAGNOSTICS COMPLETE — %d hard failure(s):", len(failures))
        for i, f in enumerate(failures, 1):
            log.error("  [%d] %s", i, f)
    else:
        log.info("DIAGNOSTICS COMPLETE — configuration OK ✓")
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

# ── Scheduler ─────────────────────────────────────────────────────────────────
def _seconds_until(hour: int, minute: int, tz=ET) -> float:
    """Return seconds from now until the next occurrence of hour:minute in tz."""
    now    = datetime.now(tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()

def run_scheduler():
    """
    Main event loop.

    Responsibilities:
      - Trigger SELL once per weekday at/after 09:31 ET.
      - Trigger BUY once per weekday at/after 15:59 ET.
      - Emit periodic heartbeat and optional position monitor logs.
      - Exit cleanly when shutdown event is set.
    """
        # The loop is long-running and only stops when _shutdown is signaled.
    log.info("Hold-Overnight scheduler started.")
    log.info(
        "Strategy: %s",
        ", ".join(f"{t} x{QTY_BY_TICKER.get(t, QTY)}" for t in TICKERS),
    )
    log.info("BUY  trigger: 1 minute before NYSE close (regular or early-close day)")
    log.info("SELL trigger: Mon–Fri %02d:%02d ET (1 min after open)",
             SELL_HOUR, SELL_MIN)

    last_reset_date:     date | None = None
    last_buy_date:       date | None = None
    last_sell_date:      date | None = None
    last_monitor_ts:     float       = 0.0
    last_heartbeat_ts:   float       = 0.0

    while not _shutdown.is_set():
        now      = datetime.now(ET)
        today    = now.date()
        weekday  = now.weekday()   # 0=Mon … 6=Sun
        # Convert to minutes-since-midnight for cheap repeated comparisons.
        hhmm     = now.hour * 60 + now.minute
        is_trade_day = _is_nyse_trading_day(today)

        buy_mins  = _buy_trigger_mins_for_day(today)
        sell_mins = SELL_HOUR * 60 + SELL_MIN

        # Reset flags at midnight
        if today != last_reset_date and now.hour == 0:
            _reset_daily()
            last_reset_date = today

        if is_trade_day:
            # SELL at 09:31
            if hhmm >= sell_mins and last_sell_date != today:
                last_sell_date = today
                t = threading.Thread(target=sell_positions, daemon=True)
                t.start()

            # BUY at 15:59
            if hhmm >= buy_mins and last_buy_date != today:
                last_buy_date = today
                t = threading.Thread(target=buy_positions, daemon=True)
                t.start()

            # Monitor positions during market hours
            if sell_mins <= hhmm < buy_mins:
                if time.time() - last_monitor_ts >= MONITOR_INTERVAL:
                    last_monitor_ts = time.time()
                    t = threading.Thread(target=monitor_positions, daemon=True)
                    t.start()

        # Heartbeat every 5 minutes
        if time.time() - last_heartbeat_ts >= 300:
            last_heartbeat_ts = time.time()
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            day_name  = day_names[weekday]

            if not is_trade_day:
                reason = "weekend" if weekday > 4 else "NYSE holiday"
                log.info(
                    "Heartbeat [%s %s ET] — %s, no trades today.",
                    day_name, now.strftime("%H:%M"),
                    reason,
                )
            else:
                sell_secs = _seconds_until(SELL_HOUR, SELL_MIN)
                buy_h, buy_m = divmod(buy_mins, 60)
                buy_secs  = _seconds_until(buy_h, buy_m)

                def _fmt(secs: float, fired: bool, label: str) -> str:
                    """Format countdown status for heartbeat logging."""
                    if fired:
                        return f"{label} DONE ✓"
                    h, rem = divmod(int(secs), 3600)
                    m, s   = divmod(rem, 60)
                    return f"{label} in {h:02d}h{m:02d}m{s:02d}s"

                with _state_lock:
                    sell_done = _sold_today
                    buy_done  = _bought_today

                log.info(
                    "Heartbeat [%s %s ET] — bought=%s  sold=%s  buy_at=%02d:%02d ET  |  %s  |  %s",
                    day_name, now.strftime("%H:%M"),
                    buy_done, sell_done, buy_h, buy_m,
                    _fmt(sell_secs, sell_done, "SELL"),
                    _fmt(buy_secs,  buy_done,  "BUY"),
                )

        _shutdown.wait(30)

    log.info("Hold-Overnight scheduler stopped.")

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    """Validate config, run optional test modes, then launch scheduler."""
    # Credential bootstrap order: local .env first, Supabase fallback second.
    global _TRADE_HEADERS, _DATA_HEADERS

    creds = auth.resolve_alpaca_credentials()
    credential_source = auth.credential_source or "local .env"

    if creds is None:
        log.error("Could not load credentials from Supabase or local .env fallback")
        sys.exit(1)

    trade_auth_id, trade_auth_secret, data_auth_id, data_auth_secret = creds
    _TRADE_HEADERS = {
        "accept": "application/json",
        "content-type": "application/json",
        "apca-api-key-id": trade_auth_id,
        "apca-api-secret-key": trade_auth_secret,
    }
    _DATA_HEADERS = {
        "accept": "application/json",
        "apca-api-key-id": data_auth_id,
        "apca-api-secret-key": data_auth_secret,
    }

    log.info("Starting hold_overnight.py …")
    log.info("Credential source: %s", credential_source)

    args = sys.argv[1:]

    if "--test-csv" in args:
        log.info("── TEST CSV ──")
        _csv_log_row(
            action="BUY", ticker="QQQ", qty=1,
            order_id="test-id-001", order_status="filled",
            fill_price=480.25, note="test-buy",
        )
        _csv_log_row(
            action="SELL", ticker="QQQ", qty=1,
            order_id="test-id-002", order_status="filled",
            fill_price=481.10, cost_basis=480.25,
            pnl=0.85, pnl_pct=0.0018, note="test-sell",
        )
        log.info("── TEST CSV DONE — check %s ──", CSV_LOG_PATH)
        return

    # Parse strategy symbols/quantities from local CLI parser.
    mt_args = parse_arguments()

    print("Parsed arguments:")
    print(f"  raw pairs: {mt_args.pairs}")
    print(f"  symbol/qty pairs: {mt_args.ticker_qty_pairs}")

    try:
        _configure_strategy_from_args(mt_args)
    except ValueError as exc:
        log.error("Argument configuration error: %s", exc)
        sys.exit(2)

    log.info("Parsed CLI symbol/qty pairs: %s", mt_args.ticker_qty_pairs)

    _ledger_load()

    if mt_args.test_mode:
        log.info("── TEST MODE (immediate buy, delayed sell) ──")
        buy_positions()
        log.info("Buy complete — waiting 60 seconds before sell …")
        time.sleep(60)
        sell_positions()
        _print_cumulative()
        log.info("── TEST MODE DONE — check %s ──", CSV_LOG_PATH)
        return

    startup_diagnostics()

    try:
        run_scheduler()
    except KeyboardInterrupt:
        log.info("Interrupted.")
    finally:
        _print_cumulative()
        log.info("Exiting.")

if __name__ == "__main__":
    main()
