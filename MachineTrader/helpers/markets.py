"""Market calendar/date helpers for trading strategies."""

from datetime import date, time as dtime
from zoneinfo import ZoneInfo

import exchange_calendars as ecals
import pandas as pd


class Markets:
    """Shared market/calendar utilities.

    This class centralizes exchange schedule lookups so strategies and SDK
    helpers can reuse one implementation.
    """

    NY_TZ = ZoneInfo("America/New_York")

    def __init__(self, calendar_name: str = "XNYS", timezone: str = "America/New_York"):
        self.calendar_name = calendar_name
        self.tzone = ZoneInfo(timezone)
        self.calendar = ecals.get_calendar(calendar_name)

    def get_open_time(self, day: date) -> dtime:
        """Return scheduled market open in local timezone for a session date."""
        day_str = day.isoformat()
        try:
            session = self.calendar.schedule.loc[day_str]
            open_utc = session["market_open"].to_pydatetime()
            return open_utc.astimezone(self.tzone).time()
        except KeyError:
            return dtime(9, 30)

    def get_close_time(self, day: date) -> dtime:
        """Return scheduled market close in local timezone for a session date."""
        day_str = day.isoformat()
        try:
            session = self.calendar.schedule.loc[day_str]
            close_utc = session["market_close"].to_pydatetime()
            return close_utc.astimezone(self.tzone).time()
        except KeyError:
            return dtime(16, 0)

    def is_trading_day(self, day: date) -> bool:
        """Return True when the exchange has a trading session on the given day."""
        try:
            return bool(self.calendar.is_session(day.isoformat()))
        except Exception:
            return False


def market_sessions_ny(
    chart_frame: pd.DataFrame,
    time_col: str = "time",
    timezone: str = "America/New_York",
    calendar_name: str = "XNYS",
) -> list[dict[str, int | str]]:
    """Return exchange session open/close epochs for dates represented in bars."""
    unique_dates = sorted(pd.Index(chart_frame[time_col].dropna().dt.date.unique()))
    if not unique_dates:
        return []

    observed_open = chart_frame.groupby(chart_frame[time_col].dt.date)[time_col].min().to_dict()
    observed_close = chart_frame.groupby(chart_frame[time_col].dt.date)[time_col].max().to_dict()
    calendar = ecals.get_calendar(calendar_name)
    schedule = calendar.schedule.loc[str(unique_dates[0]):str(unique_dates[-1])]
    open_column = "market_open" if "market_open" in schedule.columns else "open"
    close_column = "market_close" if "market_close" in schedule.columns else "close"
    sessions: list[dict[str, int | str]] = []

    for session_day in unique_dates:
        key = pd.Timestamp(session_day)
        if key in schedule.index:
            open_local = schedule.loc[key, open_column].to_pydatetime().astimezone(ZoneInfo(timezone))
            close_local = schedule.loc[key, close_column].to_pydatetime().astimezone(ZoneInfo(timezone))
            open_epoch = int(open_local.timestamp())
            close_epoch = int(close_local.timestamp())
        elif session_day in observed_open and session_day in observed_close:
            open_epoch = int(observed_open[session_day].timestamp())
            close_epoch = int(observed_close[session_day].timestamp())
        else:
            continue
        sessions.append({"day": key.strftime("%Y-%m-%d"), "open": open_epoch, "close": close_epoch})

    return sessions


def add_nearest_session_label_epochs(
    chart_frame: pd.DataFrame,
    sessions: list[dict[str, int | str]],
    time_col: str = "time",
) -> list[dict[str, int | str]]:
    """Add nearest observed bar epochs for rendering session boundary labels."""
    day_groups = {
        day.strftime("%Y-%m-%d"): group
        for day, group in chart_frame.groupby(chart_frame[time_col].dt.date)
    }
    labeled_sessions: list[dict[str, int | str]] = []
    for session in sessions:
        day_frame = day_groups.get(str(session["day"]))
        if day_frame is None or day_frame.empty:
            continue
        epochs = (day_frame[time_col].astype("int64") // 10**9).astype(int)
        open_epoch = int(session["open"])
        close_epoch = int(session["close"])
        labeled_sessions.append(
            {
                "day": str(session["day"]),
                "open": open_epoch,
                "close": close_epoch,
                "open_label_epoch": int(epochs.iloc[(epochs - open_epoch).abs().argmin()]),
                "close_label_epoch": int(epochs.iloc[(epochs - close_epoch).abs().argmin()]),
            }
        )
    return labeled_sessions
