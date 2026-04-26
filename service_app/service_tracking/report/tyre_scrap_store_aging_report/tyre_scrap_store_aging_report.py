# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import OrderedDict

import frappe
from frappe import _
from frappe.utils import flt

from service_app.service_tracking.tyre_analytics import (
    get_tyre_scrap_aging_rows,
    set_default_date_filters,
    validate_date_filters,
)


AGING_BUCKETS = ("0-30 Days", "31-60 Days", "61-90 Days", "90+ Days")


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    validate_date_filters(filters)

    columns = get_columns()
    data = get_tyre_scrap_aging_rows(filters)
    chart = get_chart_data(data)

    if not data:
        return columns, [], _("No tyre scrap-store aging records found for the selected filters."), None

    return columns, data, None, chart


def get_columns():
    return [
        {"label": _("Tyre Receiving Note"), "fieldname": "tyre_receiving_note", "fieldtype": "Link", "options": "Tyre Receiving Note", "width": 160},
        {"label": _("Tyre Request"), "fieldname": "tyre_request", "fieldtype": "Link", "options": "Tyre Request", "width": 150},
        {"label": _("Received Date"), "fieldname": "received_date", "fieldtype": "Date", "width": 110},
        {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 130},
        {"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
        {"label": _("Wheel Position"), "fieldname": "wheel_position", "fieldtype": "Link", "options": "Tyre Position", "width": 120},
        {"label": _("Item"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": _("Worn Out Brand"), "fieldname": "worn_out_brand", "fieldtype": "Data", "width": 130},
        {"label": _("Worn Out Serial No"), "fieldname": "worn_out_serial_no", "fieldtype": "Data", "width": 160},
        {"label": _("Qty Received"), "fieldname": "qty_received", "fieldtype": "Float", "width": 100},
        {"label": _("Qty Disposed"), "fieldname": "qty_disposed", "fieldtype": "Float", "width": 100},
        {"label": _("Balance Qty"), "fieldname": "balance_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Age (Days)"), "fieldname": "age_days", "fieldtype": "Int", "width": 90},
        {"label": _("Aging Bucket"), "fieldname": "aging_bucket", "fieldtype": "Data", "width": 110},
        {"label": _("Received By"), "fieldname": "received_by", "fieldtype": "Data", "width": 150},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
    ]


def get_chart_data(data):
    bucket_totals = OrderedDict((bucket, 0.0) for bucket in AGING_BUCKETS)
    for row in data:
        bucket = row.get("aging_bucket")
        if bucket not in bucket_totals:
            bucket_totals[bucket] = 0.0
        bucket_totals[bucket] += flt(row.get("balance_qty"))

    if not any(bucket_totals.values()):
        return None

    return {
        "data": {
            "labels": list(bucket_totals.keys()),
            "datasets": [{"name": _("Balance Qty"), "values": [flt(value) for value in bucket_totals.values()]}],
        },
        "type": "bar",
    }
