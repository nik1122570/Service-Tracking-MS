# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate

from service_app.service_tracking.tyre_analytics import (
    get_default_currency,
    get_tyre_purchase_rows,
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

    data = build_rows(purchase_rows)
    chart = get_chart_data(purchase_rows, data, filters)

    return columns, data, None, chart


def get_columns():
    return [
        {"label": _("Tyre Brand"), "fieldname": "tyre_brand", "fieldtype": "Data", "width": 150},
        {"label": _("Purchase Orders"), "fieldname": "purchase_orders", "fieldtype": "Int", "width": 105},
        {"label": _("Vehicles"), "fieldname": "vehicles", "fieldtype": "Int", "width": 80},
        {"label": _("Purchased Qty"), "fieldname": "purchased_qty", "fieldtype": "Float", "width": 110},
        {"label": _("Average Rate"), "fieldname": "average_rate", "fieldtype": "Currency", "options": "currency", "width": 115},
        {"label": _("Total Purchase Amount"), "fieldname": "total_purchase_amount", "fieldtype": "Currency", "options": "currency", "width": 160},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
    ]


def build_rows(purchase_rows):
    currency = get_default_currency()
    grouped = defaultdict(
        lambda: {
            "purchase_orders": set(),
            "vehicles": set(),
            "purchased_qty": 0.0,
            "total_purchase_amount": 0.0,
        }
    )

    for row in purchase_rows:
        brand = row.tyre_brand or _("Unspecified Brand")
        bucket = grouped[brand]
        bucket["purchase_orders"].add(row.purchase_order)
        if row.vehicle:
            bucket["vehicles"].add(row.vehicle)
        bucket["purchased_qty"] += flt(row.qty)
        bucket["total_purchase_amount"] += flt(row.amount)

    data = []
    for brand, bucket in sorted(grouped.items()):
        purchased_qty = flt(bucket["purchased_qty"])
        total_purchase_amount = flt(bucket["total_purchase_amount"])
        average_rate = (total_purchase_amount / purchased_qty) if purchased_qty else 0

        data.append(
            {
                "tyre_brand": brand,
                "purchase_orders": len(bucket["purchase_orders"]),
                "vehicles": len(bucket["vehicles"]),
                "purchased_qty": purchased_qty,
                "average_rate": average_rate,
                "total_purchase_amount": total_purchase_amount,
                "currency": currency,
            }
        )

    return data


def get_chart_data(purchase_rows, data, filters):
    if filters.get("brand"):
        monthly_totals = defaultdict(float)
        for row in purchase_rows:
            month_label = getdate(row.transaction_date).strftime("%b %Y")
            monthly_totals[month_label] += flt(row.amount)

        labels = list(monthly_totals.keys())
        return {
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "name": filters.brand,
                        "values": [flt(monthly_totals[label]) for label in labels],
                    }
                ],
            },
            "type": "line",
            "fieldtype": "Currency",
        }

    labels = [row["tyre_brand"] for row in data]
    if not labels:
        return None

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Total Purchase Amount"),
                    "values": [flt(row["total_purchase_amount"]) for row in data],
                }
            ],
        },
        "type": "bar",
        "fieldtype": "Currency",
    }
