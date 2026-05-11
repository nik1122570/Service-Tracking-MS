# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	columns = get_columns()
	data = get_data(filters)
	chart = get_chart_data(data)
	message = None if data else _("No trip entitlement records found for the selected filters.")

	return columns, data, message, chart


def validate_filters(filters):
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))

	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be greater than To Date."))


def get_columns():
	return [
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 160},
		{"label": _("Truck / Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 140},
		{"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
		{"label": _("Drivers Used"), "fieldname": "drivers_used", "fieldtype": "Small Text", "width": 170},
		{"label": _("Trailer 1 Used"), "fieldname": "trailer_1_used", "fieldtype": "Small Text", "width": 140},
		{"label": _("Trailer 2 Used"), "fieldname": "trailer_2_used", "fieldtype": "Small Text", "width": 140},
		{"label": _("Trip Count"), "fieldname": "trip_count", "fieldtype": "Int", "width": 100},
		{"label": _("Container Count"), "fieldname": "container_count", "fieldtype": "Float", "width": 125},
		{
			"label": _("Expected Revenue"),
			"fieldname": "expected_revenue",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 145,
		},
		{"label": _("Fuel Litres To Reimburse"), "fieldname": "fuel_litres", "fieldtype": "Float", "width": 165},
		{
			"label": _("Mileage Demanded"),
			"fieldname": "mileage_demanded",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 145,
		},
		{"label": _("Revenue Status"), "fieldname": "revenue_status", "fieldtype": "Data", "width": 120},
		{"label": _("Fuel Status"), "fieldname": "fuel_status", "fieldtype": "Data", "width": 120},
		{"label": _("Mileage Status"), "fieldname": "mileage_status", "fieldtype": "Data", "width": 120},
		{"label": _("Settlement Batches"), "fieldname": "settlement_batches", "fieldtype": "Small Text", "width": 180},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]


def get_data(filters):
	conditions = [
		"trip.docstatus = 1",
		"trip.trip_date BETWEEN %(from_date)s AND %(to_date)s",
		"item.parenttype = 'Container Trip Log'",
		"item.parentfield = 'entitlement_items'",
	]
	values = {
		"from_date": filters.from_date,
		"to_date": filters.to_date,
	}

	if filters.get("project"):
		conditions.append("trip.project = %(project)s")
		values["project"] = filters.project

	if filters.get("vehicle"):
		conditions.append("trip.vehicle = %(vehicle)s")
		values["vehicle"] = filters.vehicle

	if filters.get("driver"):
		conditions.append("trip.driver = %(driver)s")
		values["driver"] = filters.driver

	if filters.get("entitlement_status"):
		conditions.append("item.status = %(entitlement_status)s")
		values["entitlement_status"] = filters.entitlement_status

	currency = frappe.db.get_single_value("Global Defaults", "default_currency")

	rows = frappe.db.sql(
		f"""
		SELECT
			trip.project,
			trip.vehicle,
			vehicle.license_plate,
			GROUP_CONCAT(DISTINCT NULLIF(trip.driver, '') ORDER BY trip.driver SEPARATOR ', ') AS drivers_used,
			GROUP_CONCAT(DISTINCT NULLIF(trip.trailer_1, '') ORDER BY trip.trailer_1 SEPARATOR ', ') AS trailer_1_used,
			GROUP_CONCAT(DISTINCT NULLIF(trip.trailer_2, '') ORDER BY trip.trailer_2 SEPARATOR ', ') AS trailer_2_used,
			COUNT(DISTINCT trip.name) AS trip_count,
			SUM(CASE WHEN item.entitlement_type = 'Revenue' THEN item.quantity ELSE 0 END) AS container_count,
			SUM(CASE WHEN item.entitlement_type = 'Revenue' THEN item.amount ELSE 0 END) AS expected_revenue,
			SUM(CASE WHEN item.entitlement_type = 'Fuel' THEN item.quantity ELSE 0 END) AS fuel_litres,
			SUM(CASE WHEN item.entitlement_type = 'Mileage' THEN item.amount ELSE 0 END) AS mileage_demanded,
			GROUP_CONCAT(DISTINCT CASE WHEN item.entitlement_type = 'Revenue' THEN item.status END ORDER BY item.status SEPARATOR ', ') AS revenue_status,
			GROUP_CONCAT(DISTINCT CASE WHEN item.entitlement_type = 'Fuel' THEN item.status END ORDER BY item.status SEPARATOR ', ') AS fuel_status,
			GROUP_CONCAT(DISTINCT CASE WHEN item.entitlement_type = 'Mileage' THEN item.status END ORDER BY item.status SEPARATOR ', ') AS mileage_status,
			GROUP_CONCAT(DISTINCT NULLIF(item.trip_settlement_batch, '') ORDER BY item.trip_settlement_batch SEPARATOR ', ') AS settlement_batches
		FROM `tabContainer Trip Log` trip
		INNER JOIN `tabContainer Trip Entitlement Item` item
			ON item.parent = trip.name
		LEFT JOIN `tabVehicle` vehicle
			ON vehicle.name = trip.vehicle
		WHERE {' AND '.join(conditions)}
		GROUP BY trip.project, trip.vehicle, vehicle.license_plate
		ORDER BY trip.project ASC, trip.vehicle ASC
		""",
		values,
		as_dict=True,
	)

	for row in rows:
		row.currency = currency
		row.trip_count = int(row.trip_count or 0)
		row.container_count = flt(row.container_count)
		row.expected_revenue = flt(row.expected_revenue)
		row.fuel_litres = flt(row.fuel_litres)
		row.mileage_demanded = flt(row.mileage_demanded)

	return rows


def get_chart_data(data):
	if not data:
		return None

	top_rows = sorted(data, key=lambda row: flt(row.get("expected_revenue")), reverse=True)[:10]
	labels = [row.get("license_plate") or row.get("vehicle") or _("Unspecified Truck") for row in top_rows]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Expected Revenue"),
					"values": [flt(row.get("expected_revenue")) for row in top_rows],
				},
				{
					"name": _("Mileage Demanded"),
					"values": [flt(row.get("mileage_demanded")) for row in top_rows],
				},
			],
		},
		"type": "bar",
	}

