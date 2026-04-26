# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate

from service_app.service_tracking.tyre_analytics import (
    get_tyre_disposal_rows,
    get_tyre_receiving_rows,
    get_tyre_request_rows,
    set_default_date_filters,
    validate_date_filters,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    validate_date_filters(filters)

    columns = get_columns()
    data = build_rows(filters)
    chart = get_chart_data(data)

    if not data:
        return columns, [], _("No tyre serial-number traceability records found for the selected filters."), None

    return columns, data, None, chart


def get_columns():
    return [
        {"label": _("Event Date"), "fieldname": "event_date", "fieldtype": "Date", "width": 110},
        {"label": _("Event Type"), "fieldname": "event_type", "fieldtype": "Data", "width": 100},
        {"label": _("Source Type"), "fieldname": "source_doctype", "fieldtype": "Data", "width": 150},
        {"label": _("Source Document"), "fieldname": "source_document", "fieldtype": "Data", "width": 160},
        {"label": _("Tyre Request"), "fieldname": "tyre_request", "fieldtype": "Link", "options": "Tyre Request", "width": 150},
        {"label": _("Tyre Receiving Note"), "fieldname": "tyre_receiving_note", "fieldtype": "Link", "options": "Tyre Receiving Note", "width": 160},
        {"label": _("Tyre Disposal Note"), "fieldname": "tyre_disposal_note", "fieldtype": "Link", "options": "Tyre Disposal Note", "width": 160},
        {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 130},
        {"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
        {"label": _("Wheel Position"), "fieldname": "wheel_position", "fieldtype": "Link", "options": "Tyre Position", "width": 120},
        {"label": _("Item"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": _("Tyre Brand"), "fieldname": "tyre_brand", "fieldtype": "Data", "width": 120},
        {"label": _("Worn Out Brand"), "fieldname": "worn_out_brand", "fieldtype": "Data", "width": 130},
        {"label": _("Worn Out Serial No"), "fieldname": "worn_out_serial_no", "fieldtype": "Data", "width": 160},
        {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
        {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 90},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
        {"label": _("Condition"), "fieldname": "condition", "fieldtype": "Data", "width": 110},
        {"label": _("Disposition"), "fieldname": "disposition", "fieldtype": "Data", "width": 130},
        {"label": _("Handled By"), "fieldname": "handled_by", "fieldtype": "Data", "width": 150},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
    ]


def build_rows(filters):
    rows = []

    for row in get_tyre_request_rows(filters):
        rows.append(
            {
                "event_date": getdate(row.request_date),
                "event_type": "Requested",
                "source_doctype": "Tyre Request",
                "source_document": row.tyre_request,
                "tyre_request": row.tyre_request,
                "tyre_receiving_note": None,
                "tyre_disposal_note": None,
                "vehicle": row.vehicle,
                "license_plate": row.license_plate,
                "supplier": row.supplier,
                "wheel_position": row.wheel_position,
                "item": row.item,
                "item_name": row.item_name,
                "tyre_brand": row.tyre_brand,
                "worn_out_brand": row.worn_out_brand,
                "worn_out_serial_no": row.worn_out_serial_no,
                "qty": flt(row.qty),
                "uom": row.uom,
                "status": "Submitted",
                "condition": None,
                "disposition": None,
                "handled_by": None,
                "remarks": row.remarks,
                "movement_priority": 0,
            }
        )

    for row in get_tyre_receiving_rows(filters):
        rows.append(
            {
                "event_date": getdate(row.received_date),
                "event_type": "Received",
                "source_doctype": "Tyre Receiving Note",
                "source_document": row.tyre_receiving_note,
                "tyre_request": row.tyre_request,
                "tyre_receiving_note": row.tyre_receiving_note,
                "tyre_disposal_note": None,
                "vehicle": row.vehicle,
                "license_plate": row.license_plate,
                "supplier": row.supplier,
                "wheel_position": row.wheel_position,
                "item": row.item,
                "item_name": row.item_name,
                "tyre_brand": row.tyre_brand,
                "worn_out_brand": row.worn_out_brand,
                "worn_out_serial_no": row.worn_out_serial_no,
                "qty": flt(row.qty_received),
                "uom": row.uom,
                "status": row.status,
                "condition": row.condition,
                "disposition": row.disposition,
                "handled_by": row.received_by,
                "remarks": row.remarks,
                "movement_priority": 1,
            }
        )

    for row in get_tyre_disposal_rows(filters):
        rows.append(
            {
                "event_date": getdate(row.posting_date),
                "event_type": "Disposed",
                "source_doctype": "Tyre Disposal Note",
                "source_document": row.tyre_disposal_note,
                "tyre_request": row.tyre_request,
                "tyre_receiving_note": row.tyre_receiving_note,
                "tyre_disposal_note": row.tyre_disposal_note,
                "vehicle": row.vehicle,
                "license_plate": row.license_plate,
                "supplier": row.supplier,
                "wheel_position": row.wheel_position,
                "item": row.item,
                "item_name": row.item_name,
                "tyre_brand": row.tyre_brand,
                "worn_out_brand": row.worn_out_brand,
                "worn_out_serial_no": row.worn_out_serial_no,
                "qty": flt(row.qty_out),
                "uom": row.uom,
                "status": row.status,
                "condition": row.condition,
                "disposition": row.disposition,
                "handled_by": row.disposed_by,
                "remarks": row.remarks,
                "movement_priority": 2,
            }
        )

    return sorted(
        rows,
        key=lambda row: (
            row.get("worn_out_serial_no") or "",
            row.get("event_date"),
            row.get("movement_priority", 0),
            row.get("source_document") or "",
        ),
    )


def get_chart_data(data):
    if not data:
        return None

    totals = defaultdict(float)
    for row in data:
        totals[row.get("event_type") or _("Unspecified")] += flt(row.get("qty"))

    labels = ["Requested", "Received", "Disposed"]
    values = [flt(totals.get(label, 0)) for label in labels]
    if not any(values):
        return None

    return {
        "data": {"labels": labels, "datasets": [{"name": _("Quantity"), "values": values}]},
        "type": "bar",
    }
