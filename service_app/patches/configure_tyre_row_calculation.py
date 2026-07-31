import frappe


def execute():
	if frappe.db.exists("Fixed Expenses", "Tyres"):
		frappe.db.set_value(
			"Fixed Expenses",
			"Tyres",
			{
				"calculation_method": None,
				"fixed_value": 0,
			},
			update_modified=False,
		)

	for route in frappe.get_all("Simulation Routes", pluck="name"):
		frappe.db.set_value(
			"Fixed Expenses Table",
			{
				"parent": route,
				"parenttype": "Simulation Routes",
				"parentfield": "fixed_expenses",
				"expense": "Tyres",
			},
			"amount",
			0,
			update_modified=False,
		)

	for trip_name in frappe.get_all("Trip Simulation", pluck="name"):
		doc = frappe.get_doc("Trip Simulation", trip_name)
		updated = False

		for row in doc.trip_expenses_outline:
			if row.expense != "Tyres":
				continue

			frappe.db.set_value(
				row.doctype,
				row.name,
				{
					"quantity": doc.total_distance_km,
					"rate": 0,
					"amount": 0,
					"description": "Tyres are calculated from Trip Settings based on Vehicle Truck Type",
				},
				update_modified=False,
			)
			row.quantity = doc.total_distance_km
			row.rate = 0
			row.amount = 0
			updated = True

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
