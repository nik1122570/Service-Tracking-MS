# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict
import json

import frappe
from frappe import _
from frappe.utils import flt, getdate


JOB_CARD_LABOUR_ITEM_FIELDS = ("default_labour_item", "custom_default_labour_item")
PURCHASE_ORDER_JOB_CARD_LINK_FIELDS = ("custom_job_card_link", "eah_job_card", "job_card_link")


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    columns = get_columns()
    records = get_invoice_linked_maintenance_records(filters)
    if not records:
        return columns, [], _("No billed maintenance cost records found for the selected filters."), None

    vehicle_details = get_vehicle_details({record.vehicle for record in records if record.vehicle})
    data = build_report_rows(records, vehicle_details)
    chart = get_chart_data(data)

    return columns, data, None, chart


def validate_filters(filters):
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required."))

    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("From Date cannot be greater than To Date."))


def get_columns():
    return [
        {
            "label": _("Month"),
            "fieldname": "month_label",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Vehicle"),
            "fieldname": "vehicle",
            "fieldtype": "Link",
            "options": "Vehicle",
            "width": 150,
        },
        {
            "label": _("License Plate"),
            "fieldname": "license_plate",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("Job Cards"),
            "fieldname": "job_cards",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": _("Spares Cost"),
            "fieldname": "spares_cost",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": _("Service Charges"),
            "fieldname": "service_charges",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": _("Total Maintenance Cost"),
            "fieldname": "total_maintenance_cost",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 160,
        },
        {
            "label": _("Currency"),
            "fieldname": "currency",
            "fieldtype": "Link",
            "options": "Currency",
            "hidden": 1,
        },
    ]


def parse_multi_select_filter(values):
    if not values:
        return []

    if isinstance(values, list):
        return [value for value in values if value]

    if isinstance(values, str):
        parsed_values = None
        try:
            parsed_values = json.loads(values)
        except Exception:
            parsed_values = [value.strip() for value in values.split(",") if value.strip()]

        if isinstance(parsed_values, str):
            return [parsed_values]

        return [value for value in parsed_values if value]

    return [values]


def get_invoice_linked_maintenance_records(filters):
    vehicles = parse_multi_select_filter(filters.get("vehicles"))
    po_job_card_link_expression = get_purchase_order_job_card_link_expression()
    if not po_job_card_link_expression:
        return []

    job_card_labour_item_field = get_first_existing_table_column(
        "EAH Job Card",
        JOB_CARD_LABOUR_ITEM_FIELDS,
    )
    job_card_labour_item_select = (
        f"jc.`{job_card_labour_item_field}` AS job_card_labour_item"
        if job_card_labour_item_field
        else "'' AS job_card_labour_item"
    )
    conditions = [
        "pi.docstatus = 1",
        "pii.parenttype = 'Purchase Invoice'",
        "COALESCE(pii.purchase_order, '') != ''",
        f"{po_job_card_link_expression} IS NOT NULL",
        "pi.posting_date BETWEEN %(from_date)s AND %(to_date)s",
    ]
    values = {
        "from_date": filters.from_date,
        "to_date": filters.to_date,
    }

    if vehicles:
        conditions.append("jc.vehicle IN %(vehicles)s")
        values["vehicles"] = tuple(vehicles)

    records = frappe.db.sql(
        f"""
        SELECT
            pi.posting_date,
            jc.name AS job_card,
            jc.vehicle,
            pii.item_code,
            pii.base_net_amount AS total_maintenance_cost,
            {job_card_labour_item_select}
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
            ON pi.name = pii.parent
        INNER JOIN `tabPurchase Order` po
            ON po.name = pii.purchase_order
        INNER JOIN `tabEAH Job Card` jc
            ON jc.name = {po_job_card_link_expression}
        WHERE {' AND '.join(conditions)}
        ORDER BY pi.posting_date ASC, jc.vehicle ASC, pi.name ASC, pii.idx ASC
        """,
        values,
        as_dict=True,
    )

    classify_invoice_item_costs(records)
    return records


def get_purchase_order_job_card_link_expression():
    link_fields = get_existing_table_columns(
        "Purchase Order",
        PURCHASE_ORDER_JOB_CARD_LINK_FIELDS,
    )

    if not link_fields:
        return ""

    return "COALESCE({0})".format(
        ", ".join(f"NULLIF(po.`{fieldname}`, '')" for fieldname in link_fields)
    )


def classify_invoice_item_costs(records):
    default_labour_item = get_default_labour_item_from_settings()

    for record in records:
        labour_item = (record.get("job_card_labour_item") or default_labour_item or "").strip()
        amount = flt(record.get("total_maintenance_cost"))

        if labour_item and record.get("item_code") == labour_item:
            record.service_charges = amount
            record.spares_cost = 0
        else:
            record.service_charges = 0
            record.spares_cost = amount


def get_default_labour_item_from_settings():
    if not frappe.db.exists("DocType", "Service App Settings"):
        return ""

    meta = frappe.get_meta("Service App Settings")
    for fieldname in JOB_CARD_LABOUR_ITEM_FIELDS:
        if not meta.get_field(fieldname):
            continue

        value = frappe.db.get_single_value("Service App Settings", fieldname)
        return (value or "").strip() if isinstance(value, str) else value or ""

    return ""


def get_first_existing_table_column(doctype, candidate_fields):
    columns = get_existing_table_columns(doctype, candidate_fields)
    return columns[0] if columns else None


def get_existing_table_columns(doctype, candidate_fields):
    if not frappe.db.exists("DocType", doctype):
        return []

    try:
        columns = set(frappe.db.get_table_columns(doctype))
    except Exception:
        return []

    return [fieldname for fieldname in candidate_fields if fieldname in columns]


def get_vehicle_details(vehicle_names):
    if not vehicle_names:
        return {}

    vehicles = frappe.get_all(
        "Vehicle",
        filters={"name": ["in", list(vehicle_names)]},
        fields=["name", "license_plate", "model", "make"],
    )

    return {
        vehicle.name: vehicle
        for vehicle in vehicles
    }


def build_report_rows(records, vehicle_details):
    currency = frappe.db.get_single_value("Global Defaults", "default_currency")
    unassigned_vehicle = _("Unassigned Vehicle")
    monthly_cost_map = defaultdict(
        lambda: {
            "job_cards": set(),
            "spares_cost": 0.0,
            "service_charges": 0.0,
            "total_maintenance_cost": 0.0,
        }
    )

    for record in records:
        posting_date = getdate(record.posting_date)
        month_key = posting_date.strftime("%Y-%m")
        month_label = posting_date.strftime("%b %Y")
        vehicle = record.vehicle or unassigned_vehicle

        bucket = monthly_cost_map[(month_key, month_label, vehicle)]
        if record.job_card:
            bucket["job_cards"].add(record.job_card)
        bucket["spares_cost"] += flt(record.spares_cost)
        bucket["service_charges"] += flt(record.service_charges)
        bucket["total_maintenance_cost"] += flt(record.total_maintenance_cost)

    rows = []
    for (month_key, month_label, vehicle), totals in sorted(monthly_cost_map.items()):
        vehicle_info = vehicle_details.get(vehicle, {}) if vehicle != unassigned_vehicle else {}
        rows.append(
            {
                "month_key": month_key,
                "month_label": month_label,
                "vehicle": vehicle,
                "license_plate": vehicle_info.get("license_plate"),
                "job_cards": len(totals["job_cards"]),
                "spares_cost": flt(totals["spares_cost"]),
                "service_charges": flt(totals["service_charges"]),
                "total_maintenance_cost": flt(totals["total_maintenance_cost"]),
                "currency": currency,
            }
        )

    return rows


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

        dataset_points[vehicle][month_label] = flt(row.get("total_maintenance_cost"))

    datasets = []
    for vehicle, points in dataset_points.items():
        datasets.append(
            {
                "name": vehicle,
                "values": [points.get(label, 0) for label in labels],
            }
        )

    return {
        "data": {
            "labels": labels,
            "datasets": datasets,
        },
        "type": "bar",
        "fieldtype": "Currency",
    }
