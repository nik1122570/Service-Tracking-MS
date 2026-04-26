# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict
import json

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate

from service_app.service_tracking.tyre_analytics import (
    get_tyre_request_odometer_select_expr,
    set_default_date_filters,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    validate_filters(filters)

    columns = get_columns()
    rows = get_request_rows(filters)
    data = build_history_rows(rows, filters)

    if not data:
        return columns, [], _("No tyre history records found for the selected filters.")

    return columns, data


def validate_filters(filters):
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required."))

    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("From Date cannot be greater than To Date."))


def get_columns():
    return [
        {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 130},
        {"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
        {"label": _("Wheel Position"), "fieldname": "wheel_position", "fieldtype": "Link", "options": "Tyre Position", "width": 120},
        {"label": _("Tyre Request"), "fieldname": "tyre_request", "fieldtype": "Link", "options": "Tyre Request", "width": 150},
        {"label": _("Installed On"), "fieldname": "request_date", "fieldtype": "Date", "width": 110},
        {"label": _("Tyre Item"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
        {"label": _("Tyre Brand"), "fieldname": "tyre_brand", "fieldtype": "Data", "width": 120},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
        {"label": _("Start Odometer"), "fieldname": "start_odometer", "fieldtype": "Float", "width": 120},
        {"label": _("Next Request"), "fieldname": "next_tyre_request", "fieldtype": "Link", "options": "Tyre Request", "width": 150},
        {"label": _("Removed On"), "fieldname": "next_request_date", "fieldtype": "Date", "width": 110},
        {"label": _("End Odometer"), "fieldname": "end_odometer", "fieldtype": "Float", "width": 120},
        {"label": _("Distance Covered"), "fieldname": "distance_covered", "fieldtype": "Float", "width": 130},
        {"label": _("Days In Service"), "fieldname": "days_in_service", "fieldtype": "Int", "width": 110},
        {"label": _("Replacement Brand"), "fieldname": "replacement_brand", "fieldtype": "Data", "width": 130},
        {"label": _("Current Status"), "fieldname": "current_status", "fieldtype": "Data", "width": 110},
    ]


def parse_multi_select_filter(values):
    if not values:
        return []

    if isinstance(values, list):
        return [value for value in values if value]

    if isinstance(values, str):
        try:
            parsed_values = json.loads(values)
        except Exception:
            parsed_values = [value.strip() for value in values.split(",") if value.strip()]

        if isinstance(parsed_values, str):
            return [parsed_values]

        return [value for value in parsed_values if value]

    return [values]


def get_request_rows(filters):
    vehicles = parse_multi_select_filter(filters.get("vehicles"))
    conditions = ["request.docstatus = 1"]
    values = {}

    if vehicles:
        conditions.append("request.vehicle IN %(vehicles)s")
        values["vehicles"] = tuple(vehicles)

    if filters.get("wheel_position"):
        conditions.append("item.wheel_position = %(wheel_position)s")
        values["wheel_position"] = filters.wheel_position

    odometer_select_expr = get_tyre_request_odometer_select_expr()

    return frappe.db.sql(
        f"""
        SELECT
            request.name AS tyre_request,
            request.request_date,
            request.vehicle,
            request.license_plate,
            {odometer_select_expr} AS odometer_reading,
            request.supplier,
            item.wheel_position,
            item.item,
            item.item_name,
            item.tyre_brand,
            item.qty
        FROM `tabTyre Request` request
        INNER JOIN `tabTyre Request Item` item
            ON item.parent = request.name
        WHERE {' AND '.join(conditions)}
        ORDER BY request.vehicle ASC, item.wheel_position ASC, request.request_date ASC, request.creation ASC
        """,
        values,
        as_dict=True,
    )


def build_history_rows(rows, filters):
    grouped_rows = defaultdict(list)
    from_date = getdate(filters.from_date)
    to_date = getdate(filters.to_date)

    for row in rows:
        grouped_rows[(row.vehicle, row.wheel_position)].append(frappe._dict(row))

    data = []
    for group_rows in grouped_rows.values():
        group_rows.sort(key=lambda row: (getdate(row.request_date), row.tyre_request))

        for index, row in enumerate(group_rows):
            request_date = getdate(row.request_date)
            if request_date < from_date or request_date > to_date:
                continue

            if filters.get("brand") and (row.tyre_brand or "") != filters.brand:
                continue

            next_row = group_rows[index + 1] if index + 1 < len(group_rows) else None
            next_request_date = getdate(next_row.request_date) if next_row else None
            days_in_service = date_diff(next_request_date, request_date) if next_row else None
            end_odometer = flt(next_row.odometer_reading) if next_row else None
            start_odometer = flt(row.odometer_reading)
            distance_covered = (
                flt(end_odometer) - flt(start_odometer)
                if next_row and end_odometer is not None
                else None
            )

            data.append(
                {
                    "vehicle": row.vehicle,
                    "license_plate": row.license_plate,
                    "wheel_position": row.wheel_position,
                    "tyre_request": row.tyre_request,
                    "request_date": request_date,
                    "item": row.item,
                    "item_name": row.item_name,
                    "tyre_brand": row.tyre_brand,
                    "supplier": row.supplier,
                    "start_odometer": start_odometer,
                    "next_tyre_request": next_row.tyre_request if next_row else None,
                    "next_request_date": next_request_date,
                    "end_odometer": end_odometer,
                    "distance_covered": distance_covered,
                    "days_in_service": days_in_service,
                    "replacement_brand": next_row.tyre_brand if next_row else None,
                    "current_status": "Replaced" if next_row else "Active",
                }
            )

    return data
