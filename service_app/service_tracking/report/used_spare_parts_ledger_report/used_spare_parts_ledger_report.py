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
    issue_rows = get_issue_rows(filters)
    data = build_ledger_rows(receipt_rows, issue_rows)

    if not data:
        return columns, [], _("No used spare parts movements found for the selected filters.")

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
        {
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": _("Movement Type"),
            "fieldname": "movement_type",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("Source Type"),
            "fieldname": "source_doctype",
            "fieldtype": "Data",
            "width": 170,
        },
        {
            "label": _("Source Document"),
            "fieldname": "source_document",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("EAH Job Card"),
            "fieldname": "eah_job_card",
            "fieldtype": "Link",
            "options": "EAH Job Card",
            "width": 150,
        },
        {
            "label": _("Vehicle"),
            "fieldname": "vehicle",
            "fieldtype": "Link",
            "options": "Vehicle",
            "width": 130,
        },
        {
            "label": _("Item"),
            "fieldname": "item",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150,
        },
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("UOM"),
            "fieldname": "uom",
            "fieldtype": "Link",
            "options": "UOM",
            "width": 90,
        },
        {
            "label": _("Condition"),
            "fieldname": "condition",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Disposition"),
            "fieldname": "disposition",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("In Qty"),
            "fieldname": "in_qty",
            "fieldtype": "Float",
            "width": 90,
        },
        {
            "label": _("Out Qty"),
            "fieldname": "out_qty",
            "fieldtype": "Float",
            "width": 90,
        },
        {
            "label": _("Balance Qty"),
            "fieldname": "balance_qty",
            "fieldtype": "Float",
            "width": 100,
        },
        {
            "label": _("User"),
            "fieldname": "moved_by",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": _("Remarks"),
            "fieldname": "remarks",
            "fieldtype": "Data",
            "width": 220,
        },
    ]


def get_receipt_rows(filters):
    conditions = [
        "mrn.docstatus = 1",
        "mrn.received_date BETWEEN %(from_date)s AND %(to_date)s",
        "COALESCE(item.qty_received, 0) > 0",
    ]
    values = {
        "from_date": filters.from_date,
        "to_date": filters.to_date,
    }

    if filters.get("vehicle"):
        conditions.append("mrn.vehicle = %(vehicle)s")
        values["vehicle"] = filters.vehicle

    if filters.get("eah_job_card"):
        conditions.append("mrn.eah_job_card = %(eah_job_card)s")
        values["eah_job_card"] = filters.eah_job_card

    if filters.get("item"):
        conditions.append("item.item = %(item)s")
        values["item"] = filters.item

    return frappe.db.sql(
        f"""
        SELECT
            mrn.received_date AS posting_date,
            'Receipt' AS movement_type,
            'Maintenance Return Note' AS source_doctype,
            mrn.name AS source_document,
            mrn.eah_job_card,
            mrn.vehicle,
            mrn.received_by AS moved_by,
            item.item,
            item.item_name,
            item.uom,
            item.condition,
            item.disposition,
            item.remarks,
            item.qty_received AS in_qty,
            0 AS out_qty,
            0 AS movement_priority
        FROM `tabMaintenance Return Note` mrn
        INNER JOIN `tabMaintenance Return Note Item` item
            ON item.parent = mrn.name
        WHERE {' AND '.join(conditions)}
        """,
        values,
        as_dict=True,
    )


def get_issue_rows(filters):
    conditions = [
        "issue_note.docstatus = 1",
        "issue_note.posting_date BETWEEN %(from_date)s AND %(to_date)s",
        "COALESCE(item.qty_out, 0) > 0",
    ]
    values = {
        "from_date": filters.from_date,
        "to_date": filters.to_date,
    }

    if filters.get("vehicle"):
        conditions.append("issue_note.vehicle = %(vehicle)s")
        values["vehicle"] = filters.vehicle

    if filters.get("eah_job_card"):
        conditions.append("issue_note.eah_job_card = %(eah_job_card)s")
        values["eah_job_card"] = filters.eah_job_card

    if filters.get("item"):
        conditions.append("item.item = %(item)s")
        values["item"] = filters.item

    return frappe.db.sql(
        f"""
        SELECT
            issue_note.posting_date AS posting_date,
            COALESCE(issue_note.purpose, 'Issue') AS movement_type,
            'Used Spare Parts Issue Note' AS source_doctype,
            issue_note.name AS source_document,
            issue_note.eah_job_card,
            issue_note.vehicle,
            issue_note.issued_by AS moved_by,
            item.item,
            item.item_name,
            item.uom,
            item.condition,
            item.disposition,
            item.remarks,
            0 AS in_qty,
            item.qty_out AS out_qty,
            1 AS movement_priority
        FROM `tabUsed Spare Parts Issue Note` issue_note
        INNER JOIN `tabUsed Spare Parts Issue Note Item` item
            ON item.parent = issue_note.name
        WHERE {' AND '.join(conditions)}
        """,
        values,
        as_dict=True,
    )


def build_ledger_rows(receipt_rows, issue_rows):
    movements = []
    running_balance_by_item = defaultdict(float)

    for row in receipt_rows + issue_rows:
        movement = frappe._dict(row)
        movement.posting_date = getdate(movement.posting_date)
        movements.append(movement)

    movements.sort(
        key=lambda row: (
            row.posting_date,
            row.item or "",
            row.movement_priority,
            row.source_document or "",
        )
    )

    data = []
    for movement in movements:
        item_key = movement.item or "Unknown Item"
        running_balance_by_item[item_key] += flt(movement.in_qty) - flt(movement.out_qty)

        data.append(
            {
                "posting_date": movement.posting_date,
                "movement_type": movement.movement_type,
                "source_doctype": movement.source_doctype,
                "source_document": movement.source_document,
                "eah_job_card": movement.eah_job_card,
                "vehicle": movement.vehicle,
                "item": movement.item,
                "item_name": movement.item_name,
                "uom": movement.uom,
                "condition": movement.condition,
                "disposition": movement.disposition,
                "in_qty": flt(movement.in_qty),
                "out_qty": flt(movement.out_qty),
                "balance_qty": flt(running_balance_by_item[item_key]),
                "moved_by": movement.moved_by,
                "remarks": movement.remarks,
            }
        )

    return data