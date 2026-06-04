import frappe


PERCENTAGE_EXPENSES = {
	"Management Fee": 3,
	"Maintenance Fee": 10,
}


def execute():
	for expense, percentage in PERCENTAGE_EXPENSES.items():
		if not frappe.db.exists("Fixed Expenses", expense):
			continue

		frappe.db.set_value(
			"Fixed Expenses",
			expense,
			{
				"calculation_method": "Percentage of Expected Revenue",
				"percentage": percentage,
			},
			update_modified=False,
		)

	for route in frappe.get_all("Simulation Routes", pluck="name"):
		for expense in PERCENTAGE_EXPENSES:
			frappe.db.set_value(
				"Fixed Expenses Table",
				{
					"parent": route,
					"parenttype": "Simulation Routes",
					"parentfield": "fixed_expenses",
					"expense": expense,
				},
				"amount",
				0,
				update_modified=False,
			)

	recalculate_trip_expenses()


def recalculate_trip_expenses():
	for trip_name in frappe.get_all("Trip Simulation", pluck="name"):
		doc = frappe.get_doc("Trip Simulation", trip_name)
		doc.apply_calculated_expenses()
		doc.calculate_totals()

		for row in doc.trip_expenses_outline:
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
