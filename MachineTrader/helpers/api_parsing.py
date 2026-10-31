from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .timestamp_utils import coerce_datetime


def normalize_order_status(raw_status: Any) -> str:
    text = str(raw_status or "").strip().lower()
    if not text:
        return ""
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text


def enum_text(value: Any) -> str:
    if value is None:
        return ""
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value).strip().lower()
    text = str(value).strip().lower()
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def parse_broker_event_time(raw_value: Any, *, timezone: ZoneInfo) -> datetime | None:
    return coerce_datetime(
        raw_value,
        target_tz=timezone,
        naive_tz=timezone,
        fallback_to_now=False,
    )


def order_to_broker_payload(order: Any) -> dict[str, Any]:
    if order is None:
        return {}
    if isinstance(order, dict):
        return dict(order)

    for method_name in ("model_dump", "dict"):
        method = getattr(order, method_name, None)
        if callable(method):
            try:
                payload = method()
            except TypeError:
                try:
                    payload = method(mode="python")
                except Exception:
                    payload = None
            except Exception:
                payload = None
            if isinstance(payload, dict):
                return payload

    payload: dict[str, Any] = {}
    for name in dir(order):
        if name.startswith("_"):
            continue
        try:
            value = getattr(order, name)
        except Exception:
            continue
        if callable(value):
            continue
        payload[name] = value
    return payload


__all__ = [
    "normalize_order_status",
    "enum_text",
    "safe_float",
    "parse_broker_event_time",
    "order_to_broker_payload",
]
