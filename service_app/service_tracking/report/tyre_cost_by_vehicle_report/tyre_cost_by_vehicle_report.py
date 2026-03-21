# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate

from service_app.service_tracking.tyre_analytics import (
    get_default_currency,
    get_tyre_purchase_rows,
    get_vehicle_details,
    set_default_date_filters,
    validate_date_filters,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    validate_date_filters(filters)

    columns = get_columns()
    purchase_rows = get_tyre_purchase_rows(filters)
    if not purchase_rows:
        return columns, [], _("No tyre purchase records found for the selected filters."), None

    vehicle_details = get_vehicle_details({row.vehicle for row in purchase_rows if row.vehicle})
    data = build_rows(purchase_rows, vehicle_details)
    chart = get_chart_data(data)

    return columns, data, None, chart


def get_columns():
    return [
        {"label": _("Month"), "fieldname": "month_label", "fieldtype": "Data", "width": 120},
        {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 140},
        {"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
        {"label": _("Purchase Orders"), "fieldname": "purchase_orders", "fieldtype": "Int", "width": 105},
        {"label": _("Purchased Qty"), "fieldname": "purchased_qty", "fieldtype": "Float", "width": 110},
        {"label": _("Average Rate"), "fieldname": "average_rate", "fieldtype": "Currency", "options": "currency", "width": 115},
        {"label": _("Total Purchase Amount"), "fieldname": "total_purchase_amount", "fieldtype": "Currency", "options": "currency", "width": 160},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
    ]


def build_rows(purchase_rows, vehicle_details):
    currency = get_default_currency()
    grouped = defaultdict(
        lambda: {
            "purchase_orders": set(),
            "purchased_qty": 0.0,
            "total_purchase_amount": 0.0,
        }
    )

    for row in purchase_rows:
        transaction_date = getdate(row.transaction_date)
        month_key = transaction_date.strftime("%Y-%m")
        month_label = transaction_date.strftime("%b %Y")
        vehicle = row.vehicle or _("Unassigned Vehicle")
        bucket = grouped[(month_key, month_label, vehicle)]
        bucket["purchase_orders"].add(row.purchase_order)
        bucket["purchased_qty"] += flt(row.qty)
        bucket["total_purchase_amount"] += flt(row.amount)

    data = []
    for (month_key, month_label, vehicle), bucket in sorted(grouped.items()):
        vehicle_info = vehicle_details.get(vehicle, {}) if vehicle != _("Unassigned Vehicle") else {}
        purchased_qty = flt(bucket["purchased_qty"])
        total_purchase_amount = flt(bucket["total_purchase_amount"])
        average_rate = (total_purchase_amount / purchased_qty) if purchased_qty else 0

        data.append(
            {
                "month_key": month_key,
                "month_label": month_label,
                "vehicle": vehicle,
                "license_plate": vehicle_info.get("license_plate"),
                "purchase_orders": len(bucket["purchase_orders"]),
                "purchased_qty": purchased_qty,
                "average_rate": average_rate,
                "total_purchase_amount": total_purchase_amount,
                "currency": currency,
            }
        )

    return data


def get_chart_data(data):
    labels = []
    label_index = {}
    dataset_points = defaultdict(dict)

    for row in data:
        month_label = row.get("month_label")
        vehicle = row.get("vehicle")

        if month_label not in label_index:
            label_index[month_label] = len(labels)
            labels.append(month_label)

        dataset_points[vehicle][month_label] = flt(row.get("total_purchase_amount"))

    datasets = []
    for vehicle, points in dataset_points.items():
        datasets.append(
            {
                "name": vehicle,
                "values": [points.get(label, 0) for label in labels],
            }
        )

    return {
        "data": {"labels": labels, "datasets": datasets},
        "type": "bar",
        "fieldtype": "Currency",
    }
