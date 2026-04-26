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
    data = [row for row in get_tyre_history_rows(filters) if row.get("next_request_date")]
    chart = get_chart_data(data)

    if not data:
        return columns, [], _("No tyre lifespan records found for the selected filters."), None

    return columns, data, None, chart


def get_columns():
    return [
        {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 130},
        {"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
        {"label": _("Wheel Position"), "fieldname": "wheel_position", "fieldtype": "Link", "options": "Tyre Position", "width": 120},
        {"label": _("Tyre Request"), "fieldname": "tyre_request", "fieldtype": "Link", "options": "Tyre Request", "width": 150},
        {"label": _("Installed On"), "fieldname": "request_date", "fieldtype": "Date", "width": 110},
        {"label": _("Tyre Brand"), "fieldname": "tyre_brand", "fieldtype": "Data", "width": 120},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
        {"label": _("Start Odometer"), "fieldname": "start_odometer", "fieldtype": "Float", "width": 120},
        {"label": _("Removed On"), "fieldname": "next_request_date", "fieldtype": "Date", "width": 110},
        {"label": _("End Odometer"), "fieldname": "end_odometer", "fieldtype": "Float", "width": 120},
        {"label": _("Distance Covered"), "fieldname": "distance_covered", "fieldtype": "Float", "width": 130},
        {"label": _("Days In Service"), "fieldname": "days_in_service", "fieldtype": "Int", "width": 110},
        {"label": _("Replacement Brand"), "fieldname": "replacement_brand", "fieldtype": "Data", "width": 130},
    ]


def get_chart_data(data):
    grouped = defaultdict(lambda: {"days": [], "distance": []})
    for row in data:
        brand = row.get("tyre_brand") or _("Unspecified Brand")
        if row.get("days_in_service") is not None:
            grouped[brand]["days"].append(flt(row.get("days_in_service")))
        if row.get("distance_covered") is not None:
            grouped[brand]["distance"].append(flt(row.get("distance_covered")))

    labels = list(grouped.keys())
    if not labels:
        return None

    avg_days = [
        (sum(grouped[label]["days"]) / len(grouped[label]["days"])) if grouped[label]["days"] else 0
        for label in labels
    ]
    avg_distance = [
        (sum(grouped[label]["distance"]) / len(grouped[label]["distance"])) if grouped[label]["distance"] else 0
        for label in labels
    ]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Average Days"), "values": avg_days},
                {"name": _("Average Distance"), "values": avg_distance},
            ],
        },
        "type": "bar",
    }
