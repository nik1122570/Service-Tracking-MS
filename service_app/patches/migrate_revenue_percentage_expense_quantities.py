import frappe
from frappe.utils import flt


PERCENTAGE_EXPENSES = {
	"Management Fee": 3,
	"Maintenance Fee": 10,
}


def execute():
	for trip_name in frappe.get_all("Trip Simulation", pluck="name"):
		doc = frappe.get_doc("Trip Simulation", trip_name)
		updated = False

		for row in doc.trip_expenses_outline:
			if row.expense not in PERCENTAGE_EXPENSES:
				continue

			row.quantity = PERCENTAGE_EXPENSES[row.expense]
			row.rate = flt(doc.expected_revenue) / 100
			row.amount = flt(row.rate) * flt(row.quantity)
			row.description = f"{row.quantity:g}% of {flt(doc.expected_revenue):,.0f}"
			updated = True

			frappe.db.set_value(
				row.doctype,
				row.name,
				{
					"quantity": row.quantity,
					"rate": row.rate,
					"amount": row.amount,
					"description": row.description,
				},
				update_modified=False,
			)

		if not updated:
			continue

		doc.calculate_totals()
		frappe.db.set_value(
			doc.doctype,
			doc.name,
			{
				"total_trip_cost": doc.total_trip_cost,
				"net_profit": doc.net_profit,
				"net_profit_": doc.net_profit_,
			},
			update_modified=False,
		)
