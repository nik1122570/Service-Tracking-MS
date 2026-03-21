# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from service_app.service_tracking.tyre_analytics import (
    get_default_currency,
    get_tyre_history_rows,
    set_default_date_filters,
    validate_date_filters,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    validate_date_filters(filters)

    columns = get_columns()
    history_rows = get_tyre_history_rows(filters)
    data = build_rows(history_rows)
    chart = get_chart_data(data)

    if not data:
        return columns, [], _("No supplier tyre performance records found for the selected filters."), None

    return columns, data, None, chart


def get_columns():
    return [
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
        {"label": _("Tyres Fitted"), "fieldname": "tyres_fitted", "fieldtype": "Float", "width": 100},
        {"label": _("Total Spend"), "fieldname": "total_spend", "fieldtype": "Currency", "options": "currency", "width": 130},
        {"label": _("Average Rate"), "fieldname": "average_rate", "fieldtype": "Currency", "options": "currency", "width": 115},
        {"label": _("Replaced Tyres"), "fieldname": "replaced_tyres", "fieldtype": "Int", "width": 105},
        {"label": _("Average Days"), "fieldname": "average_days", "fieldtype": "Float", "width": 110},
        {"label": _("Average Distance"), "fieldname": "average_distance", "fieldtype": "Float", "width": 120},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
    ]


def build_rows(history_rows):
    currency = get_default_currency()
    grouped = defaultdict(
        lambda: {
            "tyres_fitted": 0.0,
            "total_spend": 0.0,
            "replaced_tyres": 0,
            "days": [],
            "distance": [],
        }
    )

    for row in history_rows:
        supplier = row.get("supplier") or _("Unspecified Supplier")
        bucket = grouped[supplier]
        bucket["tyres_fitted"] += flt(row.get("qty"))
        bucket["total_spend"] += flt(row.get("amount"))
        if row.get("next_request_date"):
            bucket["replaced_tyres"] += 1
            if row.get("days_in_service") is not None:
                bucket["days"].append(flt(row.get("days_in_service")))
            if row.get("distance_covered") is not None:
                bucket["distance"].append(flt(row.get("distance_covered")))

    data = []
    for supplier, bucket in sorted(grouped.items()):
        tyres_fitted = flt(bucket["tyres_fitted"])
        total_spend = flt(bucket["total_spend"])

        data.append(
            {
                "supplier": supplier,
                "tyres_fitted": tyres_fitted,
                "total_spend": total_spend,
                "average_rate": (total_spend / tyres_fitted) if tyres_fitted else 0,
                "replaced_tyres": bucket["replaced_tyres"],
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
                "currency": currency,
            }
        )

    return data


def get_chart_data(data):
    labels = [row["supplier"] for row in data]
    if not labels:
        return None

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Total Spend"),
                    "values": [flt(row["total_spend"]) for row in data],
                }
            ],
        },
        "type": "bar",
        "fieldtype": "Currency",
    }
