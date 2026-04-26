# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate, today


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_filters(filters)
    validate_filters(filters)

    columns = get_columns()
    receipt_rows = get_receipt_rows(filters)
    disposal_rows = get_disposal_rows(filters)
    data = build_ledger_rows(receipt_rows, disposal_rows)

    if not data:
        return columns, [], _("No tyre ledger movements found for the selected filters.")

    return columns, data


def set_default_filters(filters):
    if not filters.get("to_date"):
        filters.to_date = today()

    if not filters.get("from_date"):
        filters.from_date = add_months(getdate(filters.to_date), -12)


def validate_filters(filters):
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required."))

    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("From Date cannot be greater than To Date."))


def get_columns():
    return [
        {"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
        {"label": _("Movement Type"), "fieldname": "movement_type", "fieldtype": "Data", "width": 130},
        {"label": _("Source Type"), "fieldname": "source_doctype", "fieldtype": "Data", "width": 160},
        {"label": _("Source Document"), "fieldname": "source_document", "fieldtype": "Data", "width": 170},
        {"label": _("Tyre Request"), "fieldname": "tyre_request", "fieldtype": "Link", "options": "Tyre Request", "width": 150},
        {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 130},
        {"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
        {"label": _("Wheel Position"), "fieldname": "wheel_position", "fieldtype": "Link", "options": "Tyre Position", "width": 120},
        {"label": _("Item"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 140},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
        {"label": _("Tyre Brand"), "fieldname": "tyre_brand", "fieldtype": "Data", "width": 120},
        {"label": _("Worn Out Brand"), "fieldname": "worn_out_brand", "fieldtype": "Data", "width": 130},
        {"label": _("Worn Out Serial No"), "fieldname": "worn_out_serial_no", "fieldtype": "Data", "width": 160},
        {"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 90},
        {"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 90},
        {"label": _("Balance Qty"), "fieldname": "balance_qty", "fieldtype": "Float", "width": 100},
        {"label": _("User"), "fieldname": "moved_by", "fieldtype": "Data", "width": 150},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
    ]


def get_receipt_rows(filters):
    conditions = [
        "receipt.docstatus = 1",
        "receipt.received_date BETWEEN %(from_date)s AND %(to_date)s",
        "COALESCE(item.qty_received, 0) > 0",
    ]
    values = {"from_date": filters.from_date, "to_date": filters.to_date}

    if filters.get("vehicle"):
        conditions.append("receipt.vehicle = %(vehicle)s")
        values["vehicle"] = filters.vehicle

    if filters.get("brand"):
        conditions.append("COALESCE(item.worn_out_brand, '') = %(brand)s")
        values["brand"] = filters.brand

    if filters.get("serial_no"):
        conditions.append("COALESCE(item.worn_out_serial_no, '') = %(serial_no)s")
        values["serial_no"] = filters.serial_no

    return frappe.db.sql(
        f"""
        SELECT
            receipt.received_date AS posting_date,
            'Receipt' AS movement_type,
            'Tyre Receiving Note' AS source_doctype,
            receipt.name AS source_document,
            receipt.tyre_request,
            receipt.vehicle,
            receipt.license_plate,
            receipt.received_by AS moved_by,
            item.wheel_position,
            item.item,
            item.item_name,
            item.tyre_brand,
            item.worn_out_brand,
            item.worn_out_serial_no,
            item.remarks,
            item.qty_received AS in_qty,
            0 AS out_qty,
            0 AS movement_priority
        FROM `tabTyre Receiving Note` receipt
        INNER JOIN `tabTyre Receiving Note Item` item
            ON item.parent = receipt.name
        WHERE {' AND '.join(conditions)}
        """,
        values,
        as_dict=True,
    )


def get_disposal_rows(filters):
    conditions = [
        "disposal.docstatus = 1",
        "disposal.posting_date BETWEEN %(from_date)s AND %(to_date)s",
        "COALESCE(item.qty_out, 0) > 0",
    ]
    values = {"from_date": filters.from_date, "to_date": filters.to_date}

    if filters.get("vehicle"):
        conditions.append("disposal.vehicle = %(vehicle)s")
        values["vehicle"] = filters.vehicle

    if filters.get("brand"):
        conditions.append("COALESCE(item.worn_out_brand, '') = %(brand)s")
        values["brand"] = filters.brand

    if filters.get("serial_no"):
        conditions.append("COALESCE(item.worn_out_serial_no, '') = %(serial_no)s")
        values["serial_no"] = filters.serial_no

    return frappe.db.sql(
        f"""
        SELECT
            disposal.posting_date AS posting_date,
            COALESCE(disposal.disposal_method, 'Disposal') AS movement_type,
            'Tyre Disposal Note' AS source_doctype,
            disposal.name AS source_document,
            disposal.tyre_request,
            disposal.vehicle,
            disposal.license_plate,
            disposal.disposed_by AS moved_by,
            item.wheel_position,
            item.item,
            item.item_name,
            item.tyre_brand,
            item.worn_out_brand,
            item.worn_out_serial_no,
            item.remarks,
            0 AS in_qty,
            item.qty_out AS out_qty,
            1 AS movement_priority
        FROM `tabTyre Disposal Note` disposal
        INNER JOIN `tabTyre Disposal Note Item` item
            ON item.parent = disposal.name
        WHERE {' AND '.join(conditions)}
        """,
        values,
        as_dict=True,
    )


def build_ledger_rows(receipt_rows, disposal_rows):
    movements = []
    running_balance_by_key = defaultdict(float)

    for row in receipt_rows + disposal_rows:
        movement = frappe._dict(row)
        movement.posting_date = getdate(movement.posting_date)
        movements.append(movement)

    movements.sort(
        key=lambda row: (
            row.posting_date,
            row.vehicle or "",
            row.wheel_position or "",
            row.item or "",
            row.movement_priority,
            row.source_document or "",
        )
    )

    data = []
    for movement in movements:
        tracking_key = (
            movement.worn_out_serial_no
            or f"{movement.vehicle}|{movement.wheel_position}|{movement.item}|{movement.worn_out_brand}"
        )
        running_balance_by_key[tracking_key] += flt(movement.in_qty) - flt(movement.out_qty)

        data.append(
            {
                "posting_date": movement.posting_date,
                "movement_type": movement.movement_type,
                "source_doctype": movement.source_doctype,
                "source_document": movement.source_document,
                "tyre_request": movement.tyre_request,
                "vehicle": movement.vehicle,
                "license_plate": movement.license_plate,
                "wheel_position": movement.wheel_position,
                "item": movement.item,
                "item_name": movement.item_name,
                "tyre_brand": movement.tyre_brand,
                "worn_out_brand": movement.worn_out_brand,
                "worn_out_serial_no": movement.worn_out_serial_no,
                "in_qty": flt(movement.in_qty),
                "out_qty": flt(movement.out_qty),
                "balance_qty": flt(running_balance_by_key[tracking_key]),
                "moved_by": movement.moved_by,
                "remarks": movement.remarks,
            }
        )

    return data
