import frappe


def execute():
	if not frappe.db.exists("DocType", "Trip Settings"):
		return

	defaults = {
		"heavy_truck_tyre_price": 0,
		"heavy_truck_number_of_tyres": 0,
		"heavy_truck_tyre_lifecycle_km": 0,
		"light_truck_tyre_price": 0,
		"light_truck_number_of_tyres": 0,
		"light_truck_tyre_lifecycle_km": 0,
	}

	for fieldname, default_value in defaults.items():
		current_value = frappe.db.get_single_value("Trip Settings", fieldname)
		if current_value in (None, ""):
			frappe.db.set_single_value("Trip Settings", fieldname, default_value)
