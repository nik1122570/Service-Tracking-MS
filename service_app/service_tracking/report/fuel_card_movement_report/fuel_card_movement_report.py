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
	message = None if data else _("No Fuel Card movements found for the selected filters.")
	report_summary = get_report_summary(data)

	return columns, data, message, None, report_summary


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date"):
		if getdate(filters.from_date) > getdate(filters.to_date):
			frappe.throw(_("From Date cannot be greater than To Date."))


def get_columns():
	return [
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Datetime", "width": 150},
		{"label": _("Fuel Card"), "fieldname": "fuel_card", "fieldtype": "Link", "options": "Fuel Card", "width": 170},
		{"label": _("Movement"), "fieldname": "transaction_type", "fieldtype": "Data", "width": 130},
		{"label": _("Reference Type"), "fieldname": "reference_doctype", "fieldtype": "Data", "width": 150},
		{"label": _("Reference"), "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 170},
		{"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 130},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Drivers", "width": 130},
		{"label": _("In Qty (Ltr)"), "fieldname": "in_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Out Qty (Ltr)"), "fieldname": "out_qty", "fieldtype": "Float", "width": 115},
		{"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": _("Amount In"), "fieldname": "amount_in", "fieldtype": "Currency", "options": "currency", "width": 125},
		{"label": _("Amount Out"), "fieldname": "amount_out", "fieldtype": "Currency", "options": "currency", "width": 125},
		{"label": _("Balance Qty (Ltr)"), "fieldname": "balance_qty", "fieldtype": "Float", "width": 130},
		{"label": _("Balance Amount"), "fieldname": "balance_amount", "fieldtype": "Currency", "options": "currency", "width": 145},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 240},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]


def get_data(filters):
	conditions = []
	values = {}

	if filters.get("from_date"):
		conditions.append("DATE(posting_date) >= %(from_date)s")
		values["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("DATE(posting_date) <= %(to_date)s")
		values["to_date"] = filters.to_date

	if filters.get("fuel_card"):
		conditions.append("fuel_card = %(fuel_card)s")
		values["fuel_card"] = filters.fuel_card

	if filters.get("transaction_type"):
		conditions.append("transaction_type = %(transaction_type)s")
		values["transaction_type"] = filters.transaction_type

	if filters.get("vehicle"):
		conditions.append("vehicle = %(vehicle)s")
		values["vehicle"] = filters.vehicle

	if filters.get("reference_doctype"):
		conditions.append("reference_doctype = %(reference_doctype)s")
		values["reference_doctype"] = filters.reference_doctype

	where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
	currency = frappe.db.get_single_value("Global Defaults", "default_currency")

	rows = frappe.db.sql(
		f"""
		SELECT
			name,
			posting_date,
			fuel_card,
			transaction_type,
			reference_doctype,
			reference_name,
			vehicle,
			driver,
			litres_in AS in_qty,
			litres_out AS out_qty,
			rate,
			CASE WHEN litres_in > 0 THEN amount ELSE 0 END AS amount_in,
			CASE WHEN litres_out > 0 THEN amount ELSE 0 END AS amount_out,
			balance_litres_after_transaction AS balance_qty,
			balance_value_after_transaction AS balance_amount,
			remarks
		FROM `tabFuel Card Ledger Entry`
		{where_clause}
		ORDER BY posting_date ASC, creation ASC, name ASC
		""",
		values,
		as_dict=True,
	)

	for row in rows:
		row.currency = currency
		row.in_qty = flt(row.in_qty)
		row.out_qty = flt(row.out_qty)
		row.rate = flt(row.rate)
		row.amount_in = flt(row.amount_in)
		row.amount_out = flt(row.amount_out)
		row.balance_qty = flt(row.balance_qty)
		row.balance_amount = flt(row.balance_amount)

	return rows


def get_report_summary(data):
	currency = frappe.db.get_single_value("Global Defaults", "default_currency")
	total_in_qty = sum(flt(row.get("in_qty")) for row in data)
	total_out_qty = sum(flt(row.get("out_qty")) for row in data)
	total_amount_in = sum(flt(row.get("amount_in")) for row in data)
	total_amount_out = sum(flt(row.get("amount_out")) for row in data)
	last_balance_qty = flt(data[-1].get("balance_qty")) if data else 0
	last_balance_amount = flt(data[-1].get("balance_amount")) if data else 0

	return [
		{"value": total_in_qty, "label": _("Total In Qty (Ltr)"), "datatype": "Float"},
		{"value": total_out_qty, "label": _("Total Out Qty (Ltr)"), "datatype": "Float"},
		{"value": total_amount_in, "label": _("Total Amount In"), "datatype": "Currency", "currency": currency},
		{"value": total_amount_out, "label": _("Total Amount Out"), "datatype": "Currency", "currency": currency},
		{"value": last_balance_qty, "label": _("Closing Qty (Ltr)"), "datatype": "Float"},
		{"value": last_balance_amount, "label": _("Closing Amount"), "datatype": "Currency", "currency": currency},
	]
