import frappe


def execute():
	if not frappe.db.exists("DocType", "Trip Settings"):
		return

	defaults = {
		"management_fee_percentage": 3,
		"salaries_percentage": 10,
		"heavy_truck_vehicle_cost": 85000000,
		"light_truck_vehicle_cost": 45000000,
		"heavy_truck_tyre_price": 0,
		"heavy_truck_number_of_tyres": 0,
		"heavy_truck_tyre_lifecycle_km": 0,
		"light_truck_tyre_price": 0,
		"light_truck_number_of_tyres": 0,
		"light_truck_tyre_lifecycle_km": 0,
	}

	for fieldname, default_value in defaults.items():
		current_value = frappe.db.get_single_value("Trip Settings", fieldname)
		if current_value in (None, "", 0, 0.0):
			frappe.db.set_single_value("Trip Settings", fieldname, default_value)
