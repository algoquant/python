from __future__ import annotations

from typing import Any

from MachineTrader.helpers.api_parsing import normalize_order_status


API_RESPONSE_DICTIONARY: dict[str, Any] = {
    "order_status_groups": {
        "pending": frozenset(
            {
                "new",
                "accepted",
                "pending_new",
                "pending_replace",
                "accepted_for_bidding",
                "calculated",
                "partially_filled",
                "partiallyfilled",
                "partial_fill",
                "partialfill",
            }
        ),
        "filled": frozenset({"filled"}),
        "fill_progress": frozenset(
            {
                "filled",
                "partially_filled",
                "partiallyfilled",
                "partial_fill",
                "partialfill",
            }
        ),
        "terminal": frozenset(
            {
                "filled",
                "canceled",
                "cancelled",
                "rejected",
                "expired",
                "done_for_day",
                "stopped",
                "suspended",
            }
        ),
        "terminal_excluding_filled": frozenset(
            {
                "canceled",
                "cancelled",
                "rejected",
                "expired",
                "done_for_day",
                "stopped",
                "suspended",
            }
        ),
    },
    "blotter_event_type_by_status": {
        "filled": "fill",
        "partially_filled": "partial fill",
        "partial_fill": "partial fill",
        "rejected": "reject",
        "canceled": "cancel",
        "cancelled": "cancel",
    },
    "broker_event_groups": {
        "fill": frozenset({"fill", "filled"}),
        "partial_fill": frozenset({"partial_fill", "partially_filled", "partialfill", "partiallyfilled"}),
        "fill_progress": frozenset({"fill", "filled", "partial_fill", "partially_filled", "partialfill", "partiallyfilled"}),
        "pending_submit": frozenset({"pending_new", "new", "accepted"}),
        "cancel_terminal": frozenset({"canceled", "expired", "rejected", "replaced"}),
        "cancel_persist": frozenset({"canceled", "expired", "rejected"}),
    },
}


ORDER_STATUS_GROUPS = API_RESPONSE_DICTIONARY["order_status_groups"]
BLOTTER_EVENT_TYPE_BY_STATUS = API_RESPONSE_DICTIONARY["blotter_event_type_by_status"]
BROKER_EVENT_GROUPS = API_RESPONSE_DICTIONARY["broker_event_groups"]


def normalize_broker_event_name(raw_event_name: Any) -> str:
    text = str(raw_event_name or "").strip().lower()
    if "." in text:
        text = text.split(".")[-1]
    return text.replace("-", "_").replace(" ", "_")


def status_in_group(raw_status: Any, group: str) -> bool:
    normalized = normalize_order_status(raw_status)
    return normalized in ORDER_STATUS_GROUPS.get(group, frozenset())


def is_terminal_order_status(raw_status: Any) -> bool:
    return status_in_group(raw_status, "terminal")


def blotter_event_type_from_status(raw_status: Any) -> str:
    normalized = normalize_order_status(raw_status)
    return BLOTTER_EVENT_TYPE_BY_STATUS.get(normalized, normalized or "confirm")


def event_in_group(raw_event_name: Any, group: str) -> bool:
    normalized = normalize_broker_event_name(raw_event_name)
    return normalized in BROKER_EVENT_GROUPS.get(group, frozenset())


__all__ = [
    "API_RESPONSE_DICTIONARY",
    "ORDER_STATUS_GROUPS",
    "BLOTTER_EVENT_TYPE_BY_STATUS",
    "BROKER_EVENT_GROUPS",
    "normalize_broker_event_name",
    "status_in_group",
    "is_terminal_order_status",
    "blotter_event_type_from_status",
    "event_in_group",
]
