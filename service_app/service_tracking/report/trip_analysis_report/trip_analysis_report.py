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
	message = None if data else _("No Trip Simulation records found for the selected filters.")
	report_summary = get_report_summary(data)

	return columns, data, message, None, report_summary


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
			"label": _("Fuel Litres Used"),
			"fieldname": "total_fuel_consumption_qty_ratio",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("Management Fee"),
			"fieldname": "management_fee",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140,
		},
		{
			"label": _("Maintenance Fee"),
			"fieldname": "maintenance_fee",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 145,
		},
		{
			"label": _("Tyres Cost"),
			"fieldname": "tyres_cost",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 130,
		},
		{
			"label": _("Total Trip Expenses"),
			"fieldname": "total_trip_expenses",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 155,
		},
		{
			"label": _("Net Profit"),
			"fieldname": "net_profit",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 160,
		},
		{"label": _("Net Profit Margin %"), "fieldname": "net_profit_margin", "fieldtype": "Percent", "width": 145},
		{"label": _("Targeted Net Profit %"), "fieldname": "targeted_net_profit", "fieldtype": "Percent", "width": 155},
		{"label": _("Margin Variance %"), "fieldname": "margin_variance", "fieldtype": "Percent", "width": 140},
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
			trip.total_fuel_consumption_qty_ratio,
			IFNULL(expenses.management_fee, 0) AS management_fee,
			IFNULL(expenses.maintenance_fee, 0) AS maintenance_fee,
			IFNULL(expenses.tyres_cost, 0) AS tyres_cost,
			IFNULL(expenses.total_trip_expenses, 0) AS total_trip_expenses,
			trip.net_profit,
			trip.net_profit_ AS net_profit_margin,
			trip.targeted_net_profit,
			trip.net_profit_ - IFNULL(trip.targeted_net_profit, 0) AS margin_variance,
			trip.departure_date,
			trip.return_date,
			trip.days_in_trip,
			trip.cost_center
		FROM `tabTrip Simulation` trip
		LEFT JOIN (
			SELECT
				parent,
				SUM(CASE WHEN expense = 'Management Fee' THEN amount ELSE 0 END) AS management_fee,
				SUM(CASE WHEN expense = 'Maintenance Fee' THEN amount ELSE 0 END) AS maintenance_fee,
				SUM(CASE WHEN expense = 'Tyres' THEN amount ELSE 0 END) AS tyres_cost,
				SUM(amount) AS total_trip_expenses
			FROM `tabTrip Simulation Table`
			WHERE parenttype = 'Trip Simulation'
				AND parentfield = 'trip_expenses_outline'
			GROUP BY parent
		) expenses ON expenses.parent = trip.name
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
		row.total_fuel_consumption_qty_ratio = flt(row.total_fuel_consumption_qty_ratio)
		row.management_fee = flt(row.management_fee)
		row.maintenance_fee = flt(row.maintenance_fee)
		row.tyres_cost = flt(row.tyres_cost)
		row.total_trip_expenses = flt(row.total_trip_expenses)
		row.net_profit = flt(row.net_profit)
		row.net_profit_margin = flt(row.net_profit_margin)
		row.targeted_net_profit = flt(row.targeted_net_profit)
		row.margin_variance = flt(row.margin_variance)
		row.days_in_trip = int(row.days_in_trip or 0)

	return rows


def get_docstatus(status):
	status_map = {
		"Draft": 0,
		"Submitted": 1,
		"Cancelled": 2,
	}
	return status_map.get(status)


def get_report_summary(data):
	currency = frappe.db.get_single_value("Global Defaults", "default_currency")
	total_revenue = sum(flt(row.get("expected_revenue")) for row in data)
	total_expenses = sum(flt(row.get("total_trip_cost")) for row in data)
	profit_loss = total_revenue - total_expenses

	return [
		{
			"value": total_revenue,
			"label": _("Total Revenue Earned"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green",
		},
		{
			"value": sum(flt(row.get("total_fuel_costs")) for row in data),
			"label": _("Fuel Expense"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Orange",
		},
		{
			"value": sum(flt(row.get("total_fuel_consumption_qty_ratio")) for row in data),
			"label": _("Fuel Litres Used"),
			"datatype": "Float",
			"indicator": "Blue",
		},
		{
			"value": total_expenses,
			"label": _("Total Expenses"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Red",
		},
		{
			"value": profit_loss,
			"label": _("Profit / Loss"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green" if profit_loss >= 0 else "Red",
		},
	]
