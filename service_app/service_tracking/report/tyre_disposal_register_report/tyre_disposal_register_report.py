# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate

from service_app.service_tracking.tyre_analytics import (
    get_tyre_disposal_rows,
    set_default_date_filters,
    validate_date_filters,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    validate_date_filters(filters)

    columns = get_columns()
    data = get_tyre_disposal_rows(filters)
    chart = get_chart_data(data)

    if not data:
        return columns, [], _("No tyre disposal records found for the selected filters."), None

    return columns, data, None, chart


def get_columns():
    return [
        {"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
        {"label": _("Tyre Disposal Note"), "fieldname": "tyre_disposal_note", "fieldtype": "Link", "options": "Tyre Disposal Note", "width": 160},
        {"label": _("Tyre Receiving Note"), "fieldname": "tyre_receiving_note", "fieldtype": "Link", "options": "Tyre Receiving Note", "width": 160},
        {"label": _("Tyre Request"), "fieldname": "tyre_request", "fieldtype": "Link", "options": "Tyre Request", "width": 150},
        {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 130},
        {"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
        {"label": _("Wheel Position"), "fieldname": "wheel_position", "fieldtype": "Link", "options": "Maintenance Postion", "width": 120},
        {"label": _("Item"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": _("Tyre Brand"), "fieldname": "tyre_brand", "fieldtype": "Data", "width": 120},
        {"label": _("Worn Out Brand"), "fieldname": "worn_out_brand", "fieldtype": "Data", "width": 130},
        {"label": _("Worn Out Serial No"), "fieldname": "worn_out_serial_no", "fieldtype": "Data", "width": 160},
        {"label": _("Qty Out"), "fieldname": "qty_out", "fieldtype": "Float", "width": 90},
        {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 90},
        {"label": _("Condition"), "fieldname": "condition", "fieldtype": "Data", "width": 110},
        {"label": _("Disposal Method"), "fieldname": "disposal_method", "fieldtype": "Data", "width": 140},
        {"label": _("Disposition"), "fieldname": "disposition", "fieldtype": "Data", "width": 130},
        {"label": _("Disposed By"), "fieldname": "disposed_by", "fieldtype": "Data", "width": 150},
        {"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 130},
        {"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 130},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
    ]


def get_chart_data(data):
    labels = []
    label_index = {}
    dataset_points = defaultdict(dict)

    for row in data:
        posting_date = getdate(row.get("posting_date"))
        month_label = posting_date.strftime("%b %Y")
        method = row.get("disposal_method") or _("Unspecified Method")

        if month_label not in label_index:
            label_index[month_label] = len(labels)
            labels.append(month_label)

        dataset_points[method][month_label] = dataset_points[method].get(month_label, 0) + flt(row.get("qty_out"))

    if not labels:
        return None

    datasets = []
    for method, points in dataset_points.items():
        datasets.append({"name": method, "values": [flt(points.get(label, 0)) for label in labels]})

    return {"data": {"labels": labels, "datasets": datasets}, "type": "bar"}
