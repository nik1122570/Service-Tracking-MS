# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate

from service_app.service_tracking.tyre_analytics import (
    get_default_currency,
    get_tyre_purchase_rows,
    get_tyre_request_rows,
    set_default_date_filters,
    validate_date_filters,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    validate_date_filters(filters)

    columns = get_columns()
    request_rows = get_tyre_request_rows(filters)
    purchase_rows = get_tyre_purchase_rows(filters)
    data = build_rows(request_rows, purchase_rows)
    chart = get_chart_data(data)

    if not data:
        return columns, [], _("No tyre request lead-time records found for the selected filters."), None

    return columns, data, None, chart


def get_columns():
    return [
        {"label": _("Tyre Request"), "fieldname": "tyre_request", "fieldtype": "Link", "options": "Tyre Request", "width": 150},
        {"label": _("Request Date"), "fieldname": "request_date", "fieldtype": "Date", "width": 110},
        {"label": _("Purchase Order"), "fieldname": "purchase_order", "fieldtype": "Link", "options": "Purchase Order", "width": 160},
        {"label": _("Purchase Date"), "fieldname": "purchase_date", "fieldtype": "Date", "width": 110},
        {"label": _("Lead Time (Days)"), "fieldname": "lead_time_days", "fieldtype": "Int", "width": 120},
        {"label": _("Purchase Status"), "fieldname": "purchase_status", "fieldtype": "Data", "width": 120},
        {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 130},
        {"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
        {"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 130},
        {"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 130},
        {"label": _("Requested Qty"), "fieldname": "requested_qty", "fieldtype": "Float", "width": 105},
        {"label": _("Requested Amount"), "fieldname": "requested_amount", "fieldtype": "Currency", "options": "currency", "width": 130},
        {"label": _("Purchased Qty"), "fieldname": "purchased_qty", "fieldtype": "Float", "width": 105},
        {"label": _("Purchased Amount"), "fieldname": "purchased_amount", "fieldtype": "Currency", "options": "currency", "width": 130},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
    ]


def build_rows(request_rows, purchase_rows):
    currency = get_default_currency()
    request_map = {}

    for row in request_rows:
        bucket = request_map.setdefault(
            row.tyre_request,
            {
                "tyre_request": row.tyre_request,
                "request_date": getdate(row.request_date),
                "vehicle": row.vehicle,
                "license_plate": row.license_plate,
                "supplier": row.supplier,
                "project": row.project,
                "cost_center": row.cost_center,
                "requested_qty": 0.0,
                "requested_amount": 0.0,
            },
        )
        bucket["requested_qty"] += flt(row.qty)
        bucket["requested_amount"] += flt(row.qty) * flt(row.rate)

    purchase_map = defaultdict(
        lambda: {
            "purchase_orders": set(),
            "purchase_date": None,
            "purchased_qty": 0.0,
            "purchased_amount": 0.0,
        }
    )
    for row in purchase_rows:
        bucket = purchase_map[row.tyre_request]
        bucket["purchase_orders"].add(row.purchase_order)
        row_purchase_date = getdate(row.transaction_date)
        if not bucket["purchase_date"] or row_purchase_date < bucket["purchase_date"]:
            bucket["purchase_date"] = row_purchase_date
        bucket["purchased_qty"] += flt(row.qty)
        bucket["purchased_amount"] += flt(row.amount)

    data = []
    for tyre_request, request_data in sorted(request_map.items(), key=lambda entry: entry[1]["request_date"], reverse=True):
        purchase_data = purchase_map.get(tyre_request, {})
        purchase_date = purchase_data.get("purchase_date")
        purchase_orders = sorted(purchase_data.get("purchase_orders", set()))
        data.append(
            {
                **request_data,
                "purchase_order": purchase_orders[0] if purchase_orders else None,
                "purchase_date": purchase_date,
                "lead_time_days": date_diff(purchase_date, request_data["request_date"]) if purchase_date else None,
                "purchase_status": "Purchased" if purchase_date else "Pending Purchase",
                "purchased_qty": flt(purchase_data.get("purchased_qty")),
                "purchased_amount": flt(purchase_data.get("purchased_amount")),
                "currency": currency,
            }
        )

    return data


def get_chart_data(data):
    monthly_lead_times = defaultdict(list)
    pending_counts = defaultdict(int)

    for row in data:
        month_label = getdate(row.get("request_date")).strftime("%b %Y")
        if row.get("lead_time_days") is not None:
            monthly_lead_times[month_label].append(flt(row.lead_time_days))
        if row.get("purchase_status") == "Pending Purchase":
            pending_counts[month_label] += 1

    labels = sorted(set(list(monthly_lead_times.keys()) + list(pending_counts.keys())))
    if not labels:
        return None

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Average Lead Time"),
                    "values": [
                        (sum(monthly_lead_times[label]) / len(monthly_lead_times[label]))
                        if monthly_lead_times[label]
                        else 0
                        for label in labels
                    ],
                },
                {
                    "name": _("Pending Requests"),
                    "values": [pending_counts.get(label, 0) for label in labels],
                },
            ],
        },
        "type": "bar",
    }
