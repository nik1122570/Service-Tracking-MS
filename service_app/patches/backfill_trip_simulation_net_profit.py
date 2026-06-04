import frappe


def execute():
	if not frappe.db.table_exists("Trip Simulation"):
		return
	if not frappe.db.has_column("Trip Simulation", "net_profit"):
		return
	if not frappe.db.has_column("Trip Simulation", "net_profit_"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabTrip Simulation`
		SET
			net_profit = IFNULL(expected_revenue, 0) - IFNULL(total_trip_cost, 0),
			net_profit_ = CASE
				WHEN IFNULL(expected_revenue, 0) = 0 THEN 0
				ELSE (
					(IFNULL(expected_revenue, 0) - IFNULL(total_trip_cost, 0))
					/ expected_revenue
				) * 100
			END
		"""
	)
