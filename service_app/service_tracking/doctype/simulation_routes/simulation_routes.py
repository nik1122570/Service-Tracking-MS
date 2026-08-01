# Copyright (c) 2026, Nickson  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from service_app.service_tracking.expense_labels import (
	STANDARD_FIXED_EXPENSES,
	canonical_expense_label,
	normalize_expense_name,
)


class SimulationRoutes(Document):
	def validate(self):
		self.ensure_permanent_fixed_expenses()
		self.calculate_route_totals()
		self.validate_duplicate_fixed_expenses()

	def ensure_permanent_fixed_expenses(self):
		default_expenses = {
			expense: get_default_fixed_expense_row(expense)
			for expense in STANDARD_FIXED_EXPENSES
		}
		existing_expenses = {}
		unique_rows = []

		for row in self.fixed_expenses:
			if not row.expense:
				continue

			canonical_expense = canonical_expense_label(row.expense)
			expense_key = normalize_expense_name(canonical_expense)
			if expense_key in existing_expenses:
				continue

			row.expense = canonical_expense
			existing_expenses[expense_key] = row
			unique_rows.append(row)

			if canonical_expense in default_expenses:
				row.currency = default_expenses[canonical_expense].get("currency")
				row.amount = default_expenses[canonical_expense].get("amount")
			else:
				ensure_fixed_expense_row_defaults(row)

		self.fixed_expenses = unique_rows
		for expense in STANDARD_FIXED_EXPENSES:
			expense_key = normalize_expense_name(expense)
			if expense_key in existing_expenses:
				continue

			self.append("fixed_expenses", default_expenses[expense])
			existing_expenses[expense_key] = self.fixed_expenses[-1]

	def calculate_route_totals(self):
		self.total_distance = sum(flt(row.distance) for row in self.trip_steps)
		self.total_fuel_consumption_qty = 0

	def validate_duplicate_fixed_expenses(self):
		seen_expenses = set()

		for row in self.fixed_expenses:
			if not row.expense:
				continue

			expense_key = normalize_expense_name(row.expense)
			if expense_key in seen_expenses:
				frappe.throw(
					_("Expense {0} is already added in Fixed Expenses. Remove the duplicate row {1}.").format(
						frappe.bold(row.expense),
						frappe.bold(row.idx),
					)
				)

			seen_expenses.add(expense_key)


def get_default_fixed_expense_row(expense):
	expense = canonical_expense_label(expense)
	defaults = frappe.db.get_value(
		"Fixed Expenses",
		expense,
		["currency", "fixed_value", "calculation_method"],
		as_dict=True,
	) or {}

	return {
		"expense": expense,
		"currency": defaults.get("currency") or get_default_currency(),
		"amount": (
			0
			if (
				expense == "Tyres"
				or defaults.get("calculation_method") == "Percentage of Expected Revenue"
			)
			else flt(defaults.get("fixed_value"))
		),
	}


def ensure_fixed_expense_row_defaults(row):
	if not row.expense:
		return

	defaults = frappe.db.get_value(
		"Fixed Expenses",
		row.expense,
		["currency", "fixed_value"],
		as_dict=True,
	) or {}

	if not row.currency:
		row.currency = defaults.get("currency") or get_default_currency()
	if row.amount in (None, ""):
		row.amount = flt(defaults.get("fixed_value"))


def get_default_currency():
	company = frappe.defaults.get_user_default("Company")
	return (
		frappe.db.get_single_value("Global Defaults", "default_currency")
		or (frappe.db.get_value("Company", company, "default_currency") if company else None)
		or frappe.db.get_value("Company", {}, "default_currency")
	)


@frappe.whitelist()
def get_permanent_fixed_expenses():
	return [get_default_fixed_expense_row(expense) for expense in STANDARD_FIXED_EXPENSES]
