# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate

from service_app.service_tracking.tyre_analytics import (
    get_outstanding_tyre_return_rows,
    set_default_date_filters,
    validate_date_filters,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    validate_date_filters(filters)

    columns = get_columns()
    data = get_outstanding_tyre_return_rows(filters)
    chart = get_chart_data(data)

    if not data:
        return columns, [], _("No outstanding tyre returns found for the selected filters."), None

    return columns, data, None, chart


def get_columns():
    return [
        {"label": _("Tyre Request"), "fieldname": "tyre_request", "fieldtype": "Link", "options": "Tyre Request", "width": 150},
        {"label": _("Request Date"), "fieldname": "request_date", "fieldtype": "Date", "width": 110},
        {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 130},
        {"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
        {"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 130},
        {"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 130},
        {"label": _("Requested Qty"), "fieldname": "requested_qty", "fieldtype": "Float", "width": 105},
        {"label": _("Received Qty"), "fieldname": "received_qty", "fieldtype": "Float", "width": 105},
        {"label": _("Outstanding Qty"), "fieldname": "outstanding_qty", "fieldtype": "Float", "width": 115},
        {"label": _("Tyre Receiving Note"), "fieldname": "tyre_receiving_note", "fieldtype": "Link", "options": "Tyre Receiving Note", "width": 150},
        {"label": _("Receiving Status"), "fieldname": "receiving_status", "fieldtype": "Data", "width": 130},
        {"label": _("Days Outstanding"), "fieldname": "days_outstanding", "fieldtype": "Int", "width": 120},
    ]


def get_chart_data(data):
    month_totals = defaultdict(float)
    month_counts = defaultdict(int)

    for row in data:
        month_label = getdate(row.get("request_date")).strftime("%b %Y")
        month_totals[month_label] += flt(row.get("outstanding_qty"))
        month_counts[month_label] += 1

    labels = list(month_totals.keys())
    if not labels:
        return None

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Outstanding Qty"), "values": [flt(month_totals[label]) for label in labels]},
                {"name": _("Outstanding Requests"), "values": [month_counts[label] for label in labels]},
            ],
        },
        "type": "bar",
    }
