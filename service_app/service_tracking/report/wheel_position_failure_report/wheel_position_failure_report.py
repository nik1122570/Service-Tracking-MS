# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from service_app.service_tracking.tyre_analytics import (
    get_tyre_history_rows,
    set_default_date_filters,
    validate_date_filters,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    validate_date_filters(filters)

    columns = get_columns()
    history_rows = [row for row in get_tyre_history_rows(filters) if row.get("next_request_date")]
    data = build_rows(history_rows)
    chart = get_chart_data(data)

    if not data:
        return columns, [], _("No wheel-position replacement records found for the selected filters."), None

    return columns, data, None, chart


def get_columns():
    return [
        {"label": _("Wheel Position"), "fieldname": "wheel_position", "fieldtype": "Link", "options": "Maintenance Postion", "width": 120},
        {"label": _("Vehicles Affected"), "fieldname": "vehicles_affected", "fieldtype": "Int", "width": 110},
        {"label": _("Replacement Count"), "fieldname": "replacement_count", "fieldtype": "Int", "width": 125},
        {"label": _("Total Qty Replaced"), "fieldname": "total_qty_replaced", "fieldtype": "Float", "width": 125},
        {"label": _("Average Days"), "fieldname": "average_days", "fieldtype": "Float", "width": 110},
        {"label": _("Average Distance"), "fieldname": "average_distance", "fieldtype": "Float", "width": 120},
    ]


def build_rows(history_rows):
    grouped = defaultdict(
        lambda: {
            "vehicles": set(),
            "replacement_count": 0,
            "total_qty_replaced": 0.0,
            "days": [],
            "distance": [],
        }
    )

    for row in history_rows:
        wheel_position = row.get("wheel_position") or _("Unspecified Position")
        bucket = grouped[wheel_position]
        if row.get("vehicle"):
            bucket["vehicles"].add(row.get("vehicle"))
        bucket["replacement_count"] += 1
        bucket["total_qty_replaced"] += flt(row.get("qty"))
        if row.get("days_in_service") is not None:
            bucket["days"].append(flt(row.get("days_in_service")))
        if row.get("distance_covered") is not None:
            bucket["distance"].append(flt(row.get("distance_covered")))

    data = []
    for wheel_position, bucket in sorted(grouped.items()):
        data.append(
            {
                "wheel_position": wheel_position,
                "vehicles_affected": len(bucket["vehicles"]),
                "replacement_count": bucket["replacement_count"],
                "total_qty_replaced": flt(bucket["total_qty_replaced"]),
                "average_days": (
                    sum(bucket["days"]) / len(bucket["days"])
                    if bucket["days"]
                    else 0
                ),
                "average_distance": (
                    sum(bucket["distance"]) / len(bucket["distance"])
                    if bucket["distance"]
                    else 0
                ),
            }
        )

    return data


def get_chart_data(data):
    labels = [row["wheel_position"] for row in data]
    if not labels:
        return None

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Replacement Count"),
                    "values": [row["replacement_count"] for row in data],
                }
            ],
        },
        "type": "bar",
    }
