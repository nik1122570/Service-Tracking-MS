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
	message = None if data else _("No Trip Simulation records found for the selected filters.")

	return columns, data, message, chart


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date"):
		if getdate(filters.from_date) > getdate(filters.to_date):
			frappe.throw(_("From Date cannot be greater than To Date."))


def get_columns():
	return [
		{"label": _("Trip"), "fieldname": "trip", "fieldtype": "Link", "options": "Trip Simulation", "width": 180},
		{"label": _("Transaction Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 120},
		{"label": _("Route"), "fieldname": "route", "fieldtype": "Link", "options": "Simulation Routes", "width": 170},
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 150},
		{"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 140},
		{
			"label": _("Revenue of the Trip"),
			"fieldname": "expected_revenue",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 155,
		},
		{
			"label": _("Total Trip Costs"),
			"fieldname": "total_trip_cost",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 150,
		},
		{
			"label": _("Total Fuel Costs"),
			"fieldname": "total_fuel_costs",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 145,
		},
		{
			"label": _("Gross Profit Amount"),
			"fieldname": "trip_gross_profit_amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 160,
		},
		{"label": _("Gross Profit %"), "fieldname": "trip_gross_profit", "fieldtype": "Percent", "width": 120},
		{"label": _("Departure Date"), "fieldname": "departure_date", "fieldtype": "Date", "width": 120},
		{"label": _("Return Date"), "fieldname": "return_date", "fieldtype": "Date", "width": 120},
		{"label": _("Days in Trip"), "fieldname": "days_in_trip", "fieldtype": "Int", "width": 105},
		{"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 160},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]


def get_data(filters):
	conditions = []
	values = {}

	if filters.get("from_date"):
		conditions.append("trip.transaction_date >= %(from_date)s")
		values["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("trip.transaction_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	if filters.get("project"):
		conditions.append("trip.project = %(project)s")
		values["project"] = filters.project

	if filters.get("route"):
		conditions.append("trip.route = %(route)s")
		values["route"] = filters.route

	if filters.get("vehicle"):
		conditions.append("trip.vehicle = %(vehicle)s")
		values["vehicle"] = filters.vehicle

	if filters.get("cost_center"):
		conditions.append("trip.cost_center = %(cost_center)s")
		values["cost_center"] = filters.cost_center

	docstatus = get_docstatus(filters.get("docstatus"))
	if docstatus is not None:
		conditions.append("trip.docstatus = %(docstatus)s")
		values["docstatus"] = docstatus
	else:
		conditions.append("trip.docstatus < 2")

	where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
	currency = frappe.db.get_single_value("Global Defaults", "default_currency")

	rows = frappe.db.sql(
		f"""
		SELECT
			trip.name AS trip,
			trip.transaction_date,
			trip.route,
			trip.project,
			trip.vehicle,
			trip.expected_revenue,
			trip.total_trip_cost,
			trip.total_fuel_costs,
			trip.trip_gross_profit_amount,
			trip.trip_gross_profit,
			trip.departure_date,
			trip.return_date,
			trip.days_in_trip,
			trip.cost_center
		FROM `tabTrip Simulation` trip
		{where_clause}
		ORDER BY trip.transaction_date ASC, trip.name ASC
		""",
		values,
		as_dict=True,
	)

	for row in rows:
		row.currency = currency
		row.expected_revenue = flt(row.expected_revenue)
		row.total_trip_cost = flt(row.total_trip_cost)
		row.total_fuel_costs = flt(row.total_fuel_costs)
		row.trip_gross_profit_amount = flt(row.trip_gross_profit_amount)
		row.trip_gross_profit = flt(row.trip_gross_profit)
		row.days_in_trip = int(row.days_in_trip or 0)

	return rows


def get_docstatus(status):
	status_map = {
		"Draft": 0,
		"Submitted": 1,
		"Cancelled": 2,
	}
	return status_map.get(status)


def get_chart_data(data):
	if not data:
		return None

	labels = [row.get("trip") for row in data]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Revenue of the Trip"),
					"values": [flt(row.get("expected_revenue")) for row in data],
				},
				{
					"name": _("Total Trip Cost"),
					"values": [flt(row.get("total_trip_cost")) for row in data],
				},
			],
		},
		"type": "line",
	}
