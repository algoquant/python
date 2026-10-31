"""Simulated broker, clock and CSV bar feed for single-day strategy replay.

Fill model (applied against bars after the one that produced the order):
- market orders fill at the next bar close,
- buy limit orders fill at the limit price when a later bar low reaches it,
- sell limit orders fill at the limit price when a later bar high reaches it.

Unfilled orders remain open across bars until the shared strategy-delta logic
cancels them or end-of-day liquidation clears them. Session hours come from the
bar timestamp, so orders are market during RTH and limit outside it.

A symbol that did not trade in a minute has its previous close carried forward as
a flat bar, so the driver always sees a complete set of symbols per minute.
"""

from __future__ import annotations

import csv
from datetime import datetime, time as dt_time, timezone
from pathlib import Path
from typing import Any, Iterable

from MachineTrader.helpers.alpacasdk import AlpacAPI
from MachineTrader.helpers.driver_common import NY_TZ
from MachineTrader.helpers.live_data import complete_symbol_bar_set, minute_key_from_datetime

__all__ = [
    "SimOrder",
    "SimPosition",
    "SimClock",
    "SimBroker",
    "SimAlpacaAPI",
    "load_minute_bars",
    "bar_row_to_event",
]

MARKET_OPEN = dt_time(9, 30)
MARKET_CLOSE = dt_time(16, 0)


def _side_text(side: Any) -> str:
    raw = str(getattr(side, "value", side) or "").strip().lower()
    if "buy" in raw:
        return "buy"
    if "sell" in raw:
        return "sell"
    return raw


class SimPosition:
    """Duck-typed stand-in for an Alpaca position object."""

    def __init__(self, symbol: str, qty: float, avg_entry_price: float):
        self.symbol = symbol
        self.qty = str(qty)
        self.qty_available = str(abs(qty))
        self.avg_entry_price = str(avg_entry_price)
        self.side = "long" if qty >= 0 else "short"


class SimOrder:
    """Duck-typed stand-in for an Alpaca order object."""

    def __init__(
        self,
        *,
        order_id: str,
        symbol: str,
        qty: float,
        side: str,
        order_type: str,
        limit_price: float | None,
        submitted_at: datetime,
    ):
        self.id = order_id
        self.client_order_id = order_id
        self.symbol = symbol
        self.qty = float(qty)
        self.side = side
        self.type = order_type
        self.order_type = order_type
        self.limit_price = limit_price
        self.status = "new"
        self.filled_qty = 0.0
        self.filled_avg_price = None
        self.submitted_at = submitted_at
        self.created_at = submitted_at
        self.updated_at = submitted_at
        self.filled_at = None

    def payload(self, event: str) -> dict[str, Any]:
        return {
            "id": self.id,
            "client_order_id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "type": self.type,
            "order_type": self.type,
            "qty": self.qty,
            "limit_price": self.limit_price,
            "status": self.status,
            "event": event,
            "filled_qty": self.filled_qty,
            "filled_avg_price": self.filled_avg_price,
            "submitted_at": self.submitted_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
        }


class SimClock:
    """Wall clock driven by bar timestamps rather than real time."""

    def __init__(self, now_ny: datetime | None = None):
        self.now_ny = now_ny

    def advance_to(self, bar_time_ny: datetime):
        self.now_ny = bar_time_ny

    @property
    def is_open(self) -> bool:
        now = self.now_ny
        if now is None or now.weekday() >= 5:
            return False
        return MARKET_OPEN <= now.time() < MARKET_CLOSE

    # Alpaca get_clock() response shape.
    @property
    def timestamp(self):
        return self.now_ny


class SimBroker:
    """In-memory broker: accepts orders, fills them against subsequent bars."""

    def __init__(self, clock: SimClock):
        self.clock = clock
        self.orders: dict[str, SimOrder] = {}
        self.open_order_ids: list[str] = []
        self.positions: dict[str, float] = {}
        self.cost_basis: dict[str, float] = {}
        self.realized_pnl: float = 0.0
        self.fills: list[dict[str, Any]] = []
        self._sequence = 0

    # --- submission -------------------------------------------------
    def submit(self, symbol: str, qty: float, side: Any, order_type: str, limit_price: float | None) -> SimOrder:
        self._sequence += 1
        order = SimOrder(
            order_id=f"sim-{self._sequence:06d}",
            symbol=str(symbol or "").strip().upper(),
            qty=abs(float(qty or 0.0)),
            side=_side_text(side),
            order_type=str(order_type or "market").strip().lower(),
            limit_price=None if limit_price is None else float(limit_price),
            submitted_at=self.clock.now_ny,
        )
        self.orders[order.id] = order
        self.open_order_ids.append(order.id)
        return order

    # --- fill engine ------------------------------------------------
    def resolve_against_bar(self, bar: dict[str, Any]) -> list[SimOrder]:
        """Fill eligible open orders for this symbol using the current bar."""
        symbol = str(bar.get("S", "")).strip().upper()
        bar_time = bar["_ny_time"]
        high = float(bar["h"])
        low = float(bar["l"])
        close = float(bar["c"])

        filled: list[SimOrder] = []
        for order_id in list(self.open_order_ids):
            order = self.orders[order_id]
            if order.symbol != symbol or order.submitted_at >= bar_time:
                continue

            if order.type == "market":
                fill_price = close
            elif order.limit_price is None:
                continue
            elif order.side == "buy" and low <= order.limit_price:
                fill_price = order.limit_price
            elif order.side == "sell" and high >= order.limit_price:
                fill_price = order.limit_price
            else:
                continue

            self._apply_fill(order, fill_price, bar_time)
            filled.append(order)
        return filled

    def cancel_unfilled(self, bar_time: datetime) -> list[SimOrder]:
        """Cancel all remaining orders, for example before end-of-day flattening."""
        canceled: list[SimOrder] = []
        for order_id in list(self.open_order_ids):
            order = self.orders[order_id]
            order.status = "canceled"
            order.updated_at = bar_time
            self.open_order_ids.remove(order_id)
            canceled.append(order)
        return canceled

    def _apply_fill(self, order: SimOrder, fill_price: float, bar_time: datetime):
        order.status = "filled"
        order.filled_qty = order.qty
        order.filled_avg_price = float(fill_price)
        order.filled_at = bar_time
        order.updated_at = bar_time
        self.open_order_ids.remove(order.id)

        signed = order.qty if order.side == "buy" else -order.qty
        prior = self.positions.get(order.symbol, 0.0)
        prior_basis = self.cost_basis.get(order.symbol, 0.0)
        new_qty = prior + signed

        if prior == 0.0 or (prior > 0) == (signed > 0):
            total_cost = prior_basis * abs(prior) + fill_price * abs(signed)
            self.cost_basis[order.symbol] = total_cost / abs(new_qty) if new_qty else 0.0
        else:
            closed = min(abs(prior), abs(signed))
            direction = 1.0 if prior > 0 else -1.0
            self.realized_pnl += direction * closed * (fill_price - prior_basis)
            if (prior > 0) != (new_qty > 0) and new_qty != 0.0:
                self.cost_basis[order.symbol] = fill_price
            elif new_qty == 0.0:
                self.cost_basis[order.symbol] = 0.0

        self.positions[order.symbol] = new_qty
        self.fills.append(
            {
                "time": bar_time.strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": order.symbol,
                "side": order.side,
                "qty": order.qty,
                "price": float(fill_price),
                "order_type": order.type,
                "limit_price": order.limit_price,
                "position_after": new_qty,
                "realized_pnl_cum": round(self.realized_pnl, 2),
                "order_id": order.id,
            }
        )

    def mark_to_market(self, last_prices: dict[str, float]) -> float:
        total = 0.0
        for symbol, qty in self.positions.items():
            if not qty:
                continue
            price = float(last_prices.get(symbol, 0.0) or 0.0)
            if price:
                total += qty * (price - self.cost_basis.get(symbol, 0.0))
        return total

    # --- TradingClient surface --------------------------------------
    def get_clock(self):
        return self.clock

    def get_order_by_id(self, order_id: str, **_kwargs):
        return self.orders.get(str(order_id).strip())

    def cancel_order_by_id(self, order_id: str, **_kwargs):
        key = str(order_id).strip()
        if key in self.open_order_ids:
            self.open_order_ids.remove(key)
            self.orders[key].status = "canceled"
        return None

    def get_orders(self, *_args, **_kwargs):
        return [self.orders[oid] for oid in self.open_order_ids]

    def get_open_position(self, symbol: str):
        symbol_key = str(symbol or "").strip().upper()
        qty = self.positions.get(symbol_key, 0.0)
        if not qty:
            return None
        return SimPosition(symbol_key, qty, self.cost_basis.get(symbol_key, 0.0))

    def get_all_positions(self):
        return [
            SimPosition(symbol, qty, self.cost_basis.get(symbol, 0.0))
            for symbol, qty in self.positions.items()
            if qty
        ]


class SimAlpacaAPI(AlpacAPI):
    """AlpacAPI with the order path redirected to a SimBroker.

    Indicator state (process_bar, EMA, volatility) still uses the real code.
    """

    def __init__(self, broker: SimBroker):
        super().__init__()
        self.sim_broker = broker
        self.trading_client = broker
        self.last_submit_rejection = None
        self.last_submit_attempt = None

    def create_trade_clients(self, env_file=None, **_kwargs):
        self.trading_client = self.sim_broker
        return self.sim_broker, None

    def submit_order(self, symbol, shares_per_trade, side, type, limit_price):
        self.last_submit_rejection = None
        qty = abs(float(shares_per_trade or 0.0))
        self.last_submit_attempt = {
            "symbol": str(symbol or "").strip().upper(),
            "side": _side_text(side),
            "order_type": str(type or "").strip().lower(),
            "limit_price": limit_price,
            "requested_qty": qty,
            "shares_available": qty,
            "shares_to_trade": qty,
            "shares_owned": self.sim_broker.positions.get(str(symbol or "").upper(), 0.0),
            "market_is_open": self.sim_broker.clock.is_open,
            "reason": "",
        }
        if qty <= 0.0:
            self.last_submit_attempt["reason"] = "no shares available"
            return None
        return self.sim_broker.submit(symbol, qty, side, type, limit_price)

    def _is_market_open_now(self):
        return self.sim_broker.clock.is_open


def bar_row_to_event(row: dict[str, str]) -> dict[str, Any]:
    """Convert a minute CSV row into an Alpaca-shaped bar event."""
    naive = datetime.strptime(str(row["timestamp"]).strip(), "%Y-%m-%d %H:%M:%S")
    ny_time = naive.replace(tzinfo=NY_TZ)
    return {
        "T": "b",
        "S": str(row["symbol"]).strip().upper(),
        "o": float(row["open"]),
        "h": float(row["high"]),
        "l": float(row["low"]),
        "c": float(row["close"]),
        "v": float(row.get("volume") or 0.0),
        "n": int(float(row.get("trade_count") or 0)),
        "vw": float(row.get("vwap") or row["close"]),
        "t": ny_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_ny_time": ny_time,
    }


def load_minute_bars(
    bars_dir: str | Path,
    date_text: str,
    symbols: Iterable[str],
    start_time_text: str | None = None,
) -> list[tuple[datetime, list[dict[str, Any]]]]:
    """Load one day of CSV or chained parquet minute bars grouped by minute.

    ``date_text`` is YYYY-MM-DD; files are named either
    ``<SYMBOL>_<YYYYMMDD>.csv`` or ``<SYMBOL>.parquet``.
    A symbol that did not trade in a minute has its previous bar carried forward,
    so every emitted minute holds a complete set once each symbol has reported once.
    """
    directory = Path(bars_dir).expanduser()
    suffix = date_text.replace("-", "")
    wanted = {str(s).strip().upper() for s in symbols}
    start_time = dt_time.fromisoformat(str(start_time_text).strip()) if start_time_text else None

    by_minute: dict[datetime, list[dict[str, Any]]] = {}
    missing: list[str] = []
    for symbol in sorted(wanted):
        csv_path = directory / f"{symbol}_{suffix}.csv"
        parquet_path = directory / f"{symbol}.parquet"
        path = csv_path if csv_path.exists() else parquet_path
        if not path.exists():
            missing.append(symbol)
            continue
        if path.suffix == ".parquet":
            try:
                import pandas as pd
                frame = pd.read_parquet(path)
            except ImportError as exc:
                raise RuntimeError("Reading chained parquet bars requires pandas and a parquet engine.") from exc
            rows = frame.to_dict("records")
        else:
            with path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
        for raw_row in rows:
            row = {
                "symbol": symbol,
                "timestamp": raw_row.get("timestamp"),
                "open": raw_row.get("open", raw_row.get("Open")),
                "high": raw_row.get("high", raw_row.get("High")),
                "low": raw_row.get("low", raw_row.get("Low")),
                "close": raw_row.get("close", raw_row.get("Close")),
                "volume": raw_row.get("volume", raw_row.get("Volume")),
                "trade_count": raw_row.get("trade_count", raw_row.get("Trades")),
                "vwap": raw_row.get("vwap", raw_row.get("VWAP")),
            }
            try:
                row_time = datetime.strptime(str(row["timestamp"]).strip(), "%Y-%m-%d %H:%M:%S")
                if row_time.date().isoformat() != date_text:
                    continue
                if start_time is not None and row_time.time() < start_time:
                    continue
                event = bar_row_to_event(row)
            except Exception:
                continue
            by_minute.setdefault(event["_ny_time"], []).append(event)

    if missing:
        raise FileNotFoundError(
            f"No {date_text} bar files for: {', '.join(missing)} in {directory}"
        )

    last_by_symbol: dict[str, dict[str, Any]] = {}
    minutes: list[tuple[datetime, list[dict[str, Any]]]] = []
    for minute in sorted(by_minute):
        bars_by_symbol = {bar["S"]: bar for bar in by_minute[minute]}
        for symbol, bar in bars_by_symbol.items():
            last_by_symbol[symbol] = bar
        completed = complete_symbol_bar_set(
            bars_by_symbol,
            last_by_symbol,
            sorted(wanted),
            minute_key_from_datetime(minute, timezone=NY_TZ),
            timezone=NY_TZ,
        )
        if completed:
            for bar in completed:
                last_by_symbol[bar["S"]] = bar
            minutes.append((minute, completed))

    return minutes


def minute_bar_time_bounds(bars_by_minute: list[tuple[datetime, list[dict[str, Any]]]]) -> tuple[datetime, datetime]:
    """Return the first and last timestamps in a loaded replay."""
    if not bars_by_minute:
        raise ValueError("Cannot derive time bounds from empty bar data")
    timestamps = [minute_time for minute_time, _ in bars_by_minute]
    return min(timestamps), max(timestamps)


def available_bar_date_bounds(bars_dir: str | Path) -> tuple[str, str]:
    """Return earliest and latest dates available in CSV or parquet bars."""
    directory = Path(bars_dir).expanduser()
    csv_dates = [
        path.stem.rsplit("_", 1)[-1]
        for path in directory.glob("*_*.csv")
        if path.stem.rsplit("_", 1)[-1].isdigit()
    ]
    if csv_dates:
        parsed_dates = sorted(datetime.strptime(value, "%Y%m%d").date() for value in csv_dates)
        return parsed_dates[0].isoformat(), parsed_dates[-1].isoformat()

    parquet_paths = sorted(directory.glob("*.parquet"))
    if parquet_paths:
        try:
            import pandas as pd
            earliest = None
            latest = None
            for parquet_path in parquet_paths:
                frame = pd.read_parquet(parquet_path, columns=["timestamp"])
                timestamps = pd.to_datetime(frame["timestamp"], errors="coerce").dropna()
                if timestamps.empty:
                    continue
                candidate_min = timestamps.min().date()
                candidate_max = timestamps.max().date()
                earliest = candidate_min if earliest is None else min(earliest, candidate_min)
                latest = candidate_max if latest is None else max(latest, candidate_max)
            if earliest is not None and latest is not None:
                return earliest.isoformat(), latest.isoformat()
        except ImportError as exc:
            raise RuntimeError("Inferring dates from chained parquet bars requires pandas and a parquet engine.") from exc

    raise ValueError(f"No dated CSV or timestamped parquet bars found in {bars_dir}")


def load_minute_bars_range(
    bars_dir: str | Path,
    start_date_text: str,
    end_date_text: str,
    symbols: Iterable[str],
    start_time_text: str | None = None,
) -> list[tuple[datetime, list[dict[str, Any]]]]:
    """Load a replay range, reading each chained parquet symbol once."""
    directory = Path(bars_dir).expanduser()
    wanted = {str(symbol).strip().upper() for symbol in symbols}
    parquet_paths = {symbol: directory / f"{symbol}.parquet" for symbol in wanted}
    if not all(path.exists() for path in parquet_paths.values()):
        result: list[tuple[datetime, list[dict[str, Any]]]] = []
        start_date = datetime.strptime(start_date_text, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_text, "%Y-%m-%d").date()
        current = start_date
        while current <= end_date:
            suffix = current.strftime("%Y%m%d")
            if all((directory / f"{symbol}_{suffix}.csv").exists() for symbol in wanted):
                result.extend(load_minute_bars(directory, current.isoformat(), wanted, start_time_text=start_time_text))
            current = current.fromordinal(current.toordinal() + 1)
        return result

    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Reading chained parquet bars requires pandas and a parquet engine.") from exc

    start_date = datetime.strptime(start_date_text, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_text, "%Y-%m-%d").date()
    start_time = dt_time.fromisoformat(str(start_time_text).strip()) if start_time_text else None
    by_minute: dict[datetime, list[dict[str, Any]]] = {}
    for symbol, path in sorted(parquet_paths.items()):
        frame = pd.read_parquet(path)
        timestamp = pd.to_datetime(frame["timestamp"], errors="coerce")
        valid = timestamp.notna()
        valid &= timestamp.dt.date >= start_date
        valid &= timestamp.dt.date <= end_date
        if start_time is not None:
            valid &= timestamp.dt.time >= start_time
        frame = frame.loc[valid]
        timestamp = timestamp.loc[valid]
        for raw_row, row_time in zip(frame.to_dict("records"), timestamp):
            row = {
                "symbol": symbol,
                "timestamp": row_time.strftime("%Y-%m-%d %H:%M:%S"),
                "open": raw_row.get("open", raw_row.get("Open")),
                "high": raw_row.get("high", raw_row.get("High")),
                "low": raw_row.get("low", raw_row.get("Low")),
                "close": raw_row.get("close", raw_row.get("Close")),
                "volume": raw_row.get("volume", raw_row.get("Volume")),
                "trade_count": raw_row.get("trade_count", raw_row.get("Trades")),
                "vwap": raw_row.get("vwap", raw_row.get("VWAP")),
            }
            try:
                event = bar_row_to_event(row)
            except Exception:
                continue
            by_minute.setdefault(event["_ny_time"], []).append(event)

    result: list[tuple[datetime, list[dict[str, Any]]]] = []
    current_date = start_date
    while current_date <= end_date:
        day_minutes = sorted(minute for minute in by_minute if minute.date() == current_date)
        last_by_symbol: dict[str, dict[str, Any]] = {}
        for minute in day_minutes:
            bars_by_symbol = {bar["S"]: bar for bar in by_minute[minute]}
            for symbol, bar in bars_by_symbol.items():
                last_by_symbol[symbol] = bar
            completed = complete_symbol_bar_set(
                bars_by_symbol,
                last_by_symbol,
                sorted(wanted),
                minute_key_from_datetime(minute, timezone=NY_TZ),
                timezone=NY_TZ,
            )
            if completed:
                for bar in completed:
                    last_by_symbol[bar["S"]] = bar
                result.append((minute, completed))
        current_date = current_date.fromordinal(current_date.toordinal() + 1)
    return result
