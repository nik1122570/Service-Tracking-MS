# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate

from service_app.service_tracking.tyre_analytics import (
    get_default_currency,
    get_tyre_purchase_invoice_rows,
    get_vehicle_details,
    set_default_date_filters,
    validate_date_filters,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    validate_date_filters(filters)

    columns = get_columns()
    invoice_rows = get_tyre_purchase_invoice_rows(filters)
    if not invoice_rows:
        return columns, [], _("No tyre purchase invoice records found for the selected filters."), None

    vehicle_details = get_vehicle_details({row.vehicle for row in invoice_rows if row.vehicle})
    data = build_rows(invoice_rows, vehicle_details)
    chart = get_chart_data(data)

    return columns, data, None, chart


def get_columns():
    return [
        {"label": _("Month"), "fieldname": "month_label", "fieldtype": "Data", "width": 120},
        {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 140},
        {"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
        {"label": _("Purchase Invoices"), "fieldname": "purchase_invoices", "fieldtype": "Int", "width": 110},
        {"label": _("Invoiced Qty"), "fieldname": "invoiced_qty", "fieldtype": "Float", "width": 110},
        {"label": _("Average Invoice Rate"), "fieldname": "average_rate", "fieldtype": "Currency", "options": "currency", "width": 140},
        {"label": _("Total Invoice Amount"), "fieldname": "total_invoice_amount", "fieldtype": "Currency", "options": "currency", "width": 155},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
    ]


def build_rows(invoice_rows, vehicle_details):
    currency = get_default_currency()
    unassigned_vehicle = _("Unassigned Vehicle")
    grouped = defaultdict(
        lambda: {
            "purchase_invoices": set(),
            "invoiced_qty": 0.0,
            "total_invoice_amount": 0.0,
            "license_plate": None,
        }
    )

    for row in invoice_rows:
        posting_date = getdate(row.posting_date)
        month_key = posting_date.strftime("%Y-%m")
        month_label = posting_date.strftime("%b %Y")
        vehicle = row.vehicle or unassigned_vehicle
        bucket = grouped[(month_key, month_label, vehicle)]
        bucket["purchase_invoices"].add(row.purchase_invoice)
        bucket["invoiced_qty"] += flt(row.qty)
        bucket["total_invoice_amount"] += flt(row.amount)
        bucket["license_plate"] = bucket.get("license_plate") or row.get("license_plate")

    data = []
    for (month_key, month_label, vehicle), bucket in sorted(grouped.items()):
        vehicle_info = vehicle_details.get(vehicle, {}) if vehicle != unassigned_vehicle else {}
        invoiced_qty = flt(bucket["invoiced_qty"])
        total_invoice_amount = flt(bucket["total_invoice_amount"])
        average_rate = (total_invoice_amount / invoiced_qty) if invoiced_qty else 0

        data.append(
            {
                "month_key": month_key,
                "month_label": month_label,
                "vehicle": vehicle,
                "license_plate": vehicle_info.get("license_plate") or bucket.get("license_plate"),
                "purchase_invoices": len(bucket["purchase_invoices"]),
                "invoiced_qty": invoiced_qty,
                "average_rate": average_rate,
                "total_invoice_amount": total_invoice_amount,
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

        dataset_points[vehicle][month_label] = flt(row.get("total_invoice_amount"))

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
