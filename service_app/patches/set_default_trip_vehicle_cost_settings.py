import frappe


def execute():
	if not frappe.db.exists("DocType", "Trip Settings"):
		return

	defaults = {
		"heavy_truck_vehicle_cost": 85000000,
		"light_truck_vehicle_cost": 45000000,
	}

	for fieldname, default_value in defaults.items():
		current_value = frappe.db.get_single_value("Trip Settings", fieldname)
		if current_value in (None, "", 0, 0.0):
			frappe.db.set_single_value("Trip Settings", fieldname, default_value)
