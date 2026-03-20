# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict
import json

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    columns = get_columns()
    records = get_job_card_records(filters)
    if not records:
        return columns, [], _("No maintenance cost records found for the selected filters."), None

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


def get_job_card_records(filters):
    vehicles = parse_multi_select_filter(filters.get("vehicles"))

    job_card_filters = {
        "docstatus": 1,
        "service_date": ["between", [filters.from_date, filters.to_date]],
    }
    if vehicles:
        job_card_filters["vehicle"] = ["in", vehicles]

    return frappe.get_all(
        "EAH Job Card",
        filters=job_card_filters,
        fields=[
            "vehicle",
            "service_date",
            "spares_cost",
            "service_charges",
            "total_vat_exclusive",
        ],
        order_by="service_date asc, vehicle asc",
    )


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
    monthly_cost_map = defaultdict(
        lambda: {
            "job_cards": 0,
            "spares_cost": 0.0,
            "service_charges": 0.0,
            "total_maintenance_cost": 0.0,
        }
    )

    for record in records:
        service_date = getdate(record.service_date)
        month_key = service_date.strftime("%Y-%m")
        month_label = service_date.strftime("%b %Y")
        vehicle = record.vehicle or _("Unassigned Vehicle")

        bucket = monthly_cost_map[(month_key, month_label, vehicle)]
        bucket["job_cards"] += 1
        bucket["spares_cost"] += flt(record.spares_cost)
        bucket["service_charges"] += flt(record.service_charges)
        bucket["total_maintenance_cost"] += flt(record.total_vat_exclusive)

    rows = []
    for (month_key, month_label, vehicle), totals in sorted(monthly_cost_map.items()):
        vehicle_info = vehicle_details.get(vehicle, {}) if vehicle != _("Unassigned Vehicle") else {}
        rows.append(
            {
                "month_key": month_key,
                "month_label": month_label,
                "vehicle": vehicle,
                "license_plate": vehicle_info.get("license_plate"),
                "job_cards": totals["job_cards"],
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
