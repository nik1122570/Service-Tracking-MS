# Copyright (c) 2026, Nickson  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


PERMANENT_FIXED_EXPENSES = (
	"Driver Mileage",
	"Salaries",
	"Depreciation",
	"Management Fee",
	"Tyres",
	"Car Wash",
	"Maintenance Fee",
)


class SimulationRoutes(Document):
	def validate(self):
		self.ensure_permanent_fixed_expenses()
		self.calculate_route_totals()
		self.validate_duplicate_fixed_expenses()

	def ensure_permanent_fixed_expenses(self):
		default_expenses = {
			expense: get_default_fixed_expense_row(expense)
			for expense in PERMANENT_FIXED_EXPENSES
		}
		existing_expenses = set()

		for row in self.fixed_expenses:
			if not row.expense:
				continue

			existing_expenses.add(row.expense)

			if row.expense in default_expenses:
				row.currency = default_expenses[row.expense].get("currency")
				row.amount = default_expenses[row.expense].get("amount")

		for expense in PERMANENT_FIXED_EXPENSES:
			if expense in existing_expenses:
				continue

			self.append("fixed_expenses", default_expenses[expense])
			existing_expenses.add(expense)

	def calculate_route_totals(self):
		self.total_distance = sum(flt(row.distance) for row in self.trip_steps)
		self.total_fuel_consumption_qty = sum(flt(row.fuel_consumption_qty) for row in self.trip_steps)

	def validate_duplicate_fixed_expenses(self):
		seen_expenses = set()

		for row in self.fixed_expenses:
			if not row.expense:
				continue

			if row.expense in seen_expenses:
				frappe.throw(
					_("Expense {0} is already added in Fixed Expenses. Remove the duplicate row {1}.").format(
						frappe.bold(row.expense),
						frappe.bold(row.idx),
					)
				)

			seen_expenses.add(row.expense)


def get_default_fixed_expense_row(expense):
	defaults = frappe.db.get_value(
		"Fixed Expenses",
		expense,
		["currency", "fixed_value"],
		as_dict=True,
	) or {}

	return {
		"expense": expense,
		"currency": defaults.get("currency"),
		"amount": flt(defaults.get("fixed_value")),
	}


@frappe.whitelist()
def get_permanent_fixed_expenses():
	return [get_default_fixed_expense_row(expense) for expense in PERMANENT_FIXED_EXPENSES]
