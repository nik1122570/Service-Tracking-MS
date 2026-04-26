# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt

from service_app.service_tracking.tyre_analytics import (
    get_default_currency,
    get_tyre_history_rows,
    set_default_date_filters,
    validate_date_filters,
)


DEFAULT_DAYS_THRESHOLD = 90
DEFAULT_DISTANCE_THRESHOLD = 10000


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    validate_date_filters(filters)
    set_threshold_defaults(filters)

    columns = get_columns()
    history_rows = [row for row in get_tyre_history_rows(filters) if row.get("next_request_date")]
    data = build_rows(history_rows, filters)
    chart = get_chart_data(data)

    if not data:
        return columns, [], _("No early tyre replacements found for the selected filters."), None

    return columns, data, None, chart


def set_threshold_defaults(filters):
    filters.threshold_days = cint(filters.get("threshold_days") or DEFAULT_DAYS_THRESHOLD)
    filters.threshold_distance = flt(filters.get("threshold_distance") or DEFAULT_DISTANCE_THRESHOLD)


def get_columns():
    return [
        {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 130},
        {"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
        {"label": _("Wheel Position"), "fieldname": "wheel_position", "fieldtype": "Link", "options": "Tyre Position", "width": 120},
        {"label": _("Tyre Request"), "fieldname": "tyre_request", "fieldtype": "Link", "options": "Tyre Request", "width": 150},
        {"label": _("Installed On"), "fieldname": "request_date", "fieldtype": "Date", "width": 110},
        {"label": _("Removed On"), "fieldname": "next_request_date", "fieldtype": "Date", "width": 110},
        {"label": _("Tyre Brand"), "fieldname": "tyre_brand", "fieldtype": "Data", "width": 120},
        {"label": _("Replacement Brand"), "fieldname": "replacement_brand", "fieldtype": "Data", "width": 130},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
        {"label": _("Days In Service"), "fieldname": "days_in_service", "fieldtype": "Float", "width": 110},
        {"label": _("Distance Covered"), "fieldname": "distance_covered", "fieldtype": "Float", "width": 130},
        {"label": _("Threshold Days"), "fieldname": "threshold_days", "fieldtype": "Int", "width": 110},
        {"label": _("Threshold Distance"), "fieldname": "threshold_distance", "fieldtype": "Float", "width": 130},
        {"label": _("Days Shortfall"), "fieldname": "days_shortfall", "fieldtype": "Float", "width": 110},
        {"label": _("Distance Shortfall"), "fieldname": "distance_shortfall", "fieldtype": "Float", "width": 130},
        {"label": _("Early Replacement Reason"), "fieldname": "early_replacement_reason", "fieldtype": "Data", "width": 180},
        {"label": _("Purchase Amount"), "fieldname": "amount", "fieldtype": "Currency", "options": "currency", "width": 130},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
    ]


def build_rows(history_rows, filters):
    currency = get_default_currency()
    data = []

    for row in history_rows:
        days_in_service = row.get("days_in_service")
        distance_covered = row.get("distance_covered")
        day_breach = days_in_service is not None and flt(days_in_service) < flt(filters.threshold_days)
        distance_breach = (
            distance_covered is not None
            and flt(distance_covered) < flt(filters.threshold_distance)
        )
        if not day_breach and not distance_breach:
            continue

        reasons = []
        if day_breach:
            reasons.append("Days")
        if distance_breach:
            reasons.append("Distance")

        data.append(
            {
                **row,
                "threshold_days": cint(filters.threshold_days),
                "threshold_distance": flt(filters.threshold_distance),
                "days_shortfall": max(flt(filters.threshold_days) - flt(row.get("days_in_service") or 0), 0)
                if day_breach
                else 0,
                "distance_shortfall": max(
                    flt(filters.threshold_distance) - flt(row.get("distance_covered") or 0), 0
                )
                if distance_breach
                else 0,
                "early_replacement_reason": ", ".join(reasons),
                "currency": currency,
            }
        )

    return sorted(
        data,
        key=lambda row: (
            row.get("vehicle") or "",
            row.get("request_date"),
            row.get("wheel_position") or "",
        ),
        reverse=True,
    )


def get_chart_data(data):
    counts = defaultdict(int)
    for row in data:
        vehicle_label = row.get("license_plate") or row.get("vehicle") or _("Unspecified Vehicle")
        counts[vehicle_label] += 1

    labels = list(counts.keys())
    if not labels:
        return None

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": _("Early Replacements"), "values": [counts[label] for label in labels]}],
        },
        "type": "bar",
    }
