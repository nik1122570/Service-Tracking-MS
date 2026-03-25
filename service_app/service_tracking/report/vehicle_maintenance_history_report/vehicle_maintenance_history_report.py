# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    columns = get_columns()
    data = get_report_data(filters)

    if not data:
        return columns, [], _("No vehicle maintenance history records found for the selected filters.")

    return columns, data


def validate_filters(filters):
    if filters.get("from_date") and filters.get("to_date"):
        if getdate(filters.from_date) > getdate(filters.to_date):
            frappe.throw(_("From Date cannot be greater than To Date."))


def get_columns():
    return [
        {
            "label": _("EAH Job Card"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "EAH Job Card",
            "width": 150,
        },
        {
            "label": _("Vehicle"),
            "fieldname": "vehicle",
            "fieldtype": "Link",
            "options": "Vehicle",
            "width": 140,
        },
        {
            "label": _("Service Date"),
            "fieldname": "service_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": _("Supplier"),
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 160,
        },
        {
            "label": _("Driver Name"),
            "fieldname": "driver_name",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": _("Total VAT Exclusive"),
            "fieldname": "total_vat_exclusive",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": _("Spares Cost"),
            "fieldname": "spares_cost",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": _("Service Charges"),
            "fieldname": "service_charges",
            "fieldtype": "Currency",
            "width": 130,
        },
    ]


def get_report_data(filters):
    job_card_filters = {"docstatus": 1}

    if filters.get("vehicle"):
        job_card_filters["vehicle"] = filters.vehicle

    if filters.get("from_date") and filters.get("to_date"):
        job_card_filters["service_date"] = ["between", [filters.from_date, filters.to_date]]
    elif filters.get("from_date"):
        job_card_filters["service_date"] = [">=", filters.from_date]
    elif filters.get("to_date"):
        job_card_filters["service_date"] = ["<=", filters.to_date]

    return frappe.get_all(
        "EAH Job Card",
        filters=job_card_filters,
        fields=[
            "name",
            "vehicle",
            "service_date",
            "supplier",
            "driver_name",
            "total_vat_exclusive",
            "spares_cost",
            "service_charges",
        ],
        order_by="service_date desc, creation desc",
    )
